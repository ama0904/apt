# -*- coding: utf-8 -*-
"""
apetto storefront theme: renders every public page from _data/products.json + the info templates.

Used by site_builder.build_all(). Nothing here depends on the original OpenCart markup; the legacy
helpers in site_builder (i18n table, text-in-image overlays, optimized images, static search) are reused.
"""
import copy
import hashlib
import html as html_mod
import json
import posixpath
import re

from bs4 import BeautifulSoup, Comment, NavigableString

import site_builder as sb
import fitstudio as fit
import assistant as ai
import member as mem

CDN = "_ext/image-cdn-flare.qdm.cloud/q60f738cbd6a9c/image/data/"
LOGO = "assets/logo.png"  # transparent version of the shop logo (made from the original PNG; works on dark backgrounds too)
IMG = {
    "hero": CDN + "2026/08/26/b2963b09f6f2a473a8f3367f8d8ac9e2.clean.jpg",      # two dogs in the forest (text area repaired)
    "story": CDN + "2026/08/26/cf1d3a5ae88219b7f6c3868005c2ff8d.clean.jpg",     # labrador, neon raincoat, picnic (shown zoomed: top-left had text)
    "rain": CDN + "2022/01/20/84765377d689a07961bcf145562ffd35.jpg",             # shiba splashing
    "cat1": CDN + "2026/08/26/2e2d960fcdd9a821b141df7d41b8f5c7.clean.jpg",      # frenchie, blue cape
    "cat2": CDN + "2022/02/05/e413d6bbc217658bf1a529f3b51c0a28.clean.jpg",      # black dog, neon (white frame of the original PNG trimmed)
    "cat3": CDN + "2022/02/05/314005a881b4008f09fb07335e50ed44.jpg",            # lime fleece lining
    "f_water": CDN + "2022/02/05/bd9fc68d2a8955f173b21fcc8aae271a.jpg",
    "f_leash": CDN + "1f9e72ac7a5d7e832966283819693d54.jpg",
    "f_snap": CDN + "2022/02/05/c787b7d57fbf0fa0941b63be70fac92f.PNG",
    "f_name": CDN + "2022/02/05/f1d2de57fe93927106c6a19350ea87b8.PNG",
}
# product groups (商品分類 in the strategy deck): each category in products.json carries a "group" key
GROUP_IMG = {"apparel": "cat1", "outdoor": "cat2", "living": "cat3"}
DEFAULT_GROUPS = [{"key": "apparel", "name": "機能服飾", "blurb": "雨衣、保暖外套與浴袍，應對每一種天氣"},
                  {"key": "outdoor", "name": "外出配件", "blurb": "牽繩與頸圈、領巾、寵物鞋，出門的好夥伴"},
                  {"key": "living", "name": "舒適生活", "blurb": "舒適墊，回家後的放鬆時光"}]
SHOP, GUIDES, FEATURES, ABOUT = "shop.html", "guides.html", "features.html", "pages/4.html"


SITE_FILE = sb.DATA_DIR / "site.json"


def load_site():
    """Admin-editable page copy: home hero + the features page (falls back to the built-in text)."""
    site = json.loads(SITE_FILE.read_text(encoding="utf-8")) if SITE_FILE.exists() else {}
    hero = site.get("hero") or {}
    hero.setdefault("title", "為每一段毛孩生活，做好準備。")
    hero.setdefault("lead", "從天候防護到日常外出，探索 apetto 為毛孩打造的機能與舒適設計。")
    feats = site.get("features") or {}
    feats.setdefault("intro", "每一個細節，都為了雨天也能自在奔跑。")
    feats["items"] = [f for f in feats.get("items", []) if f.get("visible", True) and f.get("image")]
    return {"hero": hero, "features": feats, "palette": str(site.get("palette") or "0"), "palette_colors": site.get("palette_colors") or {}}


def groups_of(data):
    return data.get("groups") or DEFAULT_GROUPS


def cats_in(data, gkey):
    return [c for c in data["categories"] if c.get("group") == gkey]


def cat_count(c, visible):
    return len([p for p in visible if c["id"] in p.get("categories", [])])


def types_of(c):
    return [t for t in (c.get("types") or []) if t.get("key") and t.get("name")]


def type_items(visible, c, t):
    return [p for p in visible if c["id"] in p.get("categories", []) and t["key"] in (p.get("types") or [])]


def untyped_items(visible, c):
    keys = {t["key"] for t in types_of(c)}
    return [p for p in visible if c["id"] in p.get("categories", []) and not keys.intersection(p.get("types") or [])]


VERSION = "v1.0.2"
BRAND = "apetto 寵物機能衣"
HOME_TITLE = "apetto | 高機能寵物時裝：專業防水防風、專為毛孩設計的機能衣服"
HOME_DESC = ("apetto 專業製衣團隊專注研發高機能寵物時裝。嚴選防水與防風布料，結合俐落的結構剪裁與極致實用性。"
             "不僅讓毛孩輕鬆應對多變天氣，更大幅減輕飼主日常清潔的負擔。立即探索最新機能服飾，體驗毫不費力的純粹質感。")
PUBLIC = "https://ama0904.github.io/apt/"
INSTAGRAM = "https://www.instagram.com/apetto_fun/"
PINKOI = "https://www.pinkoi.com/store/apetto"
FONTS = ("https://fonts.googleapis.com/css2?family=Manrope:wght@500;600;700;800"
         "&family=Noto+Sans+TC:wght@400;500;700&family=Noto+Sans+JP:wght@400;500;700&display=swap")

# UI strings of the theme (the content strings live in _data/i18n.json)
UI = {
    "漢堡店中店": {"en": "Store in Hamburg", "ja": "ハンブルク店", "de": "Shop-in-Shop Hamburg"},
    "漢堡店": {"en": "Hamburg store", "ja": "ハンブルク店", "de": "Laden Hamburg"},
    "apetto 在德國": {"en": "apetto in Germany", "ja": "ドイツの apetto", "de": "apetto in Deutschland"},
    "apetto 的機能狗衣，現在可以在漢堡親手摸到、現場試穿。店中店位於 Eimsbüttel 的「陳美英中文書屋 × bis Buchladen」。": {
        "en": "apetto's functional dog wear can now be seen, touched and tried on in Hamburg: at the shop-in-shop inside 陳美英中文書屋 × bis Buchladen in Eimsbüttel.",
        "ja": "apetto の機能ドッグウェアを、ハンブルクで実際に手に取って試着できます。Eimsbüttel の「陳美英中文書屋 × bis Buchladen」内のショップインショップです。",
        "de": "apettos funktionale Hundebekleidung gibt es jetzt auch zum Anfassen und Anprobieren in Hamburg: im Shop-in-Shop bei „陳美英中文書屋 × bis Buchladen“ in Eimsbüttel."},
    "地址": {"en": "Address", "ja": "住所", "de": "Adresse"},
    "店中店位於書店內": {"en": "Shop-in-shop inside the bookshop", "ja": "書店内のショップインショップ", "de": "Shop-in-Shop in der Buchhandlung"},
    "在 Google 地圖開啟": {"en": "Open in Google Maps", "ja": "Google マップで開く", "de": "In Google Maps öffnen"},
    "規劃路線": {"en": "Directions", "ja": "経路を調べる", "de": "Route planen"},
    "Facebook 專頁": {"en": "Facebook page", "ja": "Facebook ページ", "de": "Facebook-Seite"},
    "載入地圖": {"en": "Load map", "ja": "地図を読み込む", "de": "Karte laden"},
    "地圖由 Google 提供，點擊後才會載入。": {"en": "The map is provided by Google and loads only when you tap.", "ja": "地図は Google 提供で、タップ後に読み込まれます。", "de": "Die Karte kommt von Google und wird erst nach dem Klick geladen."},
    "在店裡可以做什麼": {"en": "What you can do there", "ja": "お店でできること", "de": "Das erwartet euch vor Ort"},
    "親手感受布料與做工": {"en": "Feel the fabric and the finish", "ja": "生地と仕上がりを手に取って", "de": "Stoff und Verarbeitung anfassen"},
    "耐水壓 10000mmH2O 的防水布料、3M 反光條、領口可上牽繩的設計，現場看最清楚。": {
        "en": "Waterproof fabric rated 10,000 mm, 3M reflective strips and the leash opening at the collar: best seen in person.",
        "ja": "耐水圧 10,000mm の防水生地、3M 反射テープ、襟元のリード穴。実物で見るのがいちばんです。",
        "de": "Wasserdichtes Gewebe mit 10.000 mm Wassersäule, 3M-Reflexstreifen und die Leinenöffnung am Kragen: vor Ort sieht man es am besten."},
    "讓毛孩現場試穿": {"en": "Try it on your dog", "ja": "愛犬に試着", "de": "Direkt am Hund anprobieren"},
    "帶毛孩一起來，直接試穿找到合身的尺寸，不用猜。": {"en": "Bring your dog along, try it on and find the right size without guessing.", "ja": "愛犬と一緒に来て、その場で試着してぴったりのサイズを。", "de": "Bringt euren Hund mit: anprobieren, passende Größe finden, kein Raten."},
    "現場購買，馬上帶走": {"en": "Buy on the spot", "ja": "その場で購入", "de": "Vor Ort kaufen und mitnehmen"},
    "不用等從台灣寄送，喜歡就直接帶回家。": {"en": "No waiting for shipping from Taiwan: if you like it, take it home right away.", "ja": "台湾からの配送を待たずに、気に入ったらそのまま持ち帰れます。", "de": "Kein Warten auf den Versand aus Taiwan: gefällt es, nehmt ihr es gleich mit."},
    "出門前先量一下": {"en": "Measure before you come", "ja": "来店前にサイズを測ろう", "de": "Vorher kurz messen"},
    "量毛孩的背長（脖子根部到尾巴根）、領圍和腹圍，到店裡就能很快找到尺寸。想先看看穿起來的樣子，也可以用線上試衣間。": {
        "en": "Measure the back length (base of the neck to the base of the tail), neck and girth, and the right size is found quickly in the shop. Curious how it looks? Try the online fitting room first.",
        "ja": "背丈（首の付け根から尻尾の付け根）、首回り、胴回りを測っておくと、お店で素早くサイズが決まります。先に着た様子を見たいなら、オンライン試着室もどうぞ。",
        "de": "Messt Rückenlänge (Halsansatz bis Rutenansatz), Halsumfang und Bauchumfang, dann geht es im Laden schnell. Wer vorher sehen will, wie es aussieht, probiert die Online-Anprobe."},
    "尺寸怎麼量": {"en": "How to measure", "ja": "サイズの測り方", "de": "So wird gemessen"},
    "線上試衣間": {"en": "Online fitting room", "ja": "オンライン試着室", "de": "Online-Anprobe"},
    "營業時間與庫存可能變動，出發前建議先透過 Facebook 聯絡店家。": {"en": "Opening hours and stock may change; check with the shop via Facebook before you go.", "ja": "営業時間と在庫は変わることがあります。来店前に Facebook でお店にご確認ください。", "de": "Öffnungszeiten und Bestand können sich ändern; fragt am besten vorher über Facebook beim Laden nach."},
    "帶毛孩一起來，可以現場試穿、直接購買。營業時間請先透過 Facebook 向店家確認。": {"en": "Bring your dog: try it on and buy on the spot. Please check the opening hours with the shop on Facebook first.", "ja": "愛犬と一緒にどうぞ。その場で試着・購入できます。営業時間は Facebook でお店に事前にご確認ください。", "de": "Bringt euren Hund mit: vor Ort anprobieren und direkt kaufen. Die Öffnungszeiten bitte vorher über Facebook beim Laden erfragen."},
    "漢堡 · 德國": {"en": "Hamburg · Germany", "ja": "ハンブルク・ドイツ", "de": "Hamburg · Deutschland"},
    "漢堡店中店 | apetto": {"en": "Store in Hamburg | apetto", "ja": "ハンブルク店 | apetto", "de": "Shop-in-Shop Hamburg | apetto"},
    "apetto 在漢堡的店中店：Weidenallee 4, 20357 Hamburg。親手感受機能狗衣，帶毛孩現場試穿、直接購買。": {
        "en": "apetto's shop-in-shop in Hamburg: Weidenallee 4, 20357 Hamburg. See the functional dog wear, try it on your dog and buy on the spot.",
        "ja": "apetto のハンブルク店：Weidenallee 4, 20357 Hamburg。機能ドッグウェアを手に取り、愛犬に試着してその場で購入。",
        "de": "apettos Shop-in-Shop in Hamburg: Weidenallee 4, 20357 Hamburg. Funktionale Hundebekleidung anfassen, am Hund anprobieren und direkt mitnehmen."},
    "瀏覽全系列": {"en": "Shop the collection", "ja": "全ラインナップを見る", "de": "Zur Kollektion"},
    # navigation (Website Strategy deck)
    "商品分類": {"en": "Shop All", "ja": "ショップ", "de": "Shop"},
    "商品指南": {"en": "Guides", "ja": "ガイド", "de": "Ratgeber"},
    "機能與設計細節": {"en": "Features & Design Details", "ja": "機能とデザインのディテール", "de": "Funktionen & Details"},
    "品牌故事": {"en": "About Us", "ja": "ブランドストーリー", "de": "Unsere Geschichte"},
    "依用途挑選": {"en": "Pick by what you need", "ja": "用途で選ぶ", "de": "Nach Einsatz wählen"},
    "瀏覽分類": {"en": "Browse", "ja": "カテゴリーを見る", "de": "Kategorie ansehen"},
    "即將推出": {"en": "Coming soon", "ja": "近日発売", "de": "Demnächst"},
    "這個分類的商品即將推出，先看看其他系列。": {
        "en": "Products in this category are coming soon. Have a look at the other series meanwhile.",
        "ja": "このカテゴリーの商品は近日公開予定です。ほかのシリーズをご覧ください。",
        "de": "Produkte in dieser Kategorie kommen bald. Schauen Sie sich inzwischen die anderen Serien an."},
    "挑選、測量與保養的小知識": {"en": "Tips on choosing, measuring and caring", "ja": "選び方・測り方・お手入れのコツ", "de": "Tipps zu Auswahl, Maßnehmen und Pflege"},
    "閱讀指南": {"en": "Read the guide", "ja": "ガイドを読む", "de": "Ratgeber lesen"},
    "更多指南": {"en": "More guides", "ja": "ほかのガイド", "de": "Weitere Ratgeber"},
    "看完整細節": {"en": "See all the details", "ja": "詳しく見る", "de": "Alle Details"},
    "每一個細節，都為了雨天也能自在奔跑。": {"en": "Every detail is there so your dog can run free, even in the rain.",
                                     "ja": "雨の日でも自由に走れるように、細部まで。", "de": "Jedes Detail, damit Ihr Hund auch im Regen frei laufen kann."},
    "看雨衣": {"en": "Shop raincoats", "ja": "レインコートを見る", "de": "Regenmäntel ansehen"},
    "看保暖外套": {"en": "Shop warm jackets", "ja": "防寒ジャケットを見る", "de": "Wärmejacken ansehen"},
    "指南": {"en": "Guide", "ja": "ガイド", "de": "Ratgeber"},
    "雨衣、保暖外套與浴袍，應對每一種天氣": {"en": "Raincoats, warm jackets and bathrobes for every kind of weather", "ja": "レインコート、防寒ジャケット、バスローブ。どんな天気にも", "de": "Regenmäntel, Wärmejacken und Bademäntel für jedes Wetter"},
    "牽繩與頸圈、領巾、寵物鞋，出門的好夥伴": {"en": "Leashes, collars, bandanas and shoes: good company on every outing", "ja": "リード＆首輪、バンダナ、ドッグシューズ。お出かけの相棒", "de": "Leinen, Halsbänder, Halstücher und Schuhe: Begleiter für jeden Ausflug"},
    "舒適墊，回家後的放鬆時光": {"en": "Comfort mats for the downtime after the walk", "ja": "快適マットで、帰ってからのくつろぎ時間を", "de": "Komfortmatten für die Ruhe nach dem Spaziergang"},
    "防水防風，耐水壓 10000mmH2O，雨天散步不受限": {"en": "Waterproof and windproof, rated to 10,000 mmH2O. Rainy walks, no limits.", "ja": "防水・防風、耐水圧 10,000mmH2O。雨の日の散歩も自由に", "de": "Wasser- und winddicht, Wassersäule 10.000 mm. Regenspaziergänge ohne Grenzen."},
    "MIT 抗靜電刷毛內裡，濕冷寒流也暖呼呼": {"en": "Anti-static fleece lining made in Taiwan keeps the cold out", "ja": "台湾製の帯電防止フリース裏地で、湿った寒さもぽかぽか", "de": "Antistatisches Fleece-Futter aus Taiwan hält die nasskalte Luft draußen"},
    "洗澡、玩水後快速吸水，不再滿屋子甩水": {"en": "Soaks up water fast after a bath or a swim, so the house stays dry", "ja": "お風呂や水遊びのあとにさっと吸水。家じゅう水しぶきにならない", "de": "Saugt nach Bad oder Schwimmen schnell auf, damit die Wohnung trocken bleibt"},
    "每天出門都要用的，要好看也要耐用": {"en": "Used every single day, so it has to look good and last", "ja": "毎日使うものだから、見た目も丈夫さも", "de": "Jeden Tag im Einsatz, also schön und langlebig"},
    "一條領巾，造型立刻不一樣": {"en": "One bandana and the whole look changes", "ja": "バンダナ1枚で、印象ががらりと変わる", "de": "Ein Halstuch, und der ganze Look ist anders"},
    "燙地、雨天、碎石路，保護肉墊": {"en": "Hot pavement, rain, gravel: protection for the paw pads", "ja": "熱い地面、雨、砂利道から肉球を守る", "de": "Heißer Asphalt, Regen, Schotter: Schutz für die Ballen"},
    "回家後，給毛孩一個放鬆的角落": {"en": "A cosy corner to unwind in after the walk", "ja": "帰ってきたら、くつろげる場所を", "de": "Nach dem Spaziergang eine Ecke zum Entspannen"},
    "其他": {"en": "Other", "ja": "その他", "de": "Weitere"},
    "依用途挑選 apetto 的機能服飾、外出配件與舒適生活用品。": {
        "en": "Browse apetto's functional apparel, outdoor accessories and comfort items by what you need.",
        "ja": "apetto の機能ウェア、お出かけアクセサリー、おうちで快適アイテムを用途から探せます。",
        "de": "apettos Funktionsbekleidung, Zubehör für draußen und Wohlfühlartikel nach Einsatz durchstöbern."},
    "為每一段毛孩生活，做好準備。": {"en": "Ready for Every Moment in Your Pet’s Life.",
                             "ja": "愛犬との毎日の、どんな瞬間にも備えて。", "de": "Bereit für jeden Moment im Leben Ihres Hundes."},
    "從天候防護到日常外出，探索 apetto 為毛孩打造的機能與舒適設計。": {
        "en": "From weather protection to everyday adventures, discover apetto’s thoughtful designs that bring together function, comfort, and style for your furry companions.",
        "ja": "天候からの保護から日常のお出かけまで。apetto が愛犬のために考えた、機能と快適さを備えたデザインをご覧ください。",
        "de": "Vom Wetterschutz bis zum Alltagsabenteuer: Entdecken Sie apettos durchdachte Designs, die Funktion, Komfort und Stil für Ihren Vierbeiner vereinen."},
    "探索系列": {"en": "Explore", "ja": "シリーズを見る", "de": "Entdecken"},
    "為什麼選擇 apetto": {"en": "Why apetto", "ja": "apetto が選ばれる理由", "de": "Warum apetto"},
    "機能細節": {"en": "Built for the weather", "ja": "機能のディテール", "de": "Funktion im Detail"},
    "耐水壓 10000mmH2O": {"en": "10,000 mmH2O waterproof", "ja": "耐水圧 10,000mmH2O", "de": "Wassersäule 10.000 mm"},
    "頂級防水防風布料，水滴輕易滑落，台灣多雨濕冷也不怕。": {
        "en": "Premium waterproof, windproof fabric. Drops roll right off, even in rainy, damp weather.",
        "ja": "高品質な防水・防風生地。水滴は転がり落ち、雨の多い湿った寒さでも安心です。",
        "de": "Hochwertiger wasser- und winddichter Stoff. Tropfen perlen einfach ab, auch bei nasskaltem Wetter."},
    "3M 反光條": {"en": "3M reflective strips", "ja": "3M 反射テープ", "de": "3M-Reflexstreifen"},
    "穿著也能上牽繩": {"en": "Leash-ready collar", "ja": "着たままリード装着", "de": "Leine trotz Jacke"},
    "領圍開口設計，穿上 apetto 仍然可以扣上牽繩。": {
        "en": "A collar opening lets the leash clip on with the coat on.",
        "ja": "襟元の開口部で、着たままリードをつけられます。",
        "de": "Die Kragenöffnung lässt die Leine auch mit Jacke einhaken."},
    "快速穿脫": {"en": "Quick on and off", "ja": "着脱かんたん", "de": "Schnell an und aus"},
    "前扣式鈕扣與腹部插扣，扣上就能出門。": {
        "en": "Front snaps and a belly buckle: fasten and go.",
        "ja": "前ボタンと腹部バックル。留めるだけでお出かけできます。",
        "de": "Druckknöpfe vorn und Bauchschnalle: schließen und losgehen."},
    "專屬名牌，寫上毛孩的名字，衣服就是他的。": {
        "en": "A name tag makes the coat truly theirs.",
        "ja": "名前を書けば、その子だけの一着になります。",
        "de": "Ein Namensschild macht die Jacke ganz zu ihrer."},
    "三大系列": {"en": "Three series", "ja": "3つのシリーズ", "de": "Drei Serien"},
    "依毛孩體型與季節挑選": {"en": "Pick by your dog's size and the season", "ja": "体格と季節で選ぶ", "de": "Nach Größe und Jahreszeit wählen"},
    "查看全部": {"en": "View all", "ja": "すべて見る", "de": "Alle ansehen"},
    "立即購買": {"en": "Buy now", "ja": "今すぐ購入", "de": "Jetzt kaufen"},
    "將前往官方賣場完成結帳": {"en": "You will check out at our official store", "ja": "公式ストアでお支払いに進みます", "de": "Der Kauf wird im offiziellen Store abgeschlossen"},
    "本站為商品介紹，購買請至台灣官方商店。": {
        "en": "This site is a product showcase. Purchases are made through our official store in Taiwan.",
        "ja": "このサイトは商品紹介ページです。ご購入は台湾の公式ストアをご利用ください。",
        "de": "Diese Seite stellt die Produkte vor. Gekauft wird im offiziellen Store in Taiwan."},
    "前往官方商店": {"en": "Go to the official store", "ja": "公式ストアへ", "de": "Zum offiziellen Store"},
    "相關商品": {"en": "You may also like", "ja": "関連商品", "de": "Das könnte Ihnen auch gefallen"},
    "搜尋商品": {"en": "Search products", "ja": "商品を検索", "de": "Produkte suchen"},
    "搜尋結果": {"en": "Search results", "ja": "検索結果", "de": "Suchergebnisse"},
    "共 {n} 件商品": {"en": "{n} products", "ja": "全 {n} 点", "de": "{n} Produkte"},
    "聯絡我們": {"en": "Contact", "ja": "お問い合わせ", "de": "Kontakt"},
    "商品": {"en": "Products", "ja": "商品", "de": "Produkte"},
    "在 Facebook 查看貼文": {"en": "View the post on Facebook", "ja": "Facebook で投稿を見る", "de": "Beitrag auf Facebook ansehen"},
    "關閉": {"en": "Close", "ja": "閉じる", "de": "Schließen"},
    "語言": {"en": "Language", "ja": "言語", "de": "Sprache"},
    "阻擋風雨，擁抱無憂的舒適時光": {"en": "Keep out wind and rain. Embrace carefree comfort.",
                                "ja": "風雨をさえぎり、心地よい時間を。", "de": "Wind und Regen draußen, unbeschwerter Komfort drinnen."},
    "專為毛孩設計的高機能雨衣與保暖夾克。防水、防風、穿脫快速，陪你走過每一個下雨的日子。": {
        "en": "High-performance raincoats and warm jackets designed for dogs. Waterproof, windproof and quick to put on, with you on every rainy day.",
        "ja": "愛犬のために設計した高機能レインコートと防寒ジャケット。防水・防風・着脱かんたん。雨の日もいっしょに。",
        "de": "Hochfunktionale Regenmäntel und Wärmejacken für Hunde. Wasserdicht, winddicht, schnell angezogen, an jedem Regentag dabei."},
    "台灣設計製造": {"en": "Designed and made in Taiwan", "ja": "台湾でデザイン・製造", "de": "Entworfen und gefertigt in Taiwan"},
    "台灣製造": {"en": "Made in Taiwan", "ja": "台湾製", "de": "Made in Taiwan"},
    "全館免運": {"en": "Free shipping", "ja": "送料無料", "de": "Versandkostenfrei"},
    "尺寸請參考商品介紹中的尺寸表。": {"en": "See the size chart in the description.", "ja": "サイズは商品説明のサイズ表をご覧ください。", "de": "Größentabelle siehe Beschreibung."},
    "目前沒有商品": {"en": "No products yet", "ja": "商品はまだありません", "de": "Noch keine Produkte"},
    "找不到頁面": {"en": "Page not found", "ja": "ページが見つかりません", "de": "Seite nicht gefunden"},
    "回到首頁": {"en": "Back to home", "ja": "ホームへ戻る", "de": "Zur Startseite"},
    "這個頁面不存在或已被移除。": {"en": "This page does not exist or has been removed.", "ja": "このページは存在しないか、削除されました。", "de": "Diese Seite existiert nicht oder wurde entfernt."},
    "回到商品列表": {"en": "Back to products", "ja": "商品一覧へ戻る", "de": "Zurück zu den Produkten"},
    "分享": {"en": "Share", "ja": "シェア", "de": "Teilen"},
    "主選單": {"en": "Main menu", "ja": "メインメニュー", "de": "Hauptmenü"},
    "查看連結": {"en": "Open link", "ja": "リンクを見る", "de": "Link öffnen"},
    "目前沒有消息": {"en": "No news yet", "ja": "お知らせはまだありません", "de": "Noch keine Neuigkeiten"},
    "訂購步驟": {"en": "How to order", "ja": "ご注文の流れ", "de": "So bestellen Sie"},
    "選購商品": {"en": "Pick your products", "ja": "商品を選ぶ", "de": "Produkte auswählen"},
    "填寫資料與送貨方式": {"en": "Enter your details and delivery method", "ja": "お届け先と配送方法を入力", "de": "Daten und Versandart eingeben"},
    "選擇付款方式結帳": {"en": "Choose payment and check out", "ja": "支払い方法を選んで注文", "de": "Zahlungsart wählen und bestellen"},
    "email 出貨通知": {"en": "Shipping notice by email", "ja": "発送メールが届く", "de": "Versandbestätigung per E-Mail"},
    "收到商品": {"en": "Receive your order", "ja": "商品を受け取る", "de": "Bestellung erhalten"},
    "ATM 轉帳": {"en": "ATM bank transfer", "ja": "ATM 振込", "de": "ATM-Überweisung"},
    "請於 3 日內付款，付款後請使用「填寫匯款單」通知我們。": {"en": "Please pay within 3 days, then let us know with the “Payment Notice” form.", "ja": "3日以内にお振込みのうえ、「振込通知」フォームでお知らせください。", "de": "Bitte innerhalb von 3 Tagen zahlen und uns danach über das Formular „Zahlungsmitteilung“ informieren."},
    "到店取貨時付款。": {"en": "Pay when you collect the parcel at the store.", "ja": "店頭で受け取り時にお支払い。", "de": "Bezahlung bei Abholung im Laden."},
    "郵局寄送": {"en": "Post office delivery", "ja": "郵便局配送", "de": "Postversand"},
    "全家 超商取貨": {"en": "FamilyMart pickup", "ja": "ファミリーマート受け取り", "de": "Abholung bei FamilyMart"},
    "7-11 超商取貨": {"en": "7-Eleven pickup", "ja": "セブン-イレブン受け取り", "de": "Abholung bei 7-Eleven"},
    "僅限使用 ATM 付款": {"en": "ATM payment only", "ja": "ATM 振込のみ", "de": "Nur mit ATM-Überweisung"},
    "請務必填寫真實姓名，超商將核對身分證件。": {"en": "Please enter your real name. The store checks ID at pickup.", "ja": "本名をご記入ください。店舗で身分証を確認します。", "de": "Bitte den echten Namen angeben. Der Laden prüft den Ausweis."},
    "運費": {"en": "Shipping fee", "ja": "送料", "de": "Versandkosten"},
    "一起長大": {"en": "Growing up together", "ja": "いっしょに育つ", "de": "Gemeinsam aufwachsen"},
    "成年後加入": {"en": "Joining us later", "ja": "大人になってから", "de": "Später dazugekommen"},
    "年老時相伴": {"en": "Company in later years", "ja": "晩年のそばに", "de": "Begleiter im Alter"},
    "最新": {"en": "New", "ja": "新着", "de": "Neu"},
    "熱賣": {"en": "Bestseller", "ja": "人気", "de": "Bestseller"},
}

