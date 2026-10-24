# -*- coding: utf-8 -*-
"""apetto 小幫手: a chat helper that runs entirely in the browser (no AI service, no server).

At build time it reads the finished pages of each language and writes a small knowledge base,
assets/assistant/kb.<lang>.json: products (name, price, sizes, colour, size chart), categories,
the size charts, and text sections from guides, features, the shopping-flow page, the brand story,
news, plus optional hand-written answers from _data/assistant.json.
In the browser, assets/assistant.js understands the common questions (size from back length or breed,
which coat, colours, prices, shipping, delivery time, payment, how to buy, fitting room), keeps
context between turns, and falls back to searching the site text."""
import hashlib
import json
import re

from bs4 import BeautifulSoup

import site_builder as sb

# helper server (semantic matching + question log); runs on the NTU workstation, separate from the fitting room
API_BASE = "https://apetto-helper.tailbec98f.ts.net"

# Paraphrase bank for the server's semantic match (multilingual model on the bridge).
# key -> (the question the rules already answer, per language), example wordings in any language.
# The server embeds every example; when a visitor's question is close to one, the helper answers
# the canonical question for that key instead.
SEM = {
    "ship": ({"zh": "運費怎麼算", "en": "shipping cost", "ja": "送料は？", "de": "Versandkosten?"},
             ["寄過來運費多少", "寄到家要多少錢", "運送費用", "郵資多少", "寄送要另外付錢嗎", "運費會很貴嗎", "超商取貨要錢嗎",
              "how much is delivery", "what does it cost to send it to me", "is shipping free", "how much does shipping cost", "is postage expensive", "delivery fee", "shipping price", "送料はいくらですか", "Was kostet der Versand"]),
    "time": ({"zh": "多久會到貨", "en": "how long does delivery take", "ja": "届くまでの日数", "de": "Wie lange dauert die Lieferung?"},
             ["什麼時候寄出", "今天下單哪天收到", "要等多久才會到", "幾天可以拿到", "下單後多快出貨", "急用來得及嗎", "週末會寄嗎",
              "when will I get it", "how many days until it arrives", "いつ届きますか", "Wann kommt meine Bestellung"]),
    "pay": ({"zh": "怎麼付款", "en": "how to pay", "ja": "支払い方法", "de": "Wie bezahlen?"},
            ["可以刷卡嗎", "能用 LINE Pay 嗎", "結帳方式有哪些", "可以貨到付款嗎", "用什麼方式付錢", "可以轉帳嗎",
             "can I pay by card", "payment options", "カードで払えますか", "Kann ich mit Karte zahlen"]),
    "ret": ({"zh": "可以退換貨嗎", "en": "returns and exchanges", "ja": "返品・交換", "de": "Rückgabe und Umtausch"},
            ["買錯尺寸可以換嗎", "不合身可以退嗎", "收到不喜歡怎麼辦", "尺寸不對要換貨", "可以退款嗎", "穿不下怎麼辦",
             "can I exchange the size", "it does not fit what now", "サイズ交換できますか", "Passt nicht, kann ich tauschen"]),
    "size": ({"zh": "幫我挑尺寸", "en": "help me pick a size", "ja": "サイズを選びたい", "de": "Größe finden"},
             ["不知道該買哪個尺寸", "我家狗很胖要怎麼選", "穿起來會不會太大", "怕買太小", "尺寸怎麼選才對", "胖胖的狗適合哪一號", "我不確定我的狗穿什麼",
              "which size should I buy", "my dog is chubby what size", "どのサイズを買えばいい", "Welche Größe soll ich nehmen"]),
    "measure": ({"zh": "怎麼量背長", "en": "how to measure my dog", "ja": "測り方", "de": "Wie messe ich?"},
                ["要量哪裡", "背長是從哪量到哪", "皮尺怎麼量狗", "胸圍要量哪邊", "where do I measure", "どこを測ればいい", "wo muss ich messen"]),
    "warm": ({"zh": "推薦保暖款", "en": "recommend a warm jacket", "ja": "防寒タイプのおすすめ", "de": "warme Jacke empfehlen"},
             ["狗狗很怕冷要穿什麼", "冬天散步穿什麼好", "寒流來了要穿什麼", "狗會發抖", "天氣冷出門穿什麼", "短毛狗冬天會冷", "老狗怕冷",
              "my dog gets cold in winter", "what should my dog wear when it is freezing", "my pup shivers outside", "my dog shakes when it is cold", "狗狗出門一直發抖", "寒がりな犬に何を着せる", "mein Hund friert im Winter"]),
    "rain": ({"zh": "推薦雨衣", "en": "recommend a raincoat", "ja": "レインコートのおすすめ", "de": "Regenmantel empfehlen"},
             ["下雨天出門穿什麼", "梅雨季要準備什麼", "不想讓狗淋濕", "下雨天散步會弄得很髒", "狗討厭淋雨", "颱風天出門",
              "keep my dog dry on rainy walks", "what to wear in the rain", "雨の日の散歩に", "Hund soll beim Regen trocken bleiben"]),
    "compare": ({"zh": "雨衣跟保暖的差在哪", "en": "difference between the raincoat and the warm jacket", "ja": "レインコートと防寒タイプの違い", "de": "Unterschied zwischen Regenmantel und warmer Jacke"},
                ["兩種有什麼不一樣", "保暖款跟一般款哪裡不同", "該買一般的還是保暖的", "小汪跟大汪差在哪",
                 "what is the difference between the models", "違いは何ですか", "was ist der Unterschied"]),
    "care": ({"zh": "可以洗衣機洗嗎", "en": "can I wash it in the machine", "ja": "洗濯機で洗えますか", "de": "Kann ich es waschen?"},
             ["髒了怎麼辦", "怎麼清洗", "可以丟洗衣機嗎", "洗了會不會壞", "防水會不會洗掉", "要怎麼保養", "可以烘乾嗎",
              "how do I clean it", "is it machine washable", "汚れたらどうする", "wie reinige ich das"]),
    "fit": ({"zh": "試衣間怎麼用", "en": "how does the Fitting Studio work", "ja": "試着室の使い方", "de": "Wie funktioniert die Anprobe?"},
            ["可以先看穿起來的樣子嗎", "想看狗穿上去的效果", "AI 換裝", "上傳照片試穿", "能模擬穿上的樣子嗎",
             "can I see it on my dog", "virtual try on", "着せたイメージを見たい", "virtuell anprobieren"]),
    "contact": ({"zh": "客服電話", "en": "contact a person", "ja": "問い合わせ", "de": "Kontakt"},
                ["我要找真人", "有沒有客服", "可以打電話問嗎", "怎麼聯絡你們", "有 LINE 嗎", "客服信箱",
                 "how can I contact you", "I want to talk to a human", "連絡先を教えて", "Wie erreiche ich euch"]),
    "store": ({"zh": "有實體店嗎", "en": "is there a physical shop", "ja": "実店舗はありますか", "de": "Gibt es ein Ladengeschäft?"},
              ["可以去哪裡看實品", "有門市嗎", "哪裡可以摸到實品", "可以現場試穿嗎", "有店面嗎", "有沒有店可以摸摸看", "想先摸摸看布料", "can I touch it in a shop",
               "where can I see it in person", "can I try it on in a store", "実物を見られる場所", "wo kann ich es anschauen"]),
    "who": ({"zh": "你是誰", "en": "who are you", "ja": "あなたは誰", "de": "Wer bist du?"},
            ["你是機器人嗎", "你是真人嗎", "你叫什麼名字", "are you a real person", "are you AI", "ロボットですか", "bist du ein Mensch"]),
    "colors": ({"zh": "有哪些顏色", "en": "which colours", "ja": "カラーは？", "de": "Welche Farben?"},
               ["有什麼顏色可以選", "顏色有幾種", "有沒有亮一點的顏色", "有沒有比較低調的顏色", "what colors are available", "色は何色ありますか", "welche Farben gibt es"]),
    "price": ({"zh": "多少錢", "en": "how much", "ja": "価格は？", "de": "Was kostet das?"},
              ["價格多少", "一件多少", "貴不貴", "售價", "how much does it cost", "値段はいくら", "wie teuer ist das"]),
    "leash": ({"zh": "可以穿著上牽繩嗎", "en": "can I clip on a leash with the coat on", "ja": "着たままリードを付けられますか", "de": "Kann man die Leine anlegen?"},
              ["穿了還能扣牽繩嗎", "牽繩會不會卡住", "胸背帶可以一起穿嗎", "does it work with a harness", "ハーネスと一緒に使える", "geht das mit Geschirr"]),
    "night": ({"zh": "晚上散步看得到嗎", "en": "is it visible at night", "ja": "夜でも見えますか", "de": "Ist es nachts sichtbar?"},
              ["晚上散步安全嗎", "夜間車子看得到嗎", "有反光嗎", "天黑出門", "reflective for night walks", "反射材はありますか", "reflektierend"]),
    "name": ({"zh": "可以客製名字嗎", "en": "can I add my dog's name", "ja": "名前を入れられますか", "de": "Kann ich einen Namen hinzufügen?"},
             ["可以寫名字嗎", "能不能繡名字", "可以印字嗎", "personalize with a name", "名前入れ", "personalisieren"]),
    "waterproof": ({"zh": "耐水壓多少", "en": "how waterproof is it", "ja": "防水性は？", "de": "Wie wasserdicht ist es?"},
                   ["防水效果好嗎", "會不會滲水", "大雨也不會濕嗎", "颱風天撐得住嗎", "does water get through", "大雨でも大丈夫", "hält das starken Regen aus"]),
    "about": ({"zh": "你們的品牌故事", "en": "tell me about apetto", "ja": "apetto について", "de": "Über apetto"},
              ["apetto 是什麼品牌", "你們是哪裡的品牌", "是台灣品牌嗎", "品牌怎麼來的", "who makes these coats", "どこのブランド", "woher kommt die Marke"]),
}


