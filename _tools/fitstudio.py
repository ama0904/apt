# -*- coding: utf-8 -*-
"""
apetto AI fitting room ("寵物試衣間"): a page of the storefront whose heavy lifting happens on a separate
server (the FitStudio bridge, which drives Gemini). This module only holds the front end: the page markup,
its styles, the browser script that talks to the bridge, and the UI strings in the four site languages.

The bridge API (see the FitStudio hand-over notes):
  GET  /api/health                 -> {"status":"ok"}                      no auth
  POST /api/stylist                -> {"image": dataURL, "captionId": id}  x-api-key, JSON body
       {"dogImage": dataURL, "clothesImage": dataURL, "lang": "zh"|"de", "jobId": str}; synchronous, 15-240 s
  GET  /api/status/<jobId>         -> {"key": "srv.generating", "step": 6, "vars": {...}}   progress, no auth
  GET  /api/caption/<captionId>    -> {"status": "pending"|"ready"|"none", "caption": str}   x-api-key
Errors are JSON {"error": str, "errorKey": str}; the keys map to the strings in STR below.

The bridge's access key is not kept in this repository: the build reads it from the FITSTUDIO_API_KEY
environment variable (a GitHub Actions secret in deploy.yml) and writes it into the page, where it is public
anyway; the bridge's owner uses it only to turn away stray requests. With no key set, requests go out without
the header (the bridge can allow the site's origin instead). The clothes pictures must be the prepared
"garment on a black dog silhouette, white background" composites in assets/fitstudio/, not product photos.
"""
import json
import os

API_BASE = "https://tablet-uaj7iieq.tail188668.ts.net"
API_KEY = os.environ.get("FITSTUDIO_API_KEY", "")
PAGE = "fitstudio.html"
ASSET_DIR = "assets/fitstudio/"
# the bridge writes the stylist's note in the page language (zh/en/ja/de; anything else falls back to zh)
SERVER_LANG = {"zh": "zh", "de": "de", "en": "en", "ja": "ja"}
SHOW_NOTE = {"zh": True, "de": True, "en": True, "ja": True}

DOGS = [("golden", "dog_golden.jpg", "黃金獵犬"), ("labrador", "dog_labrador.webp", "拉布拉多")]
# key, prepared garment image, colour label, linked product id, size chart key in _data/image_text.json
COATS = [("pink", "pink_coat.jpg", "莓果桃", 15, "small_warm_cape"), ("yellow", "yellow_coat.jpg", "檸檬螢光黃", 16, "small_cape"),
         ("blue", "blue_coat.jpg", "普魯士藍", 8, "big_raincoat")]
# the size charts say "pick a garment about this much shorter than the dog's back length"
CHART_OFFSET = {"big_raincoat": 10, "big_jacket": 10, "small_cape": 6, "small_warm_cape": 6}

# Markup strings (zh key -> translations); merged into theme.UI so translate_soup handles the page.
UI = {
    "試衣間": {"en": "Fitting room", "ja": "試着室", "de": "Anprobe"},
    "AI 試衣間": {"en": "AI fitting room", "ja": "AI 試着室", "de": "KI-Anprobe"},
    "讓毛孩先試穿，再決定": {"en": "Let your dog try it on first", "ja": "まず試着、それから決める", "de": "Erst anprobieren, dann entscheiden"},
    "上傳一張毛孩的照片，挑一件 apetto，AI 會畫出牠穿上的樣子。": {
        "en": "Upload a photo of your dog, pick an apetto coat, and the AI shows how it looks on them.",
        "ja": "愛犬の写真をアップロードして apetto の一着を選ぶと、AI が着た姿を描きます。",
        "de": "Lade ein Foto deines Hundes hoch, wähle eine apetto-Jacke, und die KI zeigt, wie sie ihm steht."},
    "毛孩照片": {"en": "Your dog's photo", "ja": "愛犬の写真", "de": "Foto deines Hundes"},
    "選一件 apetto": {"en": "Pick an apetto coat", "ja": "apetto を選ぶ", "de": "Eine apetto-Jacke wählen"},
    "試穿結果": {"en": "Result", "ja": "試着結果", "de": "Ergebnis"},
    "點這裡選照片，或把照片拖進來": {"en": "Tap to choose a photo, or drop one here", "ja": "タップして写真を選ぶか、ここにドロップ", "de": "Tippen, um ein Foto zu wählen, oder hierher ziehen"},
    "全身、側面、光線清楚的照片效果最好。支援 JPG、PNG、WEBP。": {
        "en": "Full-body, side-on, well-lit photos work best. JPG, PNG and WEBP.",
        "ja": "全身・横向き・明るい写真がおすすめ。JPG、PNG、WEBP 対応。",
        "de": "Ganzkörper, seitlich, gut beleuchtet klappt am besten. JPG, PNG und WEBP."},
    "更換照片": {"en": "Change photo", "ja": "写真を変更", "de": "Foto ändern"},
    "沒有照片？先用示範狗狗試試": {"en": "No photo handy? Try a sample dog", "ja": "写真がない？サンプルの犬で試す", "de": "Kein Foto zur Hand? Probier einen Beispielhund"},
    "黃金獵犬": {"en": "Golden retriever", "ja": "ゴールデン", "de": "Golden Retriever"},
    "拉布拉多": {"en": "Labrador", "ja": "ラブラドール", "de": "Labrador"},
    "莓果桃": {"en": "Berry pink", "ja": "ベリーピンク", "de": "Beerenrosa"},
    "檸檬螢光黃": {"en": "Neon lemon", "ja": "ネオンイエロー", "de": "Neongelb"},
    "普魯士藍": {"en": "Prussian blue", "ja": "プルシアンブルー", "de": "Preußischblau"},
    "查看商品": {"en": "View product", "ja": "商品を見る", "de": "Produkt ansehen"},
    "開始試穿": {"en": "Try it on", "ja": "試着する", "de": "Anprobieren"},
    "AI 生成約需 20 到 40 秒，尖峰時段可能更久。": {
        "en": "Generation takes about 20 to 40 seconds, longer at busy times.",
        "ja": "生成には20〜40秒ほど、混雑時はさらにかかります。",
        "de": "Die Generierung dauert etwa 20 bis 40 Sekunden, bei Andrang länger."},
    "選好照片和衣服後，試穿結果會出現在這裡。": {
        "en": "Pick a photo and a coat, and the result appears here.",
        "ja": "写真と服を選ぶと、ここに結果が表示されます。",
        "de": "Wähle Foto und Jacke, das Ergebnis erscheint hier."},
    "下載照片": {"en": "Download photo", "ja": "写真を保存", "de": "Foto speichern"},
    "再試一件": {"en": "Try another", "ja": "別の服を試す", "de": "Noch eine probieren"},
    "AI 造型師的話": {"en": "From the AI stylist", "ja": "AI スタイリストより", "de": "Von der KI-Stylistin"},
    "試穿圖由 AI 生成，顏色與版型以實際商品為準。": {
        "en": "The picture is AI-generated. Colours and fit follow the actual product.",
        "ja": "画像は AI 生成です。色や形は実際の商品をご確認ください。",
        "de": "Das Bild ist KI-generiert. Farbe und Schnitt richten sich nach dem echten Produkt."},
    "連線中…": {"en": "Connecting…", "ja": "接続中…", "de": "Verbinde…"},
    "試衣間運作中": {"en": "The fitting room is open", "ja": "試着室 稼働中", "de": "Die Anprobe ist geöffnet"},
    "試衣間暫停服務中，請稍後再來。": {"en": "The fitting room is offline right now. Please come back later.",
                                     "ja": "ただいま試着室は停止中です。しばらくしてからお試しください。",
                                     "de": "Die Anprobe ist gerade offline. Bitte später wiederkommen."},
    "取消": {"en": "Cancel", "ja": "キャンセル", "de": "Abbrechen"},
    "試穿完成": {"en": "Done!", "ja": "試着できました", "de": "Fertig!"},
    "喜歡嗎？量一下毛孩，看該選哪一號": {"en": "Like it? Measure your dog to find the size", "ja": "気に入った？愛犬を測ってサイズを確認", "de": "Gefällt's? Miss deinen Hund für die richtige Größe"},
    "背長：從脖子根部（約前腳的位置）量到尾巴根。領圍與腹圍為圈量，可以不填。": {
        "en": "Back length: from the base of the neck (about the front legs) to the base of the tail. Neck and girth are measured around; both optional.",
        "ja": "背丈：首の付け根（前足あたり）からしっぽの付け根まで。首回り・胴回りは一周を測ります（任意）。",
        "de": "Rückenlänge: vom Halsansatz (etwa Vorderbeine) bis zum Schwanzansatz. Hals- und Bauchumfang rundherum messen; beide optional."},
    "背長": {"en": "Back length", "ja": "背丈", "de": "Rückenlänge"},
    "領圍": {"en": "Neck", "ja": "首回り", "de": "Halsumfang"},
    "腹圍": {"en": "Girth", "ja": "胴回り", "de": "Bauchumfang"},
    # home promo
    "新功能": {"en": "New", "ja": "新機能", "de": "Neu"},
    "AI 試衣間：先看牠穿上的樣子": {"en": "AI fitting room: see it on your dog first", "ja": "AI 試着室：着た姿を先に見る", "de": "KI-Anprobe: erst sehen, wie es deinem Hund steht"},
    "上傳一張照片，挑一件 apetto，約 30 秒就能看到試穿效果。": {
        "en": "Upload a photo, pick an apetto coat, and see the result in about 30 seconds.",
        "ja": "写真を1枚アップロードして apetto を選ぶだけ。約30秒で試着イメージ。",
        "de": "Foto hochladen, apetto-Jacke wählen, in etwa 30 Sekunden das Ergebnis sehen."},
    "去試衣間": {"en": "Open the fitting room", "ja": "試着室へ", "de": "Zur Anprobe"},
}