UI.update(fit.UI)
UI.update(mem.UI)

LANG_CODES = [c for c, _, _, _ in sb.LANGS]
HTML_LANG = {c: hl for c, _, _, hl in sb.LANGS}
LANG_LABEL = {c: lab for c, lab, _, _ in sb.LANGS}


# ----------------------------------------------------------------- small helpers
def esc(s):
    return html_mod.escape(str(s if s is not None else ""), quote=True)


def price_text(n):
    return "NT$" + f"{int(n):,}"


def rel_dir(site_rel):
    return posixpath.dirname(site_rel)


def link(page_dir, site_path, lang):
    """Relative href from the page in `page_dir` to the same-language variant of a site page."""
    return sb.href(page_dir, sb.lang_variant(site_path, lang))


def asset(page_dir, site_path):
    return sb.href(page_dir, site_path)


def digest(text):
    return hashlib.md5(text.encode("utf-8")).hexdigest()[:8]


_CROPS = None


def crop(site_path, key):
    """Uniform crop of a product photo made by crop_images.py ('sq' 1:1 or 'w43' 4:3); the original if none."""
    global _CROPS
    if _CROPS is None:
        f = sb.DATA_DIR / "image_crops.json"
        _CROPS = json.loads(f.read_text(encoding="utf-8")) if f.exists() else {}
    return (_CROPS.get(site_path) or {}).get(key) or site_path


def buy_link(p, data):
    settings = data.get("settings") or {}
    return (p.get("buy_url") or "").strip() or (settings.get("shop_url") or "").strip() or f"{sb.ONLINE}product/product&product_id={p['id']}"


def clean_rich_html(fragment_html, page_dir, lang="zh"):
    """Description HTML from the shop: real image sources, no inline fonts/sizes, no handlers.
    Text written in the admin editor (<div class="rt">) keeps its formatting via rich_html()."""
    frag = BeautifulSoup(fragment_html or "", "html.parser")
    rich_parts = []
    for div in frag.find_all("div", class_="rt"):
        rich_parts.append(rich_html(div.decode_contents(), page_dir, lang))
        div.replace_with(NavigableString(f"@@RT{len(rich_parts) - 1}@@"))
    for img in frag.find_all("img"):
        src = img.get("data-lazy-src") or img.get("data-src") or img.get("src") or ""
        for a in ("data-lazy-src", "data-src", "onerror", "onload", "width", "height", "style", "class"):
            if img.has_attr(a):
                del img[a]
        img["src"] = src
        img["loading"] = "lazy"
        if not img.get("alt"):
            img["alt"] = ""
    for tag in frag.find_all(True):
        for a in list(tag.attrs):
            if a.startswith("on") or a in ("dir", "id", "class", "lang"):
                del tag[a]
        if tag.name == "span" and set(tag.attrs) <= {"style"}:
            tag.unwrap()
        elif tag.has_attr("style"):
            del tag["style"]
    for tag in frag.find_all(["p", "div", "b", "strong", "span"]):
        if not tag.get_text(strip=True) and not tag.find("img") and not tag.find("iframe") and not tag.has_attr("data-chart"):
            tag.decompose()
    for t in list(frag.find_all(string=True)):
        if " " in t or re.match(r"^\s{2,}", t):
            t.replace_with(NavigableString(re.sub(r"[\s ]+", " ", t)))
    out = str(frag)
    for i, part in enumerate(rich_parts):
        out = out.replace(f"@@RT{i}@@", f'<div class="rt">{part}</div>')
    return out