# Topics the helper answers with a fixed text. Only facts that are on the site; where the site says nothing
# (invoices, discounts, orders, defects...) the answer hands over to customer service with the contact lines.
# "k": keywords (any language) for the rules; "ex": example wordings for the server's semantic match.
TOPICS = [
    {"id": "discount", "k": ["折扣", "優惠", "折價", "打折", "特價", "促銷", "coupon", "discount", "promo code", "voucher", "割引", "クーポン", "rabatt", "gutschein"],
     "ex": ["有折扣碼嗎", "最近有優惠嗎", "會打折嗎", "is there a discount", "any promo code", "セールはありますか", "gibt es rabatt"],
     "a": {"zh": "目前的優惠活動以官方賣場和 [Instagram]({ig}) 公告為準；固定的優惠是台灣地區單筆滿 **NT$3,000 免運**。想確認有沒有折扣碼，可以問客服：\n{contact}",
           "en": "Promotions are announced in our official store and on [Instagram]({ig}); orders of **NT$3,000+** ship free within Taiwan. To ask about a discount code:\n{contact}",
           "ja": "セールやキャンペーンは公式ストアと [Instagram]({ig}) でお知らせします。台湾国内は **NT$3,000 以上で送料無料**です。クーポンについてのお問い合わせ：\n{contact}",
           "de": "Aktionen kündigen wir im offiziellen Shop und auf [Instagram]({ig}) an; ab **NT$3.000** ist der Versand in Taiwan frei. Fragen zu Rabattcodes:\n{contact}"}},
    {"id": "invoice", "k": ["發票", "統編", "收據", "invoice", "receipt", "領収書", "rechnung", "quittung"],
     "ex": ["可以開統編嗎", "發票怎麼開", "can I get an invoice", "領収書はもらえますか", "bekomme ich eine rechnung"],
     "a": {"zh": "發票和統編的開立方式網站上沒有寫，請直接問客服：\n{contact}",
           "en": "The website doesn't cover invoices or receipts, so please ask us directly:\n{contact}",
           "ja": "領収書・インボイスについてはサイトに記載がないため、直接お問い合わせください：\n{contact}",
           "de": "Zu Rechnungen steht nichts auf der Website, bitte frag direkt bei uns nach:\n{contact}"}},
    {"id": "order", "k": ["訂單", "物流", "追蹤", "改地址", "取消", "order status", "track my", "tracking", "cancel my order", "change my order", "注文", "追跡", "キャンセル", "bestellung", "sendungsverfolgung", "stornieren"],
     "ex": ["我的訂單到哪了", "可以取消訂單嗎", "下錯單要改", "想改寄送地址", "where is my order", "I want to cancel", "注文をキャンセルしたい", "wo ist meine bestellung"],
     "a": {"zh": "出貨時會寄 **email 出貨通知**。想查訂單、改資料或取消，請帶著訂單編號聯絡客服：\n{contact}",
           "en": "We send an **email when your order ships**. To check, change or cancel an order, contact us with your order number:\n{contact}",
           "ja": "発送時に **メールでお知らせ**します。注文の確認・変更・キャンセルは、注文番号を添えてお問い合わせください：\n{contact}",
           "de": "Beim Versand bekommst du eine **E-Mail**. Für Fragen, Änderungen oder Stornos schreib uns mit deiner Bestellnummer:\n{contact}"}},
    {"id": "overseas", "k": ["海外", "國外", "國際運送", "寄到香港", "寄到日本", "寄到美國", "香港", "澳門", "新加坡", "馬來西亞", "overseas", "international shipping", "ship to", "worldwide", "outside taiwan", "海外発送", "日本に送", "ins ausland", "international"],
     "ex": ["可以寄到香港嗎", "有國際運送嗎", "do you ship internationally", "can you send it to the US", "日本に発送できますか", "versendet ihr nach deutschland"],
     "a": {"zh": "網站上的運費只列 **台灣地區**。海外寄送是否可行、運費多少，請先問客服：\n{contact}",
           "en": "The shipping fees on our site cover **Taiwan only**. For delivery abroad, please ask us first:\n{contact}",
           "ja": "サイトの送料は **台湾国内のみ**です。海外発送についてはお問い合わせください：\n{contact}",
           "de": "Die Versandkosten auf der Website gelten **nur für Taiwan**. Für den Versand ins Ausland frag bitte bei uns nach:\n{contact}"}},
    {"id": "material", "k": ["材質", "布料", "面料", "什麼布", "成分", "fabric", "material", "素材", "生地", "stoff"],
     "ex": ["衣服是什麼材質", "布料摸起來怎樣", "what is it made of", "素材は何ですか", "aus welchem material"],
     "a": {"zh": "材質重點：\n• 外層：滑雪衣等級的防潑水、防風布料，耐水壓 10000mmH2O\n• 保暖款內層：MIT 抗靜電刷毛\n• 3M Scotchlite™ 反光條\n更多細節在 [機能與設計細節]({features})。",
           "en": "What it's made of:\n• Outer: ski-jacket-grade water-repellent, windproof fabric rated to 10,000 mmH2O\n• Warm models: anti-static fleece lining made in Taiwan\n• 3M Scotchlite™ reflective strips\nMore in [Features & Design Details]({features}).",
           "ja": "素材のポイント：\n• 表地：スキーウェア級の撥水・防風生地、耐水圧 10000mmH2O\n• 防寒タイプの裏地：台湾製の帯電防止フリース\n• 3M Scotchlite™ 反射材\n詳しくは [機能とデザイン]({features}) へ。",
           "de": "Material:\n• Außen: wasserabweisender, winddichter Skijackenstoff, 10.000 mmH2O\n• Warme Modelle: antistatisches Fleecefutter aus Taiwan\n• 3M Scotchlite™ Reflektoren\nMehr unter [Funktionen & Details]({features})."}},
    {"id": "breathe", "k": ["悶熱", "透氣", "會熱", "太熱", "夏天", "breathable", "too hot", "summer", "蒸れ", "暑い", "atmungsaktiv", "zu warm"],
     "ex": ["穿了會不會很悶", "夏天可以穿嗎", "is it breathable", "will my dog overheat", "夏でも着られますか", "ist das im sommer zu warm"],
     "a": {"zh": "網站上沒有標示透氣度。apetto 的布料以防水防風為主，天氣悶熱時建議只在下雨時穿、到家就脫下晾乾；保暖款有刷毛內裡，比較適合冷天。",
           "en": "The site doesn't list breathability. The fabric is made to keep out rain and wind, so on warm days use it for the rain and take it off at home to dry; the warm models with fleece are for cold weather.",
           "ja": "通気性についてはサイトに記載がありません。防水・防風が中心の生地なので、蒸し暑い日は雨のときだけ着せて、帰宅したら脱がせて乾かしてください。防寒タイプは寒い日向けです。",
           "de": "Zur Atmungsaktivität steht nichts auf der Website. Der Stoff hält Regen und Wind ab; an warmen Tagen nur bei Regen tragen und zu Hause ausziehen und trocknen. Die warmen Modelle sind für kalte Tage."}},
    {"id": "puton", "k": ["怎麼穿", "穿法", "怎麼套", "好穿嗎", "how to put", "put it on", "着せ方", "anziehen"],
     "ex": ["衣服要怎麼穿上去", "穿起來麻煩嗎", "how do I put it on my dog", "着せるのは簡単ですか", "wie ziehe ich das an"],
     "a": {"zh": "• **小汪系列**：斗篷式，前腳有袖子，前面三點鈕扣扣起來就好\n• **大汪系列**：前套式，從頭套進去再扣腹部插扣\n頸部都有可調鬆緊繩，可以依體型調整。",
           "en": "• **Small Dog series**: a cape with front-leg sleeves; close the three front snaps\n• **Big Dog series**: pull it over the head and fasten the belly buckle\nBoth have an adjustable drawcord at the neck.",
           "ja": "• **小型犬シリーズ**：前足に袖のあるケープ型。前の 3 つのボタンを留めるだけ\n• **大型犬シリーズ**：頭からかぶって胴のバックルを留めます\nどちらも首元のドローコードで調整できます。",
           "de": "• **Kleine Hunde**: Cape mit Vorderbeinärmeln, vorne drei Druckknöpfe schließen\n• **Große Hunde**: über den Kopf ziehen und die Bauchschnalle schließen\nAm Hals lässt sich beides mit einem Kordelzug anpassen."}},
    {"id": "cat", "k": ["貓", "cat", "kitten", "猫", "katze"],
     "ex": ["貓咪可以穿嗎", "can my cat wear this", "猫にも使えますか", "passt das für katzen"],
     "a": {"zh": "apetto 是為狗狗設計的，尺寸表也是依狗狗的體型。貓咪的背長、胸圍如果剛好落在尺寸表範圍內可以參考，但不保證合適，建議先問客服：\n{contact}",
           "en": "apetto is designed for dogs and the size charts follow dog proportions. If your cat's measurements fall within a chart you could try, but we can't promise a good fit; please ask us first:\n{contact}",
           "ja": "apetto は犬用に作られており、サイズ表も犬の体型が基準です。猫ちゃんのサイズが表に収まる場合もありますが、合うとは限らないので先にお問い合わせください：\n{contact}",
           "de": "apetto ist für Hunde gemacht, die Größentabellen folgen Hundeproportionen. Passt deine Katze in die Maße, kann es klappen, garantieren können wir es nicht. Frag uns gern:\n{contact}"}},
    {"id": "gift", "k": ["送禮", "禮物", "包裝", "禮盒", "gift", "wrap", "ギフト", "プレゼント", "geschenk"],
     "ex": ["想送朋友可以包裝嗎", "可以附卡片嗎", "is gift wrapping available", "プレゼント包装できますか", "kann man das als geschenk verpacken"],
     "a": {"zh": "禮物包裝、附卡片這類需求網站上沒有寫，請下單前先問客服：\n{contact}\n不確定尺寸的話，先問到毛孩的背長，我幫你對尺寸表。",
           "en": "Gift wrapping and cards aren't covered on the site, so please ask us before ordering:\n{contact}\nNot sure about the size? Find out the dog's back length and I'll match it to the chart.",
           "ja": "ギフト包装やカードについてはサイトに記載がないため、ご注文前にお問い合わせください：\n{contact}\nサイズは背丈がわかれば私が確認します。",
           "de": "Geschenkverpackung steht nicht auf der Website, bitte vor der Bestellung nachfragen:\n{contact}\nFür die Größe reicht mir die Rückenlänge des Hundes."}},
    {"id": "b2b", "k": ["批發", "團購", "合作", "經銷", "代理", "業配", "寄賣", "wholesale", "bulk order", "collaboration", "reseller", "卸売", "コラボ", "großhandel", "kooperation"],
     "ex": ["想談合作", "可以批貨嗎", "我們想團購", "wholesale inquiry", "コラボしたい", "anfrage für großhandel"],
     "a": {"zh": "批發、團購或合作洽詢，請聯絡我們：\n{contact}",
           "en": "For wholesale, group orders or collaborations, please contact us:\n{contact}",
           "ja": "卸売・まとめ買い・コラボのご相談はこちらへ：\n{contact}",
           "de": "Für Großhandel, Sammelbestellungen oder Kooperationen:\n{contact}"}},
    {"id": "stock", "k": ["缺貨", "補貨", "有貨", "庫存", "現貨", "賣完", "in stock", "out of stock", "restock", "sold out", "在庫", "再入荷", "vorrätig", "ausverkauft"],
     "ex": ["M 號還有貨嗎", "什麼時候補貨", "is it in stock", "when will it be back", "在庫はありますか", "ist das noch da"],
     "a": {"zh": "各尺寸的庫存以官方賣場的頁面為準；賣完的尺寸想知道補貨時間，可以問客服：\n{contact}",
           "en": "Stock per size is shown in our official store. For restock dates, ask us:\n{contact}",
           "ja": "サイズごとの在庫は公式ストアのページでご確認ください。再入荷のお問い合わせ：\n{contact}",
           "de": "Den Bestand je Größe zeigt der offizielle Shop. Wann etwas wieder da ist:\n{contact}"}},
    {"id": "defect", "k": ["瑕疵", "壞了", "破了", "脫線", "拉鍊壞", "保固", "defect", "broken", "damaged", "warranty", "不良", "壊れ", "defekt", "garantie"],
     "ex": ["收到的衣服有破洞", "拉鍊壞掉了", "my coat arrived damaged", "the zipper broke", "壊れていました", "der reißverschluss ist kaputt"],
     "a": {"zh": "很抱歉讓你遇到這個狀況 🙏 請拍照後聯絡客服，會協助處理：\n{contact}",
           "en": "Sorry about that 🙏 Please take a photo and contact us, and we'll sort it out:\n{contact}",
           "ja": "ご不便をおかけしてすみません 🙏 写真を撮ってお問い合わせください：\n{contact}",
           "de": "Das tut uns leid 🙏 Bitte mach ein Foto und melde dich bei uns:\n{contact}"}},
    {"id": "rainwalk", "k": ["雨天散步", "下雨散步", "雨天遛狗", "下雨遛狗", "會感冒", "rainy walk", "walk in the rain", "雨の日の散歩", "regenspaziergang"],
     "ex": ["下雨天散步要注意什麼", "淋雨會不會感冒", "tips for walking in the rain", "雨の日の散歩の注意点", "tipps für spaziergänge im regen"],
     "a": {"zh": "雨天散步的小提醒：\n• 出門前穿好雨衣，傍晚選有反光條的款式\n• 避開積水和水溝蓋，路面濕滑走慢一點\n• 回家先擦乾腳掌、肚子和耳朵，毛比較厚的記得吹乾\n• 雨衣脫下後掛起來陰乾，保養看 [如何清潔與保養]({care})",
           "en": "Rainy-walk tips:\n• Put the raincoat on before you go; at dusk pick one with reflective strips\n• Avoid puddles and drain covers, and go slower on wet ground\n• At home dry the paws, belly and ears; blow-dry thick coats\n• Hang the raincoat to dry; see [Care & maintenance]({care})",
           "ja": "雨の日の散歩のポイント：\n• 出かける前にレインコートを。夕方は反射材付きを\n• 水たまりやマンホールを避けて、ゆっくり歩く\n• 帰ったら足・お腹・耳を拭いて、毛の多い子はドライヤーで\n• レインコートは陰干し。お手入れは [お手入れ方法]({care})",
           "de": "Tipps für Regenspaziergänge:\n• Regenmantel vor dem Losgehen anziehen, in der Dämmerung mit Reflektoren\n• Pfützen und Gullydeckel meiden, langsamer gehen\n• Zu Hause Pfoten, Bauch und Ohren trocknen, dichtes Fell föhnen\n• Den Mantel hängend trocknen; siehe [Pflege]({care})"}},
    {"id": "dislike", "k": ["不喜歡穿", "不肯穿", "不愛穿", "討厭穿", "不習慣穿", "won't wear", "hates wearing", "doesn't like wearing", "嫌がる", "will nichts anziehen"],
     "ex": ["我家狗不讓我穿衣服", "牠一穿就僵住不動", "my dog hates clothes", "服を嫌がります", "mein hund mag keine jacke"],
     "a": {"zh": "很多毛孩一開始都不習慣穿衣服，可以慢慢來：\n• 先讓牠聞一聞衣服，給點零食\n• 在家穿 5～10 分鐘就脫，邊玩邊給獎勵\n• 幾天後再延長時間，習慣了再穿出門\napetto 的斗篷式和前套式都好穿脫，比較不會讓牠緊張。",
           "en": "Lots of dogs need time to get used to clothes:\n• Let them sniff the coat and give a treat\n• Put it on at home for 5–10 minutes with play and rewards\n• Make it longer over a few days, then go outside\napetto's cape and pull-over designs go on quickly, which helps.",
           "ja": "最初は服に慣れない子が多いので、少しずつ：\n• まず服のにおいを嗅がせておやつを\n• 家で 5〜10 分着せて、遊びながらごほうび\n• 数日かけて時間を延ばしてから外へ\napetto は着脱が簡単なので緊張しにくいです。",
           "de": "Viele Hunde müssen sich erst an Kleidung gewöhnen:\n• Erst schnuppern lassen und ein Leckerli geben\n• Zu Hause 5–10 Minuten tragen, mit Spiel und Belohnung\n• Über ein paar Tage steigern, dann raus\napetto Modelle sind schnell an- und ausgezogen."}},
    {"id": "colordiff", "k": ["色差", "實品顏色", "跟照片一樣", "顏色準", "colour accurate", "color accurate", "looks different", "色味", "farbabweichung"],
     "ex": ["實品顏色跟照片會差很多嗎", "does the colour look like the photo", "写真と色は違いますか", "sieht die farbe aus wie auf dem foto"],
     "a": {"zh": "照片顏色會因螢幕有些差異；像芬達桔這類螢光色，實品的螢光感通常會再強烈一點。想先看看穿上的樣子，可以到 [試衣間]({fit})。",
           "en": "Colours vary a little by screen; neon shades like Fanta Orange are usually even brighter in person. To preview it on your dog, try the [Fitting Studio]({fit}).",
           "ja": "画面によって色味が少し違って見えます。ファンタオレンジのような蛍光色は実物のほうが鮮やかです。着用イメージは [試着室]({fit}) で。",
           "de": "Farben wirken je nach Bildschirm etwas anders; Neontöne wie Fanta Orange sind in echt meist noch kräftiger. Eine Vorschau gibt's in der [Anprobe]({fit})."}},
    {"id": "shrink", "k": ["縮水", "掉色", "褪色", "起毛球", "shrink", "fade", "pilling", "縮む", "色落ち", "einlaufen", "verblassen"],
     "ex": ["洗了會縮水嗎", "會不會掉色", "will it shrink in the wash", "洗うと縮みますか", "läuft das beim waschen ein"],
     "a": {"zh": "照 [清洗方式]({care}) 照顧就好：手洗或放洗衣袋用輕柔模式、水溫 30 度以下、中性洗劑，不要漂白和柔軟精；保暖款翻面洗可以減少起毛球。網站上沒有縮水或掉色的測試數據，有疑問可以問客服。",
           "en": "Follow the [care guide]({care}): hand wash or a gentle cycle in a laundry bag, 30°C or below, mild detergent, no bleach or softener; wash fleece-lined models inside out to reduce pilling. The site has no shrink or fade test data, so ask us if you're unsure.",
           "ja": "[お手入れ方法]({care}) のとおり、手洗いか洗濯ネットで弱水流、30℃以下、中性洗剤で。漂白剤・柔軟剤は使わず、防寒タイプは裏返すと毛玉が減ります。縮みや色落ちのデータはサイトにないので、気になる場合はお問い合わせください。",
           "de": "Nach der [Pflegeanleitung]({care}): Handwäsche oder Schonwaschgang im Wäschenetz, höchstens 30 °C, mildes Waschmittel, kein Bleich- oder Weichspüler; Fleece-Modelle auf links waschen. Daten zu Einlaufen oder Ausbleichen gibt es nicht, frag uns im Zweifel."}},
    {"id": "fit-privacy", "k": ["照片會保存", "照片會不會被保存", "照片隱私", "上傳的照片", "照片會被", "照片存", "刪除照片", "photo stored", "my photo", "photos saved", "写真の保存", "foto gespeichert"],
     "ex": ["試衣間照片會不會被保存", "我上傳的狗照片你們會留著嗎", "are my photos kept", "アップした写真はどうなりますか"],
     "a": {"zh": "試衣間上傳的照片和產生的試穿圖，會保存在 apetto 的系統裡，用來改善服務，不會公開在網站上。想刪除照片或有其他疑問，請聯絡客服：\n{contact}",
           "en": "Photos you upload to the Fitting Studio and the generated images are kept in apetto's own system to improve the service; they are not published on the website. To have a photo deleted, contact us:\n{contact}",
           "ja": "試着室でアップロードした写真と生成画像は apetto のシステム内に保存され、サービス改善に使われます。サイトで公開されることはありません。削除のご希望はこちらへ：\n{contact}",
           "de": "Hochgeladene Fotos und erzeugte Bilder der Anprobe werden in apettos eigenem System gespeichert, um den Dienst zu verbessern, und nicht auf der Website veröffentlicht. Zum Löschen melde dich bei uns:\n{contact}"}},
    {"id": "vet", "k": ["生病", "獸醫", "飼料", "嘔吐", "拉肚子", "預防針", "皮膚病", "vet", "sick", "vomit", "diarrhea", "dog food", "獣医", "病気", "tierarzt", "krank"],
     "ex": ["狗狗可以吃巧克力嗎", "狗一直咳嗽怎麼辦", "my dog is sick", "what should my dog eat", "犬が吐きました", "mein hund ist krank"],
     "a": {"zh": "毛孩健康和飲食的問題我不是專業的，建議諮詢獸醫喔 🐾 我能幫忙的是衣服的尺寸、款式和購物問題。",
           "en": "For health and food questions please ask a vet 🐾 I can help with coat sizes, models and shopping.",
           "ja": "健康や食事のご相談は獣医さんへどうぞ 🐾 私はサイズ・モデル・ご購入のご案内ができます。",
           "de": "Bei Gesundheits- und Futterfragen frag bitte deinen Tierarzt 🐾 Ich helfe bei Größen, Modellen und dem Kauf."}},
]


# Small talk. "x": the whole message must be one of these (after trimming punctuation); "k": contained anywhere.
# Several answers per language: one is picked at random.
PENDING = {"zh": "這個問題我還沒有確定的答案，怕說錯，幫你轉給真人比較準確 🙏\n{contact}",
           "en": "I don't have a confirmed answer to that yet and don't want to guess, so please check with a person 🙏\n{contact}",
           "ja": "その質問にはまだ確かな答えがないので、スタッフにご確認ください 🙏\n{contact}",
           "de": "Darauf habe ich noch keine sichere Antwort; bitte frag direkt bei uns nach 🙏\n{contact}"}