# Strings the browser script needs (progress, errors); emitted per page language as JSON.
STR = {
    "step.prepare": {"zh": "準備照片", "en": "Preparing photos", "ja": "写真を準備", "de": "Fotos vorbereiten"},
    "step.send": {"zh": "傳送給 AI", "en": "Sending to the AI", "ja": "AI に送信", "de": "An die KI senden"},
    "step.draw": {"zh": "AI 繪製中", "en": "AI is drawing", "ja": "AI が描画中", "de": "KI zeichnet"},
    "step.done": {"zh": "完成", "en": "Done", "ja": "完了", "de": "Fertig"},
    "elapsed": {"zh": "已經過 {sec} 秒", "en": "{sec} s elapsed", "ja": "{sec} 秒経過", "de": "{sec} s vergangen"},
    "srv.prepare": {"zh": "準備照片中…", "en": "Preparing photos…", "ja": "写真を準備中…", "de": "Fotos werden vorbereitet…"},
    "srv.launch": {"zh": "啟動 AI 引擎…", "en": "Starting the AI engine…", "ja": "AI エンジンを起動中…", "de": "KI-Engine wird gestartet…"},
    "srv.navigate": {"zh": "連線 AI 引擎…", "en": "Connecting to the AI engine…", "ja": "AI エンジンに接続中…", "de": "Verbindung zur KI-Engine…"},
    "srv.pasteDog": {"zh": "送出毛孩照片…", "en": "Sending your dog's photo…", "ja": "愛犬の写真を送信中…", "de": "Hundefoto wird gesendet…"},
    "srv.pasteClothes": {"zh": "送出衣服圖片…", "en": "Sending the coat…", "ja": "服の画像を送信中…", "de": "Jacke wird gesendet…"},
    "srv.typePrompt": {"zh": "輸入生成指令…", "en": "Writing the instructions…", "ja": "指示を入力中…", "de": "Anweisung wird eingegeben…"},
    "srv.sent": {"zh": "已送出，等待 AI 回應…", "en": "Sent, waiting for the AI…", "ja": "送信済み、AI の応答待ち…", "de": "Gesendet, warte auf die KI…"},
    "srv.generating": {"zh": "AI 繪製中… {sec} 秒", "en": "AI is drawing… {sec} s", "ja": "AI が描画中… {sec} 秒", "de": "KI zeichnet… {sec} s"},
    "srv.caption": {"zh": "撰寫推薦文案…", "en": "Writing the stylist's note…", "ja": "おすすめ文を作成中…", "de": "Empfehlung wird geschrieben…"},
    "srv.done": {"zh": "圖片完成！", "en": "Picture ready!", "ja": "画像が完成！", "de": "Bild fertig!"},
    "note.writing": {"zh": "造型師正在寫推薦…", "en": "The stylist is writing a note…", "ja": "スタイリストがコメントを作成中…", "de": "Die Stylistin schreibt gerade…"},
    "err.pickFirst": {"zh": "請先選擇毛孩照片和一件衣服。", "en": "Please choose a photo and a coat first.", "ja": "先に写真と服を選んでください。", "de": "Bitte zuerst ein Foto und eine Jacke wählen."},
    "err.offline": {"zh": "試衣間目前離線，請稍後再試。", "en": "The fitting room is offline right now. Please try again later.", "ja": "試着室は現在オフラインです。しばらくしてからお試しください。", "de": "Die Anprobe ist gerade offline. Bitte später erneut versuchen."},
    "err.network": {"zh": "和試衣間的連線中斷了，請稍後再試一次。", "en": "The connection to the fitting room dropped. Please try again in a moment.", "ja": "試着室との接続が切れました。しばらくしてからもう一度お試しください。", "de": "Die Verbindung zur Anprobe ist abgebrochen. Bitte gleich noch einmal versuchen."},
    "err.badFile": {"zh": "無法讀取這張照片，請改用 JPG、PNG 或 WEBP。", "en": "This photo could not be read. Please use a JPG, PNG or WEBP.", "ja": "この写真を読み込めません。JPG、PNG、WEBP をお使いください。", "de": "Dieses Foto lässt sich nicht lesen. Bitte JPG, PNG oder WEBP verwenden."},
    "err.busy": {"zh": "目前正在為其他人生成圖片，請等一分鐘再試。", "en": "The AI is busy with other visitors. Please try again in a minute.", "ja": "ただいま混み合っています。1分ほどしてからお試しください。", "de": "Die KI ist gerade ausgelastet. Bitte in einer Minute erneut versuchen."},
    "err.allAccountsExhausted": {"zh": "今天的生成額度已用完，請晚一點再來。", "en": "Today's generation quota is used up. Please come back later.", "ja": "本日の生成枠を使い切りました。後ほどお試しください。", "de": "Das Kontingent für heute ist aufgebraucht. Bitte später wiederkommen."},
    "err.noImageFromModel": {"zh": "AI 在這張照片裡認不出毛孩。請換一張清楚、全身、沒有太多雜物的照片再試。",
                             "en": "The AI could not find a pet in this photo. Try a clearer full-body photo with less clutter.",
                             "ja": "AI がこの写真からペットを認識できませんでした。全身がはっきり写った写真でお試しください。",
                             "de": "Die KI konnte auf diesem Foto kein Tier erkennen. Bitte ein klares Ganzkörperfoto versuchen."},
    "err.attachFailed": {"zh": "照片沒有成功送達，請再試一次。", "en": "The photos did not arrive. Please try again.", "ja": "写真の送信に失敗しました。もう一度お試しください。", "de": "Die Fotos sind nicht angekommen. Bitte erneut versuchen."},
    "err.unauthorized": {"zh": "伺服器拒絕了這次請求，請重新整理頁面再試。", "en": "The server refused the request. Please reload the page and try again.", "ja": "サーバーに拒否されました。ページを再読み込みしてお試しください。", "de": "Der Server hat die Anfrage abgelehnt. Bitte Seite neu laden und erneut versuchen."},
    "err.timeout": {"zh": "AI 回應超過 5 分鐘，請再試一次。", "en": "The AI took more than 5 minutes. Please try again.", "ja": "AI の応答が5分を超えました。もう一度お試しください。", "de": "Die KI hat über 5 Minuten gebraucht. Bitte erneut versuchen."},
    "err.noImage": {"zh": "伺服器沒有回傳圖片，請再試一次。", "en": "The server returned no picture. Please try again.", "ja": "サーバーから画像が返りませんでした。もう一度お試しください。", "de": "Der Server hat kein Bild geliefert. Bitte erneut versuchen."},
    "err.generic": {"zh": "試穿失敗：", "en": "Something went wrong: ", "ja": "試着に失敗しました：", "de": "Fehler: "},
    "err.cancelled": {"zh": "已取消。", "en": "Cancelled.", "ja": "キャンセルしました。", "de": "Abgebrochen."},
    "size.rec": {"zh": "建議尺寸", "en": "Recommended size", "ja": "おすすめサイズ", "de": "Empfohlene Größe"},
    "size.detail": {"zh": "{size} 號衣長 {len} cm，比背長短 {d} cm。", "en": "Size {size} is {len} cm long, {d} cm shorter than the back.", "ja": "{size} の着丈は {len} cm、背丈より {d} cm 短めです。", "de": "Größe {size} ist {len} cm lang, {d} cm kürzer als der Rücken."},
    "size.bumped": {"zh": "依領圍或腹圍往上調了一號。", "en": "Moved up a size for the neck or girth.", "ja": "首回り・胴回りに合わせて 1 サイズ上げました。", "de": "Wegen Hals- oder Bauchumfang eine Größe größer gewählt."},
    "size.loose": {"zh": "想寬鬆一點可選 {size}。", "en": "For a looser fit choose {size}.", "ja": "ゆったりめなら {size} も。", "de": "Für lockeren Sitz {size} wählen."},
    "size.small": {"zh": "背長比最小尺寸還短，S 可能偏大。", "en": "The back is shorter than the smallest size; S may be large.", "ja": "背丈が最小サイズより短く、S でも大きめかもしれません。", "de": "Der Rücken ist kürzer als die kleinste Größe; S könnte groß ausfallen."},
    "size.big": {"zh": "背長超過最大尺寸，{size} 可能偏短。", "en": "The back is longer than the largest size; {size} may be short.", "ja": "背丈が最大サイズを超えています。{size} でも短めかもしれません。", "de": "Der Rücken ist länger als die größte Größe; {size} könnte kurz sein."},
    "size.need": {"zh": "填入背長就能算出建議尺寸。", "en": "Enter the back length to get a size.", "ja": "背丈を入力するとサイズが出ます。", "de": "Rückenlänge eingeben, um eine Größe zu erhalten."},
    "go.product": {"zh": "前往商品頁，選 {size}", "en": "Go to the product, size {size}", "ja": "商品ページへ（{size}）", "de": "Zum Produkt, Größe {size}"},
    "go.plain": {"zh": "前往商品頁", "en": "Go to the product", "ja": "商品ページへ", "de": "Zum Produkt"},
    "file.name": {"zh": "apetto-試衣間.jpg", "en": "apetto-fitting-room.jpg", "ja": "apetto-試着室.jpg", "de": "apetto-anprobe.jpg"},
    "share.text": {"zh": "看看牠穿 apetto 的樣子！", "en": "Look at them in apetto!", "ja": "apetto を着た姿を見て！", "de": "Schau, wie apetto steht!"},
}