# ----------------------------------------------------------------- static assets (CSS / JS)
CSS = r"""
:root{color-scheme:light;--bg:#fbfaf7;--card:#fff;--ink:#17181a;--ink2:#3d4047;--mute:#6f737b;--line:#e7e4dd;--line2:#d9d5cc;--brand:#ff2414;--brand-ink:#d41d0e;--brand-soft:#fff0ec;--sand:#f3efe6;--radius:18px;--max:1200px;--gutter:20px;--font:"Manrope","Noto Sans TC","PingFang TC","Microsoft JhengHei","Hiragino Sans",system-ui,sans-serif}
:lang(ja){--font:"Manrope","Noto Sans JP","Hiragino Sans","Noto Sans TC",system-ui,sans-serif}
*{box-sizing:border-box}html{-webkit-text-size-adjust:100%;scroll-behavior:smooth;overflow-x:clip}
body{margin:0;background:var(--bg);color:var(--ink);font:16px/1.7 var(--font);-webkit-font-smoothing:antialiased}
img{max-width:100%;height:auto;display:block}a{color:inherit;text-decoration:none}
h1,h2,h3,h4{margin:0;font-weight:700;line-height:1.25;letter-spacing:-.01em}
p{margin:0 0 1em;text-wrap:pretty}h1,h2,h3{text-wrap:balance}ul,ol{margin:0;padding:0;list-style:none}button{font:inherit}
.wrap{max-width:var(--max);margin:0 auto;padding:0 var(--gutter)}
.sr{position:absolute;width:1px;height:1px;overflow:hidden;clip:rect(0 0 0 0)}
.btn{display:inline-flex;align-items:center;justify-content:center;gap:8px;min-height:48px;padding:0 26px;border-radius:999px;border:1.5px solid var(--ink);background:var(--ink);color:#fff;font-weight:700;font-size:16px;cursor:pointer;transition:transform .15s,background .15s,color .15s,border-color .15s}
.btn:hover{background:#000;transform:translateY(-1px)}
.btn.ghost{background:transparent;color:var(--ink)}.btn.ghost:hover{background:var(--ink);color:#fff}
.btn.brand{background:var(--brand);border-color:var(--brand)}.btn.brand:hover{background:var(--brand-ink);border-color:var(--brand-ink)}
.btn.big{min-height:56px;padding:0 34px;font-size:17px}
.eyebrow{display:inline-block;color:var(--brand-ink);font-weight:700;font-size:14px;letter-spacing:.08em;margin-bottom:14px}
.sec{padding:72px 0}.sec.tight{padding:48px 0}.sec-head{display:flex;align-items:flex-end;justify-content:space-between;gap:20px;margin-bottom:28px}
.sec-head h2{font-size:clamp(26px,3vw,36px)}.sec-head p{margin:6px 0 0;color:var(--mute);font-size:16px}
.sec-head .more{white-space:nowrap;font-weight:700;color:var(--ink);border-bottom:2px solid var(--brand);padding-bottom:2px}
.js .rv{opacity:0;transform:translateY(16px);transition:opacity .6s ease,transform .6s ease}.js .rv.in{opacity:1;transform:none}
@media (prefers-reduced-motion:reduce){.rv{opacity:1;transform:none;transition:none}html{scroll-behavior:auto}}

/* header */
.hd{position:sticky;top:0;z-index:50;background:rgba(251,250,247,.86);background:color-mix(in srgb,var(--bg) 86%,transparent);backdrop-filter:saturate(1.4) blur(12px);-webkit-backdrop-filter:saturate(1.4) blur(12px);border-bottom:1px solid transparent;transition:border-color .2s,box-shadow .2s}
.hd.scrolled{border-color:var(--line);box-shadow:0 4px 24px rgba(0,0,0,.05)}
.hd-in{display:grid;grid-template-columns:auto 1fr auto;grid-template-areas:"logo . lang" "nav nav nav";align-items:center;column-gap:18px;padding-top:12px}
.hd-in>.logo{grid-area:logo}.hd-in>.srch{grid-area:search}.hd-in>.lang{grid-area:lang}.hd-in>.nav{grid-area:nav;justify-content:center;padding:6px 0 8px}
.logo{display:flex;align-items:center;gap:10px;flex:0 0 auto}.logo img{height:56px;width:auto}
.nav{display:flex;gap:2px;flex-wrap:wrap;min-width:0}
.nav a{white-space:nowrap;padding:8px 14px;border-radius:999px;font-weight:600;font-size:15.5px;color:var(--ink2)}.nav a:hover{background:var(--sand);color:var(--ink)}.nav a.cur{color:var(--brand-ink)}
.hd-in>.nav a{position:relative}.hd-in>.nav a+a::before{content:"";position:absolute;left:-2px;top:50%;width:1px;height:14px;margin-top:-7px;background:var(--line2);pointer-events:none}
.srch{display:flex;align-items:center;background:var(--card);border:1.5px solid var(--line2);border-radius:999px;padding:0 6px 0 14px;height:44px;width:240px;flex:0 0 auto;transition:width .2s,border-color .2s}
.srch:focus-within{border-color:var(--ink);width:280px}.srch input{border:0;outline:0;background:none;flex:1;min-width:0;font:inherit;font-size:15px}
.srch button{border:0;background:none;width:34px;height:34px;border-radius:50%;display:grid;place-items:center;cursor:pointer;color:var(--ink)}.srch button:hover{background:var(--sand)}
.lang{display:flex;flex:0 0 auto;background:var(--card);border:1.5px solid var(--line2);border-radius:999px;padding:4px;gap:2px}
.lang a{display:inline-flex;align-items:center;justify-content:center;min-width:56px;height:38px;padding:0 13px;white-space:nowrap;border-radius:999px;font-weight:700;font-size:15px;color:var(--ink2)}
.lang a:hover{background:var(--sand);color:var(--ink)}.lang a.cur{background:var(--ink);color:#fff}
.burger{display:none;border:0;background:none;width:44px;height:44px;border-radius:12px;cursor:pointer;color:var(--ink);padding:0;transition:background .15s}
.burger:active{background:var(--sand)}
.bars{display:block;width:22px;height:14px;position:relative}.bars i{position:absolute;left:0;width:22px;height:2px;border-radius:2px;background:currentColor;transition:transform .25s,opacity .2s}
.bars i:nth-child(1){top:0}.bars i:nth-child(2){top:6px}.bars i:nth-child(3){top:12px}
body.menu-open .bars i:nth-child(1){transform:translateY(6px) rotate(45deg)}body.menu-open .bars i:nth-child(2){opacity:0}body.menu-open .bars i:nth-child(3){transform:translateY(-6px) rotate(-45deg)}
.lang-row{display:none}
.mobile-menu{display:none}
@media (max-width:1180px){.nav a{font-size:15px;padding:8px 10px}}
/* wide screens: logo, menu and languages on one row */
@media (min-width:1060px){
 .hd-in{grid-template-columns:auto 1fr auto;grid-template-areas:"logo nav lang";padding:10px 0}
 .hd-in>.nav{padding:0;flex-wrap:nowrap}.logo img{height:48px}
 .hd-in>.lang{padding:3px}.hd-in>.lang a{min-width:0;height:34px;padding:0 11px;font-size:14px}
}
@media (max-width:980px){
 .nav,.srch,.hd-in>.lang{display:none}.burger{display:grid;place-items:center;order:-1;margin-left:-11px}
 .hd-in{display:flex;align-items:center;min-height:64px;gap:12px;padding-top:0}.hd-in>.logo{margin:0 auto;padding-right:36px}.logo img{height:50px}
 /* phones: the language row sits once at the very top of the page and scrolls away; only the logo/menu bar stays sticky */
 .lang-row{display:flex;gap:6px;padding:8px var(--gutter) 2px;background:var(--bg,#fbfaf7)}
 .lang-row a{flex:1;display:inline-flex;align-items:center;justify-content:center;height:40px;border:1.5px solid var(--line2);border-radius:999px;background:var(--card);font-weight:700;font-size:15.5px;color:var(--ink2)}
 .lang-row a.cur{background:var(--ink);border-color:var(--ink);color:#fff}
 body.menu-open .mobile-menu,body.menu-closing .mobile-menu{display:block;position:fixed;inset:0;z-index:60;background:rgba(23,24,26,.8);animation:mm-fade .25s ease both}
 body.menu-closing .mobile-menu{animation:mm-fade .22s ease reverse both}
 .mm-panel{width:min(68vw,300px);height:100%;background:var(--bg);padding:20px var(--gutter) 32px;overflow:auto;box-shadow:0 0 40px rgba(0,0,0,.18);animation:mm-slide .28s cubic-bezier(.2,.8,.2,1) both}
 body.menu-closing .mm-panel{animation:mm-slide .22s ease-in reverse both}
 @keyframes mm-fade{from{opacity:0}to{opacity:1}}@keyframes mm-slide{from{transform:translateX(-100%)}to{transform:none}}
 .mm-nav a,.mm-social,.mm-search{animation:mm-rise .35s ease both}
 .mm-nav a:nth-child(1){animation-delay:.05s}.mm-nav a:nth-child(2){animation-delay:.09s}.mm-nav a:nth-child(3){animation-delay:.13s}.mm-nav a:nth-child(4){animation-delay:.17s}.mm-nav a:nth-child(5){animation-delay:.21s}.mm-nav a:nth-child(6){animation-delay:.25s}.mm-nav a:nth-child(7){animation-delay:.29s}.mm-nav a:nth-child(8){animation-delay:.33s}.mm-nav a:nth-child(9){animation-delay:.37s}.mm-social{animation-delay:.42s}
 @keyframes mm-rise{from{opacity:0;transform:translateX(-14px)}to{opacity:1;transform:none}}
 .mm-nav a{transition:padding .15s,background .15s;border-radius:8px}.mm-nav a:active{background:var(--sand);padding-left:8px}
 body.menu-open{overflow:hidden}
 @media (prefers-reduced-motion:reduce){.mm-panel,.mobile-menu,.mm-nav a,.mm-social,.mm-search{animation:none!important}}
 .mm-top{display:flex;justify-content:space-between;align-items:center;margin-bottom:24px}.mm-top img{height:48px}
 .mm-close{border:0;background:var(--sand);width:44px;height:44px;border-radius:50%;cursor:pointer;font-size:20px}
 .mm-search{display:flex;background:var(--card);border:1.5px solid var(--line2);border-radius:999px;height:52px;padding:0 6px 0 18px;margin-bottom:24px}
 .mm-search input{flex:1;border:0;outline:0;background:none;font:inherit;font-size:16px;min-width:0}.mm-search button{border:0;background:var(--ink);color:#fff;width:40px;height:40px;border-radius:50%;margin:5px 0;cursor:pointer;display:grid;place-items:center}
 .mm-nav a{display:block;padding:16px 0;border-bottom:1px solid var(--line);font-size:20px;font-weight:700}.mm-nav a.cur{color:var(--brand-ink)}
 .mm-sub{margin-top:24px;display:flex;flex-wrap:wrap;gap:8px 20px}.mm-sub a{color:var(--mute);font-weight:600}
 .mm-more{margin-top:18px;display:flex;gap:22px}.mm-more a{font-size:15.5px;font-weight:600;color:var(--ink2)}
 .mm-social{margin-top:22px;display:flex;gap:10px}.mm-social a{display:inline-flex;align-items:center;height:44px;padding:0 20px;border-radius:999px;border:1.5px solid var(--line2);background:var(--card);font-weight:700;font-size:15px}
}

/* hero */
.hero{padding:40px 0 20px}
.hero-in{display:grid;grid-template-columns:1fr 1.15fr;gap:48px;align-items:center}
.hero h1{font-size:clamp(34px,4.4vw,56px);letter-spacing:-.02em;margin-bottom:18px}.hero h1 .phr{display:inline-block}
.hero .lead{font-size:18px;color:var(--ink2);max-width:46ch;margin-bottom:28px}
.hero .cta{display:flex;gap:12px;flex-wrap:wrap}
.hero-img{position:relative;border-radius:28px;overflow:hidden;aspect-ratio:16/10;background:var(--sand)}
.hero-img img{width:100%;height:100%;object-fit:cover;object-position:70% 50%}
.hero-badges{display:flex;gap:10px;flex-wrap:wrap;margin-top:28px}
.badge{display:inline-flex;align-items:center;gap:8px;padding:8px 14px;border-radius:999px;background:var(--card);border:1px solid var(--line);font-size:14px;font-weight:600;color:var(--ink2)}
.badge i{width:8px;height:8px;border-radius:50%;background:var(--brand)}
@media (max-width:980px){.hero{padding:20px 0 10px}.hero-in{grid-template-columns:1fr;gap:26px}.hero-img{aspect-ratio:16/10;border-radius:22px;order:-1}.hero h1{font-size:clamp(30px,8vw,40px)}.hero .lead{font-size:17px}}

/* category tiles */
.tiles{display:grid;grid-template-columns:repeat(3,1fr);gap:22px}
.tile{display:block;background:var(--card);border-radius:var(--radius);overflow:hidden;border:1px solid var(--line);transition:transform .2s,box-shadow .2s}
.tile:hover{transform:translateY(-4px);box-shadow:0 18px 40px rgba(0,0,0,.08)}
.tile .img{aspect-ratio:4/3;overflow:hidden;background:var(--sand)}.tile img{width:100%;height:100%;object-fit:cover;transition:transform .5s}.tile:hover img{transform:scale(1.04)}
.tile .body{padding:20px 22px 24px}.tile h3{font-size:22px;margin-bottom:6px}.tile p{color:var(--mute);margin:0 0 12px;font-size:15px}
.tile .go{font-weight:700;color:var(--brand-ink)}
@media (max-width:980px){.tiles{grid-template-columns:1fr;gap:16px}.tile .img{aspect-ratio:16/9}}

/* product grid */
.product-grid{display:grid;grid-template-columns:repeat(4,1fr);gap:22px}
.grid-box{display:block;background:var(--card);border-radius:var(--radius);border:1px solid var(--line);overflow:hidden;transition:transform .2s,box-shadow .2s;position:relative}
.grid-box:hover{transform:translateY(-4px);box-shadow:0 18px 40px rgba(0,0,0,.08)}
.grid-box .image{aspect-ratio:1/1;overflow:hidden;background:#fff}.grid-box .image img{width:100%;height:100%;object-fit:cover;transition:transform .5s}.grid-box:hover .image img{transform:scale(1.04)}
.grid-box .inner{padding:14px 16px 18px}.grid-box .name{font-weight:600;font-size:16px;line-height:1.4;color:var(--ink)}
.grid-box .price{margin-top:6px;font-weight:700;font-size:16px;color:var(--ink2)}
.grid-box .tag{position:absolute;top:12px;left:12px;background:var(--ink);color:#fff;font-size:12px;font-weight:700;padding:5px 10px;border-radius:999px;letter-spacing:.04em}
.grid-box .tag.hot{background:var(--brand)}
@media (max-width:980px){.product-grid{grid-template-columns:repeat(3,1fr);gap:14px}}
@media (max-width:640px){.product-grid{grid-template-columns:repeat(2,1fr);gap:12px}.grid-box .inner{padding:12px 12px 14px}.grid-box .name{font-size:15px}}
.empty{padding:48px 0;text-align:center;color:var(--mute);font-size:16px}

/* feature strip */
.feats{display:grid;grid-template-columns:repeat(4,1fr);gap:20px}
.feat{background:var(--card);border:1px solid var(--line);border-radius:var(--radius);overflow:hidden}
.feat .img{aspect-ratio:3/2;overflow:hidden;background:var(--sand)}.feat img{width:100%;height:100%;object-fit:cover}
.feat .body{padding:18px 20px 22px}.feat h3{font-size:17px;margin-bottom:6px}.feat p{margin:0;color:var(--mute);font-size:14.5px;line-height:1.6}
@media (max-width:980px){.feats{grid-template-columns:repeat(2,1fr);gap:14px}}
@media (max-width:480px){.feats{grid-template-columns:1fr}}

/* story */
.story{display:grid;grid-template-columns:1.1fr 1fr;gap:48px;align-items:center}
.story.flip .story-img{order:2}
.story-img{border-radius:28px;overflow:hidden;aspect-ratio:4/3;background:var(--sand)}.story-img img{width:100%;height:100%;object-fit:cover}
.story-img.zoom img{transform:scale(1.3);transform-origin:100% 100%}
.story h2{font-size:clamp(26px,3vw,38px);margin-bottom:16px}.story p{color:var(--ink2);font-size:17px}
.story .btn{margin-top:8px}
@media (max-width:980px){.story{grid-template-columns:1fr;gap:24px}.story.flip .story-img{order:0}.story-img{aspect-ratio:16/10;border-radius:22px}}

/* banner */
.band{background:var(--ink);color:#fff;border-radius:28px;padding:56px 48px;display:grid;grid-template-columns:1fr auto;gap:24px;align-items:center}
.band h2{font-size:clamp(24px,3vw,34px);margin-bottom:8px}.band p{margin:0;color:#c9ccd3;font-size:17px;max-width:60ch}
.band .btn{background:var(--card);color:var(--ink);border-color:#fff}.band .btn:hover{background:var(--brand);border-color:var(--brand);color:#fff}
@media (max-width:980px){.band{grid-template-columns:1fr;padding:36px 26px;border-radius:22px}}

/* page header / breadcrumb */
.ph{padding:36px 0 8px}.ph h1{font-size:clamp(30px,4vw,44px);margin-bottom:8px}.ph p{color:var(--mute);font-size:17px;margin:0}
.breadcrumb{display:flex;flex-wrap:wrap;gap:6px;align-items:center;font-size:14px;color:var(--mute);padding:20px 0 0}
.breadcrumb li+li:before{content:"/";margin-right:6px;color:var(--line2)}.breadcrumb a:hover{color:var(--ink)}
.chips{display:flex;gap:8px;flex-wrap:wrap;margin:18px 0 28px}
.chips a{display:inline-flex;align-items:center;height:40px;padding:0 16px;border-radius:999px;border:1.5px solid var(--line2);background:var(--card);font-weight:600;font-size:15px;color:var(--ink2)}
.chips a:hover{border-color:var(--ink);color:var(--ink)}.chips a.cur{background:var(--ink);border-color:var(--ink);color:#fff}
.pagination{color:var(--mute);font-size:15px;margin-bottom:18px}.pagination .results{margin:0}
.bigsearch{display:flex;align-items:center;max-width:620px;margin:22px 0 4px;background:var(--card);border:1.5px solid var(--line2);border-radius:999px;height:56px;padding:0 8px 0 22px;transition:border-color .2s,box-shadow .2s}
.bigsearch:focus-within{border-color:var(--ink);box-shadow:0 8px 28px rgba(0,0,0,.08)}.bigsearch input{flex:1;min-width:0;border:0;outline:0;background:none;font:inherit;font-size:17px}
.bigsearch button{border:0;background:var(--ink);color:#fff;width:42px;height:42px;border-radius:50%;display:grid;place-items:center;cursor:pointer}.bigsearch button:hover{background:var(--brand)}
@media (max-width:640px){.bigsearch{height:52px;padding-left:18px}.bigsearch input{font-size:16px}}

/* product page */
.pd{display:grid;grid-template-columns:1.15fr 1fr;gap:48px;padding:24px 0 48px;align-items:start}.pd>*{min-width:0}
.gallery{position:sticky;top:132px}
.gal-main{border-radius:24px;overflow:hidden;background:#fff;border:1px solid var(--line);aspect-ratio:4/3}
.gal-main img{width:100%;height:100%;object-fit:cover}
.thumbs{display:flex;gap:10px;margin-top:12px;overflow-x:auto;padding-bottom:4px}
.thumbs li{flex:0 0 auto}.thumbs a{display:block;width:76px;height:76px;border-radius:14px;overflow:hidden;border:2px solid transparent;background:#fff}
.thumbs li.cur a,.thumbs a:hover{border-color:var(--ink)}.thumbs img{width:100%;height:100%;object-fit:cover}
.pi .cat{display:inline-block;color:var(--brand-ink);font-weight:700;font-size:14px;letter-spacing:.08em;margin-bottom:10px}
.pi h1{font-size:clamp(28px,3.4vw,40px);margin-bottom:12px}
.pi .product-sell-price{font-size:26px;font-weight:800;margin-bottom:18px}
.pi .product-feature-content{color:var(--ink2);font-size:17px;border-top:1px solid var(--line);padding-top:18px}
.pi .product-feature-content p{margin:0 0 .5em}.pi .product-feature-content strong{color:var(--ink)}
#options{margin-top:8px}#options .control-group{margin:18px 0}
#options .control-label{display:block;font-size:15px;color:var(--mute);margin-bottom:10px}#options .control-label b{color:var(--ink);font-weight:700}
#options label.checkbox,#options label.radio{display:inline-flex;align-items:center;justify-content:center;min-width:52px;height:44px;padding:0 16px;margin:0 8px 8px 0;border-radius:12px;border:1.5px solid var(--line2);background:var(--card);font-weight:600;font-size:15px;cursor:pointer;user-select:none}
#options label.checkbox:has(input:checked),#options label.checkbox.pick{background:var(--ink);border-color:var(--ink);color:#fff}
#options label.checkbox:hover{border-color:var(--ink)}#options input{position:absolute;opacity:0;width:0;height:0}
.showcase #options label.checkbox{cursor:default;pointer-events:none}
.buy{margin-top:24px;display:flex;flex-direction:column;gap:10px}.buy .btn{width:100%}.buy-note{margin:0;font-size:14px;color:var(--mute);text-align:center}
.buy-help{display:inline-block;margin-top:12px;font-size:14.5px;font-weight:600;color:var(--ink2);text-decoration:underline;text-underline-offset:3px}.buy .buy-help{margin-top:0;align-self:center}.buy-help:hover{color:var(--brand-ink)}
.showcase-note{margin:24px 0 0;padding:16px 18px;background:var(--sand);border-radius:14px;font-size:15px;color:var(--ink2)}
.showcase-note a{font-weight:700;color:var(--brand-ink);white-space:nowrap}
.pd-desc{padding:16px 0 64px;border-top:1px solid var(--line)}
.pd-desc h2{font-size:24px;margin:40px 0 20px}
.rich{max-width:860px;margin:0 auto;font-size:16.5px;color:var(--ink2)}
.rich p,.rich ul,.rich ol,.rich h2,.rich h3,.rich h4{max-width:680px;margin-left:auto;margin-right:auto}
.rich p,.rich li{margin-bottom:1.1em;line-height:1.9}.rich ul{list-style:disc;padding-left:1.3em;margin-bottom:1.6em}.rich li{margin-bottom:.45em}
.rich h2,.rich h3,.rich h4{color:var(--ink);font-size:20px;margin-top:2.2em;margin-bottom:.7em}.rich h2:first-child,.rich h3:first-child{margin-top:.4em}
.rich strong,.rich b{font-weight:700;color:var(--ink)}
.rich p:has(> img:only-child){max-width:none;margin:2em auto .8em}.rich img{margin:0 auto;border-radius:16px}
.rich p:has(> img:only-child)+p{text-align:center;color:var(--mute);font-size:15px;margin-bottom:2.2em}
.rich p:empty{display:none}
.apt-chart{font-family:inherit!important;color:var(--ink)!important;margin:1.5em auto 2em!important}
.apt-ov .t{background:rgba(255,255,255,.92);color:#222!important;padding:.3em .55em;border-radius:.5em;line-height:1.25;box-shadow:0 1px 4px rgba(0,0,0,.12)}
@media (max-width:980px){.pd{grid-template-columns:1fr;gap:24px;padding-top:12px}.gallery{position:static}.gal-main{border-radius:18px}.pi .product-sell-price{font-size:22px}}

/* about page */
.about-lead{max-width:860px;margin:0 auto;text-align:center;padding:24px 0 8px}
.about-lead h2{font-size:clamp(26px,3.4vw,40px);margin:0 0 18px;letter-spacing:-.02em}.about-lead p{font-size:18px;color:var(--ink2);margin:0}
.cards3{display:grid;grid-template-columns:repeat(3,1fr);gap:20px;margin-top:36px}
.cards3 div{background:var(--card);border:1px solid var(--line);border-radius:var(--radius);padding:26px 24px 28px}
.cards3 svg{width:36px;height:36px;color:var(--brand);margin-bottom:12px}.cards3 h3{font-size:19px;margin:0 0 8px}.cards3 p{margin:0;font-size:16.5px;line-height:1.7;color:var(--ink2)}
.quote{background:var(--sand);border-radius:28px;padding:48px 32px;text-align:center;margin:48px 0}
.quote p{margin:0 auto;max-width:28ch;font-size:clamp(22px,2.6vw,30px);font-weight:700;line-height:1.5;letter-spacing:-.01em}
.contact-grid{display:grid;grid-template-columns:repeat(2,1fr);gap:16px}
.contact-grid a,.contact-grid div{display:flex;gap:14px;align-items:center;background:var(--card);border:1px solid var(--line);border-radius:16px;padding:18px 20px;font-size:16px;font-weight:600;color:var(--ink)}
.contact-grid svg{flex:0 0 auto;width:26px;height:26px;color:var(--brand-ink)}.contact-grid a:hover{border-color:var(--ink)}
.about-foot{margin:18px 0 0;color:var(--mute);font-size:14px;text-align:center}
@media (max-width:980px){.cards3{grid-template-columns:1fr;gap:12px}.quote{padding:36px 22px;border-radius:22px;margin:36px 0}.contact-grid{grid-template-columns:1fr;gap:10px}}
/* terms page */
.terms-intro{max-width:760px;margin:0 auto 8px;text-align:center}.terms-intro h2{font-size:clamp(26px,3.4vw,38px);margin:0 0 14px}.terms-intro p{font-size:17px;color:var(--ink2)}
.tsec{margin-top:48px}.tsec h2{font-size:24px;margin-bottom:18px;display:flex;align-items:center;gap:10px}.tsec h2 svg{width:26px;height:26px;color:var(--brand-ink)}
.steps{display:grid;grid-template-columns:repeat(6,1fr);gap:12px;counter-reset:step}
.steps div{position:relative;background:var(--card);border:1px solid var(--line);border-radius:16px;padding:18px 14px 16px;font-weight:600;font-size:15px;line-height:1.5}
.steps div:before{counter-increment:step;content:counter(step);display:flex;align-items:center;justify-content:center;width:28px;height:28px;border-radius:50%;background:var(--brand);color:#fff;font-size:13px;font-weight:800;margin-bottom:10px}
.cards2{display:grid;grid-template-columns:repeat(2,1fr);gap:16px}
.cards2 div,.ship div{background:var(--card);border:1px solid var(--line);border-radius:var(--radius);padding:22px 24px}
.cards2 h3,.ship h3{font-size:18px;margin:0 0 6px}.cards2 p,.ship p{margin:0;color:var(--ink2);font-size:15.5px}
.ship{display:grid;grid-template-columns:repeat(3,1fr);gap:16px}
.ship .fee{display:block;font-size:28px;font-weight:800;color:var(--brand-ink);margin:6px 0 8px;letter-spacing:-.02em}.ship small{display:block;color:var(--mute);font-size:13px;margin-top:4px}
.free{background:var(--ink);color:#fff;border-radius:16px;padding:16px 22px;font-weight:700;margin-bottom:16px;display:flex;gap:10px;align-items:center}.free i{width:10px;height:10px;border-radius:50%;background:var(--brand);flex:0 0 auto}
.notebox{background:var(--sand);border-radius:var(--radius);padding:22px 26px}.notebox p{margin:0 0 .5em;font-size:16px}.notebox p:last-child{margin:0}
@media (max-width:980px){.steps{grid-template-columns:repeat(2,1fr)}.cards2,.ship{grid-template-columns:1fr;gap:12px}.tsec{margin-top:36px}}
/* article */
.article{max-width:760px;margin:0 auto;padding:0 0 64px;font-size:17px}
.article h1{font-size:clamp(28px,3.4vw,40px);margin:0 0 10px}.article .date{color:var(--mute);font-size:15px;margin-bottom:28px}
.article p{line-height:1.9;margin:0 0 1.1em}.article h2,.article h3{font-size:22px;margin:1.8em 0 .6em}
.article a{color:var(--brand-ink);font-weight:600}.article hr{border:0;border-top:1px solid var(--line);margin:32px 0}
.article .contact{background:var(--card);border:1px solid var(--line);border-radius:var(--radius);padding:22px 24px;margin-top:36px;font-size:16px}
.article .contact p{margin:0 0 .4em}
.news-list{display:grid;gap:14px;max-width:760px;margin:0 auto 64px}.news-list.home{max-width:none;margin:0;grid-template-columns:repeat(2,1fr)}
@media (max-width:760px){.news-list.home{grid-template-columns:1fr}}
.news-list a{display:flex;gap:20px;align-items:baseline;background:var(--card);border:1px solid var(--line);border-radius:var(--radius);padding:20px 24px;transition:transform .2s,box-shadow .2s}
.news-list a:hover{transform:translateY(-2px);box-shadow:0 12px 30px rgba(0,0,0,.06)}
.news-list time{flex:0 0 auto;color:var(--mute);font-size:15px;font-variant-numeric:tabular-nums}.news-list b{font-size:17px;font-weight:700}
@media (max-width:640px){.news-list a{flex-direction:column;gap:6px}}

/* footer */
.ft{background:var(--card);border-top:1px solid var(--line);margin-top:24px}
.ft-in{display:grid;grid-template-columns:1.2fr 1fr;gap:36px;padding:48px 0 32px;align-items:start}
.ft .brand img{height:56px;margin-bottom:14px}.ft .brand p{color:var(--mute);font-size:15px;max-width:34ch;margin:0 0 .4em}
.ft h4{font-size:14px;letter-spacing:.08em;color:var(--mute);margin-bottom:14px}
.ft li{margin:0 0 10px;color:var(--ink2);font-weight:600}.ft li a{color:var(--ink2)}.ft li a:hover{color:var(--brand-ink)}
.ft .social{display:flex;gap:10px;margin-top:14px}.ft .social a{display:inline-flex;align-items:center;gap:6px;padding:8px 14px;border-radius:999px;border:1.5px solid var(--line2);font-weight:600;font-size:14px}
.ft .social a:hover{border-color:var(--ink)}
.ft-bottom{border-top:1px solid var(--line);padding:18px 0;display:flex;justify-content:space-between;align-items:center;gap:12px 24px;flex-wrap:wrap;font-size:13.5px;color:var(--mute)}
.ft-links{display:flex;gap:6px 22px;flex-wrap:wrap}.ft-links a{font-weight:600;color:var(--ink2);font-size:14px}.ft-links a:hover{color:var(--brand-ink)}
.ft .contact li,.contact-grid span{word-break:keep-all;overflow-wrap:anywhere}
@media (max-width:980px){.ft-in{grid-template-columns:1fr;gap:28px;padding:36px 0 24px}.ft-bottom{flex-direction:column;align-items:flex-start}}
"""