CHAT = [
    {"id": "chat-how", "k": ["你好嗎", "最近好嗎", "how are you", "how's it going", "元気", "wie geht"], "x": [],
     "ex": ["你今天過得如何", "how are you doing today", "お元気ですか", "wie geht es dir"],
     "a": {"zh": ["我很好，謝謝關心！今天也在等著幫毛孩挑衣服 🐾 你呢？家裡的毛孩好嗎？", "很好喔！你家毛孩今天有出門散步嗎？"],
           "en": ["I'm great, thanks for asking! Ready to help your dog find a coat 🐾 How's your pup?"],
           "ja": ["元気です、ありがとうございます！ワンちゃんは元気ですか？🐾"],
           "de": ["Mir geht's gut, danke! Wie geht's deinem Hund? 🐾"]}},
    {"id": "chat-name", "k": ["你叫什麼", "你的名字", "怎麼稱呼你", "what's your name", "what is your name", "お名前", "wie heißt du"], "x": [],
     "ex": ["你叫什麼名字", "what should I call you", "名前は何ですか"],
     "a": {"zh": ["我是 apetto 小幫手 🐾 叫我小幫手就好！"], "en": ["I'm the apetto Helper 🐾"], "ja": ["apetto アシスタントです 🐾"], "de": ["Ich bin der apetto Assistent 🐾"]}},
    {"id": "chat-dogs", "k": ["你喜歡狗", "喜歡狗嗎", "do you like dogs", "犬は好き", "magst du hunde"], "x": [],
     "ex": ["你喜歡狗狗嗎", "are you a dog person"],
     "a": {"zh": ["超喜歡！每一隻毛孩都是獨一無二的寶貝 🐶 你家的是什麼狗呢？"], "en": ["I love them! Every dog is one of a kind 🐶 What breed is yours?"],
           "ja": ["大好きです！🐶 どんな犬種ですか？"], "de": ["Und wie! 🐶 Was für ein Hund ist deiner?"]}},
    {"id": "chat-joke", "k": ["講笑話", "說笑話", "笑話", "tell me a joke", "joke", "冗談", "witz"], "x": [],
     "ex": ["說個笑話來聽", "make me laugh"],
     "a": {"zh": ["為什麼狗狗下雨天不怕淋濕？因為牠有 apetto 啊 ☔ ……好吧我比較擅長挑尺寸 😅", "狗狗最喜歡哪種天氣？「汪」晴天 🌤️ 下雨的話就穿雨衣吧！"],
           "en": ["Why don't dogs mind the rain? They've got apetto ☔ …OK, I'm better at sizing 😅"],
           "ja": ["雨の日でも平気な犬は？apetto を着てる犬です ☔ …サイズ選びのほうが得意です 😅"],
           "de": ["Warum stört Hunde der Regen nicht? Sie tragen apetto ☔ …Größen kann ich besser 😅"]}},
    {"id": "chat-nice", "k": ["你好棒", "好厲害", "好聰明", "你很棒", "好可愛", "讚啦", "great job", "you're smart", "good bot", "すごい", "かわいい", "super", "toll"], "x": ["讚", "棒", "太棒了", "good", "nice", "cool"],
     "ex": ["你真聰明", "you are helpful"],
     "a": {"zh": ["謝謝誇獎！有什麼想問的儘管問 😊", "嘿嘿謝謝 🐾 還想看看哪件呢？"], "en": ["Thank you! Ask me anything 😊"], "ja": ["ありがとうございます 😊"], "de": ["Danke! Frag ruhig weiter 😊"]}},
    {"id": "chat-mean", "k": ["好笨", "很爛", "沒用", "聽不懂", "笨蛋", "useless", "stupid", "dumb", "you suck", "役に立たない", "nutzlos", "dumm"], "x": [],
     "ex": ["你根本答不出來", "this bot is bad"],
     "a": {"zh": ["抱歉沒幫上忙 🙏 我還在學習中。換個說法問問看，或直接找真人客服：\n{contact}"],
           "en": ["Sorry I couldn't help 🙏 I'm still learning. Try asking another way, or reach a person:\n{contact}"],
           "ja": ["お役に立てずすみません 🙏 言い方を変えるか、スタッフにお問い合わせください：\n{contact}"],
           "de": ["Sorry, dass ich nicht helfen konnte 🙏 Frag anders oder wende dich an uns:\n{contact}"]}},
    {"id": "chat-laugh", "k": [], "x": ["哈哈", "哈哈哈", "哈", "lol", "haha", "hahaha", "笑", "www", "草", "hehe"],
     "ex": [],
     "a": {"zh": ["😄 還有什麼想問的嗎？", "哈哈 🐾 想幫毛孩看看哪一件？"], "en": ["😄 Anything else I can help with?"], "ja": ["😄 ほかに何かありますか？"], "de": ["😄 Kann ich sonst noch helfen?"]}},
    {"id": "chat-hungry", "k": ["肚子餓", "好餓", "餓了", "餓死", "想吃東西", "i'm hungry", "so hungry", "お腹すいた", "hunger"], "x": ["餓", "hungry"],
     "ex": ["我肚子好餓", "I'm starving"],
     "a": {"zh": ["快去吃點東西吧 🍙 順便也幫毛孩準備點心？吃飽再來找我聊～", "肚子餓就先去吃飯吧！我會在這裡等你 🐾"],
           "en": ["Go grab a bite 🍙 Maybe a treat for your pup too? I'll be here."], "ja": ["何か食べてきてくださいね 🍙"], "de": ["Dann schnell was essen 🍙 Ich bin hier."]}},
    {"id": "chat-test", "k": [], "x": ["測試", "測試一下", "test", "testing", "テスト", "hallo test", "在嗎", "有人嗎", "anyone there", "hello?"],
     "ex": [],
     "a": {"zh": ["收到！我在這裡 🐾 想問尺寸、款式、運費都可以。", "在的！有什麼可以幫你？"], "en": ["I'm here 🐾 Ask me about sizes, coats or shipping."],
           "ja": ["はい、ここにいます 🐾"], "de": ["Ich bin da 🐾"]}},
    {"id": "chat-ok", "k": [], "x": ["好", "好的", "好喔", "嗯", "嗯嗯", "ok", "okay", "了解", "知道了", "收到", "sure", "got it", "はい", "了解です", "ja", "alles klar"],
     "ex": [],
     "a": {"zh": ["好的！還有其他問題隨時問我 🐾", "沒問題 👍"], "en": ["Great! Ask me anytime 🐾"], "ja": ["承知しました 🐾"], "de": ["Alles klar 🐾"]}},
    {"id": "chat-bored", "k": ["好無聊", "無聊", "陪我聊天", "聊聊天", "i'm bored", "talk to me", "chat with me", "暇", "langweilig"], "x": [],
     "ex": ["可以陪我聊天嗎", "let's chat"],
     "a": {"zh": ["來聊聊！你家毛孩叫什麼名字？是什麼狗呢？", "好啊 🐾 跟我說說你家毛孩吧，牠喜歡下雨天出門嗎？"],
           "en": ["Let's chat! What's your dog's name, and what breed?"], "ja": ["おしゃべりしましょう！ワンちゃんのお名前は？"], "de": ["Gern! Wie heißt dein Hund?"]}},
    {"id": "chat-love", "k": ["我愛你", "愛你", "love you", "大好き", "ich liebe dich"], "x": [],
     "ex": [],
     "a": {"zh": ["被告白了 🥹 我也很喜歡你和你家毛孩！"], "en": ["Aww 🥹 Right back at you and your pup!"], "ja": ["うれしいです 🥹"], "de": ["Oh 🥹 Danke!"]}},
    {"id": "chat-sad", "k": ["好難過", "心情不好", "好累", "sad", "tired", "悲しい", "疲れた", "traurig", "müde"], "x": [],
     "ex": ["今天心情很差", "I had a bad day"],
     "a": {"zh": ["抱抱 🫂 毛孩的陪伴總是最療癒的。需要的話，我隨時都在。"], "en": ["Sending a hug 🫂 Dogs are the best comfort. I'm here if you need me."],
           "ja": ["ぎゅっ 🫂 ワンちゃんが一番の癒しですね。"], "de": ["Fühl dich gedrückt 🫂 Hunde sind der beste Trost."]}},
    {"id": "chat-night", "k": ["晚安", "要睡了", "good night", "おやすみ", "gute nacht"], "x": [],
     "ex": [],
     "a": {"zh": ["晚安 🌙 祝你和毛孩好夢！"], "en": ["Good night 🌙 Sweet dreams to you and your pup!"], "ja": ["おやすみなさい 🌙"], "de": ["Gute Nacht 🌙"]}},
    {"id": "chat-morning", "k": [], "x": ["早安", "早", "早上好", "good morning", "morning", "おはよう", "guten morgen"],
     "ex": [],
     "a": {"zh": ["早安 ☀️ 今天要帶毛孩出門嗎？記得看看天氣喔！"], "en": ["Good morning ☀️ Walk time?"], "ja": ["おはようございます ☀️"], "de": ["Guten Morgen ☀️"]}},
]


COLOR_KEYS = [("灰", "gray"), ("冰川藍", "blue"), ("普魯士藍", "blue"), ("藍", "blue"), ("桔", "orange"), ("橘", "orange"),
              ("綠", "green"), ("桃", "pink"), ("粉", "pink"), ("黃", "yellow")]
# size-chart rule from the charts' own notes: big coats are about 10 cm shorter than the back, small capes 5-7 cm
CHART_OFFSET = {"big_raincoat": 10, "big_jacket": 10, "small_cape": 6, "small_warm_cape": 6}


def _soup(rel, lang):
    f = sb.SITE / sb.lang_variant(rel, lang)
    return BeautifulSoup(f.read_text(encoding="utf-8"), "html.parser") if f.exists() else None


def _txt(el):
    return re.sub(r"\s+", " ", el.get_text(" ", strip=True)).strip() if el else ""


def _split_name(name):
    if " – " in name:
        a, b = name.split(" – ", 1)
        return a.strip(), b.strip()
    if " " in name.strip():
        a, b = name.strip().rsplit(" ", 1)
        return a.strip(), b.strip()
    return name, ""


def _chart_key(p, cats):
    zh = p["name"]
    small, warm = "小汪" in zh, "保暖" in zh
    if small:
        return "small_warm_cape" if warm else "small_cape"
    if "大汪" in zh:
        return "big_jacket" if (warm or 2 in cats) else "big_raincoat"
    return ""


def _sections(soup, url, skip=()):
    """One document per h2/h3 in <main>: the heading plus the text that follows it."""
    out = []
    main = soup.find("main") if soup else None
    if not main:
        return out
    for h in main.find_all(["h2", "h3"]):
        if h.find_parent(class_=["product-grid", "sec-head", "gcard", "grid-box", "news-list", "cat-cards", "other-groups"]):
            continue
        title = _txt(h)
        if not title or title in skip:
            continue
        parts = []
        for sib in h.next_siblings:
            if getattr(sib, "name", None) in ("h1", "h2", "h3"):
                break
            t = _txt(sib) if getattr(sib, "name", None) else str(sib).strip()
            if t:
                parts.append(t)
        body = " ".join(parts).strip()
        if not body and h.parent is not None:
            body = _txt(h.parent).replace(title, "", 1).strip()
        if body:
            out.append({"t": title, "x": body[:900], "u": url})
    return out