CSS = r"""
/* fitting room */
.sr-only{position:absolute;width:1px;height:1px;overflow:hidden;clip:rect(0 0 0 0);white-space:nowrap}
.fit-head{padding:28px 0 8px}.fit-head h1{font-size:clamp(28px,4vw,42px);line-height:1.15;margin:0 0 12px;letter-spacing:-.01em}
.fit-head .lead{font-size:17px;color:var(--ink2);max-width:60ch;margin:0 0 18px}
.fit-status{display:inline-flex;align-items:center;gap:8px;padding:7px 14px 7px 10px;border-radius:999px;background:#fff;border:1px solid var(--line);font-size:14px;font-weight:600;color:var(--ink2)}
.fit-status i{width:9px;height:9px;border-radius:50%;background:#c4c7cf;flex:0 0 auto}
.fit-status.on i{background:#1fa463;box-shadow:0 0 0 4px rgba(31,164,99,.15)}.fit-status.off{background:#fff4f2;border-color:#ffd1c9;color:var(--brand-ink)}.fit-status.off i{background:var(--brand)}
.fit-grid{display:grid;grid-template-columns:minmax(0,5fr) minmax(0,6fr);gap:28px;align-items:start;padding:20px 0 56px}
.fit-card{background:var(--card);border:1px solid var(--line);border-radius:var(--radius);padding:22px 22px 24px}
.fit-card+.fit-card{margin-top:16px}
.fit-card h2{display:flex;align-items:center;gap:12px;font-size:18px;margin:0 0 14px}
.fit-card h2 b{display:inline-grid;place-items:center;width:30px;height:30px;border-radius:50%;background:var(--ink);color:#fff;font-size:14px;font-weight:800;flex:0 0 auto}
.fit-drop{position:relative;display:block;border:2px dashed var(--line2);border-radius:16px;background:var(--sand);min-height:190px;cursor:pointer;overflow:hidden;transition:border-color .15s,background .15s}
.fit-drop:hover,.fit-drop.over{border-color:var(--ink);background:#f7f3ea}.fit-drop input{position:absolute;inset:0;opacity:0;cursor:pointer;width:100%;height:100%}
.fit-drop .ph{display:flex;flex-direction:column;align-items:center;justify-content:center;text-align:center;gap:6px;padding:30px 20px;color:var(--ink2);min-height:190px}
.fit-drop .ph svg{width:36px;height:36px;color:var(--ink);margin-bottom:6px}.fit-drop .ph b{font-size:16px;color:var(--ink)}.fit-drop .ph span{font-size:13.5px;color:var(--mute);max-width:34ch}
.fit-drop .pv{display:none;position:relative;aspect-ratio:4/3;background:var(--sand)}.fit-drop .pv img{width:100%;height:100%;object-fit:contain;display:block}
.fit-drop .pv span{position:absolute;left:50%;bottom:12px;transform:translateX(-50%);background:rgba(255,255,255,.92);color:var(--ink);font-size:13px;font-weight:700;padding:6px 12px;border-radius:999px;white-space:nowrap}
.fit-drop.has .ph{display:none}.fit-drop.has .pv{display:block}
.fit-demo{margin:16px 0 0;font-size:14px;color:var(--mute)}.fit-demo p{margin:0 0 8px}
.fit-demo .row{display:flex;gap:10px;flex-wrap:wrap}
.fit-demo button{display:inline-flex;align-items:center;gap:10px;padding:6px 14px 6px 6px;border-radius:999px;border:1.5px solid var(--line2);background:#fff;font:inherit;font-size:14px;font-weight:600;color:var(--ink2);cursor:pointer}
.fit-demo button img{width:34px;height:34px;border-radius:50%;object-fit:cover}.fit-demo button:hover{border-color:var(--ink);color:var(--ink)}.fit-demo button.cur{border-color:var(--ink);background:var(--ink);color:#fff}
.fit-coats{display:grid;grid-template-columns:repeat(3,1fr);gap:12px}
.fit-coat{position:relative;border:2px solid var(--line);border-radius:16px;background:#fff;padding:10px 10px 12px;text-align:left;cursor:pointer;font:inherit;color:var(--ink);transition:border-color .15s,transform .15s,box-shadow .15s}
.fit-coat:hover{border-color:var(--ink2);transform:translateY(-2px);box-shadow:0 10px 24px rgba(0,0,0,.06)}.fit-coat.cur{border-color:var(--ink);box-shadow:0 0 0 3px rgba(23,24,26,.12)}
.fit-coat .img{aspect-ratio:1;border-radius:10px;overflow:hidden;background:#fff;display:grid;place-items:center}.fit-coat img{width:100%;height:100%;object-fit:contain}
.fit-coat .nm{display:block;font-weight:700;font-size:14.5px;margin-top:10px;line-height:1.3}.fit-coat .sub{display:block;font-size:12.5px;color:var(--mute);line-height:1.35;margin-top:2px}
.fit-coat .chk{position:absolute;top:8px;right:8px;width:24px;height:24px;border-radius:50%;background:var(--ink);color:#fff;display:none;place-items:center}.fit-coat.cur .chk{display:grid}
.fit-coat-links{display:flex;gap:12px;flex-wrap:wrap;margin:12px 0 0;font-size:13.5px}.fit-coat-links a{color:var(--ink2);border-bottom:1px solid var(--line2)}.fit-coat-links a:hover{color:var(--ink);border-color:var(--ink)}
.fit-go{margin-top:16px}.fit-go .btn{width:100%}.fit-go .btn:disabled{opacity:.45;cursor:not-allowed;transform:none}
.fit-go p{margin:10px 0 0;font-size:13.5px;color:var(--mute);text-align:center}
.fit-stage{position:sticky;top:96px}
.fit-stage .box{position:relative;background:var(--card);border:1px solid var(--line);border-radius:var(--radius);overflow:hidden;aspect-ratio:1;display:grid;place-items:center}
.fit-stage .box>*{grid-area:1/1}
.fit-stage .empty{display:flex;flex-direction:column;align-items:center;text-align:center;gap:8px;padding:30px;color:var(--mute);font-size:15px;max-width:34ch}
.fit-stage .empty svg{width:44px;height:44px;color:var(--line2)}
.fit-stage .shot{width:100%;height:100%;object-fit:contain;display:none;background:#fff}
.fit-stage .busy{display:none;width:100%;height:100%;background:#111}
.fit-stage .busy img{width:100%;height:100%;object-fit:contain;opacity:.55;filter:saturate(.7)}
.fit-stage .busy:after{content:"";position:absolute;left:0;right:0;top:-30%;height:30%;background:linear-gradient(to bottom,transparent,rgba(255,255,255,.55),transparent);animation:fit-scan 2.2s linear infinite}
@keyframes fit-scan{to{top:100%}}
.fit-stage .prog{position:absolute;left:0;right:0;bottom:0;padding:16px 18px 18px;background:linear-gradient(to top,rgba(0,0,0,.78),rgba(0,0,0,0));color:#fff;display:none}
.fit-stage .prog b{display:block;font-size:16px;margin-bottom:4px}.fit-stage .prog span{font-size:13px;color:#d6d8de}
.fit-stage .prog .bar{height:4px;border-radius:2px;background:rgba(255,255,255,.25);margin-top:12px;overflow:hidden}.fit-stage .prog .bar i{display:block;height:100%;width:5%;background:#fff;border-radius:2px;transition:width .8s ease}
.fit-stage[data-state=busy] .busy,.fit-stage[data-state=busy] .prog{display:block}.fit-stage[data-state=busy] .empty,.fit-stage[data-state=done] .empty{display:none}
.fit-stage[data-state=done] .shot{display:block;animation:fit-pop .7s cubic-bezier(.2,.8,.2,1) both}
@keyframes fit-pop{from{opacity:0;transform:scale(.92)}to{opacity:1;transform:none}}
.fit-stage.flash .box{animation:fit-ring 1.8s ease-out both}
@keyframes fit-ring{0%{box-shadow:0 0 0 0 rgba(255,36,20,.55)}60%{box-shadow:0 0 0 14px rgba(255,36,20,0)}100%{box-shadow:0 0 0 0 rgba(255,36,20,0)}}
.fit-stage .done-badge{position:absolute;top:14px;left:14px;display:none;align-items:center;gap:8px;background:var(--brand);color:#fff;font-weight:800;font-size:15px;padding:9px 16px;border-radius:999px;box-shadow:0 8px 24px rgba(255,36,20,.35);z-index:2}
.fit-stage.flash .done-badge{display:inline-flex;animation:fit-badge 3.2s ease both}
@keyframes fit-badge{0%{opacity:0;transform:translateY(-10px) scale(.9)}12%{opacity:1;transform:none}80%{opacity:1}100%{opacity:0;transform:translateY(-6px)}}
@media (prefers-reduced-motion:reduce){.fit-stage[data-state=done] .shot,.fit-stage.flash .box,.fit-stage.flash .done-badge{animation:none}.fit-stage.flash .done-badge{display:inline-flex}}
.fit-steps{display:flex;gap:6px;margin:14px 0 0}.fit-steps span{flex:1;height:4px;border-radius:2px;background:var(--line)}.fit-steps span.on{background:var(--ink)}.fit-steps span.done{background:#1fa463}
.fit-note{display:none;margin-top:14px;background:var(--sand);border-radius:14px;padding:14px 16px;font-size:15px;color:var(--ink2)}
.fit-note b{display:block;font-size:13px;color:var(--brand-ink);letter-spacing:.06em;margin-bottom:4px}.fit-note p{margin:0}.fit-note.wait p{color:var(--mute);font-style:italic}
.fit-note.show{display:block}
.fit-actions{display:none;gap:10px;margin-top:14px;flex-wrap:wrap}.fit-actions .btn{flex:1 1 160px}.fit-stage[data-state=done] .fit-actions{display:flex}
.fit-actions .btn svg{width:18px;height:18px;flex:0 0 auto}
.fit-fine{margin:12px 0 0;font-size:13px;color:var(--mute)}
.fit-err{display:none;margin-top:14px;background:#fff4f2;border:1px solid #ffd1c9;color:var(--brand-ink);border-radius:14px;padding:12px 16px;font-size:14.5px}.fit-err.show{display:block}
.fit-cancel{display:none;margin-top:10px;text-align:center}.fit-stage[data-state=busy] .fit-cancel{display:block}
.fit-cancel button{background:none;border:0;font:inherit;font-size:14px;color:var(--mute);text-decoration:underline;cursor:pointer}
.fit-size{display:none;margin-top:14px;background:var(--card);border:1px solid var(--line);border-radius:16px;padding:16px 18px 18px}
.fit-stage[data-state=done] .fit-size{display:block;animation:fit-pop .6s .35s cubic-bezier(.2,.8,.2,1) both}
.fit-size h3{font-size:16px;margin:0 0 6px}.fit-size .hint{margin:0 0 12px;font-size:13.5px;color:var(--mute);line-height:1.55}
.fit-size .fields{display:grid;grid-template-columns:repeat(3,1fr);gap:10px}
.fit-size label{display:flex;flex-direction:column;gap:4px;font-size:13px;color:var(--ink2);font-weight:600}
.fit-size label>div{display:flex;align-items:center;border:1.5px solid var(--line2);border-radius:10px;background:#fff;padding:0 10px}
.fit-size label>div:focus-within{border-color:var(--ink)}.fit-size input{width:100%;min-width:0;border:0;outline:0;background:none;font:inherit;font-size:16px;font-weight:600;padding:9px 0;color:var(--ink)}
.fit-size em{font-style:normal;font-size:13px;color:var(--mute)}
.fit-size-out{margin-top:12px;font-size:14.5px;color:var(--ink2)}.fit-size-out .big{display:flex;align-items:baseline;gap:10px;margin-bottom:4px}
.fit-size-out .big b{font-size:28px;color:var(--ink);line-height:1}.fit-size-out .big span{font-size:13px;color:var(--brand-ink);font-weight:700;letter-spacing:.06em}
.fit-size-out p{margin:0 0 4px}.fit-size-out .btn{margin-top:10px;width:100%}
@media (max-width:480px){.fit-size .fields{grid-template-columns:1fr 1fr 1fr;gap:6px}.fit-size label{font-size:12px}.fit-size label>div{padding:0 8px}}
.fit-promo{background:#fff;border:1px solid var(--line);border-radius:28px;padding:40px 44px;display:grid;grid-template-columns:1fr auto;gap:28px;align-items:center}
.fit-promo h2{font-size:clamp(22px,2.6vw,30px);margin:0 0 8px}.fit-promo p{margin:0;color:var(--ink2);font-size:16.5px;max-width:52ch}
.fit-promo .coats{display:flex;gap:-6px}.fit-promo .coats img{width:84px;height:84px;border-radius:50%;object-fit:cover;object-position:60% 50%;border:3px solid #fff;background:#fff;box-shadow:0 2px 10px rgba(0,0,0,.08);margin-left:-14px}
.fit-promo .coats img:first-child{margin-left:0}.fit-promo .side{display:flex;align-items:center;gap:22px}
@media (max-width:980px){.fit-grid{grid-template-columns:1fr;gap:18px;padding-bottom:40px}.fit-stage{position:static}.fit-card{padding:18px 16px 20px}
 .fit-promo{grid-template-columns:1fr;padding:26px 22px;border-radius:22px}.fit-promo .side{flex-direction:column;align-items:flex-start;gap:16px}.fit-promo .coats img{width:64px;height:64px}}
@media (max-width:480px){.fit-coats{gap:8px}.fit-coat{padding:8px 8px 10px}.fit-coat .nm{font-size:13.5px}.fit-coat .sub{display:none}}
"""