JS = r"""/* a language link click is a deliberate choice: remember it so the region-based pick never overrides it */
document.addEventListener('click',function(e){var a=e.target.closest&&e.target.closest('a[hreflang]');if(a)try{localStorage.setItem('apetto_lang',a.getAttribute('hreflang'));}catch(x){}});
/* Shop-in-Shop page: the Google map is embedded only after a click */
document.addEventListener('click',function(e){var b=e.target.closest&&e.target.closest('.map-load');if(!b)return;var f=document.createElement('iframe');f.src=b.dataset.src;f.loading='lazy';f.referrerPolicy='no-referrer-when-downgrade';f.setAttribute('allowfullscreen','');f.title='Google Maps';b.parentNode.appendChild(f);b.remove();});
/* colour-scheme preview bar: only appears after visiting a page with ?palette=N */
(function(){var cur;try{cur=sessionStorage.getItem('apetto_palette');}catch(e){}if(cur===null||cur===undefined)return;var H=document.documentElement;
 var P=[['0','原本','#fbfaf7'],['1','杏仁奶茶','#efe0c9'],['2','蜜桃','#ffe4d4'],['3','奶油黃','#fbeebb'],['4','鼠尾草','#e6e8d6'],['5','焦糖','#e6cdaa']];if(window.apPcStyle){var pcb=(sessionStorage.getItem('apetto_pc')||'').slice(0,6);P.push(['c','自訂','#'+pcb]);}
 var bar=document.createElement('div');bar.className='pal-bar';bar.innerHTML='<b>配色預覽</b>';
 function set(v){try{sessionStorage.setItem('apetto_palette',v);}catch(e){}H.removeAttribute('style');if(v==='0')H.removeAttribute('data-palette');else{H.setAttribute('data-palette',v);if(v==='c'&&window.apPcStyle)H.setAttribute('style',window.apPcStyle);}
  [].forEach.call(bar.querySelectorAll('button[data-v]'),function(b){b.classList.toggle('cur',b.getAttribute('data-v')===v);});}
 P.forEach(function(p){var b=document.createElement('button');b.type='button';b.setAttribute('data-v',p[0]);b.innerHTML='<i style="background:'+p[2]+'"></i>'+(p[0]==='0'||p[0]==='c'?'':p[0]+' ')+p[1];b.onclick=function(){set(p[0]);};bar.appendChild(b);});
 var x=document.createElement('button');x.type='button';x.className='x';x.textContent='關閉預覽 ✕';x.onclick=function(){try{sessionStorage.removeItem('apetto_palette');sessionStorage.removeItem('apetto_pc');}catch(e){}location.href=location.pathname+location.hash;};bar.appendChild(x);
 document.body.appendChild(bar);set(cur);})();
(function(){
var b=document.querySelector('.burger'),mm=document.querySelector('.mobile-menu');
function openMenu(){document.body.classList.remove('menu-closing');document.body.classList.add('menu-open');if(b)b.setAttribute('aria-expanded','true');}
function closeMenu(){if(!document.body.classList.contains('menu-open'))return;document.body.classList.remove('menu-open');document.body.classList.add('menu-closing');
 if(b)b.setAttribute('aria-expanded','false');setTimeout(function(){document.body.classList.remove('menu-closing');},240);}
if(b&&mm){b.addEventListener('click',function(){if(document.body.classList.contains('menu-open'))closeMenu();else openMenu();});
 mm.querySelectorAll('.mm-close,a').forEach(function(el){el.addEventListener('click',closeMenu);});
 mm.addEventListener('click',function(e){if(e.target===mm)closeMenu();});
 document.addEventListener('keydown',function(e){if(e.key==='Escape')closeMenu();});}
/* swipe right opens the menu, swipe left closes it (phones only; horizontal thumbnail strips and the helper chat are left alone) */
var sx=0,sy=0,swiping=false;
document.addEventListener('touchstart',function(e){var t=e.touches[0];sx=t.clientX;sy=t.clientY;swiping=!e.target.closest('.thumbs,.lang-row,input,textarea,.ai-panel');},{passive:true});
document.addEventListener('touchend',function(e){if(!swiping||!b||getComputedStyle(b).display==='none')return;var t=e.changedTouches[0],dx=t.clientX-sx,dy=t.clientY-sy;
 if(Math.abs(dx)<70||Math.abs(dy)>60||Math.abs(dy)>Math.abs(dx)*0.6)return;
 if(dx>0&&!document.body.classList.contains('menu-open'))openMenu();else if(dx<0)closeMenu();},{passive:true});
var hd=document.querySelector('.hd');function sh(){if(hd)hd.classList.toggle('scrolled',window.scrollY>8);}
window.addEventListener('scroll',sh,{passive:true});sh();
/* #size=M (from the fitting room) preselects that size chip */
var sm=location.hash.match(/size=([^&]+)/);if(sm){var want=decodeURIComponent(sm[1]).toLowerCase();document.querySelectorAll('#options label.checkbox').forEach(function(l){
 if(l.textContent.trim().toLowerCase().split(/[\s【(]/)[0]===want){var i=l.querySelector('input');if(i)i.checked=true;l.classList.add('pick');setTimeout(function(){l.scrollIntoView({block:'center',behavior:'smooth'});},300);}});}
var main=document.getElementById('main-defer-image');
document.querySelectorAll('#image-additional a').forEach(function(a){a.addEventListener('click',function(e){e.preventDefault();var img=a.querySelector('img');
 if(main&&img)main.src=a.getAttribute('href')||img.src;document.querySelectorAll('#image-additional li').forEach(function(l){l.classList.remove('cur');});a.parentNode.classList.add('cur');});});
if('IntersectionObserver' in window){var io=new IntersectionObserver(function(es){es.forEach(function(e){if(e.isIntersecting){e.target.classList.add('in');io.unobserve(e.target);}});},{rootMargin:'0px 0px -6% 0px'});
 document.querySelectorAll('.rv').forEach(function(el){io.observe(el);});}else{document.querySelectorAll('.rv').forEach(function(el){el.classList.add('in');});}
document.querySelectorAll('.type-tabs').forEach(function(bar){var grid=document.getElementById(bar.dataset.grid);if(!grid)return;
 var soon=document.getElementById(bar.dataset.grid+'-soon');
 function pick(k){var n=0;bar.querySelectorAll('button').forEach(function(x){x.classList.toggle('cur',x.dataset.type===k);x.setAttribute('aria-pressed',x.dataset.type===k?'true':'false');});
  grid.querySelectorAll('.grid-box').forEach(function(c){var on=!k||(' '+(c.dataset.types||'')+' ').indexOf(' '+k+' ')>=0;c.hidden=!on;if(on)n++;});
  grid.hidden=n===0;if(soon)soon.hidden=n>0;}
 bar.addEventListener('click',function(e){var x=e.target.closest('button');if(!x)return;pick(x.dataset.type);
  try{history.replaceState(null,'',x.dataset.type?'#type-'+x.dataset.type:location.pathname+location.search);}catch(err){}});
 var h=decodeURIComponent((location.hash||'').replace(/^#type-/,''));if(h&&bar.querySelector('[data-type="'+h+'"]'))pick(h);});
/* Chinese: mark word boundaries (the browser's own dictionary segmenter) so lines break between words, never inside one */
if(window.Intl&&Intl.Segmenter&&/^zh/i.test(document.documentElement.lang)){
 var seg=new Intl.Segmenter('zh-Hant',{granularity:'word'}),HAN=/[㐀-鿿]/,NOSTART=/^[，、。！？；：）」』】〉》…,.!?;:)\]>›]/,NOEND=/[（「『【〈《(\[<‹]$/;
 document.querySelectorAll('main h1,main h2,main h3,main h4,main p,main li,main .steps div,main .grid-box .name,main .fit-coat span,main .cat-card .sub').forEach(function(el){
  if(el.classList.contains('wb')||el.closest('.rte,textarea'))return;
  var tw=document.createTreeWalker(el,NodeFilter.SHOW_TEXT),nodes=[],n;while((n=tw.nextNode()))nodes.push(n);
  nodes.forEach(function(t){if(!HAN.test(t.data))return;var parts=[],it=seg.segment(t.data)[Symbol.iterator](),r;while(!(r=it.next()).done)parts.push(r.value.segment);
   if(parts.length<2)return;var f=document.createDocumentFragment();
   parts.forEach(function(x,i){var glue=i&&(NOSTART.test(x)||NOEND.test(parts[i-1]));if(i&&!glue)f.appendChild(document.createElement('wbr'));f.appendChild(document.createTextNode((glue?'⁠':'')+x));});
   t.parentNode.replaceChild(f,t);});
  el.classList.add('wb');});
}
})();"""

ICON_SEARCH = ('<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" aria-hidden="true">'
               '<circle cx="11" cy="11" r="7"/><path d="m20 20-3.5-3.5"/></svg>')
ICON_MENU = ('<svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" aria-hidden="true">'
             '<path d="M4 7h16M4 12h16M4 17h16"/></svg>')
ICON_ARROW = ('<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">'
              '<path d="M5 12h14M13 6l6 6-6 6"/></svg>')


# ----------------------------------------------------------------- shell
NAV = [("index.html", "首頁"), (SHOP, "商品分類"), (GUIDES, "商品指南"), (FEATURES, "機能與設計細節"), (fit.PAGE, "試衣間"), (ABOUT, "品牌故事")]


STORE = "pages/hamburg.html"


def nav_links(data, page_dir, lang, current=""):
    items = list(NAV)
    if lang == "de":
        items.append((STORE, "漢堡店"))
    out = []
    for site_path, label in items:
        cls = ' class="cur"' if site_path == current else ""
        out.append(f'<a href="{link(page_dir, site_path, lang)}"{cls}>{esc(label)}</a>')
    return "".join(out)


def cur(flag):
    return ' class="cur"' if flag else ""


def lang_links(site_rel, lang, cls=""):
    base = posixpath.basename(site_rel)
    return "".join(f'<a href="{sb.lang_variant(base, c)}" hreflang="{c}" lang="{HTML_LANG[c]}"{cur(c == lang)}>{LANG_LABEL[c]}</a>'
                   for c in LANG_CODES)


def header(data, site_rel, lang, current=""):
    d = rel_dir(site_rel)
    member_link = f'<a href="{link(d, mem.PAGE, lang)}">會員專區</a>' if mem.config() else ""
    search = link(d, "search.html", lang)
    return f"""<div class="lang-row" aria-label="語言">{lang_links(site_rel, lang)}</div>
<header class="hd">
 <div class="wrap hd-in">
  <a class="logo" href="{link(d, 'index.html', lang)}" aria-label="apetto"><img src="{asset(d, LOGO)}" alt="apetto"></a>
  <nav class="nav" aria-label="主選單">{nav_links(data, d, lang, current)}</nav>
  <div class="lang" aria-label="語言">{lang_links(site_rel, lang)}</div>
  <button class="burger" aria-label="選單" aria-expanded="false"><span class="bars"><i></i><i></i><i></i></span></button>
 </div>
</header>
<div class="mobile-menu" role="dialog" aria-label="選單"><div class="mm-panel">
  <div class="mm-top"><a href="{link(d, 'index.html', lang)}" aria-label="apetto"><img src="{asset(d, LOGO)}" alt="apetto"></a><button class="mm-close" aria-label="關閉">✕</button></div>
  <nav class="mm-nav">{nav_links(data, d, lang, current)}</nav>
  <nav class="mm-more"><a href="{link(d, "pages/5.html", lang)}">購物流程</a><a href="{link(d, "information/news.html", lang)}">最新消息</a><a href="{link(d, STORE, lang)}">漢堡店中店</a>{member_link}</nav>
  <div class="mm-social"><a href="{INSTAGRAM}" target="_blank" rel="noopener">Instagram</a><a href="{PINKOI}" target="_blank" rel="noopener">Pinkoi</a></div>
</div></div>"""


def footer(data, site_rel, lang):
    d = rel_dir(site_rel)
    links = [(SHOP, "商品分類"), ("search.html", "全系列"), (GUIDES, "商品指南"), (fit.PAGE, "試衣間"),
             ("pages/5.html", "購物流程"), ("information/news.html", "最新消息"), (ABOUT, "品牌故事"), (STORE, "漢堡店中店")] + ([(mem.PAGE, "會員專區")] if mem.config() else [])
    small = "".join(f'<a href="{link(d, sp, lang)}">{esc(t)}</a>' for sp, t in links)
    return f"""<footer class="ft">
 <div class="wrap">
  <div class="ft-in">
   <div class="brand"><img src="{asset(d, LOGO)}" alt="apetto"><p>為專業、機能狗衣而生</p><p>阻擋風雨，擁抱無憂的舒適時光</p>
    <div class="social"><a href="{INSTAGRAM}" target="_blank" rel="noopener">Instagram</a><a href="{PINKOI}" target="_blank" rel="noopener">Pinkoi</a></div></div>
   <div class="contact"><h4>聯絡我們</h4><ul><li><a href="mailto:info@hweider.url.tw">客服信箱：info@hweider.url.tw</a></li><li><a href="tel:+886289915001">連絡電話: 02-89915001</a></li><li>服務時間：週一~週五 10:00-12:00、14:00-18:00</li><li>LINE @apetto</li></ul></div>
  </div>
  <div class="ft-bottom"><nav class="ft-links">{small}</nav><span>Copyright ©2026 apetto 機能寵物衣 · <span class="ver">{VERSION}</span></span></div>
 </div>
</footer>"""