def build(data, visible, lang_codes):
    charts = sb.load_image_text().get("charts", {})
    custom = {}
    cf = sb.DATA_DIR / "assistant.json"
    if cf.exists():
        custom = json.loads(cf.read_text(encoding="utf-8"))
    out_dir = sb.SITE / "assets" / "assistant"
    out_dir.mkdir(parents=True, exist_ok=True)
    for lang in lang_codes:
        L = lambda rel: sb.lang_variant(rel, lang)
        kb = {"lang": lang, "products": [], "cats": [], "charts": {}, "docs": [], "faq": [],
              "links": {"shop": L("shop.html"), "guides": L("guides.html"), "features": L("features.html"), "fit": L("fitstudio.html"),
                        "about": L("pages/4.html"), "flow": L("pages/5.html"), "news": L("information/news.html"),
                        "measure": L("guide/measure.html"), "care": L("guide/care.html"), "choose": L("guide/choose-raincoat.html"),
                        "ig": "https://www.instagram.com/apetto_fun/", "pinkoi": "https://www.pinkoi.com/store/apetto"}}
        # products, read from the finished product pages so names and prices are already translated
        for p in visible:
            rel = sb.product_page(p)
            s = _soup(rel, lang)
            if not s:
                continue
            name = _txt(s.select_one(".product-heading-title")) or p["name"]
            line, color = _split_name(name)
            zline, zcolor = _split_name(p["name"])
            cats = p.get("categories", [])
            sizes = []
            for o in p.get("options", []):
                for v in o.get("values", []):
                    m = re.match(r"\s*([0-9]*X*[SML]|\d?XL)", v)
                    if m:
                        x = re.search(r"\$(\d+)", v)
                        sizes.append({"s": m.group(1), "x": int(x.group(1)) if x else 0})
            desc = _txt(s.select_one(".pd-desc .rich")) or _txt(s.select_one(".product-feature-content"))
            img = sb.SITE / p["image"]["full"]
            from theme import crop  # theme imports this module, so import late
            kb["products"].append({
                "id": str(p["id"]), "n": name, "line": line, "lk": zline, "c": color, "ck": next((k for w, k in COLOR_KEYS if w in zcolor), ""),
                "p": int(re.sub(r"\D", "", str(p.get("price", "0"))) or 0), "u": L(rel), "img": crop(p["image"]["full"], "sq") if img else "",
                "cat": cats[0] if cats else None, "ser": "small" if "小汪" in p["name"] else "big" if "大汪" in p["name"] else "",
                "warm": "保暖" in p["name"] or 2 in cats, "ch": _chart_key(p, cats), "sz": sizes, "d": desc[:700]})
        # categories with their localized names (from the shop page)
        s = _soup("shop.html", lang)
        names = {}
        if s:
            for a in s.select(".grp-card li a"):
                m = re.search(r"path=(\d+)", a.get("href", ""))
                if m:
                    names[int(m.group(1))] = _txt(a.find("span")) or _txt(a)
        for c in data["categories"]:
            n = sum(1 for p in visible if c["id"] in p.get("categories", []))
            kb["cats"].append({"id": c["id"], "zh": c["name"], "n": names.get(c["id"], c["name"]), "u": L(sb.category_page(c["id"])), "cnt": n})
        # size charts (numbers only; labels come from the page text)
        for k, ch in charts.items():
            rows = []
            for r in ch.get("rows", []):
                try:
                    belly = [float(x) for x in re.findall(r"\d+(?:\.\d+)?", r[3])]
                    rows.append({"s": r[0], "len": float(r[1]), "neck": float(r[2]), "belly": belly})
                except (IndexError, ValueError):
                    pass
            kb["charts"][k] = {"off": CHART_OFFSET.get(k, 8), "rows": rows}
        # text documents for free questions
        docs = []
        for g in sorted((sb.SITE / "guide").glob("*.html")):
            if re.search(r"\.(en|ja|de)\.html$", g.name):   # language copies; each language reads its own below
                continue
            rel = f"guide/{g.name}"
            gs = _soup(rel, lang)
            if gs:
                title = _txt(gs.select_one("h1"))
                docs += [dict(d, t=f"{title} · {d['t']}") for d in _sections(gs, L(rel))]
        for rel in ("features.html", "pages/5.html", "pages/4.html"):
            docs += _sections(_soup(rel, lang), L(rel))
        fs = _soup("fitstudio.html", lang)
        if fs:
            docs.append({"t": _txt(fs.select_one(".fit-head h1")), "x": _txt(fs.select_one(".fit-head"))[:600], "u": L("fitstudio.html"), "k": "fit"})
        for p in kb["products"]:
            if p["d"]:
                docs.append({"t": p["n"], "x": p["d"], "u": p["u"], "pid": p["id"]})
        ns = _soup("information/news.html", lang)
        if ns:
            for a in ns.select(".news-list a")[:8]:
                docs.append({"t": _txt(a.find("b")) or _txt(a), "x": _txt(a), "u": _news_url(a.get("href", ""), lang), "k": "news"})
        kb["docs"] = docs
        kb["contact"] = ""
        ab = _soup("pages/4.html", lang)
        if ab:
            h = next((x for x in ab.select("main h2") if re.search(r"聯絡|contact|お問い合わせ|連絡|kontakt", x.get_text(), re.I)), None)
            box = h and (h.find_parent("section") or h.parent.parent)
            if box:
                items = [t.strip() for t in box.get_text(" | ", strip=True).split(" | ")]
                items = [t for t in items if t and t != h.get_text(strip=True) and "©" not in t]
                kb["contact"] = chr(10).join("• " + t for t in items[:6])
        # paraphrase bank for the server: examples with their key, and each key's question in this language
        kb["sem"] = {"ex": [[ex, k] for k, (_, exs) in SEM.items() for ex in exs], "q": {k: q.get(lang) or q["zh"] for k, (q, _) in SEM.items()}}
        own = set()
        for f in custom.get("faq", []):
            a = f.get("a") or {}
            ans = (a.get(lang) or a.get("zh")) if isinstance(a, dict) else a
            if not ans or not str(ans).strip():
                continue   # not answered yet in the admin
            own.add(f.get("id"))
            link = f.get("link", "")
            kb["faq"].append({"id": f.get("id", ""), "q": [w for w in (f.get("k") or f.get("q") or []) if w], "a": ans, "t": f.get("title", ""),
                              "u": L(link) if link and not link.startswith("http") else link})
            kb["sem"]["ex"] += [[ex, "faq:" + f.get("id", "")] for ex in (f.get("ex") or []) + [f.get("title", "")] if ex]
        for tp in TOPICS:
            if tp["id"] not in own:
                kb["faq"].append({"id": tp["id"], "q": tp["k"], "a": tp["a"].get(lang) or tp["a"]["en"], "t": tp["ex"][0], "u": ""})
                kb["sem"]["ex"] += [[ex, "faq:" + tp["id"]] for ex in tp["ex"]]
        for f in custom.get("faq", []):
            a = f.get("a") or {}
            answered = (a.get("zh") if isinstance(a, dict) else a) or ""
            if answered.strip() or f.get("id") in own or any(tp["id"] == f.get("id") for tp in TOPICS) or not str(f.get("hint", "")).startswith("目前回答：無"):
                continue
            kb["faq"].append({"id": f.get("id", ""), "q": [w for w in (f.get("k") or []) if w], "a": PENDING.get(lang, PENDING["en"]), "u": "", "pending": 1})
            kb["sem"]["ex"] += [[ex, "faq:" + f.get("id", "")] for ex in (f.get("ex") or []) + [f.get("title", "")] if ex]
        for tp in CHAT:
            kb["faq"].append({"id": tp["id"], "q": tp["k"], "x": tp["x"], "a": tp["a"].get(lang) or tp["a"]["en"], "u": "", "chat": 1})
            kb["sem"]["ex"] += [[ex, "faq:" + tp["id"]] for ex in tp["ex"]]
        kb["v"] = hashlib.sha1(json.dumps([kb["sem"], [(d["t"], d["x"]) for d in kb["docs"]], [f["a"] for f in kb["faq"]]], ensure_ascii=False).encode("utf-8")).hexdigest()[:12]
        (out_dir / f"kb.{lang}.json").write_text(json.dumps(kb, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")


def _news_url(href, lang):
    # links on information/news*.html are relative to information/
    if not href or href.startswith("http"):
        return href
    return href if href.startswith("information/") else "information/" + href.lstrip("./")


CSS = r"""
/* apetto 小幫手 */
.ai-fab{position:fixed;right:20px;bottom:20px;z-index:55;width:58px;height:58px;border-radius:50%;border:0;background:var(--ink);color:#fff;display:grid;place-items:center;cursor:pointer;box-shadow:0 10px 30px rgba(23,24,26,.25);transition:transform .2s,box-shadow .2s}
.ai-fab:hover{transform:translateY(-2px);box-shadow:0 14px 34px rgba(23,24,26,.3)}.ai-fab svg{width:26px;height:26px}
.ai-fab .dot{position:absolute;top:6px;right:6px;width:12px;height:12px;border-radius:50%;background:var(--brand);border:2px solid #fff}
.ai-tip{position:fixed;right:20px;bottom:90px;z-index:55;max-width:250px;background:#fff;border:1px solid var(--line);border-radius:16px 16px 4px 16px;padding:12px 34px 12px 14px;font-size:14.5px;line-height:1.5;box-shadow:0 10px 30px rgba(0,0,0,.12);cursor:pointer;animation:ai-in .3s ease both}
.ai-tip button{position:absolute;top:6px;right:6px;border:0;background:none;width:24px;height:24px;cursor:pointer;color:var(--mute);font-size:14px}
.ai-panel{position:fixed;right:20px;bottom:20px;z-index:56;width:380px;height:min(620px,calc(100vh - 40px));background:var(--bg,#fbfaf7);border:1px solid var(--line);border-radius:22px;box-shadow:0 24px 60px rgba(23,24,26,.22);display:flex;flex-direction:column;overflow:hidden;animation:ai-in .25s ease both}
.ai-panel[hidden]{display:none}
@keyframes ai-in{from{opacity:0;transform:translateY(12px) scale(.98)}to{opacity:1;transform:none}}
.ai-hd{display:flex;align-items:center;gap:12px;padding:14px 14px 12px 16px;background:#fff;border-bottom:1px solid var(--line)}
.ai-av{width:40px;height:40px;border-radius:50%;background:var(--sand);display:grid;place-items:center;flex:0 0 auto}.ai-av img{width:26px;height:auto}
.ai-hd b{display:block;font-size:16px}.ai-hd span{font-size:12.5px;color:var(--mute);display:flex;align-items:center;gap:6px}
.ai-hd span i{width:8px;height:8px;border-radius:50%;background:#2fb344;display:inline-block}
.ai-hd .ai-x,.ai-hd .ai-rs{margin-left:auto;border:0;background:none;width:38px;height:38px;border-radius:50%;cursor:pointer;color:var(--ink2);display:grid;place-items:center}
.ai-hd .ai-rs{margin-left:auto}.ai-hd .ai-rs+.ai-x{margin-left:0}.ai-hd button:hover{background:var(--sand)}.ai-hd svg{width:18px;height:18px}
.ai-log{flex:1;overflow-y:auto;padding:16px 14px 8px;display:flex;flex-direction:column;gap:10px;overscroll-behavior:contain}.ai-log>*{flex-shrink:0}
.ai-m{max-width:86%;font-size:15px;line-height:1.6;word-wrap:break-word}
.ai-m.me{align-self:flex-end;background:var(--ink);color:#fff;padding:9px 14px;border-radius:18px 18px 4px 18px;white-space:pre-wrap}
.ai-m.bot{align-self:flex-start;background:#fff;border:1px solid var(--line);padding:10px 14px;border-radius:18px 18px 18px 4px}
.ai-m.bot p{margin:0}.ai-m.bot p+p{margin-top:8px}.ai-m.bot ul{margin:6px 0 0;padding-left:18px}.ai-m.bot li{margin:2px 0}
.ai-m.bot a{color:var(--brand-ink);font-weight:600;text-decoration:underline;text-underline-offset:2px}
.ai-m .ai-src{display:block;margin-top:8px;font-size:13px;color:var(--mute)}
.ai-cards{display:flex;gap:8px;overflow-x:auto;padding:2px 2px 6px;align-self:stretch;scrollbar-width:thin}
.ai-card{flex:0 0 138px;background:#fff;border:1px solid var(--line);border-radius:14px;overflow:hidden;color:var(--ink);font-size:13.5px;display:flex;flex-direction:column}
.ai-card img{width:100%;aspect-ratio:1;object-fit:cover;background:var(--sand)}.ai-card div{padding:8px 10px 10px}.ai-card b{display:block;font-weight:600;line-height:1.35}.ai-card span{color:var(--brand-ink);font-weight:700}
.ai-card:hover{border-color:var(--ink2)}
.ai-tbl{border-collapse:collapse;margin-top:8px;font-size:13.5px;width:100%}.ai-tbl th,.ai-tbl td{border-bottom:1px solid var(--line);padding:5px 6px;text-align:left}.ai-tbl tr.on td{background:var(--sand);font-weight:700}
.ai-typing{align-self:flex-start;background:#fff;border:1px solid var(--line);border-radius:18px 18px 18px 4px;padding:12px 16px;display:flex;gap:5px}
.ai-typing i{width:7px;height:7px;border-radius:50%;background:var(--mute);animation:ai-dot 1.2s infinite ease-in-out}.ai-typing i:nth-child(2){animation-delay:.15s}.ai-typing i:nth-child(3){animation-delay:.3s}
@keyframes ai-dot{0%,60%,100%{opacity:.3;transform:none}30%{opacity:1;transform:translateY(-3px)}}
.ai-chips{display:flex;gap:6px;flex-wrap:wrap;padding:4px 14px 10px}
.ai-chips button{border:1.5px solid var(--line2);background:#fff;border-radius:999px;padding:6px 12px;font:inherit;font-size:13.5px;font-weight:600;color:var(--ink2);cursor:pointer}
.ai-chips button:hover{border-color:var(--ink);color:var(--ink)}
.ai-in{display:flex;align-items:flex-end;gap:8px;padding:10px 12px;background:#fff;border-top:1px solid var(--line)}
.ai-in textarea{flex:1;resize:none;border:1.5px solid var(--line2);border-radius:18px;padding:9px 14px;font:inherit;font-size:15.5px;line-height:1.4;max-height:110px;outline:0;background:var(--bg,#fbfaf7);overflow-y:hidden;scrollbar-width:thin}
.ai-in textarea:focus{border-color:var(--ink)}
.ai-in button{flex:0 0 auto;width:42px;height:42px;border-radius:50%;border:0;background:var(--brand);color:#fff;display:grid;place-items:center;cursor:pointer}.ai-in button:disabled{opacity:.4;cursor:default}.ai-in svg{width:18px;height:18px}
.ai-foot{font-size:11.5px;color:var(--mute);text-align:center;padding:0 12px 8px;background:#fff}
@media (max-width:980px){
 .ai-fab{right:16px;bottom:16px;width:54px;height:54px}
 .ai-tip{right:16px;bottom:80px}
 .ai-panel{inset:0;width:auto;height:auto;border-radius:0;border:0}
 .ai-in textarea{font-size:16px}
}
@media (prefers-reduced-motion:reduce){.ai-panel,.ai-tip{animation:none}.ai-typing i{animation:none}}
@media print{.ai-fab,.ai-panel,.ai-tip{display:none!important}}
"""

JS = r"""(function(){
'use strict';
var SC=document.currentScript, API=SC.getAttribute('data-api')||'', BASE=(SC.getAttribute('src')||'').replace(/assets\/assistant\.js.*$/,''), LANG=SC.getAttribute('data-lang')||'zh', LOGO=SC.getAttribute('data-logo')||'';
var TX={
zh:{name:'apetto 小幫手',status:'線上 · 通常幾秒內回覆',ph:'輸入問題，例如：柴犬穿幾號？',open:'開啟小幫手',close:'關閉',reset:'重新開始',send:'送出',
 foot:'小幫手依照 apetto 網站資料自動回答',logged:'問題會匿名記錄，用來改善回答',ai:'AI 回答僅供參考，以客服答覆為準',tip:'尺寸不確定嗎？告訴我背長或品種，我幫你挑 🐾',
 hello:['嗨！我是 apetto 小幫手 🐾\n可以幫你挑尺寸、推薦款式，也能回答運費和出貨的問題。想問什麼呢？'],
 chips0:['幫我挑尺寸','雨衣怎麼選？','運費怎麼算？','多久會到貨？','有哪些顏色？'],
 greet:['嗨！很高興見到你 😊 想幫毛孩找雨衣，還是保暖外套呢？','哈囉！今天想幫毛孩找什麼呢？'],
 thanks:['不客氣！還有其他問題隨時問我 🐾','能幫上忙真好！祝毛孩出門都乾乾爽爽 ☔'],
 bye:['掰掰！歡迎隨時回來問我 🐾'],
 who:'我是 apetto 的線上小幫手，根據網站上的商品、尺寸表和購物說明來回答。比較特別的狀況，可以私訊 [Instagram]({ig}) 找真人客服喔。',
 contact:'想找真人客服，可以這樣聯絡我們：\n{contact}\n也可以私訊 [Instagram]({ig})。',
 ship:'運費這樣算：\n• 郵局寄送 **NT$65**（限 ATM 付款）\n• 全家、7-11 超商取貨 **NT$60**\n寄送台灣地區，單筆滿 **NT$3,000 免運**。',
 time:'付款後大約 **3～6 個工作天** 會收到（不含假日）。\n平日收到款項的隔天確認資料，三天內安排出貨；例假日和國定假日不出貨。',
 pay:'目前有兩種付款方式：\n• **ATM 轉帳**：3 日內付款，付款後用「填寫匯款單」通知我們\n• **超商取貨付款**：到店取貨時付款',
 ret:'退換貨的細節以官方賣場的說明為準，我這邊沒有完整資料，建議直接私訊 [Instagram]({ig}) 確認。\n小提醒：下單前先量背長、讓我幫你對一下尺寸，可以大幅減少換貨的機會喔。',
 buy:'在商品頁按「**立即購買**」，就會前往官方賣場結帳。\n流程：選商品 → 加入購物車 → 填資料與送貨方式 → 付款 → 收到出貨通知。',
 askBack:'沒問題！先告訴我毛孩的 **背長**（從脖子根部量到尾巴根，單位公分）；知道 **胸圍** 的話也一起給我，會更準。\n不方便量的話，告訴我品種也可以，我先幫你估。',
 askBack2:'要幫你算尺寸的話，我需要毛孩的背長（公分），或告訴我品種也行喔。',
 measure:'這樣量最準：\n• **背長**：從脖子根部（大約前腳的位置）沿著背量到尾巴根\n• **胸圍**：前腳後方、胸口最寬處繞一圈\n• **領圍**：脖子根部繞一圈\n有圖解的完整說明在 [如何測量狗狗尺寸]({measure})。量好告訴我，我幫你對尺寸表！',
 sizeHead:'背長 **{back} 公分**{chest}，我對了一下尺寸表：',chestPart:'、胸圍 {chest} 公分',
 sizeLine:'**{line}**：{fit} 號合身{loose}',loose:'，想寬鬆一點選 {s} 號',
 chestUp:'（考慮胸圍，已往上調一號）',chestWarn:'（胸圍偏大，最大號可能也會有點緊）',
 tooSmall:'背長比最小號還短一些，S 號可能會偏大。',tooBig:'背長超過最大號，{s} 號可能會偏短。',
 sizeTail:['尺寸表有 1～3 公分誤差；介於兩個尺寸之間時，毛量多或想內搭的選大一號。','想先看看穿上的樣子？可以到 [試衣間]({fit}) 上傳照片試穿。'],
 breed:'一般{breed}的背長大約 **{cm} 公分**，我先用這個估算（每隻體型差很多，量一下最準喔）。',
 kg:'{kg} 公斤的毛孩通常穿{series}，不過衣服主要看背長。可以幫我量一下背長嗎？',
 serSmall:'小汪系列（小型犬）',serBig:'大汪系列（中大型犬）',
 price:'**{name}** 售價 **NT${p}**{x}。',priceX:'（{s} 號加價 NT${x}）',
 priceAll:'目前各系列的價格：',
 colors:'**{line}** 有這些顏色：{list}。',colorsAll:'目前各系列的顏色：',
 reco:['依你說的，我推薦這幾件：','這幾件應該很適合：'],recoWarm:'天冷又下雨的話，保暖款內層有刷毛，會比較舒服：',recoRain:'只需要擋雨的話，這幾件輕巧好穿脫：',
 recoAsk:'想找下雨天穿的，還是保暖的？毛孩是小型犬還是中大型犬？告訴我，我幫你挑。',
 soon:'**{cat}** 還在準備中，即將推出！可以先追蹤我們的 [Instagram]({ig})，上架會第一時間公告。',
 fit:'可以到 **[試衣間]({fit})** 上傳一張毛孩照片，挑一件 apetto，AI 會畫出牠穿上的樣子，還會附上造型師的評語喔。',
 found:['我在〈{t}〉找到相關說明：','這段應該能回答你（出自〈{t}〉）：'],more:'看完整內容 →',
 unknown:'這題我還沒把握回答 🙏 我最擅長的是：挑尺寸、推薦款式、運費和出貨。\n也可以私訊 [Instagram]({ig}) 問真人客服。',
 card:'看商品',cardsAll:'看全部商品 →',
 chipsSize:['有哪些顏色？','多少錢？','多久會到貨？'],chipsShip:['多久會到貨？','怎麼付款？','幫我挑尺寸'],chipsAfter:['幫我挑尺寸','運費怎麼算？','試衣間怎麼用？'],
 store:'網站上沒有列出實體門市的資訊。可以在官方賣場或 [Pinkoi]({pinkoi}) 線上購買；我們偶爾會參加展售會和快閃活動，會公告在 [最新消息]({news}) 和 [Instagram]({ig})。\n想看實品的話，也可以先問客服：\n{contact}',
 sizeHas:'有的，各系列的尺寸：',sizeNone:'目前沒有 {s} 號，最大到：',
 compare:'簡單說：\n• **一般款**（小汪防水斗篷、大汪雨衣）：單層防水布，輕、好穿脫，適合一般雨天散步\n• **保暖款**（小汪保暖防水斗篷、大汪保暖夾克）：一樣防水，內層多了 MIT 抗靜電刷毛，適合又濕又冷的冬天\n另外「小汪」是小型犬的斗篷式前扣設計，「大汪」是中大型犬的套頭加腹部插扣。',
 weather:'我沒辦法查天氣 🙈 不過出門前如果在下雨，記得幫毛孩穿上雨衣；天冷的話保暖款會更舒服喔。',
 colorHit:'有的！這幾件是你要找的顏色：',chipsBreed:['柴犬','貴賓','柯基','黃金獵犬'],
 dogName:['{name}，好可愛的名字！🐾 {name} 是什麼狗呢？告訴我品種或背長，我幫 {name} 挑尺寸。','{name} 你好 👋 想幫 {name} 找雨衣還是保暖外套？'],forDog:'幫 {name} 對好了 🐾 ',
 chartAsk:'想看哪個系列的尺寸表？',chartHead:'**{line}** 尺寸表（公分，圈量）：',chartRow:'{s}：衣長 {len}、領圍 {neck}、腹圍 {belly}',chartTail:'挑尺寸的方法：衣長比背長短約 {off} 公分最合身。告訴我背長，我直接幫你算。',
 sizeWord:'號',cm:'公分'},
en:{name:'apetto Helper',status:'Online · usually replies in seconds',ph:'Ask me, e.g. what size for a Shiba?',open:'Open the helper',close:'Close',reset:'Start over',send:'Send',
 foot:'Answers come from the apetto website',logged:'questions are logged anonymously to improve answers',ai:'AI answers are for reference only; our support team has the final word',tip:'Not sure about the size? Tell me the back length or breed 🐾',
 hello:["Hi! I'm the apetto helper 🐾\nI can pick a size, suggest a coat, and answer questions about shipping and delivery. What would you like to know?"],
 chips0:['Help me pick a size','Which raincoat?','Shipping cost?','Delivery time?','Which colours?'],
 greet:['Hi there! 😊 Looking for a raincoat or a warm jacket?','Hello! What can I find for your dog today?'],
 thanks:["You're welcome! Ask me anytime 🐾",'Happy to help! Dry walks ahead ☔'],
 bye:['Bye! Come back anytime 🐾'],
 who:"I'm apetto's online helper. I answer from the products, size charts and shopping info on this site. For anything special, message us on [Instagram]({ig}) to reach a person.",
 contact:'To reach a person:\n{contact}\nOr message us on [Instagram]({ig}).',
 ship:'Shipping in Taiwan:\n• Post office **NT$65** (ATM payment only)\n• FamilyMart / 7-Eleven pickup **NT$60**\nOrders of **NT$3,000+** ship free within Taiwan.',
 time:'After payment it takes about **3–6 working days** (weekends excluded).\nWe check your order the day after payment arrives and ship within three days; no shipping on weekends or public holidays.',
 pay:'Two ways to pay:\n• **ATM transfer** within 3 days, then send us the transfer form\n• **Pay at pickup** at the convenience store',
 ret:"Return and exchange details follow our official store's terms, and I don't have the full policy here, so please ask us on [Instagram]({ig}).\nTip: measure the back length first and let me check the size, which avoids most exchanges.",
 buy:"This site is a showcase; purchases are made in our official store in Taiwan. On a product page, use the store link to check out.",
 askBack:"Sure! What's your dog's **back length** (base of the neck to the base of the tail, in cm)? The **chest** girth helps too.\nIf you can't measure now, tell me the breed and I'll estimate.",
 askBack2:"To work out the size I need the back length in cm, or just the breed.",
 measure:'How to measure:\n• **Back length**: from the base of the neck (about where the front legs are) along the back to the base of the tail\n• **Chest**: around the widest part, just behind the front legs\n• **Neck**: around the base of the neck\nIllustrated guide: [How to measure your dog]({measure}). Tell me the numbers and I will match the chart!',
 sizeHead:'Back length **{back} cm**{chest}. Here is what the size charts say:',chestPart:', chest {chest} cm',
 sizeLine:'**{line}**: size {fit} fits{loose}',loose:', {s} for a looser fit',
 chestUp:' (one size up for the chest)',chestWarn:' (the chest is large; even the biggest size may be snug)',
 tooSmall:'The back is a bit shorter than the smallest size, so S may be roomy.',tooBig:'The back is longer than the largest size, so {s} may be short.',
 sizeTail:['Charts can vary by 1–3 cm; between two sizes, go up if your dog is fluffy or wears layers.','Want to see it on your dog first? Try the [Fitting Studio]({fit}).'],
 breed:'A typical {breed} has a back length of about **{cm} cm**, so I used that (dogs vary a lot, measuring is best).',
 kg:'At {kg} kg most dogs wear the {series}, but coats are sized by back length. Could you measure it?',
 serSmall:'Small Dog series',serBig:'Big Dog series',
 price:'**{name}** is **NT${p}**{x}.',priceX:' ({s} +NT${x})',
 priceAll:'Current prices:',
 colors:'**{line}** comes in: {list}.',colorsAll:'Colours by series:',
 reco:['Based on what you told me, I suggest:','These should suit your dog:'],recoWarm:'For cold, wet days, the warm models have a fleece lining:',recoRain:'For rain only, these are light and quick to put on:',
 recoAsk:'Rain only, or rain and cold? And is your dog small, or medium to large? Tell me and I will pick.',
 soon:'**{cat}** is coming soon! Follow us on [Instagram]({ig}) to hear first.',
 fit:'In the **[Fitting Studio]({fit})** you upload a photo of your dog, pick an apetto coat, and AI draws your dog wearing it, with a stylist note.',
 found:['I found this in "{t}":','This should help (from "{t}"):'],more:'Read more →',
 unknown:"I'm not sure about that one 🙏 I'm best at sizes, coat suggestions, shipping and delivery.\nYou can also ask a person on [Instagram]({ig}).",
 card:'View',cardsAll:'See all products →',
 chipsSize:['Which colours?','How much?','Delivery time?'],chipsShip:['Delivery time?','How to pay?','Help me pick a size'],chipsAfter:['Help me pick a size','Shipping cost?','How does the Fitting Studio work?'],
 store:"The website doesn't list a physical shop. You can buy online in our official store or on [Pinkoi]({pinkoi}); fairs and pop-ups are announced in [News]({news}) and on [Instagram]({ig}).\nTo ask about seeing the coats in person:\n{contact}",
 sizeHas:'Yes, sizes by series:',sizeNone:'There is no {s} at the moment; the largest sizes are:',
 compare:'In short:\n• **Standard** (Small Dog Waterproof Cape, Big Dog Raincoat): a single waterproof layer, light and quick to put on, for everyday rain\n• **Warm** (Small Dog Warm Waterproof Cape, Big Dog Warm Jacket): just as waterproof, plus an anti-static fleece lining for cold, wet winters\n"Small Dog" models are capes with front snaps; "Big Dog" models pull over and buckle under the belly.',
 weather:"I can't check the weather 🙈 but if it's raining, a raincoat keeps your dog dry, and the warm models help on cold days.",
 colorHit:'Yes! These come in that colour:',chipsBreed:['Shiba','Poodle','Corgi','Golden Retriever'],
 dogName:["{name} is a lovely name! 🐾 What breed is {name}? Tell me the breed or back length and I'll pick a size."],forDog:'Here you go for {name} 🐾 ',
 chartAsk:'Which series would you like the size chart for?',chartHead:'**{line}** size chart (cm, girths):',chartRow:'{s}: length {len}, neck {neck}, chest {belly}',chartTail:'Rule of thumb: the coat length should be about {off} cm shorter than the back. Tell me the back length and I will work it out.',
 sizeWord:'',cm:'cm'},
ja:{name:'apetto アシスタント',status:'オンライン · すぐにお返事します',ph:'例：柴犬は何サイズ？',open:'アシスタントを開く',close:'閉じる',reset:'最初から',send:'送信',
 foot:'apetto サイトの情報をもとに自動で回答します',logged:'質問は改善のため匿名で記録されます',ai:'AI の回答は参考情報です。正式な回答はスタッフから',tip:'サイズに迷ったら、背丈か犬種を教えてください 🐾',
 hello:['こんにちは！apetto アシスタントです 🐾\nサイズ選びやおすすめ、送料・発送についてお答えします。何でも聞いてください。'],
 chips0:['サイズを選びたい','レインコートの選び方','送料は？','届くまでの日数','カラーは？'],
 greet:['こんにちは！😊 レインコートと防寒ジャケット、どちらをお探しですか？'],
 thanks:['どういたしまして！いつでも聞いてください 🐾'],bye:['またいつでもどうぞ 🐾'],
 who:'apetto のオンラインアシスタントです。サイトの商品・サイズ表・ご購入案内をもとにお答えします。個別のご相談は [Instagram]({ig}) へどうぞ。',
 contact:'スタッフへのお問い合わせ：\n{contact}\n[Instagram]({ig}) の DM でも受け付けています。',
 ship:'台湾国内の送料：\n• 郵便 **NT$65**（ATM 払いのみ）\n• ファミリーマート／セブン受け取り **NT$60**\n**NT$3,000 以上で送料無料**です。',
 time:'お支払い後、**3〜6 営業日**ほどでお届けします（土日祝を除く）。',
 pay:'お支払い方法：\n• **ATM 振込**（3 日以内）\n• **コンビニ受け取り時払い**',
 ret:'返品・交換は公式ストアの規定に従います。詳細は [Instagram]({ig}) でお問い合わせください。\nご注文前に背丈を測ってサイズを確認すると安心です。',
 buy:'このサイトは商品紹介用です。ご購入は台湾の公式ストアからお願いします。',
 askBack:'承知しました！**背丈**（首の付け根から尾の付け根まで、cm）を教えてください。**胸囲**もあればより正確です。\n測れない場合は犬種でも大丈夫です。',
 askBack2:'サイズを計算するには背丈（cm）か犬種を教えてください。',
 measure:'測り方：\n• **背丈**：首の付け根（前足のあたり）から背中に沿って尾の付け根まで\n• **胸囲**：前足のすぐ後ろ、いちばん太いところを一周\n• **首回り**：首の付け根を一周\n図解は [サイズの測り方]({measure}) へ。',
 sizeHead:'背丈 **{back} cm**{chest}の場合、サイズ表ではこうなります：',chestPart:'、胸囲 {chest} cm',
 sizeLine:'**{line}**：{fit} がぴったり{loose}',loose:'、ゆったりなら {s}',
 chestUp:'（胸囲を考えて 1 サイズ上）',chestWarn:'（胸囲が大きめで、最大サイズでもきついかもしれません）',
 tooSmall:'最小サイズより背丈が短めなので、S でも大きめかもしれません。',tooBig:'最大サイズより背丈が長いので、{s} でも短めかもしれません。',
 sizeTail:['サイズ表には 1〜3 cm の誤差があります。迷ったら毛量の多い子は大きめを。','着た姿は [試着室]({fit}) で確認できます。'],
 breed:'一般的な{breed}の背丈は約 **{cm} cm** なので、それで計算しました（個体差があるので測るのがいちばんです）。',
 kg:'{kg} kg なら多くは{series}ですが、サイズは背丈で決まります。測っていただけますか？',
 serSmall:'小型犬シリーズ',serBig:'大型犬シリーズ',
 price:'**{name}** は **NT${p}**{x}です。',priceX:'（{s} は +NT${x}）',priceAll:'現在の価格：',
 colors:'**{line}** のカラー：{list}。',colorsAll:'シリーズごとのカラー：',
 reco:['おすすめはこちらです：'],recoWarm:'寒くて雨の日は、内側がフリースの防寒モデルが快適です：',recoRain:'雨よけだけなら、軽くて着せやすいこちら：',
 recoAsk:'雨用ですか、防寒も必要ですか？小型犬か中・大型犬かも教えてください。',
 soon:'**{cat}** は準備中です。[Instagram]({ig}) で入荷をお知らせします。',
 fit:'**[試着室]({fit})** でワンちゃんの写真をアップロードして apetto を選ぶと、AI が着用イメージを描きます。',
 found:['「{t}」にこう書かれています：'],more:'続きを読む →',
 unknown:'その質問にはまだうまく答えられません 🙏 サイズ選び・おすすめ・送料・発送が得意です。\n[Instagram]({ig}) でスタッフにも聞けます。',
 card:'見る',cardsAll:'すべての商品 →',
 chipsSize:['カラーは？','価格は？','届くまでの日数'],chipsShip:['届くまでの日数','支払い方法','サイズを選びたい'],chipsAfter:['サイズを選びたい','送料は？','試着室の使い方'],
 store:'サイトには実店舗の情報が載っていません。公式ストアまたは [Pinkoi]({pinkoi}) でお買い求めいただけます。イベント出店は [ニュース]({news}) と [Instagram]({ig}) でお知らせします。\nお問い合わせ：\n{contact}',
 sizeHas:'はい、シリーズごとのサイズ：',sizeNone:'{s} は現在ありません。最大サイズ：',
 compare:'ざっくり言うと：\n• **スタンダード**（小型犬 防水ケープ、大型犬レインコート）：防水 1 枚仕立てで軽く、普段の雨の日に\n• **防寒タイプ**：同じく防水で、内側に帯電防止フリース付き。寒くて雨の冬に\n小型犬用は前ボタンのケープ、大型犬用はかぶって胴でバックルを留めるタイプです。',
 weather:'天気は調べられません 🙈 雨ならレインコートを、寒い日は防寒タイプがおすすめです。',
 colorHit:'あります！そのカラーはこちら：',chipsBreed:['柴犬','プードル','コーギー','ゴールデン'],
 dogName:['{name}ちゃん、素敵な名前ですね 🐾 犬種か背丈を教えてください。'],forDog:'{name}ちゃんのサイズです 🐾 ',
 chartAsk:'どのシリーズのサイズ表を見ますか？',chartHead:'**{line}** サイズ表（cm・周囲）：',chartRow:'{s}：着丈 {len}、首回り {neck}、胴回り {belly}',chartTail:'目安は着丈が背丈より約 {off} cm 短いもの。背丈を教えていただければ計算します。',
 sizeWord:'',cm:'cm'},
de:{name:'apetto Assistent',status:'Online · antwortet meist sofort',ph:'z. B. Welche Größe für einen Shiba?',open:'Assistent öffnen',close:'Schließen',reset:'Neu starten',send:'Senden',
 foot:'Antworten basieren auf der apetto Website',logged:'Fragen werden anonym gespeichert, um Antworten zu verbessern',ai:'KI-Antworten sind unverbindlich; verbindlich ist unser Kundenservice',tip:'Unsicher bei der Größe? Nenn mir Rückenlänge oder Rasse 🐾',
 hello:['Hallo! Ich bin der apetto Assistent 🐾\nIch helfe bei Größe und Modellwahl und beantworte Fragen zu Versand und Lieferung.'],
 chips0:['Größe finden','Welcher Regenmantel?','Versandkosten?','Lieferzeit?','Welche Farben?'],
 greet:['Hallo! 😊 Suchst du einen Regenmantel oder eine warme Jacke?'],thanks:['Gern geschehen! Frag jederzeit 🐾'],bye:['Tschüss! Bis bald 🐾'],
 who:'Ich bin der Online-Assistent von apetto und antworte anhand der Produkte, Größentabellen und Kaufinfos dieser Website. Für Persönliches schreib uns auf [Instagram]({ig}).',
 contact:'So erreichst du uns:\n{contact}\nOder schreib uns auf [Instagram]({ig}).',
 ship:'Versand in Taiwan:\n• Post **NT$65** (nur bei ATM-Zahlung)\n• Abholung bei FamilyMart / 7-Eleven **NT$60**\nAb **NT$3.000** versandkostenfrei.',
 time:'Nach Zahlungseingang dauert es etwa **3–6 Werktage** (ohne Wochenende und Feiertage).',
 pay:'Zahlungsarten:\n• **ATM-Überweisung** innerhalb von 3 Tagen\n• **Bezahlung bei Abholung** im Convenience Store',
 ret:'Rückgabe und Umtausch richten sich nach den Bedingungen unseres offiziellen Shops; frag am besten auf [Instagram]({ig}) nach.\nTipp: Rückenlänge messen und Größe prüfen lassen vermeidet die meisten Umtausche.',
 buy:'Diese Website zeigt unsere Produkte; gekauft wird im offiziellen Shop in Taiwan.',
 askBack:'Gern! Wie lang ist der **Rücken** deines Hundes (Halsansatz bis Rutenansatz, in cm)? Der **Brustumfang** hilft auch.\nOder nenn mir einfach die Rasse.',
 askBack2:'Für die Größe brauche ich die Rückenlänge in cm oder die Rasse.',
 measure:'So misst du:\n• **Rückenlänge**: vom Halsansatz (etwa über den Vorderbeinen) bis zum Rutenansatz\n• **Brust**: an der breitesten Stelle hinter den Vorderbeinen\n• **Hals**: um den Halsansatz\nBebildert: [Hund richtig messen]({measure}).',
 sizeHead:'Rückenlänge **{back} cm**{chest} – laut Größentabellen:',chestPart:', Brust {chest} cm',
 sizeLine:'**{line}**: Größe {fit} passt{loose}',loose:', {s} für lockerer',
 chestUp:' (wegen der Brust eine Größe größer)',chestWarn:' (die Brust ist groß; auch die größte Größe könnte eng sein)',
 tooSmall:'Der Rücken ist kürzer als die kleinste Größe; S könnte groß ausfallen.',tooBig:'Der Rücken ist länger als die größte Größe; {s} könnte kurz sein.',
 sizeTail:['Tabellen können 1–3 cm abweichen; im Zweifel bei viel Fell eine Größe größer.','Wie es aussieht, zeigt dir die [Anprobe]({fit}).'],
 breed:'Ein typischer {breed} hat etwa **{cm} cm** Rückenlänge; damit habe ich gerechnet (Messen ist am genauesten).',
 kg:'Mit {kg} kg passt meist die {series}, entscheidend ist aber die Rückenlänge. Kannst du sie messen?',
 serSmall:'Serie für kleine Hunde',serBig:'Serie für große Hunde',
 price:'**{name}** kostet **NT${p}**{x}.',priceX:' ({s} +NT${x})',priceAll:'Aktuelle Preise:',
 colors:'**{line}** gibt es in: {list}.',colorsAll:'Farben je Serie:',
 reco:['Das würde ich empfehlen:'],recoWarm:'Für kalte, nasse Tage mit Fleecefutter:',recoRain:'Nur gegen Regen, leicht und schnell angezogen:',
 recoAsk:'Nur Regen oder auch Kälte? Und ist dein Hund klein oder mittel bis groß?',
 soon:'**{cat}** kommt bald! Folge uns auf [Instagram]({ig}).',
 fit:'In der **[Anprobe]({fit})** lädst du ein Foto hoch, wählst ein apetto Modell, und die KI zeigt deinen Hund damit.',
 found:['Dazu steht in „{t}“:'],more:'Weiterlesen →',
 unknown:'Da bin ich mir nicht sicher 🙏 Am besten kann ich Größen, Modelle, Versand und Lieferung.\nAuf [Instagram]({ig}) antwortet dir auch ein Mensch.',
 card:'Ansehen',cardsAll:'Alle Produkte →',
 chipsSize:['Welche Farben?','Was kostet das?','Lieferzeit?'],chipsShip:['Lieferzeit?','Wie bezahlen?','Größe finden'],chipsAfter:['Größe finden','Versandkosten?','Wie funktioniert die Anprobe?'],
 store:'Ein Ladengeschäft ist auf der Website nicht angegeben. Gekauft wird online im offiziellen Shop oder auf [Pinkoi]({pinkoi}); Messen und Pop-ups kündigen wir unter [Neuigkeiten]({news}) und auf [Instagram]({ig}) an.\nKontakt:\n{contact}',
 sizeHas:'Ja, Größen je Serie:',sizeNone:'{s} gibt es derzeit nicht; die größten Größen:',
 compare:'Kurz gesagt:\n• **Standard** (Cape für kleine Hunde, Regenmantel für große Hunde): eine wasserdichte Lage, leicht, für normale Regentage\n• **Warm**: genauso wasserdicht, dazu antistatisches Fleecefutter für kalte, nasse Tage\nModelle für kleine Hunde sind Capes mit Druckknöpfen vorn, die für große Hunde werden übergezogen und am Bauch geschlossen.',
 weather:'Das Wetter kann ich nicht abrufen 🙈 Bei Regen hält ein Regenmantel trocken, an kalten Tagen helfen die warmen Modelle.',
 colorHit:'Ja! In dieser Farbe gibt es:',chipsBreed:['Shiba','Pudel','Corgi','Golden Retriever'],
 dogName:['{name} – schöner Name! 🐾 Welche Rasse ist {name}? Dann finde ich die Größe.'],forDog:'Für {name} 🐾 ',
 chartAsk:'Für welche Serie möchtest du die Größentabelle?',chartHead:'**{line}** Größentabelle (cm, Umfang):',chartRow:'{s}: Länge {len}, Hals {neck}, Brust {belly}',chartTail:'Faustregel: Die Mantellänge etwa {off} cm kürzer als der Rücken. Nenn mir die Rückenlänge, dann rechne ich.',
 sizeWord:'',cm:'cm'}};
var T=TX[LANG]||TX.zh;
// ---------------------------------------------------------------- language understanding
var R={
 greet:/^(hi|hello|hey|yo|hallo|servus|moin)\b|^guten (tag|morgen|abend)|^(哈囉|哈啰|你好|您好|嗨|安安|哈嘍|早安|午安|晚安|こんにちは|こんばんは|おはよう|はじめまして)/,
 thanks:/(謝謝|感謝|謝啦|3q|thx|thank|ありがと|danke)/,
 bye:/^(掰|再見|bye|see you|さようなら|またね|tschüss|ciao)/,
 who:/(你是誰|你是(ai|機器人|真人|人嗎)|機器人嗎|真人嗎|who are you|are you (a )?(bot|human|real|ai)|あなたは(誰|ロボット)|bist du (ein )?(bot|mensch))/,
 contact:/(客服|真人|聯絡|聯繫|電話|line|instagram|\big\b|email|信箱|contact|human|person|問い合わせ|スタッフ|kontakt|mensch)/,
 ship:/(運費|免運|寄送|郵寄|宅配|超商|7-?11|全家|shipping|postage|delivery (cost|fee)|送料|配送料|versand(kosten)?|porto)/,
 time:/(多久|幾天|何時(會)?到|什麼時候(會)?到|出貨|到貨|工作天|how long|when will|arrive|delivery time|ship(ping)? time|いつ届|何日|発送|lieferzeit|wann kommt|wie lange)/,
 pay:/(付款|匯款|atm|轉帳|信用卡|貨到付款|刷卡|pay|payment|credit card|支払|振込|zahl|bezahl|überweis)/,
 ret:/(退貨|換貨|退換|退款|不合身|太大|太小|return|exchange|refund|返品|交換|rückgab|umtausch|zurück)/,
 buy:/(怎麼買|哪裡買|購買|下單|訂購|買得到|how (can|do) i (buy|order)|where.*buy|purchase|place an order|購入|注文|買いたい|kaufen|bestell)/,
 measure:/(怎麼量|如何量|怎樣量|測量|量法|量哪|how (do i|to) measure|measuring|測り方|測る|wie messe|messen)/,
 size:/(尺寸|幾號|多大|大小|號數|穿什麼|穿哪|適合.*號|背長|胸圍|腹圍|領圍|\bsize|sizing|fit\b|サイズ|何号|背丈|größe|grösse)/,
 fit:/(試衣|試穿|try ?on|fitting|試着|anprob)/,
 care:/(洗|清潔|保養|烘|晾|wash|clean|care|dry|洗濯|お手入れ|wasch|pflege|reinig)/,
 price:/(多少錢|價格|價錢|售價|幾元|貴|便宜|price|cost|how much|いくら|値段|価格|preis|kostet|kosten)/,
 colors:/(顏色|色|配色|colou?r|カラー|色は|farbe)/,
 reco:/(推薦|哪件|哪個好|哪一件|選哪|怎麼選|差別|比較|差在|適合|建議|recommend|which (one|coat|is)|difference|suggest|best|おすすめ|違い|どれ|選び方|empfehl|unterschied|welche[rs]?)/,
 rain:/(雨衣|斗篷|防水|雨天|下雨|雨|rain|cape|waterproof|レイン|ケープ|雨|regen|cape|wasserdicht)/,
 warm:/(保暖|外套|夾克|冬|冷|寒|刷毛|毛絨|warm|jacket|coat|winter|cold|fleece|防寒|ジャケット|冬|jacke|kalt|winter)/,
 small:/(小汪|小型|小狗|小隻|small|little|小型犬|kleine?n?\b)/,
 store:/(實體店|實體門市|門市|店面|哪裡有店|可以去哪看|現場看|physical (store|shop)|shop near|brick|店舗|実店舗|laden|geschäft vor ort)/,
 about:/(品牌故事|品牌理念|關於 ?apetto|apetto 是|apetto是|創立|由來|about (you|apetto|the brand)|your story|brand story|ブランド|について|über apetto|geschichte)/,
 sell:/(有賣|有沒有|有在賣|賣不賣|販售|推出|上架|什麼時候有|do you (sell|have)|available|sell|販売|ありますか|verkauft|gibt es)/,
 chart:/(尺寸表|尺寸對照|size ?chart|size table|サイズ表|größentabelle|masstabelle)/,
 sizeAsk:/(?:^|[^a-z])(xs|s|m|l|xl|2xl|xxl|3xl)(?:號|号|size)?(?=$|[^a-z])/,
 compare:/(差在|差別|差異|不同|比較|difference|differ|compare|vs|違い|比べ|unterschied|vergleich)/,
 weather:/(天氣|氣溫|下雨嗎|會下雨|weather|forecast|天気|wetter)/,
 thisOne:/(這件|這款|這個|它|this one|this coat|\bit\b|これ|この|dieses?)/,
 big:/(大汪|大型|中型|中大型|大狗|大隻|big|large|medium|大型犬|中型犬|große?n?\b|mittel)/
};
var COLORS={gray:/(灰|gr[ae]y|グレー|grau)/,blue:/(藍|blue|ブルー|青|blau)/,orange:/(桔|橘|orange|オレンジ)/,green:/(綠|green|グリーン|緑|grün)/,pink:/(桃|粉|pink|ピンク|rosa|beere)/,yellow:/(黃|黄|yellow|lemon|neon|イエロー|レモン|gelb)/};
var BREEDS=[[/(吉娃娃|chihuahua|チワワ)/,22],[/(約克夏|yorkshire|yorkie|ヨーキー|ヨークシャー)/,24],[/(博美|pomeranian|ポメ|zwergspitz)/,25],[/(馬爾濟斯|maltese|マルチーズ|malteser)/,27],
 [/(貴賓犬|貴賓|泰迪|poodle|プードル|pudel)/,29],[/(比熊|bichon|ビション)/,30],[/(西施|shih ?tzu|シーズー)/,31],[/(巴哥|pug|パグ|mops)/,30],[/(瑪爾|蝴蝶犬|papillon|パピヨン)/,27],
 [/(法國鬥牛犬|法鬥|法國鬥牛|french bulldog|frenchie|フレブル|フレンチ・?ブルドッグ|französische bulldogge)/,34],[/(雪納瑞|schnauzer|シュナウザー)/,35],[/(傑克羅素|jack russell|ジャックラッセル)/,33],
 [/(臘腸|dachshund|ダックス|dackel)/,38],[/(柯基|corgi|コーギー)/,40],[/(柴犬|柴柴|shiba|しばいぬ|柴)/,40],[/(米格魯|beagle|ビーグル)/,40],[/(喜樂蒂|sheltie|シェルティ)/,40],
 [/(鬥牛犬|英國鬥牛|bulldog|ブルドッグ|bulldogge)/,40],[/(邊境牧羊犬|邊境牧羊|邊牧|border collie|ボーダーコリー)/,50],[/(哈士奇|husky|ハスキー)/,55],[/(拉布拉多犬|拉布拉多|labrador|ラブラドール)/,58],
 [/(黃金獵犬|黃金|golden|ゴールデン)/,60],[/(德國狼犬|german shepherd|シェパード|schäferhund)/,63],[/(杜賓|doberman|ドーベルマン)/,62]];
var CAT_WORDS={3:/(浴袍|浴巾|bathrobe|robe|hoodie|バスローブ|bademantel)/,4:/(牽繩|頸圈|項圈|胸背|leash|collar|harness|リード|首輪|leine|halsband)/,5:/(領巾|圍巾|bandana|scarf|バンダナ|halstuch)/,6:/(鞋|shoe|boot|靴|シューズ|schuh)/,7:/(墊|睡墊|床|pad|mat|bed|マット|ベッド|matte|decke)/};
function norm(s){return String(s||'').normalize('NFKC').toLowerCase().replace(/[“”"'`]/g,'').replace(/\s+/g,' ').trim();}
function faqText(f){var a=Array.isArray(f.a)?pick(f.a):f.a;return a+(f.u?'\n['+T.more+']('+f.u+')':'');}
function kwHit(s,w){w=norm(w);if(!w)return false;if(/^[a-z0-9' ]+$/.test(w))return new RegExp('(^|[^a-z])'+w.replace(/ /g,'\\s+')+'($|[^a-z])').test(s);return s.indexOf(w)>=0;}
function pick(a){return Array.isArray(a)?a[Math.floor(Math.random()*a.length)]:a;}
function fmt(s,v){return String(s).replace(/\{(\w+)\}/g,function(m,k){return v&&v[k]!=null?v[k]:(KB&&KB.links[k]!=null?KB.links[k]:(KB&&typeof KB[k]==='string'?KB[k]:m));});}
function money(n){return Number(n).toLocaleString('en-US');}
// tokens for search: CJK bigrams + words
var STOP={'請問':1,'什麼':1,'怎麼':1,'可以':1,'一下':1,'我們':1,'你們':1,'有沒':1,'沒有':1,'是不':1,'不是':1,'如何':1,'狗狗':1,'毛孩':1,'我家':1,'家的':1,'的話':1,'the':1,'a':1,'is':1,'do':1,'you':1,'my':1,'to':1,'of':1,'for':1,'what':1,'how':1,'can':1,'and':1,'in':1,'it':1,'dog':1,'der':1,'die':1,'das':1,'ist':1,'und':1,'ich':1,'mein':1};
function toks(s){var out=[];norm(s).replace(/[぀-ヿ㐀-鿿]+|[a-z0-9äöüß]+/g,function(w){
 if(/^[a-z0-9äöüß]+$/.test(w)){if(w.length>1&&!STOP[w])out.push(w.length>4?w.replace(/(es|en|s|e)$/,''):w);}
 else if(w.length===1)out.push(w);else for(var i=0;i<w.length-1;i++){var b=w.substr(i,2);if(!STOP[b])out.push(b);}return w;});return out;}
// ---------------------------------------------------------------- knowledge base + search index
var KB=null,IDX=null,kbP=null,K=null;
function loadKB(){if(!kbP)kbP=fetch(BASE+'assets/assistant/kb.'+LANG+'.json',{cache:'no-cache'}).then(function(r){return r.json();}).then(function(j){KB=j;buildIdx();
 var pm=location.pathname.match(/product_id=(\d+)/)||decodeURIComponent(location.href).match(/product_id=(\d+)/);if(pm&&prodById(pm[1]))ST.prod=pm[1];  // on a product page, "this one" means that product
 return j;});return kbP;}
function buildIdx(){var docs=KB.docs.slice();KB.faq.forEach(function(f){if(!f.chat&&!f.pending)docs.push({t:'',x:Array.isArray(f.a)?f.a.join(' '):f.a,u:f.u,faq:f});});
 var df={},N=docs.length,len=0;docs.forEach(function(d){var tk=toks(d.t+' '+d.t+' '+d.x+(d.faq?' '+d.faq.q.join(' ')+' '+d.faq.q.join(' '):''));d.tf={};tk.forEach(function(t){d.tf[t]=(d.tf[t]||0)+1;});d.len=tk.length;len+=tk.length;Object.keys(d.tf).forEach(function(t){df[t]=(df[t]||0)+1;});});
 IDX={docs:docs,df:df,N:N,avg:len/Math.max(1,N)};}
var SYN=[[/(客製|訂製|刺繡|印名字|名字)/,' 寫上名字 名字 name'],[/(晚上|夜間|夜晚|天黑|看得到|看不到|安全|night|dark|visible)/,' 反光條 反光 3m reflective'],
 [/(牽繩|leash|リード|leine)/,' 牽繩 上牽繩 領圍 開口 leash'],[/(穿脫|好穿|難穿|easy to put|on and off)/,' 快速穿脫 鈕扣 quick'],[/(靜電|炸毛|static)/,' 炸毛 抗靜電 static'],
 [/(洗衣機|機洗|手洗|washing machine|machine|洗濯機|waschmaschine)/,' 清洗 洗衣袋 washing wash 洗い方 waschen'],[/(防水|耐水|潑水|waterproof|water)/,' 耐水壓 防水 waterproof'],[/(口袋|pocket)/,' 口袋 拉鍊 pocket']];
function expand(q){var s=norm(q),x=q;SYN.forEach(function(p){if(p[0].test(s))x+=p[1];});return x;}
function search(q){q=expand(q);var qt=toks(q),best=[];if(!qt.length)return best;var uq={};qt.forEach(function(t){uq[t]=1;});
 IDX.docs.forEach(function(d){var s=0,hit=0;Object.keys(uq).forEach(function(t){var f=d.tf[t];if(!f)return;hit++;var idf=Math.log(1+(IDX.N-IDX.df[t]+.5)/(IDX.df[t]+.5));s+=idf*f*2.2/(f+1.2*(.25+.75*d.len/IDX.avg));});
  if(s>0)best.push({d:d,s:s,cov:hit/Object.keys(uq).length});});
 best.sort(function(a,b){return b.s-a.s;});return best;}
function snippet(d,q){var qt={};toks(q).forEach(function(t){qt[t]=1;});var sents=d.x.replace(/([。！？!?；;])\s*/g,'$1\n').replace(/\.\s+/g,'.\n').split('\n').filter(function(x){return x.trim();});
 var sc=sents.map(function(s,i){var n=0;toks(s).forEach(function(t){if(qt[t])n++;});return {i:i,n:n};}).sort(function(a,b){return b.n-a.n||a.i-b.i;});
 var keep=sc.slice(0,2).map(function(x){return x.i;}).sort(function(a,b){return a-b;}),out=keep.map(function(i){return sents[i];}).join(' ');
 if(out.length>220)out=out.slice(0,210)+'…';return out||d.x.slice(0,200);}
// ---------------------------------------------------------------- state
var ST={prod:null,ser:null,warm:null,back:null,chest:null,want:null,breed:null,dog:null};
function prodById(id){return KB.products.filter(function(p){return p.id===id;})[0]||null;}
function curLine(){var p=ST.prod&&prodById(ST.prod);return p?p.lk:null;}
function lines(){var seen={},out=[];KB.products.forEach(function(p){if(!seen[p.lk]){seen[p.lk]=1;out.push({lk:p.lk,line:p.line,ser:p.ser,warm:p.warm,ch:p.ch,ps:KB.products.filter(function(q){return q.lk===p.lk;})});}});return out;}
function measures(q){var m={},s=norm(q).replace(/,/g,'.'),num='(\\d{1,3}(?:\\.\\d)?)',x;
 x=s.match(new RegExp('(背長|背|身長|後背|back(?: length)?|length|rücken(?:länge)?|背丈)\\D{0,6}?'+num));if(x)m.back=+x[2];
 x=s.match(new RegExp('(胸圍|胸|腹圍|腹|chest|girth|brust(?:umfang)?|bauch|胴回り|胸囲)\\D{0,6}?'+num));if(x)m.chest=+x[2];
 x=s.match(new RegExp('(領圍|頸圍|脖子|neck|hals|首回り)\\D{0,6}?'+num));if(x)m.neck=+x[2];
 x=s.match(new RegExp(num+'\\s*(kg|公斤|キロ|kilo)'));if(x)m.kg=+x[1];
 if(!m.back){x=s.match(new RegExp(num+'\\s*(cm|公分|センチ|厘米)'));if(x&&+x[1]!==m.chest&&+x[1]!==m.neck)m.back=+x[1];}
 if(!m.back&&!m.kg&&ST.want==='back'){x=s.match(/^\D{0,6}(\d{2,3}(?:\.\d)?)\D{0,8}$/);if(x)m.back=+x[1];}
 if(m.back&&(m.back<12||m.back>110))delete m.back;return m;}
function breedOf(q){var s=norm(q);for(var i=0;i<BREEDS.length;i++){var x=s.match(BREEDS[i][0]);if(x){var full=BREEDS[i][0].source.slice(1).split('|')[0].replace(/[()]/g,'');return {name:/^[a-z]/.test(x[1])?x[1].replace(/(^|\s)[a-z]/g,function(c){return c.toUpperCase();}):(LANG==='zh'&&/[\u4e00-\u9fff]/.test(full)?full:x[1]),cm:BREEDS[i][1]};}}return null;}
// size from a chart: the size closest to (back - offset), smaller on ties, then one up if the chest does not fit
function sizeFor(chKey,back,chest){var ch=KB.charts[chKey];if(!ch||!ch.rows.length)return null;var target=back-ch.off,bi=0,bd=1e9;
 ch.rows.forEach(function(r,i){var d=Math.abs(r.len-target);if(d<bd-0.01){bd=d;bi=i;}});var up=false,warn=false;
 if(chest){var lim=function(r){return r.belly.length>1?r.belly[1]:r.belly[0]-2;};while(bi<ch.rows.length-1&&lim(ch.rows[bi])<chest){bi++;up=true;}if(lim(ch.rows[bi])<chest)warn=true;}
 return {fit:ch.rows[bi].s,loose:bi+1<ch.rows.length?ch.rows[bi+1].s:null,small:target<ch.rows[0].len-4,big:target>ch.rows[ch.rows.length-1].len+3,up:up,warn:warn,last:ch.rows[ch.rows.length-1].s};}
// ---------------------------------------------------------------- answers
function A(text,o){o=o||{};o.text=fmt(text);return o;}
function chipsFor(k){return T[k]||T.chipsAfter;}
function pickProducts(q){var s=norm(q),ps=KB.products.slice(),f;
 var ser=R.small.test(s)?'small':R.big.test(s)?'big':null,warm=R.warm.test(s)?true:(/(只|only|nur|だけ)/.test(s)&&R.rain.test(s))?false:null,col=null;
 Object.keys(COLORS).forEach(function(k){if(COLORS[k].test(s))col=k;});
 if(ser)ps=ps.filter(function(p){return p.ser===ser;});if(warm!=null)ps=ps.filter(function(p){return p.warm===warm;});if(col){f=ps.filter(function(p){return p.ck===col;});if(f.length)ps=f;}
 return {ps:ps,ser:ser,warm:warm,col:col,any:!!(ser||warm!=null||col)};}
function sizeAnswer(back,chest,src,narrow){
 var ls=lines(),head=(ST.dog?fmt(T.forDog,{name:ST.dog}):'')+fmt(T.sizeHead,{back:back,chest:chest?fmt(T.chestPart,{chest:chest}):''}),rows=[],tail=[];
 var pool=ls.filter(function(l){if(narrow&&narrow.lk)return l.lk===narrow.lk;if(narrow&&narrow.ser&&l.ser!==narrow.ser)return false;if(narrow&&narrow.warm!=null&&l.warm!==narrow.warm)return false;
  if(narrow&&narrow.ser)return true;return back<=44?l.ser==='small':back>=45?l.ser==='big':true;});
 if(!pool.length)pool=ls;
 var anyTooSmall=false,anyTooBig=null,best=null;
 pool.forEach(function(l){var r=sizeFor(l.ch,back,chest);if(!r)return;if(!best)best={l:l,r:r};
  rows.push('• '+fmt(T.sizeLine,{line:l.line,fit:r.fit,loose:r.loose&&!r.warn?fmt(T.loose,{s:r.loose}):''})+(r.up?T.chestUp:'')+(r.warn?T.chestWarn:''));
  if(r.small)anyTooSmall=true;if(r.big)anyTooBig=r.last;});
 if(anyTooSmall)tail.push(T.tooSmall);if(anyTooBig)tail.push(fmt(T.tooBig,{s:anyTooBig}));
 tail.push(T.sizeTail[0]);
 var cards=[];pool.forEach(function(l){l.ps.slice(0,2).forEach(function(p){if(cards.length<6)cards.push(p.id);});});
 ST.ser=pool[0]&&pool.every(function(l){return l.ser===pool[0].ser;})?pool[0].ser:ST.ser;
 return A((src?src+'\n':'')+head+'\n'+rows.join('\n')+'\n'+tail.join('\n')+(Math.random()<.5?'\n'+T.sizeTail[1]:''),{cards:cards,chips:chipsFor('chipsSize')});}
function priceLine(p){var x=p.sz.filter(function(z){return z.x;});return fmt(T.price,{name:p.line,p:money(p.p),x:x.length?fmt(T.priceX,{s:x.map(function(z){return z.s;}).join('/'),x:money(x[0].x)}):''});}
function answer(q){
 K=null;var s=norm(q),m=measures(q),br=breedOf(q),pp=pickProducts(q),cat=null,k,mentionsProduct=pp.any;
 Object.keys(CAT_WORDS).forEach(function(id){if(CAT_WORDS[id].test(s))cat=+id;});
 // hand-written answers win when they match well
 var bare=s.replace(/[\s!！?？.。,，~～…]+/g,'');
 var dn=q.match(/(?:我家|我的)(?:狗狗|狗|毛孩|寶貝|小孩)?(?:叫做|叫|名字是|名字叫)\s*([\u4e00-\u9fffA-Za-z]{1,8})/)||q.match(/my dog(?:'s name)? is (?:called |named )?([A-Z][a-z]{1,12})/)||q.match(/my dog is called ([A-Za-z]{2,12})/i);
 if(dn&&!/^(什麼|啥|多大|幾歲)/.test(dn[1])){ST.dog=dn[1];K='chat-dogname';return A(fmt(pick(T.dogName),{name:dn[1]}),{chips:T.chipsBreed});}
 var hasIntent=R.size.test(s)||R.reco.test(s)||!!breedOf(q);
 for(var i=0;i<KB.faq.length;i++){var f=KB.faq[i];if(f.pending&&hasIntent)continue;if(f.q.some(function(w){return kwHit(s,w);})||(f.x||[]).some(function(w){return bare===norm(w).replace(/[\s!！?？.。,，~～…]+/g,'');})){K=f.chat?f.id:f.pending?'pending':'faq';return A(faqText(f),{chips:f.chat?T.chips0.slice(0,3):T.chipsAfter});}}
 if(R.who.test(s))return K='who',A(T.who,{chips:T.chips0.slice(0,3)});
 if(R.contact.test(s)&&!R.store.test(s))return K='contact',A(T.contact,{chips:T.chipsAfter});
 if(R.greet.test(s)&&s.length<14)return K='greet',A(pick(T.greet),{chips:T.chips0});
 if(R.thanks.test(s)&&s.length<20)return K='thanks',A(pick(T.thanks),{chips:T.chipsAfter});
 if(R.bye.test(s)&&s.length<16)return K='bye',A(pick(T.bye));
 // categories that are not on sale yet
 var soonCat=null;if(cat){var c=KB.cats.filter(function(x){return x.id===cat;})[0];if(c&&!c.cnt){if(R.sell.test(s)||s.length<=4)return K='soon',A(fmt(T.soon,{cat:c.n}),{chips:T.chipsAfter});soonCat=c;}}
 if(R.store.test(s))return K='store',A(T.store,{chips:T.chipsAfter});
 if(R.about.test(s)){var ab=KB.docs.filter(function(d){return d.u===KB.links.about;});if(ab.length)return K='about',A(ab.slice(0,2).map(function(d){return '**'+d.t+'**\n'+snippet(d,d.t);}).join('\n')+'\n['+T.more+']('+KB.links.about+')',{chips:T.chipsAfter});}
 var sz=s.match(R.sizeAsk);if(sz&&(R.sell.test(s)||/(嗎|\?|？|有)/.test(s))&&!m.back){var want=sz[1].replace('xxl','2xl').toUpperCase(),has=lines().filter(function(l){return l.ps[0].sz.some(function(z){return z.s===want;});});
  var lsz=function(l){var seen={},o=[];l.ps.forEach(function(p){p.sz.forEach(function(z){if(!seen[z.s]){seen[z.s]=1;o.push(z);}});});return o;};
  has=lines().filter(function(l){return lsz(l).some(function(z){return z.s===want;});});
  var row=function(l){var zs=lsz(l),x=zs.filter(function(z){return z.x;});return '• '+l.line+'：'+zs.map(function(z){return z.s;}).join(' / ')+(x.length?fmt(T.priceX,{s:x.map(function(z){return z.s;}).join('/'),x:money(x[0].x)}):'');};
  return K='sizeAvail',A((has.length?T.sizeHas:fmt(T.sizeNone,{s:want}))+'\n'+lines().map(row).join('\n').replace(/：/g,LANG==='zh'?'：':': '),{chips:[T.chips0[0]].concat(T.chipsSize.slice(0,1))});}
 if(R.chart.test(s)){var named=lines().filter(function(l){return s.indexOf(norm(l.line))>=0;});var cls=named.length?named:lines().filter(function(l){return (pp.any?((!pp.ser||l.ser===pp.ser)&&(pp.warm==null||l.warm===pp.warm)):curLine()?l.lk===curLine():ST.ser?l.ser===ST.ser:false);});
  if(cls.length!==1){K='chartAsk';return A(T.chartAsk,{chips:lines().map(function(l){return l.line;}).slice(0,4).map(function(n){return n+(LANG==='zh'?' 尺寸表':LANG==='ja'?' サイズ表':LANG==='de'?' Größentabelle':' size chart');})});}
  var cl=cls[0],ch=KB.charts[cl.ch];ST.prod=cl.ps[0].id;K='chart';
  return A(fmt(T.chartHead,{line:cl.line})+'\n'+ch.rows.map(function(r){return '• '+fmt(T.chartRow,{s:r.s,len:r.len,neck:r.neck,belly:r.belly.join('~')});}).join('\n')+'\n'+fmt(T.chartTail,{off:ch.off}),{chips:[T.chips0[0]].concat(T.chipsSize.slice(0,1))});}
 if(R.measure.test(s))return K='measure',A(T.measure,{chips:T.chips0.slice(0,1).concat(T.chipsSize.slice(2))});
 // size: numbers, breed, or a size question
 if(m.chest)ST.chest=m.chest;
 var wantsSize=R.size.test(s)||(ST.want==='back'&&!!m.back);
 if(m.back||(br&&(wantsSize||!mentionsProduct))){var back=m.back||br.cm,src=!m.back&&br?fmt(T.breed,{breed:br.name,cm:br.cm}):'';
  if(!m.chest&&(br&&(!ST.breed||ST.breed.name!==br.name)||(ST.back&&Math.abs(back-ST.back)>4)))ST.chest=null;
  ST.back=back;ST.breed=br||null;ST.want=null;
  var narrow=pp.any?{ser:pp.ser,warm:pp.warm}:(curLine()&&R.thisOne.test(s)?{lk:curLine()}:null);return K='size',sizeAnswer(back,m.chest||ST.chest,src,narrow);}
 if(m.kg&&!m.back){ST.want='back';return K='kg',A(fmt(T.kg,{kg:m.kg,series:m.kg<=9?T.serSmall:T.serBig}),{chips:[T.chips0[0]]});}
 if(wantsSize&&!R.ship.test(s)&&!(pp.any&&!ST.back&&!R.chart.test(s)&&!/(尺寸|幾號|size|サイズ|größe)/.test(s))){if(ST.back&&(pp.any||curLine()))return K='size',sizeAnswer(ST.back,ST.chest,'',pp.any?{ser:pp.ser,warm:pp.warm}:{lk:curLine()});var again=ST.want==='back';ST.want='back';return A(again?T.askBack2:T.askBack,{chips:T.chipsBreed});}
 if(R.weather.test(s))return K='weather',A(T.weather,{chips:T.chips0.slice(0,2)});
 if(R.compare.test(s)&&(R.warm.test(s)||R.rain.test(s)||R.small.test(s)||R.big.test(s)))return K='compare',A(T.compare,{cards:lines().map(function(l){return l.ps[0].id;}),chips:[T.chips0[0]].concat(T.chipsSize.slice(0,2))});
 if(R.ship.test(s))return K='ship',A(T.ship,{chips:T.chipsShip});
 if(R.time.test(s))return K='time',A(T.time,{chips:[T.chips0[2]].concat(T.chipsShip.slice(1))});
 if(R.pay.test(s))return K='pay',A(T.pay,{chips:T.chipsShip.slice(0,1).concat(T.chips0.slice(2,3))});
 if(R.ret.test(s))return K='ret',A(T.ret,{chips:[T.chips0[0]]});
 if(R.buy.test(s))return K='buy',A(T.buy,{chips:T.chipsShip});
 if(R.fit.test(s))return K='fit',A(T.fit,{chips:T.chipsAfter.slice(0,2)});
 // product questions
 if(R.price.test(s)){var ps=pp.any?pp.ps:(curLine()?[prodById(ST.prod)]:ST.ser?KB.products.filter(function(p){return p.ser===ST.ser;}):null);
  if(ps&&ps.length){var seen={},out=[];ps.forEach(function(p){if(!seen[p.lk]){seen[p.lk]=1;out.push('• '+priceLine(p));}});ST.prod=ps[0].id;return K='price',A(out.length===1?out[0].slice(2):out.join('\n'),{cards:ps.slice(0,6).map(function(p){return p.id;}),chips:T.chipsSize});}
  return K='priceAll',A(T.priceAll+'\n'+lines().map(function(l){return '• '+l.line+(LANG==='zh'?'：':': ')+'NT$'+money(l.ps[0].p);}).join('\n'),{chips:T.chipsSize.slice(0,1).concat(T.chips0.slice(0,1))});}
 if(pp.col&&!R.reco.test(s)&&!R.price.test(s)){var cl=pp.ps.filter(function(p){return p.ck===pp.col;});if(cl.length){ST.prod=cl[0].id;return K='colorHit',A(T.colorHit,{cards:cl.map(function(p){return p.id;}),chips:T.chipsSize.slice(1).concat(T.chips0.slice(0,1))});}}
 if(R.colors.test(s)&&!pp.col){var ls=lines().filter(function(l){return (!pp.ser||l.ser===pp.ser)&&(pp.warm==null||l.warm===pp.warm)&&(!curLine()||pp.any||l.lk===curLine());});
  if(!ls.length)ls=lines();
  return K='colors',A((ls.length>1?T.colorsAll+'\n':'')+ls.map(function(l){return (ls.length>1?'• ':'')+fmt(T.colors,{line:l.line,list:l.ps.map(function(p){return p.c;}).join(LANG==='zh'||LANG==='ja'?'、':', ')});}).join('\n'),{cards:[].concat.apply([],ls.map(function(l){return l.ps.map(function(p){return p.id;});})).slice(0,8),chips:T.chipsSize.slice(1).concat(T.chips0.slice(0,1))});}
 if(R.care.test(s)&&!mentionsProduct){var hit=search(q).filter(function(h){return h.d.u===KB.links.care;})[0];if(hit)return docAnswer(hit.d,q);}
 if(R.reco.test(s)||mentionsProduct||R.rain.test(s)||R.warm.test(s)){
  if(!pp.any&&!ST.back){if(R.reco.test(s))return K='recoAsk',A(T.recoAsk,{chips:LANG==='zh'?['小型犬，下雨天穿','中大型犬，冬天保暖','先幫我挑尺寸']:T.chips0.slice(0,2)});}
  var list=pp.ps;if(!pp.ser&&ST.ser)list=list.filter(function(p){return p.ser===ST.ser;});if(!list.length)list=pp.ps;
  if(list.length&&list.length<KB.products.length){ST.prod=list[0].id;if(pp.ser)ST.ser=pp.ser;
   var intro=pp.warm===true?T.recoWarm:pp.warm===false?T.recoRain:pick(T.reco),extra=ST.back?'\n'+sizeAnswer(ST.back,ST.chest,'',{ser:list[0].ser,warm:pp.warm}).text.split('\n').slice(1,-1).join('\n'):'';
   return K='reco',A(intro+extra,{cards:list.slice(0,6).map(function(p){return p.id;}),chips:ST.back?T.chipsSize:[T.chips0[0]].concat(T.chipsSize.slice(1,2))});}
 }
 // free text: search the site
 var hits=search(q);if(hits.length&&hits[0].s>2.2&&hits[0].cov>=.25)return docAnswer(hits[0].d,expand(q));
 if(soonCat)return K='soon',A(fmt(T.soon,{cat:soonCat.n}),{chips:T.chipsAfter});
 return K='unknown',A(T.unknown,{chips:T.chips0.slice(0,4)});}
// ---------------------------------------------------------------- server (optional): semantic match + question log
var SRV=null,srvP=null,SID='',LLM=false;
try{SID=sessionStorage.getItem('apetto_ai_sid')||'';if(!SID){SID=Math.random().toString(36).slice(2,10)+Date.now().toString(36);sessionStorage.setItem('apetto_ai_sid',SID);}}catch(e){SID='x'+Math.random().toString(36).slice(2,10);}
function srvOn(){if(!API)return Promise.resolve(false);if(SRV!==null)return Promise.resolve(SRV);
 if(!srvP){var ctl=new AbortController(),tm=setTimeout(function(){ctl.abort();},10000);
  // the first connection through the tunnel can be slow; if it fails, try again 20 s later
  srvP=fetch(API+'/api/health',{cache:'no-store',signal:ctl.signal}).then(function(r){return r.json();}).then(function(j){SRV=!!(j&&j.helper);LLM=SRV&&!!j.llm;return SRV;}).catch(function(){SRV=false;setTimeout(function(){SRV=null;srvP=null;},20000);return false;}).then(function(v){clearTimeout(tm);if(v&&foot)foot.textContent=T.foot+' · '+T.logged+(LLM?' · '+T.ai:'');return v;});}
 return srvP;}
function srvMatch(q){return srvOn().then(function(on){if(!on||!KB.v)return null;var ctl=new AbortController(),tm=setTimeout(function(){ctl.abort();},3000);
 return fetch(API+'/api/helper/match',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({q:q.slice(0,300),lang:LANG,v:KB.v}),signal:ctl.signal})
  .then(function(r){return r.ok?r.json():null;}).catch(function(){return null;}).then(function(j){clearTimeout(tm);return j;});});}
function srvLog(q,a){if(!SRV)return;try{fetch(API+'/api/helper/log',{method:'POST',keepalive:true,headers:{'Content-Type':'application/json'},
 body:JSON.stringify({sid:SID,q:q.slice(0,300),lang:LANG,page:decodeURIComponent(location.pathname.slice(new URL(BASE||'./',location.href).pathname.length)),kind:a.kind||'',via:a.via||'rule',score:a.score||null,ans:a.text.slice(0,160),t:new Date().toISOString()})}).catch(function(){});}catch(e){}}
// use the server's match when the rules had nothing good, or when the server is very sure and the rules picked something else
function refine(q,a,mr){if(!mr||mr.v!==KB.v||!KB.sem)return a;var th=mr.th||{},weak=a.kind==='unknown'||a.kind==='doc';
 var ex=(mr.ex||[]).filter(function(e){return KB.sem.ex[e.i];}),top=ex[0];
 if(top){var key=KB.sem.ex[top.i][1],other=ex.filter(function(e){return KB.sem.ex[e.i][1]!==key;})[0],margin=other?top.s-other.s:1,canon=KB.sem.q[key];
  var tf=/^faq:/.test(key)?KB.faq.filter(function(f){return f.id===key.slice(4);})[0]:null;
  if(tf&&top.s>=(th.ex||.8)&&margin>=(th.margin||.02)&&(weak||top.s>=(th.strong||.9))&&a.kind!=='faq'&&!/^chat/.test(a.kind||'')){var t=A(faqText(tf),{chips:T.chipsAfter});t.kind=tf.chat?tf.id:tf.pending?'pending':'faq';t.via='sem';t.score=+top.s.toFixed(3);t.semKey=key;return t;}
  if(canon&&top.s>=(th.ex||.8)&&margin>=(th.margin||.02)&&(weak||top.s>=(th.strong||.9))){
   var keep=JSON.stringify(ST),b=answer(canon);b.kind=K;
   if(weak||b.kind!==a.kind){b.via='sem';b.score=+top.s.toFixed(3);b.semKey=key;return b;}
   Object.assign(ST,JSON.parse(keep));}}
 var dd=(mr.docs||[])[0];if(weak&&dd&&KB.docs[dd.i]&&dd.s>=(th.doc||.8)&&(a.kind==='unknown'||!a.doc||a.doc!==dd.i)){var c=docAnswer(KB.docs[dd.i],q);c.kind=K;c.via='sem';c.score=+dd.s.toFixed(3);return c;}
 return a;}
function docAnswer(d,q){K=d.faq?'faq':'doc';if(d.faq)return A(faqText(d.faq),{chips:T.chipsAfter});
 if(d.pid)ST.prod=d.pid;
 return A(fmt(pick(T.found),{t:d.t})+'\n'+snippet(d,q)+'\n['+T.more+']('+d.u+')',{cards:d.pid?[d.pid]:null,chips:T.chipsAfter});}
// ---------------------------------------------------------------- rendering (all text is escaped; links only to this site or known stores)
function esc(s){return String(s).replace(/[&<>"]/g,function(c){return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c];});}
function safeUrl(u){if(/^https:\/\/(www\.instagram\.com|www\.pinkoi\.com|www\.apetto\.com\.tw)\//.test(u))return u;if(/^[a-z0-9][\w\-\/.&=?#%]*$/i.test(u)&&!/^[a-z]+:/i.test(u))return BASE+u;return '';}
function md(t){var h=esc(t).replace(/\*\*(.+?)\*\*/g,'<strong>$1</strong>').replace(/\[([^\]]+)\]\(([^)\s]+)\)/g,function(m,a,u){var s=safeUrl(u.replace(/&amp;/g,'&'));return s?'<a href="'+esc(s)+'"'+(/^https?:/.test(s)?' target="_blank" rel="noopener"':'')+'>'+a+'</a>':a;});
 var out=[],ul=[];h.split('\n').forEach(function(l){if(/^• /.test(l))ul.push('<li>'+l.slice(2)+'</li>');else{if(ul.length){out.push('<ul>'+ul.join('')+'</ul>');ul=[];}if(l.trim())out.push('<p>'+l+'</p>');}});if(ul.length)out.push('<ul>'+ul.join('')+'</ul>');return out.join('');}
var root,log,chipsEl,ta,sendBtn,panel,fab,foot,busy=false,HIST=[];
var SKEY='apetto_ai_'+LANG;
function save(){try{sessionStorage.setItem(SKEY,JSON.stringify({h:HIST.slice(-40),st:ST}));}catch(e){}}
function restore(){try{var j=JSON.parse(sessionStorage.getItem(SKEY)||'null');if(j){HIST=j.h||[];Object.assign(ST,j.st||{});}}catch(e){}}
function scroll(){log.scrollTop=log.scrollHeight;}
function addMe(t){var d=document.createElement('div');d.className='ai-m me';d.textContent=t;log.appendChild(d);scroll();}
function addCards(ids){if(!ids||!ids.length)return;var w=document.createElement('div');w.className='ai-cards';
 ids.forEach(function(id){var p=prodById(id);if(!p)return;var a=document.createElement('a');a.className='ai-card';a.href=BASE+p.u;
  a.innerHTML=(p.img?'<img src="'+esc(BASE+p.img)+'" alt="" loading="lazy">':'')+'<div><b>'+esc(p.n)+'</b><span>NT$'+money(p.p)+'</span></div>';w.appendChild(a);});
 log.appendChild(w);}
function setChips(list){chipsEl.innerHTML='';(list||[]).slice(0,4).forEach(function(c){var b=document.createElement('button');b.type='button';b.textContent=c;b.onclick=function(){ask(c);};chipsEl.appendChild(b);});}
function addBot(a,instant,done){var d=document.createElement('div');d.className='ai-m bot';log.appendChild(d);var full=md(a.text);
 if(instant||matchMedia('(prefers-reduced-motion: reduce)').matches){d.innerHTML=full;addCards(a.cards);scroll();done&&done();return;}
 // type it out: reveal the plain text progressively, then swap in the formatted version
 var plain=a.text.replace(/\*\*/g,'').replace(/\[([^\]]+)\]\([^)]+\)/g,'$1'),i=0,step=Math.max(2,Math.round(plain.length/60));
 (function tick(){i+=step;if(i>=plain.length){d.innerHTML=full;addCards(a.cards);scroll();done&&done();return;}d.textContent=plain.slice(0,i);scroll();setTimeout(tick,16);})();}
function typing(){var t=document.createElement('div');t.className='ai-typing';t.innerHTML='<i></i><i></i><i></i>';log.appendChild(t);scroll();return function(){t.remove();};}
function ask(q){q=String(q||'').trim();if(!q||busy)return;busy=true;sendBtn.disabled=true;ta.value='';grow();setChips([]);addMe(q);HIST.push({me:q});
 loadKB().then(function(){var a;try{a=answer(q);a.kind=K;}catch(e){a=A(T.unknown,{chips:T.chips0});a.kind='error';}a.via='rule';
  var stop=typing(),wait=Math.min(1400,450+a.text.length*6+Math.random()*250);
  Promise.all([Promise.race([srvMatch(q).catch(function(){return null;}),new Promise(function(r){setTimeout(function(){r(null);},3500);})]),new Promise(function(r){setTimeout(r,wait);})]).then(function(res){
   var b=a;try{b=refine(q,a,res[0]);}catch(e){b=a;}
   var fin=function(x){HIST.push({bot:x});save();setChips(x.chips);srvLog(q,x);busy=false;sendBtn.disabled=!ta.value.trim();ta.focus({preventScroll:true});};
   if(useAI(b))aiAnswer(q,b,stop,fin);else{stop();addBot(b,false,function(){fin(b);});}});
 }).catch(function(){busy=false;sendBtn.disabled=false;});}
// the small AI model on the server takes what the rules could not answer, plus small talk, and streams its reply;
// if it is slow to start or anything fails, the rule answer is shown instead
function useAI(b){return LLM&&(b.kind==='unknown'||b.kind==='doc'||b.kind==='error'||/^chat/.test(b.kind||''));}
function aiHist(){var o=[];HIST.slice(0,-1).slice(-4).forEach(function(h){if(h.me)o.push({r:'u',t:String(h.me).slice(0,300)});else if(h.bot)o.push({r:'a',t:String(h.bot.text||'').slice(0,400)});});return o;}
function aiAnswer(q,fb,stop,fin){var ctl=new AbortController(),d=null,txt='',tm=setTimeout(function(){ctl.abort();},15000),cap=setTimeout(function(){ctl.abort();},60000);
 var end=function(){clearTimeout(tm);clearTimeout(cap);
  if(!d){stop();addBot(fb,false,function(){fin(fb);});return;}
  var t=txt.trim(),a={text:t,chips:T.chipsAfter,kind:'ai',via:'ai'};d.innerHTML=md(t);scroll();fin(a);};
 fetch(API+'/api/helper/chat',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({q:q.slice(0,300),lang:LANG,hist:aiHist()}),signal:ctl.signal})
 .then(function(r){if(!r.ok||!r.body)throw new Error('ai');var rd=r.body.getReader(),dec=new TextDecoder();
  return (function pump(){return rd.read().then(function(x){if(x.done)return;txt+=dec.decode(x.value,{stream:true});
   if(!d&&txt.trim()){clearTimeout(tm);stop();d=document.createElement('div');d.className='ai-m bot';log.appendChild(d);}
   if(d){d.textContent=txt.replace(/\*\*/g,'');scroll();}return pump();});})();})
 .then(end,end);}
function grow(){ta.style.height='auto';var h=ta.scrollHeight+2;ta.style.height=Math.min(110,h)+'px';ta.style.overflowY=h>110?'auto':'hidden';}
function openPanel(){if(!root)build();var tip=document.querySelector('.ai-tip');if(tip)tip.remove();panel.hidden=false;fab.style.display='none';fab.setAttribute('aria-expanded','true');
 try{sessionStorage.setItem('apetto_ai_tip','1');}catch(e){}
 loadKB();srvOn();if(matchMedia('(max-width:980px)').matches)document.documentElement.style.overflow='hidden';setTimeout(function(){ta.focus({preventScroll:true});},60);scroll();}
function closePanel(){panel.hidden=true;fab.style.display='';fab.setAttribute('aria-expanded','false');document.documentElement.style.overflow='';fab.focus({preventScroll:true});}
function reset(){HIST=[];for(var k in ST)ST[k]=null;save();log.innerHTML='';addBot(A(pick(T.hello)),true);setChips(T.chips0);}
function build(){root=document.createElement('div');
 root.innerHTML='<div class="ai-panel" role="dialog" aria-label="'+esc(T.name)+'" hidden><div class="ai-hd"><div class="ai-av">'+(LOGO?'<img src="'+esc(LOGO)+'" alt="">':'')+'</div><div><b>'+esc(T.name)+'</b><span><i></i>'+esc(T.status)+'</span></div>'
  +'<button type="button" class="ai-rs" title="'+esc(T.reset)+'" aria-label="'+esc(T.reset)+'"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M3 12a9 9 0 1 0 3-6.7L3 8"/><path d="M3 3v5h5"/></svg></button>'
  +'<button type="button" class="ai-x" aria-label="'+esc(T.close)+'"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M6 6l12 12M18 6 6 18"/></svg></button></div>'
  +'<div class="ai-log" aria-live="polite"></div><div class="ai-chips"></div>'
  +'<form class="ai-in"><textarea rows="1" placeholder="'+esc(T.ph)+'" aria-label="'+esc(T.ph)+'"></textarea><button type="submit" aria-label="'+esc(T.send)+'" disabled><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M5 12h14M13 6l6 6-6 6"/></svg></button></form>'
  +'<div class="ai-foot">'+esc(T.foot)+'</div></div>';
 document.body.appendChild(root);panel=root.querySelector('.ai-panel');foot=root.querySelector('.ai-foot');log=root.querySelector('.ai-log');chipsEl=root.querySelector('.ai-chips');ta=root.querySelector('textarea');sendBtn=root.querySelector('.ai-in button');
 root.querySelector('.ai-x').onclick=closePanel;root.querySelector('.ai-rs').onclick=reset;
 root.querySelector('form').onsubmit=function(e){e.preventDefault();ask(ta.value);};
 ta.addEventListener('input',function(){grow();sendBtn.disabled=busy||!ta.value.trim();});
 ta.addEventListener('keydown',function(e){if(e.key==='Enter'&&!e.shiftKey&&!e.isComposing){e.preventDefault();ask(ta.value);}});
 document.addEventListener('keydown',function(e){if(e.key==='Escape'&&!panel.hidden)closePanel();});
 restore();
 if(!HIST.length){addBot(A(pick(T.hello)),true);setChips(T.chips0);}
 else loadKB().then(function(){HIST.forEach(function(h){if(h.me)addMe(h.me);else addBot(h.bot,true);});var last=HIST[HIST.length-1];setChips(last&&last.bot?last.bot.chips:T.chips0);scroll();});}
function init(){fab=document.createElement('button');fab.type='button';fab.className='ai-fab';fab.setAttribute('aria-label',T.open);fab.setAttribute('aria-expanded','false');
 fab.innerHTML='<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M21 12a8 8 0 0 1-11.6 7.1L4 20l1-4.6A8 8 0 1 1 21 12z"/><path d="M8.5 12h.01M12 12h.01M15.5 12h.01" stroke-width="2.6"/></svg>';
 fab.onclick=openPanel;document.body.appendChild(fab);
 // product pages: offer size help once per visit
 var seen=false;try{seen=!!sessionStorage.getItem('apetto_ai_tip');}catch(e){}
 if(!seen&&document.querySelector('.product-heading-title')){setTimeout(function(){if(root&&!panel.hidden)return;var t=document.createElement('div');t.className='ai-tip';t.setAttribute('role','status');
   t.innerHTML=esc(T.tip)+'<button type="button" aria-label="'+esc(T.close)+'">✕</button>';t.onclick=function(e){if(e.target.tagName==='BUTTON'){t.remove();try{sessionStorage.setItem('apetto_ai_tip','1');}catch(x){}return;}openPanel();setTimeout(function(){ask(T.chips0[0]);},250);};
   document.body.appendChild(t);try{sessionStorage.setItem('apetto_ai_tip','1');}catch(x){}},9000);}
 if(/[?&#]ask/.test(location.search+location.hash))openPanel();}
if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',init);else init();
})();
"""