JS = r"""(function(){
var el=document.getElementById('apt-fit');if(!el)return;var cfg=JSON.parse(el.textContent),S=cfg.strings;
function t(k,v){var s=S[k]||k;if(v)for(var x in v)s=s.split('{'+x+'}').join(v[x]);return s;}
function auth(h){h=h||{};if(cfg.key)h['x-api-key']=cfg.key;return h;}
var $=function(q){return document.querySelector(q);};
var drop=$('.fit-drop'),file=$('.fit-drop input'),pv=$('.fit-drop .pv img'),stage=$('.fit-stage'),shot=$('.fit-stage .shot'),busyImg=$('.fit-stage .busy img'),
 progT=$('.fit-stage .prog b'),progS=$('.fit-stage .prog span'),bar=$('.fit-stage .prog .bar i'),steps=document.querySelectorAll('.fit-steps span'),
 go=$('.fit-go .btn'),err=$('.fit-err'),note=$('.fit-note'),noteP=$('.fit-note p'),status=$('.fit-status'),dl=$('.fit-dl'),share=$('.fit-share'),again=$('.fit-again'),cancelBtn=$('.fit-cancel button');
var dog=null,coat=null,online=null,running=null,resultUrl='',captionTimer=null;
function setErr(m){err.textContent=m||'';err.classList.toggle('show',!!m);}
function setStatus(st){online=st;status.className='fit-status '+(st===null?'':st?'on':'off');
 status.lastElementChild.textContent=st===null?cfg.ui.connecting:st?cfg.ui.online:cfg.ui.offline;update();}
function update(){go.disabled=!(dog&&coat&&!running);}
function health(){var c=new AbortController();var tm=setTimeout(function(){c.abort();},8000);
 fetch(cfg.api+'/api/health',{signal:c.signal,cache:'no-store'}).then(function(r){setStatus(r.ok);}).catch(function(){setStatus(false);}).then(function(){clearTimeout(tm);});}
health();setInterval(health,45000);
document.addEventListener('visibilitychange',function(){if(!document.hidden)health();});
/* photo */
function loadImg(src){return new Promise(function(res,rej){var i=new Image();i.onload=function(){res(i);};i.onerror=rej;i.src=src;});}
function compress(src,max,q){return loadImg(src).then(function(i){var r=Math.min(max/i.width,max/i.height,1),c=document.createElement('canvas');
 c.width=Math.max(1,Math.round(i.width*r));c.height=Math.max(1,Math.round(i.height*r));var g=c.getContext('2d');g.fillStyle='#fff';g.fillRect(0,0,c.width,c.height);g.drawImage(i,0,0,c.width,c.height);return c.toDataURL('image/jpeg',q);});}
function setDog(src,demo){setErr('');return loadImg(src).then(function(){dog=src;pv.src=src;drop.classList.add('has');
 document.querySelectorAll('.fit-demo button').forEach(function(b){b.classList.toggle('cur',b.dataset.dog===demo);});update();}).catch(function(){setErr(t('err.badFile'));});}
function pick(f){if(!f)return;if(!/^image\//.test(f.type)&&!/\.(heic|heif|jpe?g|png|webp|gif|bmp)$/i.test(f.name)){setErr(t('err.badFile'));return;}
 var rd=new FileReader();rd.onload=function(){setDog(rd.result,null);};rd.onerror=function(){setErr(t('err.badFile'));};rd.readAsDataURL(f);}
file.addEventListener('change',function(){pick(file.files[0]);file.value='';});
['dragenter','dragover'].forEach(function(n){drop.addEventListener(n,function(e){e.preventDefault();drop.classList.add('over');});});
['dragleave','drop'].forEach(function(n){drop.addEventListener(n,function(e){e.preventDefault();drop.classList.remove('over');});});
drop.addEventListener('drop',function(e){pick(e.dataTransfer.files&&e.dataTransfer.files[0]);});
document.querySelectorAll('.fit-demo button').forEach(function(b){b.addEventListener('click',function(){setDog(b.dataset.src,b.dataset.dog);});});
/* coat */
var coatKey=null;
document.querySelectorAll('.fit-coat').forEach(function(b){b.addEventListener('click',function(){coat=b.dataset.src;coatKey=b.dataset.coat;
 document.querySelectorAll('.fit-coat').forEach(function(x){x.classList.toggle('cur',x===b);});update();sizeOut();});});
/* size advice from the chosen coat's size chart: garment length ~ back length - offset, bumped up if neck/girth exceed the row */
var sizeBox=$('.fit-size-out');
function mval(k){var i=$('.fit-size input[data-m='+k+']');return i?parseFloat(i.value)||0:0;}
function recommend(c){var back=mval('back'),neck=mval('neck'),belly=mval('belly');if(!back||!c||!c.chart)return null;
 var rows=c.chart.rows.map(function(r){return {size:r[0],len:+r[1],neck:+r[2],belly:+String(r[3]).split(/[~\-–]/).pop()};});
 var target=back-c.chart.offset,best=0,bd=1e9;rows.forEach(function(r,i){var d=Math.abs(r.len-target);if(d<bd){bd=d;best=i;}});
 var i=best;while(i<rows.length-1&&((neck&&neck>rows[i].neck)||(belly&&belly>rows[i].belly)))i++;
 var r=rows[i],note='';if(target<rows[0].len-3)note=t('size.small');else if(target>rows[rows.length-1].len+3)note=t('size.big',{size:r.size});
 return {size:r.size,len:r.len,diff:Math.round((back-r.len)*10)/10,bumped:i>best,loose:rows[i+1]?rows[i+1].size:null,note:note};}
function sizeOut(){var c=coatKey&&cfg.coats[coatKey];if(!sizeBox||!c)return;var rec=recommend(c),h='';
 if(rec){h='<div class="big"><span>'+t('size.rec')+'</span><b>'+rec.size+'</b></div><p>'+t('size.detail',{size:rec.size,len:rec.len,d:rec.diff})+(rec.bumped?' '+t('size.bumped'):'')+(rec.loose?' '+t('size.loose',{size:rec.loose}):'')+'</p>'+(rec.note?'<p>'+rec.note+'</p>':'');}
 else h='<p>'+t('size.need')+'</p>';
 if(stage.dataset.state==='done'&&c.url)h+='<a class="btn" href="'+c.url+(rec?'#size='+encodeURIComponent(rec.size):'')+'">'+(rec?t('go.product',{size:rec.size}):t('go.plain'))+'</a>';
 sizeBox.innerHTML=h;}
document.querySelectorAll('.fit-size input').forEach(function(i){i.addEventListener('input',sizeOut);});
/* progress */
var curStep=0;
function step(n,txt){curStep=n;steps.forEach(function(s,i){s.className=i<n?'done':i===n?'on':'';});if(txt)progT.textContent=txt;bar.style.width=Math.min(96,8+n*28)+'%';}
function showNote(text,pending){clearTimeout(captionTimer);if(!cfg.showNote){note.classList.remove('show');return;}
 note.classList.toggle('wait',!!pending);noteP.textContent=pending?t('note.writing'):(text||'');note.classList.toggle('show',!!(pending||(text||'').trim()));}
function pollCaption(id){if(!id||!cfg.showNote)return;var end=Date.now()+120000;showNote('',true);
 var tick=function(){if(Date.now()>end){showNote('');return;}
  fetch(cfg.api+'/api/caption/'+encodeURIComponent(id),{headers:auth()}).then(function(r){return r.ok?r.json():null;}).then(function(d){
   if(d&&d.status==='ready'){showNote(d.caption);return;}if(d&&d.status==='none'){showNote('');return;}captionTimer=setTimeout(tick,2000);}).catch(function(){captionTimer=setTimeout(tick,2500);});};
 captionTimer=setTimeout(tick,1500);}
/* make the finished picture impossible to miss: scroll to it, pulse the frame, badge, a short buzz on phones */
var flashTimer=null;
function celebrate(){stage.classList.remove('flash');void stage.offsetWidth;stage.classList.add('flash');clearTimeout(flashTimer);flashTimer=setTimeout(function(){stage.classList.remove('flash');},3400);
 var box=$('.fit-stage .box');setTimeout(function(){box.scrollIntoView({behavior:'smooth',block:'center'});},80);
 try{if(navigator.vibrate)navigator.vibrate([40,60,40]);}catch(e){}
 if(document.hidden){var old=document.title,n=0,tt=setInterval(function(){document.title=(n++%2?'✓ ':'')+old;if(!document.hidden||n>20){clearInterval(tt);document.title=old;}},900);}}
function finish(){if(running){clearInterval(running.poll);clearInterval(running.tick);clearTimeout(running.tm);running=null;}update();}
go.addEventListener('click',function(){
 if(!dog||!coat){setErr(t('err.pickFirst'));return;}if(online===false){setErr(t('err.offline'));return;}
 setErr('');showNote('');resultUrl='';var jobId=(crypto.randomUUID&&crypto.randomUUID())||(Date.now()+'-'+Math.random().toString(36).slice(2));
 var ctl=new AbortController(),t0=Date.now(),run={ctl:ctl};running=run;update();
 busyImg.src=dog;stage.dataset.state='busy';step(0,t('step.prepare'));progS.textContent=t('elapsed',{sec:0});sizeOut();
 if(window.innerWidth<981)setTimeout(function(){stage.scrollIntoView({behavior:'smooth',block:'start'});},50);
 run.tick=setInterval(function(){progS.textContent=t('elapsed',{sec:Math.round((Date.now()-t0)/1000)});},1000);
 run.tm=setTimeout(function(){ctl.abort('timeout');},300000);
 var soft=setTimeout(function(){if(running===run&&curStep<1)step(1,t('step.send'));},9000);
 Promise.all([compress(dog,800,.82),compress(coat,600,.82)]).then(function(imgs){
  step(1,t('step.send'));
  run.poll=setInterval(function(){fetch(cfg.api+'/api/status/'+encodeURIComponent(jobId),{cache:'no-store'}).then(function(r){return r.ok?r.json():null;}).then(function(d){
   if(!d||running!==run)return;var txt=d.key&&S[d.key]?t(d.key,d.vars||{}):'';var st=d.step||0;
   if(st>=6)step(2,txt||t('step.draw'));else if(st>=3)step(1,txt||t('step.send'));else if(txt&&st>=2)progT.textContent=txt;}).catch(function(){});},1000);
  return fetch(cfg.api+'/api/stylist',{method:'POST',signal:ctl.signal,headers:auth({'Content-Type':'application/json'}),
   body:JSON.stringify({dogImage:imgs[0],clothesImage:imgs[1],lang:cfg.serverLang,jobId:jobId})});
 }).then(function(r){
  if(!r.ok){return r.json().catch(function(){return {};}).then(function(d){
   if(r.status===429)throw new Error(t(d.errorKey||'err.busy'));if(r.status===503)throw new Error(t(d.errorKey||'err.allAccountsExhausted'));
   if(r.status===401)throw new Error(t('err.unauthorized'));if(d.errorKey&&S[d.errorKey])throw new Error(t(d.errorKey));throw new Error(d.error||('HTTP '+r.status));});}
  return r.json();
 }).then(function(d){
  if(running!==run)return;var src=d&&d.image;if(!src||!(/^data:image|^https?:/.test(src)))throw new Error(t('err.noImage'));
  step(3,t('step.done'));return loadImg(src).then(function(){resultUrl=src;shot.src=src;stage.dataset.state='done';finish();sizeOut();celebrate();
   if(d.caption&&String(d.caption).trim())showNote(d.caption);else pollCaption(d.captionId);});
 }).catch(function(e){
  if(running!==run&&!(e&&e.name==='AbortError'))return;var msg;
  if(e&&e.name==='AbortError')msg=ctl.signal.reason==='timeout'?t('err.timeout'):t('err.cancelled');else if(e instanceof TypeError)msg=t(online===false?'err.offline':'err.network');
  else msg=t('err.generic')+((e&&e.message)||e);
  stage.dataset.state=resultUrl?'done':'empty';finish();sizeOut();setErr(msg);if(e instanceof TypeError)health();
 }).then(function(){clearTimeout(soft);});
});
cancelBtn.addEventListener('click',function(){if(running)running.ctl.abort('cancel');});
/* result actions */
dl.addEventListener('click',function(){if(!resultUrl)return;var a=document.createElement('a');a.href=resultUrl;a.download=t('file.name');document.body.appendChild(a);a.click();a.remove();});
function toFile(){return fetch(resultUrl).then(function(r){return r.blob();}).then(function(b){return new File([b],t('file.name'),{type:b.type||'image/jpeg'});});}
if(navigator.share){share.addEventListener('click',function(){toFile().then(function(f){var d={files:[f],text:t('share.text')};
 if(navigator.canShare&&!navigator.canShare(d))d={text:t('share.text'),url:location.href};return navigator.share(d);}).catch(function(){});});}else{share.style.display='none';}
again.addEventListener('click',function(){stage.dataset.state='empty';resultUrl='';showNote('');setErr('');coat=null;coatKey=null;
 document.querySelectorAll('.fit-coat').forEach(function(x){x.classList.remove('cur');});update();$('.fit-coats').scrollIntoView({behavior:'smooth',block:'center'});});
})();"""