# Runs first in <head>: applies a colour-scheme preview (?palette=0-5, or ?palette=c&pc=<4 hex colours>) for this tab.
# The secondary colours of a custom scheme are mixed from its four colours (same formula as custom_vars below).
HEAD_JS = ('document.documentElement.className+=" js";'
    'function apX(a,b,t){var r="#";for(var i=0;i<6;i+=2){var v=Math.round(parseInt(a.substr(i,2),16)*(1-t)+parseInt(b.substr(i,2),16)*t);r+=(v<16?"0":"")+v.toString(16);}return r;}'
    'function apV(c){var bg=c[0],k=c[3];return "--bg:#"+bg+";--card:#"+c[1]+";--sand:#"+c[2]+";--ink:#"+k+";--line:"+apX(bg,k,.12)+";--line2:"+apX(bg,k,.2)+";--ink2:"+apX(k,bg,.25)+";--mute:"+apX(k,bg,.5)+";--brand-soft:"+apX(bg,"ff2414",.1);}'
    'try{var h=document.documentElement,ss=sessionStorage,L=location.search,m=L.match(/[?&]palette=([0-5c])/),q=L.match(/[?&]pc=([0-9a-fA-F]{24})/);'
    'if(q)ss.setItem("apetto_pc",q[1].toLowerCase());if(m)ss.setItem("apetto_palette",m[1]);var pv=ss.getItem("apetto_palette"),pc=(ss.getItem("apetto_pc")||"").match(/.{6}/g);'
    'if(pc&&pc.length===4)window.apPcStyle=apV(pc);'
    'if(pv){h.removeAttribute("style");if(pv==="0")h.removeAttribute("data-palette");else{h.setAttribute("data-palette",pv);if(pv==="c"&&window.apPcStyle)h.setAttribute("style",window.apPcStyle);}}}catch(e){}')


# Language by region, first visit only: browser language when it is one of ours (zh / ja / de), otherwise the
# country of the visitor's IP (Cloudflare trace, fallback api.country.is): TW HK MO CN SG -> zh, JP -> ja,
# DE AT CH LI -> de, anything else -> en. The result (or a click on a language link) is kept in localStorage
# apetto_lang, so this runs once. Only the Chinese (default) pages redirect; ?lang=x skips it; bots are left alone.
GEO_LANG_JS = (
    'try{var ls=localStorage,P=location.pathname,L=location.search,cur=(P.match(/\\.(en|ja|de)\\.html$/)||[])[1]||"zh";'
    'if(!ls.getItem("apetto_lang")&&cur==="zh"&&!/[?&]lang=/.test(L)&&!navigator.webdriver){'
    'var CC={TW:"zh",HK:"zh",MO:"zh",CN:"zh",SG:"zh",JP:"ja",DE:"de",AT:"de",CH:"de",LI:"de"},done=false;'
    'var go=function(l){if(done)return;done=true;ls.setItem("apetto_lang",l);if(l&&l!=="zh"){var b=P.replace(/\\/$/,"/index.html").replace(/\\.html$/,"."+l+".html");location.replace(b+L+location.hash);}};'
    'var nl=(navigator.language||"").toLowerCase();'
    'if(/^zh/.test(nl))go("zh");else if(/^ja/.test(nl))go("ja");else if(/^de/.test(nl))go("de");'
    'else{var ctl="AbortController"in window?new AbortController():null;setTimeout(function(){if(ctl)ctl.abort();},2500);'
    'fetch("https://www.cloudflare.com/cdn-cgi/trace",{cache:"no-store",signal:ctl&&ctl.signal}).then(function(r){return r.text();}).then(function(t){var c=(t.match(/^loc=(\\w+)/m)||[])[1];go(CC[c]||"en");})'
    '.catch(function(){fetch("https://api.country.is/",{signal:ctl&&ctl.signal}).then(function(r){return r.json();}).then(function(j){go(CC[j.country]||"en");}).catch(function(){});});}}}catch(e){}')
HEAD_JS = HEAD_JS + GEO_LANG_JS


def _mix(a, b, t):
    a, b = a.lstrip("#"), b.lstrip("#")
    return "#" + "".join("%02x" % round(int(a[i:i + 2], 16) * (1 - t) + int(b[i:i + 2], 16) * t) for i in (0, 2, 4))


def custom_vars(c):
    """CSS variables for a custom scheme {bg, card, sand, ink} chosen in the admin."""
    bg, card, sand, ink = (str(c.get(k) or "").lstrip("#").lower() for k in ("bg", "card", "sand", "ink"))
    if not all(re.fullmatch(r"[0-9a-f]{6}", x) for x in (bg, card, sand, ink)):
        return ""
    return (f"--bg:#{bg};--card:#{card};--sand:#{sand};--ink:#{ink};--line:{_mix(bg, ink, .12)};--line2:{_mix(bg, ink, .2)};"
            f"--ink2:{_mix(ink, bg, .25)};--mute:{_mix(ink, bg, .5)};--brand-soft:{_mix(bg, 'ff2414', .1)}")


def page(data, site_rel, lang, title, body, desc="", og_image=None, current="", body_class="", extra_head=""):
    d = rel_dir(site_rel)
    base = posixpath.basename(site_rel)
    alts = "".join(f'<link rel="alternate" hreflang="{HTML_LANG[c]}" href="{sb.lang_variant(base, c)}">' for c in LANG_CODES)
    og = f'<meta property="og:image" content="{esc(PUBLIC + og_image)}">' if og_image else ""
    cls = f' class="{body_class}"' if body_class else ""
    site_cfg = load_site()
    pal = site_cfg["palette"]
    pal_attr = f' data-palette="{pal}"' if pal in ("1", "2", "3", "4", "5") else ""
    if pal == "c" and custom_vars(site_cfg["palette_colors"]):
        pal_attr = f' data-palette="c" style="{custom_vars(site_cfg["palette_colors"])}"'
    return f"""<!DOCTYPE html>
<html lang="{HTML_LANG[lang]}"{pal_attr}>
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="color-scheme" content="light">
<title>{esc(title)}</title>
<meta name="description" content="{esc(desc)}">
<meta property="og:title" content="{esc(title)}"><meta property="og:description" content="{esc(desc)}"><meta property="og:type" content="website">{og}
<link rel="icon" href="{asset(d, 'favicon.ico')}" sizes="48x48">
<link rel="icon" type="image/png" sizes="32x32" href="{asset(d, 'assets/favicon-32.png')}">
<link rel="icon" type="image/png" sizes="192x192" href="{asset(d, 'assets/icon-192.png')}">
<link rel="apple-touch-icon" href="{asset(d, 'assets/icon-192.png')}">
<script>{HEAD_JS}</script>
<link rel="canonical" href="{esc(base)}">{alts}
<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="{FONTS}">
<link rel="stylesheet" href="{asset(d, 'assets/theme.css')}?v={ASSET_VER['css']}">
{extra_head}</head>
<body{cls}>
{header(data, site_rel, lang, current)}
<main>
{body}
</main>
{footer(data, site_rel, lang)}
<script src="{asset(d, 'assets/theme.js')}?v={ASSET_VER['js']}" defer></script>
<script src="{asset(d, 'assets/assistant.js')}?v={ASSET_VER['ai']}" data-lang="{lang}" data-logo="{asset(d, LOGO)}" data-api="{ai.API_BASE}" defer></script>
</body>
</html>"""


CSS += """
/* ---- strategy-deck additions: group tiles, shop page, guides, features ---- */
.tile .img{display:block}
.tile .subs{display:flex;flex-wrap:wrap;gap:6px;margin-top:4px}
.tile .subs a{display:inline-flex;align-items:center;gap:6px;height:32px;padding:0 12px;border-radius:999px;border:1.5px solid var(--line2);background:var(--card);font-size:13.5px;font-weight:600;color:var(--ink2)}
.tile .subs a:hover{border-color:var(--ink);color:var(--ink)}.tile .subs a i{font-style:normal;font-size:11px;color:var(--mute);font-weight:600}
.shop-group{scroll-margin-top:140px}.shop-group .sec-head p{margin-top:6px}
.shop-cat{margin-bottom:40px}.shop-cat:last-child{margin-bottom:0}
.shop-cat-head{display:flex;align-items:flex-end;justify-content:space-between;gap:16px;margin-bottom:16px}.shop-cat-head h3{font-size:22px}.shop-cat-head p{margin:4px 0 0;color:var(--mute);font-size:15px}
.shop-cat-head .more{white-space:nowrap;font-weight:700;color:var(--ink);border-bottom:2px solid var(--brand);padding-bottom:2px}
.soon{display:flex;align-items:center;gap:14px;background:var(--sand);border-radius:var(--radius);padding:20px 22px;color:var(--ink2)}
.soon .tag{background:var(--ink);color:#fff;font-size:12px;font-weight:700;padding:5px 10px;border-radius:999px;letter-spacing:.04em;white-space:nowrap}.soon p{margin:0}
.gcards{display:grid;grid-template-columns:repeat(4,1fr);gap:20px}
.gcard{display:flex;flex-direction:column;background:var(--card);border:1px solid var(--line);border-radius:var(--radius);padding:22px 22px 20px;transition:transform .2s,box-shadow .2s;color:var(--ink)}
.gcard:hover{transform:translateY(-4px);box-shadow:0 18px 40px rgba(0,0,0,.08)}
.gcard .num{font-size:12.5px;font-weight:800;letter-spacing:.1em;color:var(--brand-ink);margin-bottom:12px}
.gcard h3{font-size:19px;margin-bottom:8px}.gcard p{margin:0 0 18px;color:var(--mute);font-size:14.5px;line-height:1.6;flex:1}
.gcard .go{font-weight:700;color:var(--ink);border-bottom:2px solid var(--brand);align-self:flex-start;padding-bottom:2px}
.article.guide .ph p{font-size:18px}.article.guide h2{font-size:22px;margin:34px 0 10px}.article.guide ul{padding-left:22px}.article.guide li{margin:6px 0}
.article.guide .guide-cta{margin-top:32px}.article.guide .guide-cta .btn{color:#fff}.article.guide ul{list-style:disc}
.features .story{margin-bottom:56px}.features .story:last-child{margin-bottom:0}
@media (max-width:980px){.gcards{grid-template-columns:1fr;gap:14px}.shop-cat-head{flex-direction:column;align-items:flex-start;gap:6px}.features .story{margin-bottom:36px}.shop-group{scroll-margin-top:80px}}
"""
CSS += """
.fs-s{font-size:.85em}.fs-l{font-size:1.25em}.fs-xl{font-size:1.6em;line-height:1.35}.tc-brand{color:var(--brand-ink)}.tc-mute{color:var(--mute)}
.rich-text p{margin:0 0 .8em}.rich-text p:last-child{margin-bottom:0}.rich-text ul,.rich-text ol{padding-left:1.3em;margin:0 0 .8em}.rich-text ul{list-style:disc}.rich-text ol{list-style:decimal}
.rich-text h2,.rich-text h3,.rich-text h4{margin:.8em 0 .4em}.article ol{list-style:decimal;padding-left:22px}.article ul{list-style:disc;padding-left:22px}
.article blockquote,.rich-text blockquote{margin:1em 0;padding:.4em 0 .4em 1em;border-left:3px solid var(--brand);color:var(--ink2)}
"""
CSS += """
/* sub-category blocks */
.grp-cards{display:grid;grid-template-columns:repeat(3,1fr);gap:20px;align-items:start;margin:10px 0 64px}
.grp-card{background:var(--card);border:1px solid var(--line);border-radius:var(--radius);overflow:hidden;scroll-margin-top:140px}
.grp-card .img{aspect-ratio:16/9;background:var(--sand)}.grp-card .img img{width:100%;height:100%;object-fit:cover}
.grp-card .img{display:block}.grp-card .bd{padding:18px 20px 8px}.grp-card h2{font-size:22px;margin-bottom:4px}.grp-card h2 a{color:var(--ink)}.grp-card h2 a:hover{color:var(--brand-ink)}.grp-card h2 a span{font-size:.8em;color:var(--mute)}
.other-groups{margin-top:28px}.grp-card .bd>p{color:var(--mute);font-size:14.5px;margin:0 0 6px}
.grp-card ul{list-style:none;margin:0;padding:0 20px 10px}
.grp-card li a{display:flex;align-items:center;justify-content:space-between;gap:10px;padding:13px 0;border-top:1px solid var(--line);color:var(--ink);font-weight:600}
.grp-card li a:hover{color:var(--brand-ink)}.grp-card li small{font-weight:600;color:var(--mute);font-size:13px;white-space:nowrap}
.grp-card li a.empty{color:var(--ink2);font-weight:500}
@media (max-width:980px){.grp-cards{grid-template-columns:1fr;gap:16px}.grp-card{scroll-margin-top:80px}}
.shop-group{padding:28px 0 8px;scroll-margin-top:140px}.shop-group-head{margin-bottom:16px}.shop-group-head h2{font-size:clamp(22px,2.4vw,28px)}.shop-group-head p{margin:4px 0 0;color:var(--mute)}
.cat-cards{display:grid;grid-template-columns:repeat(3,1fr);gap:18px}
.cat-card{display:flex;flex-direction:column;background:var(--card);border:1px solid var(--line);border-radius:var(--radius);overflow:hidden;color:var(--ink);transition:border-color .15s}
.cat-card:hover{border-color:var(--ink)}
.cat-card .img{aspect-ratio:16/10;background:var(--sand);overflow:hidden}.cat-card .img img{width:100%;height:100%;object-fit:cover}
.cat-card .ph-empty{display:flex;align-items:center;justify-content:center;width:100%;height:100%}.cat-card .ph-empty img{width:56px;height:auto;opacity:.22;filter:grayscale(1)}
.cat-card .body{padding:14px 16px 16px;display:flex;flex-direction:column;gap:6px;flex:1}
.cat-card h3{font-size:18px}.cat-card p{margin:0;font-size:14px;color:var(--mute);line-height:1.5}
.cat-card .n{margin-top:auto;font-size:13.5px;font-weight:600;color:var(--ink2)}
.cat-card .tag{margin-top:auto;align-self:flex-start;background:var(--ink);color:#fff;font-size:12px;font-weight:700;padding:4px 10px;border-radius:999px}
.chips button{display:inline-flex;align-items:center;gap:6px;height:40px;padding:0 16px;border-radius:999px;border:1.5px solid var(--line2);background:var(--card);font-weight:600;font-size:15px;color:var(--ink2);cursor:pointer}
.chips button small{font-size:12px;font-weight:600;color:var(--mute)}
.chips button:hover{border-color:var(--ink);color:var(--ink)}.chips button.cur{background:var(--ink);border-color:var(--ink);color:#fff}.chips button.cur small{color:#c9ccd3}
.chips button.empty{color:var(--mute)}
.grid-box[hidden],.product-grid[hidden]{display:none}
@media (max-width:980px){.cat-cards{grid-template-columns:repeat(2,1fr);gap:12px}.cat-card .body{padding:12px 12px 14px}.cat-card h3{font-size:16px}.shop-group{scroll-margin-top:80px}}
"""
CSS += """
/* words marked by the script above: break only between them (a word wider than the line still wraps) */
:lang(zh) .wb,:lang(zh) .wb *{word-break:keep-all;overflow-wrap:anywhere}
/* CJK line breaking.
   zh: names, buttons and labels never split inside a word (they break at spaces / punctuation; a run that is wider than the line still wraps).
   ja: the browser's phrase detection. Headings and short text are balanced so no line ends up with one or two characters. */
:lang(zh) :is(.btn,.chips a,.chips button,.nav a,.mm-nav a,.lang a,.grid-box .name,.product-heading-title,.cat-card h3,.cat-card .sub,.tag,.badge,.news-list b,.ft-links a,.breadcrumb li,label,summary,.fit-coat .nm,.fit-coat .sub){word-break:keep-all;overflow-wrap:anywhere}
:lang(ja) :is(h1,h2,h3,h4,p,li,.btn,.chips a,.chips button,.nav a,.mm-nav a,.grid-box .name,.product-heading-title,.cat-card .sub,.eyebrow,.tag,.badge,.news-list b,.steps div,.ship h3,label,summary,.fit-coat .nm,.fit-coat .sub){word-break:auto-phrase}
:is(h4,.lead,.ph p,.cat-card p,.gcard p,.feat p,.soon p,.quote p,.fit-promo p,.grid-box .name,.news-list b,.eyebrow,.steps div,.ship h3,.product-heading-title){text-wrap:balance}
:is(.article p,.article li,.rich p,.rich li,.rich-text p,.rich-text li,.story p,.notebox p){text-wrap:pretty}
.fit-coat span{text-wrap:balance}
:lang(ja){line-break:strict}
"""
CSS = CSS + mem.CSS + '''
/* Shop-in-Shop page */
.store-head{padding:28px 0 22px}.store-head h1{font-size:clamp(30px,4.4vw,46px);line-height:1.12;margin:0 0 12px;letter-spacing:-.01em}.store-head .lead{font-size:17px;color:var(--ink2);max-width:62ch;margin:0}
.store-photo{border-radius:20px;overflow:hidden;aspect-ratio:16/8;margin:0 0 20px;background:var(--sand)}.store-photo img{width:100%;height:100%;object-fit:cover;object-position:50% 60%;display:block}
@media (max-width:860px){.store-photo{aspect-ratio:4/3}}
.store-foot{margin:4px 0 40px;padding:20px 22px;border-radius:16px;background:var(--sand);display:grid;gap:14px}.store-foot p{margin:0;font-size:15.5px;line-height:1.6;color:var(--ink2);max-width:62ch}.store-foot nav{display:flex;flex-wrap:wrap;gap:10px}.store-foot nav a{display:inline-flex;align-items:center;min-height:40px;padding:0 16px;border-radius:999px;border:1.5px solid var(--line2);background:var(--card);color:var(--ink);font-size:14.5px;font-weight:600;text-decoration:none}.store-foot nav a:hover{border-color:var(--brand);color:var(--brand)}
.store-grid{display:grid;grid-template-columns:minmax(0,1fr) minmax(0,1.1fr);gap:20px;align-items:stretch;margin-bottom:12px}
.store-card{background:var(--card);border:1px solid var(--line);border-radius:20px;padding:26px 26px 22px;display:flex;flex-direction:column;gap:10px}.store-card h2{margin:0;font-size:24px;line-height:1.25}.store-card .store-sub{margin:-4px 0 6px;color:var(--mute);font-size:14px}
.store-card address{display:flex;gap:12px;align-items:flex-start;font-style:normal;font-size:18px;line-height:1.5;padding:14px 16px;border-radius:14px;background:var(--sand)}.store-card address svg{width:26px;height:26px;flex:0 0 auto;color:var(--brand)}.store-card address em{font-style:normal;color:var(--mute);font-size:14px}
.store-acts{display:flex;flex-wrap:wrap;gap:10px;margin-top:6px}.store-acts .btn{min-height:44px;padding:0 18px;font-size:15px}
.store-note{margin:10px 0 0;font-size:13.5px;color:var(--mute);line-height:1.55}
.store-map{position:relative;min-height:320px;border-radius:20px;overflow:hidden;border:1px solid var(--line);background:var(--sand)}.store-map iframe{position:absolute;inset:0;width:100%;height:100%;border:0}
.store-map .map-load{position:absolute;inset:0;display:flex;flex-direction:column;align-items:center;justify-content:center;gap:6px;border:0;background:var(--sand);color:var(--ink);font:inherit;cursor:pointer;padding:24px;text-align:center}.store-map .map-load svg{width:40px;height:40px;color:var(--brand)}.store-map .map-load b{font-size:18px}.store-map .map-load span{color:var(--ink2)}.store-map .map-load small{color:var(--mute);font-size:12.5px;max-width:36ch}.store-map .map-load:hover{background:var(--line)}
@media (max-width:860px){.store-grid{grid-template-columns:1fr}.store-map{min-height:260px}}
''' + fit.CSS + ai.CSS + '\n/* warmer colour schemes, previewed with ?palette=1..5 (the red logo colour stays the same) */\nhtml[data-palette="1"]{--bg:#efe0c9;--card:#fbf3e6;--sand:#e2caa6;--line:#dbc4a2;--line2:#cdb08a;--ink:#3a2a1e;--ink2:#5c4636;--mute:#86705c;--brand-soft:#fbe3d6}\nhtml[data-palette="2"]{--bg:#ffe4d4;--card:#fff4ec;--sand:#ffcfb5;--line:#f6c3a6;--line2:#ebac8b;--ink:#3d211a;--ink2:#64392e;--mute:#93665a;--brand-soft:#ffd9cc}\nhtml[data-palette="3"]{--bg:#fbeebb;--card:#fffaea;--sand:#f4dc8e;--line:#ead48a;--line2:#dcc070;--ink:#3a3115;--ink2:#5d5128;--mute:#857a4f;--brand-soft:#ffe6cf}\nhtml[data-palette="4"]{--bg:#e6e8d6;--card:#f8f7ee;--sand:#d3d8bb;--line:#cbd0b3;--line2:#b7bd9a;--ink:#2f3526;--ink2:#4c533f;--mute:#737a63;--brand-soft:#fbe5dc}\nhtml[data-palette="5"]{--bg:#e6cdaa;--card:#f7ecdb;--sand:#d6b285;--line:#d3b48c;--line2:#c19b6c;--ink:#3a2213;--ink2:#5e3f2a;--mute:#7f6249;--brand-soft:#f8dccb}\n.pal-bar{position:fixed;left:12px;top:50%;transform:translateY(-50%);z-index:9998;display:flex;flex-direction:column;gap:6px;background:#fff;color:#17181a;border:1px solid #ddd;border-radius:16px;padding:10px;box-shadow:0 8px 30px rgba(0,0,0,.18);font:600 13px/1.2 system-ui,"Noto Sans TC",sans-serif}\n.pal-bar b{font-size:12px;color:#666;padding:0 4px 2px}\n.pal-bar button{display:flex;align-items:center;gap:8px;border:1.5px solid #ddd;background:#fff;color:#17181a;border-radius:999px;padding:6px 12px 6px 6px;cursor:pointer;font:inherit;text-align:left}\n.pal-bar button i{width:22px;height:22px;border-radius:50%;flex:0 0 auto;border:1px solid rgba(0,0,0,.15)}\n.pal-bar button.cur{border-color:#ff2414;box-shadow:0 0 0 2px #ff2414 inset}\n.pal-bar .x{justify-content:center;padding:6px;color:#666}\n@media (max-width:700px){.pal-bar{top:auto;bottom:12px;transform:none;left:8px;right:8px;flex-direction:row;flex-wrap:wrap;justify-content:center;padding:8px}.pal-bar b{width:100%;text-align:center}.pal-bar button{padding:5px 10px 5px 5px}}\n'
ASSET_VER = {"css": digest(CSS), "js": digest(JS), "fit": digest(fit.JS), "ai": digest(ai.JS)}