ICON_UP = ('<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">'
           '<path d="M4 16v2a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-2M12 4v12M7 9l5-5 5 5"/></svg>')
ICON_PIC = ('<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">'
            '<rect x="3" y="4" width="18" height="16" rx="3"/><circle cx="9" cy="10" r="2"/><path d="m21 16-5-5-9 9"/></svg>')
ICON_DL = ('<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">'
           '<path d="M12 4v11M7 10l5 5 5-5M4 19h16"/></svg>')
ICON_CHECK = '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M5 12l5 5L20 7"/></svg>'


def config_json(data, lang):
    import theme as th
    strings = {k: v.get(lang) or v["zh"] for k, v in STR.items()}
    ui = {"connecting": "連線中…", "online": "試衣間運作中", "offline": "試衣間暫停服務中，請稍後再來。"}
    ui = {k: (UI[v].get(lang) if lang != "zh" else v) or v for k, v in ui.items()}
    charts = th.sb.load_image_text().get("charts", {})
    by_id = {p["id"]: p for p in data["products"]}
    coats = {}
    for k, f, colour, pid, chart_key in COATS:
        p = by_id.get(pid)
        c = charts.get(chart_key)
        coats[k] = {"url": th.link(th.rel_dir(PAGE), th.sb.product_page(p), lang) if p and p.get("visible", True) else "",
                    "chart": {"rows": c["rows"], "offset": CHART_OFFSET.get(chart_key, 8)} if c else None}
    return json.dumps({"api": API_BASE, "key": API_KEY, "serverLang": SERVER_LANG.get(lang, "zh"),
                       "showNote": SHOW_NOTE.get(lang, False), "strings": strings, "ui": ui, "coats": coats}, ensure_ascii=False)