# ----------------------------------------------------------------- components
def product_card(p, page_dir, lang, tag=None, attrs=""):
    url = link(page_dir, sb.product_page(p), lang)
    sq = crop(p["image"]["full"], "sq")
    thumb = asset(page_dir, sq if sq != p["image"]["full"] else (p["image"]["thumb"] or p["image"]["full"]))
    badge = ""
    if tag == "hot":
        badge = '<span class="tag hot">熱賣</span>'
    elif tag == "new":
        badge = '<span class="tag">最新</span>'
    return (f'<a class="grid-box" href="{url}" data-producttlid="{p["id"]}" data-zh-name="{esc(p["name"])}"{attrs}>'
            f'<div class="image"><img src="{thumb}" alt="{esc(p["name"])}" loading="lazy"></div>{badge}'
            f'<div class="inner"><div class="name">{esc(p["name"])}</div><div class="price">{price_text(p["price"])}</div></div></a>')


def product_grid(items, page_dir, lang, tag=None, cls=""):
    if not items:
        return f'<p class="empty">目前沒有商品</p>'
    return f'<div class="product-grid {cls}">' + "".join(product_card(p, page_dir, lang, tag) for p in items) + "</div>"


def section(title, body, sub="", more=None, sid="", cls="", page_dir="", lang="zh"):
    more_html = f'<a class="more" href="{link(page_dir, more[0], lang)}">{esc(more[1])}</a>' if more else ""
    sub_html = f"<p>{esc(sub)}</p>" if sub else ""
    idattr = f' id="{sid}"' if sid else ""
    return (f'<section class="sec {cls}"{idattr}><div class="wrap"><div class="sec-head rv"><div><h2>{esc(title)}</h2>{sub_html}</div>{more_html}</div>'
            f'<div class="rv">{body}</div></div></section>')


# ----------------------------------------------------------------- pages
def render_home(data, visible, lang):
    """Home: hero, recommended products, the fitting room, latest news. Everything else lives on its own page."""
    d = ""
    latest = [p for p in visible if "latest" in p.get("sections", [])]
    site = load_site()
    news_html = "".join(f'<a href="{link(d, news_page(n), lang)}"><time>{esc(n.get("date", ""))}</time><b>{esc(news_text(n, lang, "title"))}</b></a>' for n in load_news()[:4])
    news_html = f'<div class="news-list home">{news_html}</div>' if news_html else ""
    body = f"""<section class="hero"><div class="wrap hero-in">
 <div class="rv in"><span class="eyebrow">{esc(BRAND)}</span><h1>{esc(site["hero"]["title"])}</h1>
  <p class="lead">{esc(site["hero"]["lead"])}</p>
  <div class="cta"><a class="btn brand" href="{link(d, SHOP, lang)}">商品分類</a><a class="btn" href="{link(d, fit.PAGE, lang)}">試衣間</a></div>
  <div class="hero-badges"><span class="badge"><i></i>耐水壓 10000mmH2O</span><span class="badge"><i></i>3M 反光條</span><span class="badge"><i></i>台灣設計製造</span></div>
 </div>
 <div class="hero-img rv in"><img src="{asset(d, IMG['hero'])}" alt="apetto" fetchpriority="high"></div>
</div></section>
{section('推薦商品', product_grid(latest, d, lang, tag='new'), more=(SHOP, '查看全部'), sid='latest-products', cls='tight', page_dir=d, lang=lang) if latest else ''}
{fit.home_promo(d, lang)}
{section('最新消息', news_html, more=('information/news.html', '查看全部'), sid='home-news', cls='tight', page_dir=d, lang=lang) if news_html else ''}
<div style="height:24px"></div>"""
    return page(data, "index.html", lang, HOME_TITLE, body, HOME_DESC, og_image=IMG["hero"], current="index.html")


def category_chips(data, page_dir, lang, current):
    chips = f'<a href="{link(page_dir, "search.html", lang)}"{cur(current == "all")}>全系列</a>'
    for g in groups_of(data):
        for c in cats_in(data, g["key"]):
            chips += f'<a href="{link(page_dir, sb.category_page(c["id"]), lang)}"{cur(current == c["id"])}>{esc(c["name"])}</a>'
    return f'<div class="chips">{chips}</div>'


def render_listing(data, site_rel, lang, title, items, sub="", current="all", search=False):
    d = rel_dir(site_rel)
    count = f'<div class="pagination"><p class="results">共 {len(items)} 件商品</p></div>' if not search else '<div class="pagination"><p class="results"></p></div>'
    box = (f'<form class="bigsearch" action="{sb.lang_variant("search.html", lang)}" role="search"><input type="search" name="q" placeholder="輸入關鍵字，例如「斗篷」或「保暖」" aria-label="搜尋商品" autocomplete="off">'
           f'<button type="submit" aria-label="搜尋">{ICON_SEARCH}</button></form>') if search else ""
    body = f"""<div class="wrap">
<ol class="breadcrumb"><li><a href="{link(d, 'index.html', lang)}">首頁</a></li>{f'<li><a href="{link(d, SHOP, lang)}">商品分類</a></li>' if isinstance(current, int) else ''}<li><span>{esc(title)}</span></li></ol>
<div class="ph"><h1>{esc(title)}</h1>{f'<p>{esc(sub)}</p>' if sub else ''}</div>
{box}
{category_chips(data, d, lang, current)}
{count}
{product_grid(items, d, lang)}
<div style="height:48px"></div>
</div>"""
    return page(data, site_rel, lang, f"{title} | {BRAND}", body, sub or title, current=SHOP if isinstance(current, int) else "")


def gallery_html(p, d):
    name = p["name"]
    fulls = [p["image"]["full"]] + [g["full"] for g in p.get("gallery", [])]
    main = asset(d, crop(fulls[0], "w43"))
    lis = "".join(f'<li{cur(i == 0)}><a href="{asset(d, crop(f, "w43"))}" title="{esc(name)}"><img src="{asset(d, crop(f, "sq"))}" alt="{esc(name)}" loading="lazy"></a></li>'
                  for i, f in enumerate(fulls))
    hidden = "" if len(fulls) > 1 else " hidden"
    return (f'<div class="gallery"><div class="gal-main"><img id="main-defer-image" src="{main}" alt="{esc(name)}"></div>'
            f'<ul id="image-additional" class="thumbs"{hidden}>{lis}</ul></div>')


def options_html(p, lang):
    if not p.get("options"):
        return '<div id="options" hidden></div>'
    groups = ""
    for i, opt in enumerate(p["options"]):
        labels = ""
        for j, val in enumerate(opt["values"]):
            inp = f'<input type="radio" name="option[{100 + i}]" value="{esc(val)}"{" checked" if j == 0 else ""}>' if lang == "zh" else ""
            labels += f'<label class="checkbox">{inp}{esc(val)}</label>'
        groups += (f'<div class="control-group" data-option-name="{esc(opt["name"])}"><label class="control-label"><b>{esc(opt["name"])}</b></label>'
                   f'{labels}</div>')
    return f'<div id="options">{groups}</div>'


def render_product(data, visible, p, lang, overrides):
    site_rel = sb.product_page(p)
    d = rel_dir(site_rel)
    o = overrides.get(lang) or {}
    name = p["name"]
    cats = [c for c in data["categories"] if c["id"] in p.get("categories", [])]
    cat = cats[0] if cats else None
    desc_text = (o.get("summary") or p.get("summary") or re.sub(r"<[^>]+>", " ", p.get("feature_html", "")) or name)
    desc_text = re.sub(r"\s+", " ", desc_text).strip()[:200]
    feature = o.get("feature_html") or p.get("feature_html", "")
    description = o.get("description_html") or p.get("description_html", "")
    online_url = f"{sb.ONLINE}product/product&product_id={p['id']}"
    if lang == "zh":
        buy = (f'<div class="buy"><a class="btn big brand" href="{esc(buy_link(p, data))}" target="_blank" rel="noopener">立即購買</a>'
               f'<p class="buy-note">將前往官方賣場完成結帳</p>'
               f'<a class="buy-help" href="{link(d, "pages/5.html", lang)}">購物流程<span aria-hidden="true"> →</span></a></div>')
    else:
        buy = (f'<p class="showcase-note">本站為商品介紹，購買請至台灣官方商店。 <a href="{esc(online_url)}" target="_blank" rel="noopener">前往官方商店<span aria-hidden="true"> →</span></a></p>'
               f'<a class="buy-help" href="{link(d, "pages/5.html", lang)}">購物流程<span aria-hidden="true"> →</span></a>')
    related = [q for q in visible if q["id"] != p["id"] and (not cat or cat["id"] in q.get("categories", []))][:4]
    crumbs = f'<li><a href="{link(d, "index.html", lang)}">首頁</a></li><li><a href="{link(d, SHOP, lang)}">商品分類</a></li>'
    if cat:
        crumbs += f'<li><a href="{link(d, sb.category_page(cat["id"]), lang)}">{esc(cat["name"])}</a></li>'
        ptype = next((t for t in types_of(cat) if t["key"] in (p.get("types") or [])), None)
        if ptype:
            crumbs += f'<li><a href="{link(d, sb.category_page(cat["id"]), lang)}#type-{esc(ptype["key"])}">{esc(ptype["name"])}</a></li>'
    crumbs += f"<li><span>{esc(name)}</span></li>"
    ld = {"@context": "https://schema.org", "@type": "Product", "productID": str(p["id"]), "name": name, "description": desc_text,
          "image": [PUBLIC + p["image"]["full"]] + [PUBLIC + g["full"] for g in p.get("gallery", [])],
          "brand": {"@type": "Brand", "name": "apetto"}, "url": online_url,
          "offers": {"@type": "Offer", "priceCurrency": "TWD", "price": str(p["price"]), "availability": "https://schema.org/InStock", "url": online_url}}
    body = f"""<div class="wrap">
<ol class="breadcrumb">{crumbs}</ol>
<div class="pd">
 {gallery_html(p, d)}
 <div class="pi">
  {f'<a class="cat" href="{link(d, sb.category_page(cat["id"]), lang)}">{esc(cat["name"])}</a>' if cat else ''}
  <h1 class="product-heading-title">{esc(name)}</h1>
  <div class="price product-sell-price" data-content="{p['price']}">{price_text(p['price'])}</div>
  <div class="product-feature-content">{clean_rich_html(feature, d)}</div>
  {options_html(p, lang)}
  {buy}
  <input type="hidden" id="product_id" value="{p['id']}">
 </div>
</div>
<section class="pd-desc"><h2>商品介紹</h2><div id="tab-description" class="rich">{clean_rich_html(description, d, lang)}</div></section>
</div>
{section('相關商品', product_grid(related, d, lang), cls='tight', page_dir=d, lang=lang) if related else ''}"""
    extra = f'<script type="application/ld+json">{json.dumps(ld, ensure_ascii=False)}</script>\n'
    return page(data, site_rel, lang, f"{name} | {BRAND}", body, desc_text, og_image=p["image"]["full"],
                current=SHOP, body_class="" if lang == "zh" else "showcase", extra_head=extra)


# ----------------------------------------------------------------- info pages (about / terms / news / announcements)
INFO_TITLES = {"pages/4.html": "品牌故事", "pages/5.html": "購物流程", "pages/hamburg.html": "漢堡店中店", "information/news.html": "最新消息", "information/notice.html": "最新消息"}
INFO_PARENT = {"information/news&news_id=1.html": "information/news.html", "information/notice&notice_id=1.html": "information/news.html"}


def _info_soup(rel):
    tpl = sb.TPL / "info" / rel
    if not tpl.exists():
        return None
    return BeautifulSoup(tpl.read_text(encoding="utf-8").lstrip("﻿"), "lxml")


def _article_body(container):
    """Shop-editor HTML -> clean article HTML."""
    frag = BeautifulSoup(str(container), "html.parser")
    root = frag.find(True)
    for c in root.find_all(string=lambda s: isinstance(s, Comment)):
        c.extract()
    for el in root.select(".share, script, style"):
        el.decompose()
    for ifr in root.find_all("iframe"):
        src = ifr.get("src", "")
        m = re.search(r"href=([^&]+)", src)
        if m and "facebook.com" in src:
            a = frag.new_tag("a", href=html_mod.unescape(sb.unquote(m.group(1))), target="_blank", rel="noopener")
            a.string = "在 Facebook 查看貼文"
            ifr.replace_with(a)
        else:
            ifr.decompose()
    for tag in root.find_all(True):
        for a in list(tag.attrs):
            if a.startswith("on") or a in ("style", "dir", "id", "class", "role", "tabindex"):
                del tag[a]
        if tag.name == "span":
            tag.unwrap()
    for tag in root.find_all(["p", "b", "strong", "div"]):
        if not tag.get_text(strip=True) and not tag.find(["img", "a"]):
            tag.decompose()
    for br in root.find_all("br"):
        if br.parent is root:
            br.decompose()
    return "".join(str(c) for c in root.contents)


def info_items(rel):
    """[(date, title, site_path)] of a news / notice list page."""
    soup = _info_soup(rel)
    out = []
    if soup is None:
        return out
    d = rel_dir(rel)
    for li in soup.select("#content ul li"):
        a = li.select_one("a[href]")
        if not a:
            continue
        small = li.select_one("small")
        out.append((small.get_text(strip=True) if small else "", a.get_text(" ", strip=True).replace(" ", " "),
                    sb.to_site_path(d, a["href"].replace("&amp;", "&"))))
    return out


def render_info(data, rel, lang):
    soup = _info_soup(rel)
    if soup is None:
        return None
    d = rel_dir(rel)
    title = INFO_TITLES.get(rel) or soup.title.get_text().split(" | ")[0].replace("\xa0", " ").strip()
    crumbs = f'<li><a href="{link(d, "index.html", lang)}">首頁</a></li>'
    parent = INFO_PARENT.get(rel)
    if parent:
        crumbs += f'<li><a href="{link(d, parent, lang)}">{esc(INFO_TITLES[parent])}</a></li>'
    crumbs += f"<li><span>{esc(title)}</span></li>"
    if rel == "pages/4.html":
        return render_about(data, rel, lang, crumbs)
    if rel == "pages/5.html":
        return render_terms(data, rel, lang, crumbs)
    if rel in ("information/news.html", "information/notice.html"):
        title = "最新消息"
        crumbs = f'<li><a href="{link(d, "index.html", lang)}">首頁</a></li><li><span>{esc(title)}</span></li>'
        merged = sorted(info_items("information/news.html") + info_items("information/notice.html"), key=lambda x: x[0], reverse=True)
        items = ""
        for date, title_i, target in merged:
            href_v = link(d, target, lang) if sb._LOCALIZED_RE.match(target) else sb.href(d, target)
            items += f'<a href="{href_v}"><time>{esc(date)}</time><b>{esc(title_i)}</b></a>'
        content = f'<div class="news-list">{items or "<p class=empty>目前沒有商品</p>"}</div>'
        body = f'<div class="wrap"><ol class="breadcrumb">{crumbs}</ol><div class="ph"><h1>{esc(title)}</h1></div><div style="height:24px"></div>{content}</div>'
    else:
        container = soup.select_one(".info-inner") or soup.select_one(".content-news .news") or soup.select_one("#content")
        inner = _article_body(container) if container else ""
        frag = BeautifulSoup(inner, "html.parser")
        first = frag.find(["p", "h1", "h2", "h3"])
        heading = title
        if first is not None:
            ftxt = first.get_text(" ", strip=True).replace("\xa0", " ")
            if ftxt and (ftxt == title or len(ftxt) <= 24 and (first.find(["strong", "b"]) or first.name.startswith("h"))):
                heading = ftxt if ftxt != title else title
                first.decompose()
        inner = str(frag)
        # the About page: contact lines after "--" become a contact card
        parts = re.split(r"<p>\s*--\s*</p>", inner, 1)
        if len(parts) == 2 and parts[1].strip():
            inner = parts[0] + f'<div class="contact">{parts[1]}</div>'
        date = ""
        if parent:
            for dt, _t, target in info_items("information/news.html") + info_items("information/notice.html"):
                if posixpath.basename(target) == posixpath.basename(rel):
                    date = dt
        intro = story_block(d) if rel == "pages/4.html" else ""
        body = (f'<div class="wrap"><ol class="breadcrumb">{crumbs}</ol></div>{intro}<div class="wrap"><article class="article"><div class="ph"><h1>{esc(heading)}</h1></div>'
                f'{f"<p class=date>{esc(date)}</p>" if date else "<div style=height:20px></div>"}{inner}</article></div>')
    return page(data, rel, lang, f"{title} | {BRAND}", body, title, current=rel if rel in INFO_TITLES else "")


def story_block(d):
    return f"""<section class="sec tight"><div class="wrap"><div class="story rv">
 <div class="story-img zoom"><img src="{asset(d, IMG['story'])}" alt="" loading="lazy"></div>
 <div><span class="eyebrow">為專業、機能狗衣而生</span><h2>陪你走過每一個下雨的日子</h2>
  <p>無論是春日裡的梅雨，還是冬日裡的綿綿細雨，每一個下雨的日子，apetto 狗衣系列，讓毛孩子盡情在戶外奔跑。</p>
  <p>apetto 提供高品質、防風保護，頂級布料耐水壓 10000mmH2O，水滴在布料上能輕易滑落，提供舒適的防水防護。</p></div>
</div></div></section>"""


ICON_PAW = ('<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" aria-hidden="true">'
            '<ellipse cx="7" cy="8" rx="2" ry="2.6"/><ellipse cx="17" cy="8" rx="2" ry="2.6"/><ellipse cx="4.5" cy="13" rx="1.8" ry="2.2"/><ellipse cx="19.5" cy="13" rx="1.8" ry="2.2"/>'
            '<path d="M12 11c3 0 6 3.2 6 6a3 3 0 0 1-3 3c-1.2 0-2-.5-3-.5s-1.8.5-3 .5a3 3 0 0 1-3-3c0-2.8 3-6 6-6z"/></svg>')
ICON_BUDDY = ('<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">'
              '<path d="M4 20v-5a4 4 0 0 1 4-4h2"/><circle cx="8" cy="6" r="3"/><path d="M12 20l1-5 3-3 3 3 1 5"/><path d="M16 12V9l3-2"/><circle cx="16" cy="6.5" r="1.3"/></svg>')
ICON_HEART = ('<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">'
              '<path d="M12 20s-7-4.4-7-10a4 4 0 0 1 7-2.6A4 4 0 0 1 19 10c0 5.6-7 10-7 10z"/><path d="M12 7.4V20"/></svg>')
ICON_MAIL = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><rect x="3" y="5" width="18" height="14" rx="2"/><path d="m3 7 9 6 9-6"/></svg>'
ICON_PHONE = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M5 4h4l2 5-2.5 1.5a11 11 0 0 0 5 5L15 13l5 2v4a2 2 0 0 1-2 2A16 16 0 0 1 3 6a2 2 0 0 1 2-2"/></svg>'
ICON_CLOCK = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" aria-hidden="true"><circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/></svg>'
ICON_LINE = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linejoin="round" aria-hidden="true"><path d="M12 4C7 4 3 7.2 3 11.2c0 3.5 3 6.4 7.2 7l-.4 2.8 3.4-2.1c4.5-.3 7.8-3.3 7.8-7.7C21 7.2 17 4 12 4z"/></svg>'


def render_about(data, rel, lang, crumbs):
    d = rel_dir(rel)
    body = f"""<div class="wrap"><ol class="breadcrumb">{crumbs}</ol></div>
{story_block(d)}
<section class="sec tight"><div class="wrap">
 <div class="about-lead rv"><span class="eyebrow">關於 apetto</span><h2>起源自 a pet to … 的發想，進而誕生了 apetto。</h2>
  <p>每一位毛小孩對我們而言，都是獨一無二的寶貝，更是生命軌跡中的一部分。</p></div>
 <div class="cards3 rv">
  <div>{ICON_PAW}<h3>一起長大</h3><p>有的毛小孩陪著我們一起長大，成為我們的手足。</p></div>
  <div>{ICON_BUDDY}<h3>成年後加入</h3><p>有的毛小孩在我們成年後加入，成為了最佳戰友。</p></div>
  <div>{ICON_HEART}<h3>年老時相伴</h3><p>有的毛小孩在年老時來到身邊，璀璨了遲暮之年。</p></div>
 </div>
 <div class="quote rv"><p>毛小孩是我們最忠實且貼心的家人。</p></div>
 <div class="story flip rv">
  <div class="story-img"><img src="{asset(d, IMG['rain'])}" alt="" loading="lazy"></div>
  <div><span class="eyebrow">{esc(BRAND)}</span><h2>為專業、機能狗衣而生</h2>
   <p>apetto 擁有強大的團隊，因著照顧家人的心，為毛小孩們設計出高機能且時尚的衣服。</p>
   <p>其具有防水及透氣功能，讓我們的毛孩子們在下雨天也可以盡情奔跑。</p>
   <a class="btn" href="{link(d, 'search.html', lang)}">瀏覽全系列</a></div>
 </div>
</div></section>
<section class="sec tight"><div class="wrap">
 <div class="sec-head rv"><div><h2>聯絡我們</h2></div></div>
 <div class="contact-grid rv">
  <a href="mailto:info@hweider.url.tw">{ICON_MAIL}<span>客服信箱：info@hweider.url.tw</span></a>
  <a href="tel:+886289915001">{ICON_PHONE}<span>連絡電話: 02-89915001</span></a>
  <div>{ICON_CLOCK}<span>服務時間：週一~週五 10:00-12:00、14:00-18:00</span></div>
  <div>{ICON_LINE}<span>LINE @apetto</span></div>
 </div>
 <p class="about-foot">apetto © 匯得興業有限公司</p>
</div></section>"""
    return page(data, rel, lang, f"品牌故事 | {BRAND}", body, "關於 apetto", og_image=IMG["story"], current=rel)


ICON_PIN = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M12 21s-6-5.4-6-10a6 6 0 0 1 12 0c0 4.6-6 10-6 10z"/><circle cx="12" cy="11" r="2.2"/></svg>'
STORE_NAME = "Shop-in-Shop in Hamburg"
STORE_HOST = "陳美英中文書屋 × bis Buchladen"
STORE_STREET, STORE_CITY = "Weidenallee 4", "20357 Hamburg"
STORE_FB = "https://www.facebook.com/bisBuchladen/"
STORE_Q = "Weidenallee+4,+20357+Hamburg"
STORE_PHOTO = "assets/store/hamburg-1.jpg"   # inside the bookshop, from the owner


def render_store(data, lang):
    rel = STORE
    d = rel_dir(rel)
    crumbs = f'<li><a href="{link(d, "index.html", lang)}">首頁</a></li><li><span>漢堡店中店</span></li>'
    hl = {"zh": "zh-TW", "en": "en", "ja": "ja", "de": "de"}[lang]
    embed = f"https://www.google.com/maps?q={STORE_Q}&z=16&hl={hl}&output=embed"
    ld = json.dumps({"@context": "https://schema.org", "@type": "Store", "name": "apetto " + STORE_NAME,
                     "address": {"@type": "PostalAddress", "streetAddress": STORE_STREET, "postalCode": "20357", "addressLocality": "Hamburg", "addressCountry": "DE"},
                     "containedInPlace": {"@type": "BookStore", "name": STORE_HOST, "sameAs": STORE_FB}}, ensure_ascii=False)
    body = f"""<div class="wrap"><ol class="breadcrumb">{crumbs}</ol>
<div class="store-head rv in"><span class="eyebrow">apetto 在德國</span><h1>{esc(STORE_NAME)}</h1>
 <p class="lead">apetto 的機能狗衣，現在可以在漢堡親手摸到、現場試穿。店中店位於 Eimsbüttel 的「陳美英中文書屋 × bis Buchladen」。</p></div>
<div class="store-photo rv in"><img src="{asset(d, STORE_PHOTO)}" alt="{esc(STORE_HOST)}"></div>
<div class="store-grid rv in">
 <div class="store-card">
  <span class="eyebrow">地址</span>
  <h2>{esc(STORE_HOST)}</h2>
  <p class="store-sub">店中店位於書店內</p>
  <address>{ICON_PIN}<span>{esc(STORE_STREET)}<br>{esc(STORE_CITY)}<br><em>漢堡 · 德國</em></span></address>
  <div class="store-acts">
   <a class="btn" href="https://www.google.com/maps/dir/?api=1&destination={STORE_Q}" target="_blank" rel="noopener">規劃路線</a>
   <a class="btn ghost" href="https://www.google.com/maps/search/?api=1&query={STORE_Q}" target="_blank" rel="noopener">在 Google 地圖開啟</a>
   <a class="btn ghost" href="{STORE_FB}" target="_blank" rel="noopener">Facebook 專頁</a>
  </div>
 </div>
 <div class="store-map"><button type="button" class="map-load" data-src="{esc(embed)}">{ICON_PIN}<b>載入地圖</b><span>{esc(STORE_STREET)}, {esc(STORE_CITY)}</span><small>地圖由 Google 提供，點擊後才會載入。</small></button></div>
</div></div>
<div class="store-foot rv in"><p>帶毛孩一起來，可以現場試穿、直接購買。營業時間請先透過 Facebook 向店家確認。</p>
 <nav><a href="{link(d, GUIDES, lang)}">尺寸怎麼量</a><a href="{link(d, fit.PAGE, lang)}">線上試衣間</a></nav></div></div>"""
    return page(data, rel, lang, "漢堡店中店 | apetto", body, "apetto 在漢堡的店中店：Weidenallee 4, 20357 Hamburg。親手感受機能狗衣，帶毛孩現場試穿、直接購買。",
                og_image=STORE_PHOTO, current=rel, extra_head=f'<script type="application/ld+json">{ld}</script>')


ICON_CART = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M3 4h2l2.4 11h11l2-7H6.5"/><circle cx="9" cy="19" r="1.5"/><circle cx="17" cy="19" r="1.5"/></svg>'
ICON_CARD = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><rect x="3" y="6" width="18" height="12" rx="2"/><path d="M3 10h18M7 14h4"/></svg>'
ICON_TRUCK = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linejoin="round" aria-hidden="true"><path d="M3 7h11v9H3zM14 10h4l3 3v3h-7z"/><circle cx="7" cy="17" r="1.6"/><circle cx="17" cy="17" r="1.6"/></svg>'


def render_terms(data, rel, lang, crumbs):
    d = rel_dir(rel)
    steps = "".join(f"<div>{esc(t)}</div>" for t in ("選購商品", "加入購物車", "填寫資料與送貨方式", "選擇付款方式結帳", "email 出貨通知", "收到商品"))
    body = f"""<div class="wrap"><ol class="breadcrumb">{crumbs}</ol>
<section class="sec tight">
 <div class="terms-intro rv"><span class="eyebrow">購物流程</span><h2>親愛的毛主人們，歡迎來到 apetto。</h2>
  <p>在享受為毛小孩添購新衣的同時，為了擁有良好的購物過程，請您詳閱以下說明事項，可以更瞭解我們的付款方式與出貨流程。謝謝!</p></div>
 <div class="tsec rv"><h2>{ICON_CART}訂購步驟</h2><div class="steps">{steps}</div></div>
 <div class="tsec rv"><h2>{ICON_CARD}付款方式</h2><div class="cards2">
  <div><h3>ATM 轉帳</h3><p>請於 3 日內付款，付款後請使用「填寫匯款單」通知我們。</p></div>
  <div><h3>超商取貨付款</h3><p>到店取貨時付款。</p></div></div></div>
 <div class="tsec rv"><h2>{ICON_TRUCK}寄送方式及運費計算</h2>
  <div class="free"><i></i><span>寄送目的地為台灣地區，單筆金額滿新台幣 $3000 以上，即享免運優惠!</span></div>
  <div class="ship">
   <div><h3>郵局寄送</h3><span class="fee">$65</span><p>僅限使用 ATM 付款</p></div>
   <div><h3>全家 超商取貨</h3><span class="fee">$60</span><p>請務必填寫真實姓名，超商將核對身分證件。</p></div>
   <div><h3>7-11 超商取貨</h3><span class="fee">$60</span><p>請務必填寫真實姓名，超商將核對身分證件。</p></div>
  </div></div>
 <div class="tsec rv"><h2>{ICON_CLOCK}出貨工作天</h2><div class="notebox">
  <p>訂單確認後，從付款到收到貨品，大約需要 3~6 個工作天 (不含假日)。</p>
  <p>平日（週一～週五）收到您款項的隔天，確認您的資料無誤將三天內安排出貨。</p>
  <p>例假日與國定假日無法進行出貨，請您特別留意。</p></div></div>
</section></div>"""
    return page(data, rel, lang, f"購物流程 | {BRAND}", body, "購物流程", current=rel)


# ----------------------------------------------------------------- rich text from the admin editor (sanitized again at build time)
RICH_TAGS = {"p", "h2", "h3", "h4", "strong", "em", "u", "s", "ul", "ol", "li", "a", "br", "span", "blockquote"}
RICH_RENAME = {"b": "strong", "i": "em", "div": "p", "h1": "h2", "h5": "h4", "h6": "h4", "strike": "s"}
RICH_BLOCKS = {"p", "h2", "h3", "h4", "li", "blockquote"}
RICH_CLASSES = {"fs-s", "fs-l", "fs-xl", "tc-brand", "tc-mute"}
_ALIGN_RE = re.compile(r"text-align\s*:\s*(left|center|right|justify)", re.I)
_COLOR_RE = re.compile(r"(?:^|;)\s*color\s*:\s*(#[0-9a-fA-F]{6})\b")
_HTML_START = re.compile(r"^\s*<(p|h[1-6]|ul|ol|div|blockquote|span|strong|b|em|i|u|a|br)\b", re.I)


def is_rich(text):
    return bool(_HTML_START.match(text or ""))


def rich_html(text, page_dir="", lang="zh"):
    soup = BeautifulSoup(text or "", "html.parser")
    for el in soup.find_all(["script", "style", "iframe", "object", "embed", "form", "input", "img", "video", "audio"]):
        el.decompose()
    for c in soup.find_all(string=lambda x: isinstance(x, Comment)):
        c.extract()
    for el in list(soup.find_all(True)):
        el.name = RICH_RENAME.get(el.name, el.name)
        if el.name not in RICH_TAGS:
            el.unwrap()
            continue
        style, align_attr = el.get("style", ""), (el.get("align") or "").lower()
        cls = [c for c in (el.get("class") or []) if c in RICH_CLASSES]
        href = (el.get("href") or "").strip()
        el.attrs = {}
        m = _ALIGN_RE.search(style)
        align = (m.group(1).lower() if m else align_attr) if el.name in RICH_BLOCKS else ""
        if align in ("left", "center", "right", "justify") and align != "left":
            el["style"] = f"text-align:{align}"
        if el.name == "span":
            m_col = _COLOR_RE.search(style)
            if cls:
                el["class"] = cls
            if m_col:
                el["style"] = f"color:{m_col.group(1).lower()}"
            if not cls and not m_col:
                el.unwrap()
            continue
        if el.name == "a":
            if not href or re.match(r"^\s*(javascript|data|vbscript):", href, re.I):
                el.unwrap()
            elif re.match(r"^[a-z][a-z0-9+.-]*:", href, re.I):          # external / mailto / tel
                el["href"] = href
                if href.lower().startswith("http"):
                    el["target"], el["rel"] = "_blank", "noopener"
            else:                                                       # a page of this site, same language
                el["href"] = link(page_dir, href.lstrip("/"), lang) if sb._LOCALIZED_RE.match(href.lstrip("/").split("#")[0]) else sb.href(page_dir, href.lstrip("/"))
    return str(soup)


def rich_or_plain(text, page_dir="", lang="zh"):
    """Rich HTML from the editor, or the older plain-text format (one paragraph per line)."""
    if is_rich(text):
        return rich_html(text, page_dir, lang)
    return "".join(f"<p>{esc(x.strip())}</p>" for x in (text or "").splitlines() if x.strip())


def plain_of(text):
    return re.sub(r"\s+", " ", html_mod.unescape(re.sub(r"<[^>]+>", " ", text or ""))).strip() if is_rich(text) else (text or "")


def item_text(obj, lang, field):
    """Admin-entered translation of a rich field when present, else the Chinese text."""
    o = ((obj.get("i18n") or {}).get(lang) or {}) if lang != "zh" else {}
    return (o.get(field) or "").strip() or (obj.get(field) or "")



# ----------------------------------------------------------------- 商品分類 (shop.html): a directory of category cards
SOON = '<div class="soon"><span class="tag">即將推出</span><p>這個分類的商品即將推出，先看看其他系列。</p></div>'


def group_page(g):
    return f"group/{g['key']}.html"


def category_card(c, visible, d, lang):
    items = [p for p in visible if c["id"] in p.get("categories", [])]
    if items:
        pic = f'<img src="{asset(d, crop(items[0]["image"]["full"], "w43"))}" alt="" loading="lazy">'
        meta = f'<span class="n">共 {len(items)} 件商品</span>'
    else:
        pic = f'<span class="ph-empty" aria-hidden="true"><img src="{asset(d, LOGO)}" alt=""></span>'
        meta = '<span class="tag">即將推出</span>'
    types = "・".join(esc(t["name"]) for t in types_of(c))
    return (f'<a class="cat-card" href="{link(d, sb.category_page(c["id"]), lang)}"><div class="img">{pic}</div>'
            f'<div class="body"><h3>{esc(c["name"])}</h3>{f"<p>{types}</p>" if types else ""}{meta}</div></a>')


def render_group(data, visible, g, lang):
    """A group page: its categories as cards (photo, name, sub-categories, count or 即將推出)."""
    rel = group_page(g)
    d = rel_dir(rel)
    cards = "".join(category_card(c, visible, d, lang) for c in cats_in(data, g["key"]))
    others = "".join(f'<a href="{link(d, group_page(x), lang)}">{esc(x["name"])}</a>' for x in groups_of(data) if x["key"] != g["key"] and cats_in(data, x["key"]))
    body = f"""<div class="wrap">
<ol class="breadcrumb"><li><a href="{link(d, 'index.html', lang)}">首頁</a></li><li><a href="{link(d, SHOP, lang)}">商品分類</a></li><li><span>{esc(g["name"])}</span></li></ol>
<div class="ph"><h1>{esc(g["name"])}</h1>{f'<p>{esc(g["blurb"])}</p>' if g.get("blurb") else ''}</div>
<div style="height:18px"></div>
<div class="cat-cards">{cards or SOON}</div>
{f'<div class="chips other-groups">{others}</div>' if others else ''}
<div style="height:48px"></div>
</div>"""
    return page(data, rel, lang, f"{g['name']} | {BRAND}", body, g.get("blurb") or g["name"], current=SHOP)