def render(data, lang):
    import theme as th
    d = th.rel_dir(PAGE)
    by_id = {p["id"]: p for p in data["products"]}
    demo = "".join(f'<button type="button" data-dog="{k}" data-src="{th.asset(d, ASSET_DIR + f)}"><img src="{th.asset(d, ASSET_DIR + f)}" alt="">{th.esc(name)}</button>'
                   for k, f, name in DOGS)
    coats, links = "", ""
    for k, f, colour, pid, _chart in COATS:
        p = by_id.get(pid)
        sub = f'<span class="sub">{th.esc(p["name"])}</span>' if p else ""
        coats += (f'<button type="button" class="fit-coat" data-coat="{k}" data-src="{th.asset(d, ASSET_DIR + f)}">'
                  f'<span class="chk">{ICON_CHECK}</span><span class="img"><img src="{th.asset(d, ASSET_DIR + f)}" alt="{th.esc(colour)}" loading="lazy"></span>'
                  f'<span class="nm">{th.esc(colour)}</span>{sub}</button>')
        if p and p.get("visible", True):
            links += f'<a href="{th.link(d, th.sb.product_page(p), lang)}">{th.esc(colour)}<span aria-hidden="true"> · </span>查看商品</a>'
    crumbs = f'<li><a href="{th.link(d, "index.html", lang)}">首頁</a></li><li>AI 試衣間</li>'
    body = f"""<div class="wrap"><ol class="breadcrumb">{crumbs}</ol>
<div class="fit-head rv in"><span class="eyebrow">AI 試衣間</span><h1>讓毛孩先試穿，再決定</h1>
 <p class="lead">上傳一張毛孩的照片，挑一件 apetto，AI 會畫出牠穿上的樣子。</p>
 <div class="fit-status" role="status"><i></i><span>連線中…</span></div></div>
<div class="fit-grid">
 <div class="fit-col rv in">
  <section class="fit-card"><h2><b>1</b>毛孩照片</h2>
   <label class="fit-drop"><input type="file" accept="image/*" aria-label="毛孩照片">
    <div class="ph">{ICON_UP}<b>點這裡選照片，或把照片拖進來</b><span>全身、側面、光線清楚的照片效果最好。支援 JPG、PNG、WEBP。</span></div>
    <div class="pv"><img alt="毛孩照片"><span>更換照片</span></div></label>
   <div class="fit-demo"><p>沒有照片？先用示範狗狗試試</p><div class="row">{demo}</div></div>
  </section>
  <section class="fit-card"><h2><b>2</b>選一件 apetto</h2>
   <div class="fit-coats">{coats}</div>
   <div class="fit-coat-links">{links}</div>
   <div class="fit-go"><button type="button" class="btn brand big" disabled>開始試穿</button><p>AI 生成約需 20 到 40 秒，尖峰時段可能更久。</p></div>
   <div class="fit-err" role="alert"></div>
  </section>
 </div>
 <section class="fit-stage rv in" data-state="empty" aria-live="polite"><h2 class="sr-only">試穿結果</h2>
  <div class="box">
   <div class="empty">{ICON_PIC}<span>選好照片和衣服後，試穿結果會出現在這裡。</span></div>
   <div class="busy"><img alt=""></div>
   <img class="shot" alt="試穿結果">
   <div class="prog"><b></b><span></span><div class="bar"><i></i></div></div>
   <div class="done-badge"><span aria-hidden="true">✓</span><span>試穿完成</span></div>
  </div>
  <div class="fit-steps" aria-hidden="true"><span></span><span></span><span></span><span></span></div>
  <div class="fit-cancel"><button type="button">取消</button></div>
  <div class="fit-size"><h3>喜歡嗎？量一下毛孩，看該選哪一號</h3><p class="hint">背長：從脖子根部（約前腳的位置）量到尾巴根。領圍與腹圍為圈量，可以不填。</p>
   <div class="fields"><label><span>背長</span><div><input type="number" inputmode="decimal" min="10" max="120" step="0.5" data-m="back"><em>cm</em></div></label>
    <label><span>領圍</span><div><input type="number" inputmode="decimal" min="10" max="120" step="0.5" data-m="neck"><em>cm</em></div></label>
    <label><span>腹圍</span><div><input type="number" inputmode="decimal" min="10" max="150" step="0.5" data-m="belly"><em>cm</em></div></label></div>
   <div class="fit-size-out"></div></div>
  <div class="fit-note"><b>AI 造型師的話</b><p></p></div>
  <div class="fit-actions"><button type="button" class="btn fit-dl">{ICON_DL}下載照片</button><button type="button" class="btn ghost fit-share">分享</button><button type="button" class="btn ghost fit-again">再試一件</button></div>
  <p class="fit-fine">試穿圖由 AI 生成，顏色與版型以實際商品為準。</p>
 </section>
</div></div>
<script id="apt-fit" type="application/json">{config_json(data, lang)}</script>
<script src="{th.asset(d, 'assets/fitstudio.js')}?v={th.ASSET_VER['fit']}" defer></script>"""
    title = {"zh": "AI 試衣間", "en": "AI fitting room", "ja": "AI 試着室", "de": "KI-Anprobe"}[lang]
    return th.page(data, PAGE, lang, f"{title} | {th.BRAND}", body, "上傳一張毛孩的照片，挑一件 apetto，AI 會畫出牠穿上的樣子。",
                   og_image=ASSET_DIR + COATS[1][1], current=PAGE, extra_head=f'<link rel="preconnect" href="{API_BASE}">')


def home_promo(d, lang):
    import theme as th
    pics = "".join(f'<img src="{th.asset(d, ASSET_DIR + f)}" alt="" loading="lazy">' for _, f, _, _, _ in COATS)
    return (f'<section class="sec tight"><div class="wrap"><div class="fit-promo rv"><div><span class="eyebrow">新功能</span><h2>AI 試衣間：先看牠穿上的樣子</h2>'
            f'<p>上傳一張照片，挑一件 apetto，約 30 秒就能看到試穿效果。</p></div>'
            f'<div class="side"><div class="coats">{pics}</div><a class="btn" href="{th.link(d, PAGE, lang)}">去試衣間</a></div></div></div></section>')