def render_shop(data, visible, lang):
    """商品分類: one card per group (photo, name, blurb) listing its categories with a count or 即將推出."""
    d = ""
    cards = ""
    for g in groups_of(data):
        cats = cats_in(data, g["key"])
        if not cats:
            continue
        img = IMG.get(GROUP_IMG.get(g["key"], ""), "")
        lis = ""
        for c in cats:
            n = cat_count(c, visible)
            meta = f'共 {n} 件商品<span aria-hidden="true"> →</span>' if n else "即將推出"
            lis += (f'<li><a{"" if n else " class=empty"} href="{link(d, sb.category_page(c["id"]), lang)}"><span>{esc(c["name"])}</span>'
                    f'<small>{meta}</small></a></li>')
        gl = link(d, group_page(g), lang)
        pic = f'<a class="img" href="{gl}" tabindex="-1" aria-hidden="true"><img src="{asset(d, img)}" alt="" loading="lazy"></a>' if img else ""
        cards += (f'<section class="grp-card" id="{g["key"]}">{pic}<div class="bd"><h2><a href="{gl}">{esc(g["name"])}</a></h2>'
                  f'{("<p>" + esc(g.get("blurb", "")) + "</p>") if g.get("blurb") else ""}</div><ul>{lis}</ul></section>')
    body = f"""<div class="wrap">
<ol class="breadcrumb"><li><a href="{link(d, 'index.html', lang)}">首頁</a></li><li><span>商品分類</span></li></ol>
<div class="ph"><h1>商品分類</h1><p>依用途挑選</p></div>
<div class="grp-cards">{cards}</div>
</div>"""
    return page(data, SHOP, lang, f"商品分類 | {BRAND}", body, "依用途挑選 apetto 的機能服飾、外出配件與舒適生活用品。", current=SHOP)


def render_category(data, visible, c, lang):
    """A category page: one product grid, filtered by sub-category tabs (works without JS: everything shows)."""
    site_rel = sb.category_page(c["id"])
    d = rel_dir(site_rel)
    g = next((x for x in groups_of(data) if x["key"] == c.get("group")), None)
    items = [p for p in visible if c["id"] in p.get("categories", [])]
    types = types_of(c)
    grid_id = f"cat{c['id']}-grid"
    tabs = ""
    if types and items:
        tabs = f'<button type="button" class="cur" data-type="">全部 <small>{len(items)}</small></button>'
        for t in types:
            k = len(type_items(visible, c, t))
            tabs += (f'<button type="button" data-type="{esc(t["key"])}">{esc(t["name"])} <small>{k}</small></button>' if k else
                     f'<button type="button" data-type="{esc(t["key"])}" class="empty">{esc(t["name"])} <small>即將推出</small></button>')
        tabs = f'<div class="chips type-tabs" data-grid="{grid_id}" role="toolbar">{tabs}</div>'
    cards = "".join(product_card(p, d, lang, attrs=f' data-types="{esc(" ".join(p.get("types") or []))}"') for p in items)
    grid = (f'<div class="product-grid" id="{grid_id}">{cards}</div><div id="{grid_id}-soon" hidden>{SOON}</div>' if items else SOON)
    crumbs = (f'<li><a href="{link(d, "index.html", lang)}">首頁</a></li><li><a href="{link(d, SHOP, lang)}">商品分類</a></li>'
              + (f'<li><a href="{link(d, group_page(g), lang)}">{esc(g["name"])}</a></li>' if g else "") + f'<li><span>{esc(c["name"])}</span></li>')
    body = f"""<div class="wrap">
<ol class="breadcrumb">{crumbs}</ol>
<div class="ph"><h1>{esc(c["name"])}</h1>{f'<p>{esc(c["blurb"])}</p>' if c.get("blurb") else ''}</div>
{tabs or '<div style="height:18px"></div>'}
{grid}
<div style="height:48px"></div>
</div>"""
    return page(data, site_rel, lang, f"{c['name']} | {BRAND}", body, c.get("blurb") or c["name"], current=SHOP)


# ----------------------------------------------------------------- 商品指南 (_data/guides.json -> guides.html, guide/<key>.html)
GUIDES_FILE = sb.DATA_DIR / "guides.json"


def load_guides():
    items = json.loads(GUIDES_FILE.read_text(encoding="utf-8")).get("items", []) if GUIDES_FILE.exists() else []
    return [g for g in items if g.get("visible", True)]


def guide_page(g):
    return f"guide/{g['key']}.html"


def guide_text(g, lang, field):
    o = (g.get("i18n") or {}).get(lang) or {}
    return (o.get(field) or "").strip() or (g.get(field) or "")


def guide_body_html(text, page_dir="", lang="zh"):
    """Rich HTML from the admin editor, or the older '## heading' / '- bullet' / paragraph lines."""
    if is_rich(text):
        return rich_html(text, page_dir, lang)
    out, ul = [], []

    def flush():
        nonlocal ul
        if ul:
            out.append("<ul>" + "".join(f"<li>{esc(x)}</li>" for x in ul) + "</ul>")
            ul = []
    for line in (text or "").splitlines():
        line = line.strip()
        if not line:
            continue
        if line.startswith("## "):
            flush()
            out.append(f"<h2>{esc(line[3:])}</h2>")
        elif line.startswith("- "):
            ul.append(line[2:])
        else:
            flush()
            out.append(f"<p>{esc(line)}</p>")
    flush()
    return "\n".join(out)


def guide_cards(d, lang, skip=None):
    cards = ""
    for i, g in enumerate(load_guides()):
        if skip and g["key"] == skip:
            continue
        cards += (f'<a class="gcard" href="{link(d, guide_page(g), lang)}"><span class="num"><span>指南</span> {i + 1:02d}</span>'
                  f'<h3>{esc(guide_text(g, lang, "title"))}</h3><p>{esc(guide_text(g, lang, "summary"))}</p>'
                  f'<span class="go">閱讀指南<span aria-hidden="true"> →</span></span></a>')
    return f'<div class="gcards">{cards}</div>'


def render_guides_list(data, lang):
    d = ""
    body = f"""<div class="wrap">
<ol class="breadcrumb"><li><a href="{link(d, 'index.html', lang)}">首頁</a></li><li><span>商品指南</span></li></ol>
<div class="ph"><h1>商品指南</h1><p>挑選、測量與保養的小知識</p></div>
<div style="height:24px"></div>
{guide_cards(d, lang)}
<div style="height:48px"></div>
</div>"""
    return page(data, GUIDES, lang, f"商品指南 | {BRAND}", body, "挑選、測量與保養的小知識", current=GUIDES)


def render_guide(data, g, lang):
    rel = guide_page(g)
    d = rel_dir(rel)
    title = guide_text(g, lang, "title")
    summary = guide_text(g, lang, "summary")
    crumbs = (f'<li><a href="{link(d, "index.html", lang)}">首頁</a></li><li><a href="{link(d, GUIDES, lang)}">商品指南</a></li>'
              f'<li><span>{esc(title)}</span></li>')
    extra = ""
    if g.get("link"):
        label = esc(guide_text(g, lang, "link_text") or "查看連結")
        if re.match(r"^[a-z][a-z0-9+.-]*:", g["link"], re.I):      # external URL: new tab
            extra = f'<p class="guide-cta"><a class="btn brand" href="{esc(g["link"])}" target="_blank" rel="noopener">{label}</a></p>'
        else:
            extra = f'<p class="guide-cta"><a class="btn brand" href="{link(d, g["link"].lstrip("/"), lang)}">{label}</a></p>'
    body = (f'<div class="wrap"><ol class="breadcrumb">{crumbs}</ol><article class="article guide"><div class="ph"><span class="eyebrow">商品指南</span>'
            f'<h1>{esc(title)}</h1><p>{esc(summary)}</p></div>{guide_body_html(guide_text(g, lang, "body"), d, lang)}{extra}</article></div>'
            f'{section("更多指南", guide_cards(d, lang, skip=g["key"]), cls="tight", page_dir=d, lang=lang)}')
    return page(data, rel, lang, f"{title} | {BRAND}", body, summary, current=GUIDES)


# ----------------------------------------------------------------- 機能與設計細節 (features.html): the original site's feature copy
def render_features(data, visible, lang):
    d = ""
    site = load_site()
    rows_html = ""
    for i, f in enumerate(site["features"]["items"]):
        tag = f'<span class="eyebrow">{esc(f["tag"])}</span>' if f.get("tag") else ""
        rows_html += (f'<div class="story{" flip" if i % 2 else ""} rv"><div class="story-img"><img src="{asset(d, f["image"])}" alt="" loading="lazy"></div>'
                      f'<div>{tag}<h2>{esc(f.get("title", ""))}</h2><div class="rich-text">{rich_or_plain(item_text(f, lang, "text"), d, lang)}</div></div></div>')
    body = f"""<div class="wrap">
<ol class="breadcrumb"><li><a href="{link(d, 'index.html', lang)}">首頁</a></li><li><span>機能與設計細節</span></li></ol>
<div class="ph"><h1>機能與設計細節</h1><p>{esc(site["features"]["intro"])}</p></div>
</div>
<section class="sec tight"><div class="wrap features">{rows_html}</div></section>
{fit.home_promo(d, lang)}"""
    return page(data, FEATURES, lang, f"機能與設計細節 | {BRAND}", body, site["features"]["intro"], og_image=IMG["rain"], current=FEATURES)


# ----------------------------------------------------------------- news (admin-managed _data/news.json)
NEWS_FILE = sb.DATA_DIR / "news.json"


def load_news():
    items = json.loads(NEWS_FILE.read_text(encoding="utf-8")).get("items", []) if NEWS_FILE.exists() else []
    return sorted([n for n in items if n.get("visible", True)], key=lambda n: n.get("date", ""), reverse=True)


def news_page(n):
    return f"information/news&news_id={n['id']}.html"


def news_text(n, lang, field):
    """Admin-entered translation when present, else the Chinese text (the i18n table may still translate it)."""
    o = (n.get("i18n") or {}).get(lang) or {}
    return (o.get(field) or "").strip() or (n.get(field) or "")


_URL_RE = re.compile(r"(https?://[^\s<>\"]+)")


def news_body_html(text, page_dir="", lang="zh"):
    if is_rich(text):
        return rich_html(text, page_dir, lang)
    out = []
    for line in (text or "").splitlines():
        line = line.strip()
        if not line:
            continue
        parts = _URL_RE.split(line)
        html_line = "".join(f'<a href="{esc(p)}" target="_blank" rel="noopener">{esc(p)}</a>' if _URL_RE.fullmatch(p) else esc(p) for p in parts)
        out.append(f"<p>{html_line}</p>")
    return "\n".join(out)


def render_news_list(data, lang, rel="information/news.html"):
    d = rel_dir(rel)
    crumbs = f'<li><a href="{link(d, "index.html", lang)}">首頁</a></li><li><span>最新消息</span></li>'
    items = "".join(f'<a href="{link(d, news_page(n), lang)}"><time>{esc(n.get("date", ""))}</time><b>{esc(news_text(n, lang, "title"))}</b></a>' for n in load_news())
    content = f'<div class="news-list">{items or "<p class=empty>目前沒有消息</p>"}</div>'
    body = f'<div class="wrap"><ol class="breadcrumb">{crumbs}</ol><div class="ph"><h1>最新消息</h1></div><div style="height:24px"></div>{content}</div>'
    return page(data, rel, lang, f"最新消息 | {BRAND}", body, "最新消息", current="information/news.html")


def render_news_article(data, n, lang, rel=None):
    rel = rel or news_page(n)
    d = rel_dir(rel)
    title = news_text(n, lang, "title")
    crumbs = (f'<li><a href="{link(d, "index.html", lang)}">首頁</a></li><li><a href="{link(d, "information/news.html", lang)}">最新消息</a></li>'
              f'<li><span>{esc(title)}</span></li>')
    extra = ""
    if n.get("link"):
        label = esc(news_text(n, lang, "link_text") or "查看連結")
        if re.match(r"^[a-z][a-z0-9+.-]*:", n["link"], re.I):      # external URL: new tab
            extra = f'<p><a href="{esc(n["link"])}" target="_blank" rel="noopener">{label}</a></p>'
        else:                                                      # a page of this site: same tab, same language
            extra = f'<p><a class="btn" href="{link(d, n["link"].lstrip("/"), lang)}">{label}</a></p>'
    body = (f'<div class="wrap"><ol class="breadcrumb">{crumbs}</ol><article class="article"><div class="ph"><h1>{esc(title)}</h1></div>'
            f'<p class="date">{esc(n.get("date", ""))}</p>{news_body_html(news_text(n, lang, "body"), d, lang)}{extra}</article></div>')
    return page(data, rel, lang, f"{title} | {BRAND}", body, title, current="information/news.html")


def render_404(data, lang):
    body = (f'<div class="wrap" style="padding:80px 0 120px;text-align:center"><div class="ph"><h1>找不到頁面</h1><p>這個頁面不存在或已被移除。</p></div>'
            f'<a class="btn" href="{sb.lang_variant("index.html", lang)}">回到首頁</a></div>')
    return page(data, "404.html", lang, f"找不到頁面 | {BRAND}", body, "")


# ----------------------------------------------------------------- finishing (translation, images, search) + writing
def finish(html_text, site_rel, lang, table):
    soup = BeautifulSoup(html_text, "lxml")
    d = rel_dir(site_rel)
    sb.apply_image_text(soup, d)
    charts = sb.load_image_text().get("charts", {})
    for el in soup.select("[data-chart]"):  # size chart chosen in the admin editor
        chart = charts.get(el.get("data-chart"))
        if chart:
            el.replace_with(sb._chart_html(soup, chart))
        else:
            el.decompose()
    if lang != "zh":
        sb.translate_soup(soup, lang, table)
    keep_phrases(soup, lang)
    sb.use_optimized_images(soup, d)
    sb.add_search(soup, lang, site_rel)
    return str(soup)


_PHRASE_END = re.compile(r"(?<=[，、。！？；：,!?])")


def keep_phrases(soup, lang):
    """Chinese / Japanese headlines: break lines only after punctuation, never inside a phrase.
    Each phrase becomes an inline-block, so it still wraps internally if it alone is wider than the line."""
    if lang not in ("zh", "ja"):
        return
    for h in soup.select(".hero h1"):
        text = h.get_text()
        parts = [x for x in _PHRASE_END.split(text) if x]
        if len(parts) < 2 or h.find(True):
            continue
        h.clear()
        for x in parts:
            sp = soup.new_tag("span", attrs={"class": "phr"})
            sp.string = x
            h.append(sp)


def write_page(html_text, site_rel, lang, table):
    sb.write_text(sb.SITE / sb.lang_variant(site_rel, lang), finish(html_text, site_rel, lang, table))


def i18n_table(data):
    table = sb.load_i18n(data)
    for k, v in UI.items():
        table.setdefault(k, {}).update({kk: vv for kk, vv in v.items() if kk not in table.get(k, {})})
    for n in load_news() + load_guides():
        for lang, o in (n.get("i18n") or {}).items():
            if (o or {}).get("title") and n.get("title"):
                table.setdefault(re.sub(r"\s+", " ", n["title"]).strip(), {})[lang] = o["title"]
    def put(obj, fields):
        for lang, o in (obj.get("i18n") or {}).items():
            for f in fields:
                zh, tr = (obj.get(f) or "").strip(), ((o or {}).get(f) or "").strip()
                if zh and tr:
                    table.setdefault(re.sub(r"\s+", " ", zh), {})[lang] = tr
    for g in data["categories"] + groups_of(data):
        put(g, ("name", "blurb"))
    for c in data["categories"]:
        for t in types_of(c):
            put(t, ("name",))
    site = load_site()
    put(site["hero"], ("title", "lead"))
    put(site["features"], ("intro",))
    for f in site["features"]["items"]:
        put(f, ("title", "tag") if is_rich(f.get("text")) else ("title", "text", "tag"))
    return table


def build_all(data, visible):
    table = i18n_table(data)
    sb._PATTERN_CACHE.clear()
    global _CROPS
    _CROPS = None
    assets = sb.SITE / "assets"
    assets.mkdir(exist_ok=True)
    (assets / "theme.css").write_text(CSS.strip() + "\n", encoding="utf-8")
    (assets / "theme.js").write_text(JS + "\n", encoding="utf-8")
    (assets / "fitstudio.js").write_text(fit.JS + "\n", encoding="utf-8")
    (assets / "assistant.js").write_text(ai.JS + "\n", encoding="utf-8")
    (assets / "member.js").write_text(mem.JS + "\n", encoding="utf-8")
    for lang in LANG_CODES:
        write_page(render_home(data, visible, lang), "index.html", lang, table)
        for c in data["categories"]:
            items = [p for p in visible if c["id"] in p.get("categories", [])]
            write_page(render_category(data, visible, c, lang), sb.category_page(c["id"]), lang, table)
        write_page(render_shop(data, visible, lang), SHOP, lang, table)
        for g in groups_of(data):
            write_page(render_group(data, visible, g, lang), group_page(g), lang, table)
        write_page(render_features(data, visible, lang), FEATURES, lang, table)
        write_page(render_guides_list(data, lang), GUIDES, lang, table)
        for g in load_guides():
            write_page(render_guide(data, g, lang), guide_page(g), lang, table)
        write_page(render_listing(data, "search.html", lang, "全系列", visible, current="all", search=True), "search.html", lang, table)
        write_page(fit.render(data, lang), fit.PAGE, lang, table)
        for p in visible:
            write_page(render_product(data, visible, p, lang, sb.product_i18n(p)), sb.product_page(p), lang, table)
        for rel in ("pages/4.html", "pages/5.html"):
            out = render_info(data, rel, lang)
            if out:
                write_page(out, rel, lang, table)
        write_page(render_store(data, lang), STORE, lang, table)
        if mem.config():
            write_page(mem.render_page(data, lang), mem.PAGE, lang, table)
        write_page(render_news_list(data, lang), "information/news.html", lang, table)
        write_page(render_news_list(data, lang, "information/notice.html"), "information/notice.html", lang, table)  # old link
        for n in load_news():
            write_page(render_news_article(data, n, lang), news_page(n), lang, table)
            if n.get("alias"):
                write_page(render_news_article(data, n, lang, n["alias"]), n["alias"], lang, table)
        write_page(render_404(data, lang), "404.html", lang, table)
    keepgr = {sb.lang_variant(group_page(g), c) for g in groups_of(data) for c in LANG_CODES}
    for f in (sb.SITE / "group").glob("*.html"):
        if f.relative_to(sb.SITE).as_posix() not in keepgr:
            f.unlink()
    keepg = {sb.lang_variant(guide_page(g), c) for g in load_guides() for c in LANG_CODES}
    for f in (sb.SITE / "guide").glob("*.html"):
        if f.relative_to(sb.SITE).as_posix() not in keepg:
            f.unlink()
    keep = {sb.lang_variant(p, c) for n in load_news() for p in [news_page(n)] + ([n["alias"]] if n.get("alias") else []) for c in LANG_CODES}
    for f in list((sb.SITE / "information").glob("news&news_id=*.html")) + list((sb.SITE / "information").glob("notice&notice_id=*.html")):
        if f.relative_to(sb.SITE).as_posix() not in keep:
            f.unlink()
    ai.build(data, visible, LANG_CODES)   # reads the finished pages, so it runs last
