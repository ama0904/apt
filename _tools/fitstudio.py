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
import hashlib
import json
import os

API_BASE = "https://apetto-server.tailbec98f.ts.net:8443"
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
# Dog breed / size guess: the photo goes to the fitting-room server (POST /api/dogsize, see _tools/fit_dogsize),
# which runs a small image model on the laptop. Only a hint above the start button, never a block.
# coat card tag: (small dogs, medium & large dogs, back-length range)
FITFOR = {"zh": ("小型犬", "中大型犬", "背長約 {a}～{b} cm", "各種體型", "小型到大型犬都適合"), "en": ("Small dogs", "Medium & large dogs", "Back {a}–{b} cm", "All sizes", "Small to large dogs"),
          "ja": ("小型犬", "中・大型犬", "背丈 約{a}〜{b} cm", "全サイズ", "小型犬から大型犬まで"), "de": ("Kleine Hunde", "Mittlere & große Hunde", "Rücken {a}–{b} cm", "Alle Größen", "Kleine bis große Hunde")}


def coat_fit(coat, charts, lang):
    """Who a coat fits, from its size chart: back length = garment length + the chart offset."""
    key = coat.get("chart") or ""
    c = charts.get(key)
    if not c or not c.get("rows"):
        return None
    off = CHART_OFFSET.get(key, 8)
    lens = [float(r[1]) for r in c["rows"]]
    small, big, rng, allk, allr = FITFOR.get(lang, FITFOR["zh"])
    lo, hi = round(min(lens) + off), round(max(lens) + off)
    if coat.get("allsizes"):   # admin flag: made for every size, so never warned about and always among the suggestions
        return {"kind": allk, "range": allr, "min": 0, "max": 999, "cut": "A"}
    return {"kind": small if c.get("small") else big, "range": rng.format(a=lo, b=hi), "min": lo, "max": hi,
            "cut": "S" if c.get("small") else "L"}


def _load_items(kind, fallback):
    """Admin-managed lists from _data/fitstudio.json ("coats": [{key, label, image, product, chart, visible, i18n}],
    "dogs": [{key, label, image, visible, i18n}]). Falls back to the built-in tuples when the file lacks the list."""
    import theme as th
    f = th.sb.DATA_DIR / "fitstudio.json"
    items = []
    if f.exists():
        try:
            items = json.loads(f.read_text(encoding="utf-8")).get(kind, [])
        except (ValueError, OSError):
            items = []
    if not items:
        items = fallback
    return [c for c in items if c.get("key") and c.get("image") and c.get("visible", True)]


def load_coats():
    return _load_items("coats", [{"key": k, "image": ASSET_DIR + fn, "label": c, "product": pid, "chart": ch} for k, fn, c, pid, ch in COATS])


def load_dogs():
    return _load_items("dogs", [{"key": k, "image": ASSET_DIR + fn, "label": n} for k, fn, n in DOGS])


def img_url(d, site_path):
    """Asset URL plus ?v=<content hash>: swapping a demo dog or coat picture never shows the old cached file."""
    import theme as th
    f = th.sb.SITE / site_path
    try:
        return th.asset(d, site_path) + "?v=" + hashlib.md5(f.read_bytes()).hexdigest()[:8]
    except OSError:
        return th.asset(d, site_path)


# colourways of each fitting-room coat for the recolour test (?recolor=1); the first is the colour Gemini draws.
# (name, hex, product id). Hex values were picked from try-on pictures and product photos.
COLORWAYS = {   # every coat offers 藍 / 紅 / 黃 in the test (the owner's call); product id 0 = no matching product page
    "blue": [("普魯士藍", "#2346b5", 8), ("莓果桃", "#e0306e", 0), ("檸檬螢光黃", "#cfe23f", 6)],
    "yellow": [("檸檬螢光黃", "#cfe23f", 16), ("普魯士藍", "#2346b5", 9), ("莓果桃", "#e0306e", 0)],
    "pink": [("莓果桃", "#e0306e", 15), ("普魯士藍", "#2346b5", 0), ("檸檬螢光黃", "#cfe23f", 0)],
}


def coat_label(c, lang):
    return (((c.get("i18n") or {}).get(lang) or {}).get("label") or c.get("label") or c["key"]).strip()

# Markup strings (zh key -> translations); merged into theme.UI so translate_soup handles the page.
UI = {
    "試衣間": {"en": "Fitting Studio", "ja": "試着室", "de": "Anprobe"},
    "建議款": {"en": "Suggested", "ja": "おすすめ", "de": "Empfohlen"},
    "AI 試衣間": {"en": "AI Fitting Studio", "ja": "AI 試着室", "de": "KI-Anprobe"},
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
    "造型師寫好了": {"en": "Note ready", "ja": "コメント完成", "de": "Notiz fertig"},
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
    "AI 試衣間：先看牠穿上的樣子": {"en": "AI Fitting Studio: see it on your dog first", "ja": "AI 試着室：着た姿を先に見る", "de": "KI-Anprobe: erst sehen, wie es deinem Hund steht"},
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
    "srv.retrying": {"zh": "遇到一點狀況，正在自動重試…", "en": "Hit a snag, retrying automatically…", "ja": "問題が発生したため、自動で再試行中…", "de": "Kleines Problem, es wird automatisch erneut versucht…"},
    "srv.queued": {"zh": "排隊中，前面還有 {pos} 位…", "en": "In the queue, {pos} ahead of you…", "ja": "順番待ち：前に {pos} 人…", "de": "In der Warteschlange, {pos} vor dir…"},
    "srv.queuedNext": {"zh": "排隊中，下一個就輪到你…", "en": "In the queue, you're next…", "ja": "順番待ち：次はあなたです…", "de": "In der Warteschlange, du bist als Nächstes dran…"},
    "srv.done": {"zh": "圖片完成！", "en": "Picture ready!", "ja": "画像が完成！", "de": "Bild fertig!"},
    "note.writing": {"zh": "造型師正在寫推薦…", "en": "The stylist is writing a note…", "ja": "スタイリストがコメントを作成中…", "de": "Die Stylistin schreibt gerade…"},
    "note.missed": {"zh": "造型師這次沒留話，再試一次會有。", "en": "The stylist skipped the note this time. Try again and there will be one.", "ja": "今回はスタイリストのコメントがありませんでした。もう一度試すと届きます。", "de": "Diesmal gab es keine Notiz der Stylistin. Beim nächsten Versuch kommt eine."},
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
    "ai.title": {"zh": "AI 判斷（測試模式）", "en": "AI guess (test mode)", "ja": "AI 判定（テストモード）", "de": "KI-Schätzung (Testmodus)"},
    "ai.wait": {"zh": "AI 判斷中…", "en": "Thinking…", "ja": "判定中…", "de": "Schätze…"},
    "ai.breed": {"zh": "品種", "en": "Breed", "ja": "犬種", "de": "Rasse"},
    "ai.size": {"zh": "體型", "en": "Size", "ja": "体格", "de": "Größe"},
    "ai.sizes": {"zh": "小型 {s}%・中型 {m}%・大型 {l}%", "en": "small {s}% · medium {m}% · large {l}%", "ja": "小型 {s}%・中型 {m}%・大型 {l}%", "de": "klein {s}% · mittel {m}% · groß {l}%"},
    "ai.verdict": {"zh": "結論", "en": "Verdict", "ja": "結論", "de": "Ergebnis"},
    "ai.S": {"zh": "小型犬（建議小汪斗篷）", "en": "small dog (small capes)", "ja": "小型犬（小型犬向けケープ）", "de": "kleiner Hund (kleine Capes)"},
    "ai.L": {"zh": "中大型犬（建議大汪雨衣）", "en": "medium or large dog (big raincoat)", "ja": "中・大型犬（大型犬向けレインコート）", "de": "mittlerer/großer Hund (großer Regenmantel)"},
    "ai.M": {"zh": "中型犬（兩種都可能，請以背長為準）", "en": "medium dog (either may fit; go by the back length)", "ja": "中型犬（どちらも可、背丈で判断）", "de": "mittelgroßer Hund (beides möglich; nach Rückenlänge gehen)"},
    "ai.none": {"zh": "不確定，不提醒客人", "en": "not sure, no hint shown", "ja": "判定できず（ヒントなし）", "de": "unsicher, kein Hinweis"},
    "ai.nodog": {"zh": "照片裡看不太到狗", "en": "no clear dog in the photo", "ja": "写真に犬がはっきり写っていません", "de": "kein Hund klar erkennbar"},
    "ai.err": {"zh": "AI 判斷暫時無法使用", "en": "AI guess unavailable right now", "ja": "AI 判定は現在利用できません", "de": "KI-Schätzung gerade nicht verfügbar"},
    "ai.time": {"zh": "判斷用時 {s} 秒", "en": "took {s} s", "ja": "{s} 秒", "de": "{s} s"},
    "ai.note": {"zh": "品種和體型都是 AI 從照片估計的，約 55 種常見犬種；米克斯或少見品種會顯示最像的。", "en": "Breed and size are AI estimates from the photo (about 55 common breeds); mixed or rare breeds show the closest match.", "ja": "犬種・体格は写真からの AI 推定です（約 55 犬種）。ミックスや珍しい犬種は最も近いものが表示されます。", "de": "Rasse und Größe sind KI-Schätzungen aus dem Foto (etwa 55 Rassen); Mischlinge und seltene Rassen zeigen die ähnlichste."},
    "ai.unsure": {"zh": "品種不太確定，可能是米克斯或少見品種", "en": "breed unsure: maybe mixed or uncommon", "ja": "犬種は不確か（ミックスか珍しい犬種かも）", "de": "Rasse unsicher: vielleicht Mischling oder selten"},
    "guess.small": {"zh": "照片看起來是小型犬，這件是中大型犬款，可能會太大。", "en": "Your dog looks small; this one is cut for medium and large dogs and may be too big.", "ja": "写真では小型犬のようです。こちらは中・大型犬向けなので大きすぎるかもしれません。", "de": "Dein Hund wirkt klein; dieses Modell ist für mittlere und große Hunde und könnte zu groß sein."},
    "guess.large": {"zh": "照片看起來是中大型犬，這件是小型犬款，可能會太小。", "en": "Your dog looks medium or large; this one is cut for small dogs and may be too small.", "ja": "写真では中・大型犬のようです。こちらは小型犬向けなので小さすぎるかもしれません。", "de": "Dein Hund wirkt mittelgroß oder groß; dieses Modell ist für kleine Hunde und könnte zu klein sein."},
    "guess.mid": {"zh": "照片看起來是中型犬，斗篷和雨衣都可能合身，請以背長為準；全尺寸的款式最保險。", "en": "Your dog looks medium-sized: both the capes and the raincoat may fit, so go by the back length; the all-sizes style is the safe pick.", "ja": "写真では中型犬のようです。ケープもレインコートも合う可能性があるので背丈を目安に。全サイズ対応の型がいちばん安心です。", "de": "Dein Hund wirkt mittelgroß: Capes und Regenmantel können beide passen, also nach der Rückenlänge gehen; das Modell für alle Größen ist die sichere Wahl."},
    "guess.note": {"zh": "這是依照片估計的，幼犬或混種請以背長為準，也可以照樣試穿。", "en": "Estimated from the photo; for puppies and mixed breeds go by the back length. You can still try it on.", "ja": "写真からの推定です。子犬やミックス犬は背丈を目安に。このまま試着もできます。", "de": "Nach dem Foto geschätzt; bei Welpen und Mischlingen zählt die Rückenlänge. Anprobieren geht trotzdem."},
    "guess.pick": {"zh": "改選 {name}（{kind}）", "en": "Pick {name} ({kind})", "ja": "{name}（{kind}）にする", "de": "{name} wählen ({kind})"},
    "warn.title": {"zh": "這件可能不合身", "en": "This one may not fit", "ja": "サイズが合わないかもしれません", "de": "Das passt vielleicht nicht"},
    "warn.guess": {"zh": "從照片看，你家毛孩像是{dog}，而這件是{coat}款。試穿圖一定會畫得剛好合身，不代表實際尺寸，購買前請以背長和尺寸表為準。", "en": "From the photo, your dog looks like a {dog}, but this one is cut for {coat}. The try-on picture always fits perfectly and does not show the real size; check the back length and size chart before buying.", "ja": "写真では愛犬は{dog}のようですが、こちらは{coat}向けです。試着画像は必ずぴったりに描かれ、実際のサイズを示しません。購入前に背丈とサイズ表をご確認ください。", "de": "Laut Foto wirkt dein Hund wie ein {dog}, dieses Modell ist aber für {coat}. Das Anprobe-Bild passt immer perfekt und zeigt nicht die echte Größe; prüfe vor dem Kauf Rückenlänge und Größentabelle."},
    "warn.back": {"zh": "依你填的背長，這件的尺寸對你家毛孩{bad}。試穿圖一定會畫得剛好合身，不代表實際尺寸。", "en": "By the back length you entered, this one is {bad} for your dog. The try-on picture always fits perfectly and does not show the real size.", "ja": "入力した背丈では、こちらは愛犬に{bad}。試着画像は必ずぴったりに描かれ、実際のサイズを示しません。", "de": "Nach der eingegebenen Rückenlänge ist dieses Modell für deinen Hund {bad}. Das Anprobe-Bild passt immer perfekt und zeigt nicht die echte Größe."},
    "warn.big": {"zh": "太大", "en": "too big", "ja": "大きすぎます", "de": "zu groß"},
    "warn.smallB": {"zh": "太小", "en": "too small", "ja": "小さすぎます", "de": "zu klein"},
    "warn.go": {"zh": "我知道了，還是要試穿", "en": "I understand, try it anyway", "ja": "了解して、このまま試着", "de": "Verstanden, trotzdem anprobieren"},
    "warn.switch": {"zh": "改選 {name}（{kind}）", "en": "Switch to {name} ({kind})", "ja": "{name}（{kind}）にする", "de": "Zu {name} wechseln ({kind})"},
    "warn.cancel": {"zh": "取消", "en": "Cancel", "ja": "キャンセル", "de": "Abbrechen"},
    "fit.tooBig": {"zh": "這件對你家毛孩太大了", "en": "This one is too big for your dog", "ja": "このウェアは大きすぎます", "de": "Das ist zu groß für deinen Hund"},
    "fit.tooBigP": {"zh": "這件最小號適合背長約 {min} cm 以上的狗狗。", "en": "Its smallest size fits a back of about {min} cm or more.", "ja": "最小サイズでも背丈 約{min} cm 以上向けです。", "de": "Die kleinste Größe passt ab etwa {min} cm Rückenlänge."},
    "fit.tooSmall": {"zh": "這件對你家毛孩太小了", "en": "This one is too small for your dog", "ja": "このウェアは小さすぎます", "de": "Das ist zu klein für deinen Hund"},
    "fit.tooSmallP": {"zh": "這件最大號適合背長約 {max} cm 以下的狗狗。", "en": "Its largest size fits a back of up to about {max} cm.", "ja": "最大サイズでも背丈 約{max} cm までです。", "de": "Die größte Größe passt bis etwa {max} cm Rückenlänge."},
    "fit.better": {"zh": "這些比較適合：", "en": "These fit better:", "ja": "こちらがおすすめです：", "de": "Besser passen:"},
    "fit.also": {"zh": "這個背長也可以穿：", "en": "This back length also fits:", "ja": "この背丈ならこちらも：", "de": "Diese Rückenlänge passt auch:"},
    "fit.try": {"zh": "改試穿 {name}（{kind}）", "en": "Try {name} ({kind})", "ja": "{name}（{kind}）を試着", "de": "{name} anprobieren ({kind})"},
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
.fit-coat{position:relative;border:2px solid var(--line);border-radius:16px;background:var(--card);padding:10px 10px 12px;text-align:left;cursor:pointer;font:inherit;color:var(--ink);transition:border-color .15s,transform .15s,box-shadow .15s}
.fit-coat:hover{border-color:var(--ink2);transform:translateY(-2px);box-shadow:0 10px 24px rgba(0,0,0,.06)}.fit-coat.cur{border-color:var(--brand);box-shadow:0 0 0 1px var(--brand);transform:translateY(-2px)}
.fit-coat .img{aspect-ratio:1;border-radius:10px;overflow:hidden;background:#fff;display:grid;place-items:center}.fit-coat img{width:100%;height:100%;object-fit:contain}
.fit-coat .nm{display:block;font-weight:700;font-size:14.5px;margin-top:10px;line-height:1.3}.fit-coat .sub{display:block;font-size:12.5px;color:var(--mute);line-height:1.35;margin-top:2px}
.fit-coat .fitfor{display:block;margin-top:8px;font-size:12px;line-height:1.35;color:var(--ink2)}.fit-coat .fitfor b{display:inline-block;padding:2px 9px;border-radius:999px;background:var(--sand);font-weight:700}.fit-coat .fitfor i{display:block;font-style:normal;margin-top:4px;color:var(--mute)}
.fit-warn{margin:0 0 12px;padding:12px 14px;border-radius:12px;background:var(--brand-soft);border:1px solid #ffc9bf}.fit-warn b{display:block;font-size:15.5px;color:var(--brand-ink);margin-bottom:4px}
.fit-also{margin:10px 0 0;padding-top:10px;border-top:1px dashed var(--line2)}.fit-size-out .fit-alt{margin-top:8px;min-height:44px;font-size:15px}
.fit-coat .rec{display:none;position:absolute;top:8px;left:8px;background:var(--brand);color:#fff;font-size:11.5px;font-weight:800;letter-spacing:.03em;padding:3px 8px;border-radius:999px;box-shadow:0 2px 8px rgba(255,36,20,.3)}
.fit-coats.has-rec .fit-coat.rec-coat{border-color:var(--brand);border-style:dashed}.fit-coats.has-rec .fit-coat.rec-coat .rec{display:inline-block}.fit-coats.has-rec .fit-coat .img{margin-top:28px}.fit-coats.has-rec .fit-coat:not(.rec-coat):not(.cur){opacity:.62}.fit-coats.has-rec .fit-coat.rec-coat.cur{border-style:solid}
.fit-coat .chk{position:absolute;top:6px;right:6px;width:30px;height:30px;border-radius:50%;background:var(--brand);color:#fff;display:none;place-items:center;box-shadow:0 2px 8px rgba(255,36,20,.35);z-index:1}.fit-coat.cur .chk{display:grid}
.fit-coat-links{display:flex;gap:12px;flex-wrap:wrap;margin:12px 0 0;font-size:13.5px}.fit-coat-links a{color:var(--ink2);border-bottom:1px solid var(--line2)}.fit-coat-links a:hover{color:var(--ink);border-color:var(--ink)}
.fit-ai{margin-top:14px;padding:12px 14px;border-radius:12px;border:1.5px dashed var(--line2);background:var(--card);font-size:14px;color:var(--ink2);line-height:1.55}
.fit-ai b{color:var(--ink)}.fit-ai h4{margin:0 0 6px;font-size:13px;letter-spacing:.04em;color:var(--brand-ink)}.fit-ai p{margin:2px 0}.fit-ai small{display:block;margin-top:6px;color:var(--mute);font-size:12px}
.fit-guess{display:none;margin-top:14px;padding:12px 14px;border-radius:12px;background:var(--brand-soft);border:1px solid #ffc9bf;font-size:14.5px;color:var(--ink2)}.fit-guess.show{display:block}
.fit-guess b{display:block;color:var(--brand-ink);margin-bottom:4px}.fit-guess p{margin:0;font-size:13px;color:var(--mute)}
.fit-guess .row{display:flex;flex-wrap:wrap;gap:8px;margin-top:10px}.fit-guess button{min-height:40px;padding:0 16px;border-radius:999px;border:1.5px solid var(--ink);background:var(--card);color:var(--ink);font:inherit;font-size:14px;font-weight:700;cursor:pointer}
.fit-modal{position:fixed;inset:0;z-index:60;display:flex;align-items:center;justify-content:center;padding:20px;background:rgba(23,24,26,.55)}
.fit-modal .box{width:min(440px,100%);background:var(--card);border-radius:18px;padding:22px 22px 18px;box-shadow:0 24px 60px rgba(0,0,0,.25)}
.fit-modal h3{margin:0 0 8px;font-size:19px;color:var(--brand-ink)}.fit-modal p{margin:0 0 14px;font-size:15px;line-height:1.6;color:var(--ink2)}
.fit-modal .acts{display:grid;gap:8px}.fit-modal .acts .btn{width:100%}.fit-modal .acts .cancel{background:none;border:0;font:inherit;font-size:14px;color:var(--mute);text-decoration:underline;cursor:pointer;padding:6px}
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
.fit-note b{display:flex;align-items:center;gap:9px;font-size:13px;color:var(--brand-ink);letter-spacing:.06em;margin-bottom:6px}.fit-note p{margin:0}.fit-note.wait p{color:var(--mute);font-style:italic}
.fit-note.show{display:block}
.fit-note.miss p{color:var(--mute)}.fit-note.miss .led{background:#c9c2b8;box-shadow:0 0 0 3px rgba(0,0,0,.05)}
/* LED in the title: spinning + glowing while the stylist is still writing, steady green once the note is in */
.fit-note .led{position:relative;flex:0 0 auto;width:14px;height:14px;border-radius:50%;background:#1fa463;box-shadow:0 0 0 3px rgba(31,164,99,.18),0 0 10px rgba(31,164,99,.55)}
.fit-note.wait .led{background:rgba(255,36,20,.12);animation:fit-led-glow 1.1s ease-in-out infinite alternate}
.fit-note.wait .led::after{content:"";position:absolute;inset:0;border-radius:50%;background:conic-gradient(from 0deg,var(--brand) 0 72%,transparent 72% 100%);-webkit-mask:radial-gradient(farthest-side,transparent 52%,#000 56%);mask:radial-gradient(farthest-side,transparent 52%,#000 56%);animation:fit-led-spin .9s linear infinite}
@keyframes fit-led-spin{to{transform:rotate(360deg)}}
@keyframes fit-led-glow{from{box-shadow:0 0 0 2px rgba(255,36,20,.12),0 0 4px rgba(255,36,20,.3)}to{box-shadow:0 0 0 5px rgba(255,36,20,.1),0 0 16px 3px rgba(255,36,20,.75)}}
/* the note just arrived: slide in, pulse a ring twice, flash the background, show a badge for a few seconds */
.fit-note .new{display:none;margin-left:auto;background:var(--brand);color:#fff;font-size:12px;font-weight:800;letter-spacing:.04em;padding:4px 10px;border-radius:999px;white-space:nowrap}
.fit-note .new::before{content:"✓ "}
.fit-note.pop{animation:fit-note-in .5s cubic-bezier(.2,.8,.3,1.2) both,fit-note-ring 1.6s ease-out .1s 2 both,fit-note-bg 4.4s ease both}
.fit-note.pop .new{display:inline-block;animation:fit-badge 4.4s ease both}
@keyframes fit-note-in{from{opacity:0;transform:translateY(14px) scale(.96)}to{opacity:1;transform:none}}
@keyframes fit-note-ring{0%{box-shadow:0 0 0 0 rgba(255,36,20,.55)}70%{box-shadow:0 0 0 12px rgba(255,36,20,0)}100%{box-shadow:0 0 0 0 rgba(255,36,20,0)}}
@keyframes fit-note-bg{0%,45%{background:#fff0ec;outline:2px solid rgba(255,36,20,.5)}100%{background:var(--sand);outline:2px solid transparent}}
@media (prefers-reduced-motion:reduce){.fit-note.wait .led,.fit-note.wait .led::after,.fit-note.pop,.fit-note.pop .new{animation:none}.fit-note.pop{background:#fff0ec;outline:2px solid rgba(255,36,20,.5)}}
.fit-actions{display:none;gap:10px;margin-top:14px;flex-wrap:wrap}.fit-actions .btn{flex:1 1 160px}.fit-stage[data-state=done] .fit-actions{display:flex}
.fit-colors{display:none;margin-top:14px;padding:12px 14px;border:1.5px dashed var(--line2);border-radius:14px}.fit-stage[data-state=done] .fit-colors.on{display:block}
.fit-colors h4{margin:0 0 8px;font-size:13px;color:var(--brand-ink);letter-spacing:.04em}.fit-colors .row{display:flex;flex-wrap:wrap;gap:8px}
.fit-colors button{display:inline-flex;align-items:center;gap:8px;min-height:40px;padding:0 14px 0 8px;border-radius:999px;border:1.5px solid var(--line2);background:var(--card);color:var(--ink);font:inherit;font-size:14px;font-weight:600;cursor:pointer}
.fit-colors button i{width:22px;height:22px;border-radius:50%;border:1px solid rgba(0,0,0,.2)}.fit-colors button.cur{border-color:var(--brand);box-shadow:0 0 0 1px var(--brand)}
.fit-colors button:disabled{opacity:.6;cursor:wait}.fit-colors p{margin:8px 0 0;font-size:12.5px;color:var(--mute)}
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
.fit-promo{background:var(--card);border:1px solid var(--line);border-radius:28px;padding:40px 44px;display:grid;grid-template-columns:1fr auto;gap:28px;align-items:center}
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
function health(again){var c=new AbortController();var tm=setTimeout(function(){c.abort();},20000);
 // a busy server can answer slowly: wait up to 20 s and try once more before showing "offline"
 fetch(cfg.api+'/api/health',{signal:c.signal,cache:'no-store'}).then(function(r){setStatus(r.ok);}).catch(function(){if(again)setStatus(false);else setTimeout(function(){health(true);},3000);}).then(function(){clearTimeout(tm);});}
health();setInterval(health,45000);
document.addEventListener('visibilitychange',function(){if(!document.hidden)health();});
/* photo */
function loadImg(src){return new Promise(function(res,rej){var i=new Image();i.onload=function(){res(i);};i.onerror=rej;i.src=src;});}
function compress(src,max,q){return loadImg(src).then(function(i){var r=Math.min(max/i.width,max/i.height,1),c=document.createElement('canvas');
 c.width=Math.max(1,Math.round(i.width*r));c.height=Math.max(1,Math.round(i.height*r));var g=c.getContext('2d');g.fillStyle='#fff';g.fillRect(0,0,c.width,c.height);g.drawImage(i,0,0,c.width,c.height);return c.toDataURL('image/jpeg',q);});}
function setDog(src,demo){setErr('');warnOk=false;return loadImg(src).then(function(){dog=src;pv.src=src;drop.classList.add('has');guessSize(src,demo);
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
document.querySelectorAll('.fit-coat').forEach(function(b){b.addEventListener('click',function(){coat=b.dataset.src;coatKey=b.dataset.coat;warnOk=false;
 document.querySelectorAll('.fit-coat').forEach(function(x){x.classList.toggle('cur',x===b);});update();sizeOut();guessOut();});});
/* small or large dog? The photo (shrunk to 384 px) goes to the fitting-room server, which runs an image model on the
   laptop and answers with the closest breeds and small / medium / large (trained on ~2,300 labelled dog photos).
   A hint is shown only when fairly sure; ?dogai=1 shows the breeds and numbers under the photo (test mode). */
var aiDebug=/[?&]dogai=1/.test(location.search);try{sessionStorage.removeItem('apetto_dogai');}catch(e){}
var guess=null,guessFor=null,guessDemo=false,guessCtl=null,aiBox=$('.fit-ai'),warnOk=false;
/* the chosen coat does not fit (AI guess from the photo, or the typed back length): ask once before generating */
function misfit(){var c=coatKey&&cfg.coats[coatKey];if(!c||!c.cut)return null;
 var fw=typeof fitWarn==='function'?fitWarn(c):null;if(fw&&fw.bad)return {why:'back',bad:mval('back')<c.min?t('warn.big'):t('warn.smallB'),alts:altCoats(mval('back'),c,mval('back')<c.min?-1:1)};
 if(guess&&guess!=='M'&&dog&&dog===guessFor&&c.cut!=='A'&&c.cut!==guess){var alts=Object.keys(cfg.coats).filter(function(k){var x=cfg.coats[k].cut;return x===guess||x==='A';});
  return {why:'guess',dog:alts.length?cfg.coats[alts[0]].kind:'',coat:c.kind,alts:alts};}
 return null;}
function showWarn(m){var old=$('.fit-modal');if(old)old.remove();var d=document.createElement('div');d.className='fit-modal';d.setAttribute('role','dialog');d.setAttribute('aria-modal','true');
 var txt=m.why==='back'?t('warn.back',{bad:m.bad}):t('warn.guess',{dog:m.dog,coat:m.coat});
 d.innerHTML='<div class="box"><h3>'+t('warn.title')+'</h3><p>'+escHtml(txt)+'</p><div class="acts">'+m.alts.map(function(k){var o=cfg.coats[k];return '<button type="button" class="btn" data-k="'+k+'">'+escHtml(t('warn.switch',{name:o.label,kind:o.kind}))+'</button>';}).join('')+
  '<button type="button" class="btn ghost" data-go="1">'+t('warn.go')+'</button><button type="button" class="cancel">'+t('warn.cancel')+'</button></div></div>';
 d.addEventListener('click',function(e){var b=e.target.closest('button');if(e.target===d){d.remove();return;}if(!b)return;d.remove();
  if(b.dataset.k){var card=$('.fit-coat[data-coat="'+b.dataset.k+'"]');if(card){card.click();setTimeout(function(){go.click();},50);}}
  else if(b.dataset.go){warnOk=true;go.click();}});
 document.body.appendChild(d);var f=d.querySelector('.btn');if(f)f.focus();}
function escHtml(x){return String(x).replace(/[&<>"]/g,function(c){return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c];});}
function breedName(x){return (cfg.serverLang==='zh'&&x.zh)||x.name||'';}
function aiShow(state,r,ms){if(!aiBox||!aiDebug)return;aiBox.hidden=false;var h='<h4>'+t('ai.title')+'</h4>';
 if(state==='wait')h+='<p>'+t('ai.wait')+'</p>';else if(state==='error')h+='<p>'+t('ai.err')+'</p>';
 else{h+='<p><b>'+t('ai.breed')+'</b>：'+(r.top||[]).map(function(x){return escHtml(breedName(x))+' '+Math.round(x.p*100)+'%';}).join('、')+(r.breedSure===false?'（'+t('ai.unsure')+'）':'')+'</p>';
  if(r.P)h+='<p><b>'+t('ai.size')+'</b>：'+t('ai.sizes',{s:Math.round(r.P[0]*100),m:Math.round(r.P[1]*100),l:Math.round(r.P[2]*100)})+'</p>';
  h+='<p><b>'+t('ai.verdict')+'</b>：'+t(!r.P?'ai.nodog':guess?'ai.'+guess:'ai.none')+'</p><small>'+t('ai.time',{s:(ms/1000).toFixed(1)})+'<br>'+t('ai.note')+'</small>';}
 aiBox.innerHTML=h;}
function guessSize(src,demo){guess=null;guessFor=src;guessDemo=!!demo;guessMark('');guessOut();
 if(guessCtl){guessCtl.abort();guessCtl=null;}
 if(!src){if(aiBox)aiBox.hidden=true;return;}
 var t0=Date.now(),ctl=new AbortController();guessCtl=ctl;aiShow('wait');
 compress(src,384,.85).then(function(img){return fetch(cfg.api+'/api/dogsize',{method:'POST',signal:ctl.signal,headers:auth({'Content-Type':'application/json'}),body:JSON.stringify({image:img})});})
  .then(function(r){if(!r.ok)throw new Error('HTTP '+r.status);return r.json();})
  .then(function(r){if(guessFor!==src)return;guess=r.guess==='S'||r.guess==='L'?r.guess:(r.P&&r.P[1]>=0.5?'M':null);guessMark(guess||(r.P?'none':'nodog'));aiShow('done',r,Date.now()-t0);guessOut();})
  .catch(function(e){if(guessFor!==src||(e&&e.name==='AbortError'))return;guessMark('error');aiShow('error');});}
var guessBox=$('.fit-guess');
/* data-guess shows the last result (S / L / none / error), handy when checking the page */
function guessMark(v){if(guessBox)guessBox.setAttribute('data-guess',v);}
function guessOut(){var c=coatKey&&cfg.coats[coatKey];if(!guessBox)return;
 var rec=guess&&dog&&dog===guessFor?guess:null,grid=$('.fit-coats');
 document.querySelectorAll('.fit-coat').forEach(function(b){var o=cfg.coats[b.dataset.coat];b.classList.toggle('rec-coat',!!(rec&&o&&(o.cut==='A'||(rec!=='M'&&o.cut===rec))));});
 if(grid)grid.classList.toggle('has-rec',!!rec);
 if(guess==='M'&&dog&&dog===guessFor){guessBox.innerHTML='<b>'+t('guess.mid')+'</b><p>'+t('guess.note')+'</p>';guessBox.classList.add('show');return;}
 if(!guess||!c||!c.cut||c.cut==='A'||c.cut===guess||!dog||dog!==guessFor){guessBox.classList.remove('show');guessBox.innerHTML='';return;}
 var alts=Object.keys(cfg.coats).filter(function(k){var x=cfg.coats[k].cut;return x===guess||x==='A';});
 guessBox.innerHTML='<b>'+t(guess==='S'?'guess.small':'guess.large')+'</b><p>'+t('guess.note')+'</p>'+(alts.length?'<div class="row">'+alts.map(function(k){var o=cfg.coats[k];
  return '<button type="button" data-k="'+k+'">'+t('guess.pick',{name:o.label,kind:o.kind})+'</button>';}).join('')+'</div>':'');
 guessBox.classList.add('show');}
if(guessBox)guessBox.addEventListener('click',function(e){var b=e.target.closest('button[data-k]');if(!b)return;var card=$('.fit-coat[data-coat="'+b.dataset.k+'"]');if(card)card.click();});
/* size advice from the chosen coat's size chart: garment length ~ back length - offset, bumped up if neck/girth exceed the row */
var sizeBox=$('.fit-size-out');
function mval(k){var i=$('.fit-size input[data-m='+k+']');return i?parseFloat(i.value)||0:0;}
function recommend(c){var back=mval('back'),neck=mval('neck'),belly=mval('belly');if(!back||!c||!c.chart)return null;
 var rows=c.chart.rows.map(function(r){return {size:r[0],len:+r[1],neck:+r[2],belly:+String(r[3]).split(/[~\-–]/).pop()};});
 var target=back-c.chart.offset,best=0,bd=1e9;rows.forEach(function(r,i){var d=Math.abs(r.len-target);if(d<bd){bd=d;best=i;}});
 var i=best;while(i<rows.length-1&&((neck&&neck>rows[i].neck)||(belly&&belly>rows[i].belly)))i++;
 var r=rows[i],note='';if(target<rows[0].len-3)note=t('size.small');else if(target>rows[rows.length-1].len+3)note=t('size.big',{size:r.size});
 return {size:r.size,len:r.len,diff:Math.round((back-r.len)*10)/10,bumped:i>best,loose:rows[i+1]?rows[i+1].size:null,note:note};}
/* other coats whose sizes cover this back length; if none and the chosen one is too big (or small), a clearly smaller (or bigger) cut */
function altCoats(back,c,dir){var fit=[],side=[];for(var k in cfg.coats){var o=cfg.coats[k];if(k===coatKey||!o.min)continue;
 if(back>=o.min-3&&back<=o.max+3)fit.push(k);else if((dir<0&&o.min<c.min-3)||(dir>0&&o.max>c.max+3))side.push(k);}return fit.length||!dir?fit:side;}
function fitWarn(c){var back=mval('back');if(!back||!c.min)return null;var dir=back<c.min-3?-1:back>c.max+3?1:0,alts=altCoats(back,c,dir);
 var btns=alts.map(function(k){var o=cfg.coats[k];return '<button type="button" class="btn'+(dir?'':' ghost')+' fit-alt" data-k="'+k+'">'+t('fit.try',{name:o.label,kind:o.kind})+'</button>';}).join('');
 if(dir<0)return {bad:true,h:'<div class="fit-warn"><b>'+t('fit.tooBig')+'</b><p>'+t('fit.tooBigP',{min:c.min})+(alts.length?' '+t('fit.better'):'')+'</p>'+btns+'</div>'};
 if(dir>0)return {bad:true,h:'<div class="fit-warn"><b>'+t('fit.tooSmall')+'</b><p>'+t('fit.tooSmallP',{max:c.max})+(alts.length?' '+t('fit.better'):'')+'</p>'+btns+'</div>'};
 return alts.length?{bad:false,h:'<div class="fit-also"><p>'+t('fit.also')+'</p>'+btns+'</div>'}:null;}
function sizeOut(){var c=coatKey&&cfg.coats[coatKey];if(!sizeBox||!c)return;var rec=recommend(c),h='',fw=fitWarn(c);
 if(fw&&fw.bad){h=fw.h;rec=null;}
 else if(rec){h='<div class="big"><span>'+t('size.rec')+'</span><b>'+rec.size+'</b></div><p>'+t('size.detail',{size:rec.size,len:rec.len,d:rec.diff})+(rec.bumped?' '+t('size.bumped'):'')+(rec.loose?' '+t('size.loose',{size:rec.loose}):'')+'</p>'+(rec.note?'<p>'+rec.note+'</p>':'');}
 else if(!fw||!fw.bad)h='<p>'+t('size.need')+'</p>';
 if(fw&&!fw.bad)h+=fw.h;
 if(stage.dataset.state==='done'&&c.url)h+='<a class="btn'+(fw&&fw.bad?' ghost':'')+'" href="'+c.url+(rec?'#size='+encodeURIComponent(rec.size):'')+'">'+(rec?t('go.product',{size:rec.size}):t('go.plain'))+'</a>';
 sizeBox.innerHTML=h;}
document.querySelectorAll('.fit-size input').forEach(function(i){i.addEventListener('input',sizeOut);});
/* "try this one instead": pick that coat and start again with the same photo */
if(sizeBox)sizeBox.addEventListener('click',function(e){var b=e.target.closest('.fit-alt');if(!b)return;var card=$('.fit-coat[data-coat="'+b.dataset.k+'"]');if(!card)return;
 card.click();if(dog&&!running)go.click();});
/* progress */
var curStep=0;
function step(n,txt){curStep=n;steps.forEach(function(s,i){s.className=i<n?'done':i===n?'on':'';});if(txt)progT.textContent=txt;bar.style.width=Math.min(96,8+n*28)+'%';}
var noteTimer=null;
/* missed: the server finished the picture but never produced a note; say so instead of hiding the panel */
function showNote(text,pending,missed){clearTimeout(captionTimer);if(!cfg.showNote){note.classList.remove('show');return;}
 var arrived=!pending&&!missed&&(text||'').trim()&&note.classList.contains('wait');
 note.classList.toggle('wait',!!pending);note.classList.toggle('miss',!!missed);
 noteP.textContent=pending?t('note.writing'):missed?t('note.missed'):(text||'');note.classList.toggle('show',!!(pending||missed||(text||'').trim()));
 if(!pending)note.classList.remove('pop');if(arrived)noteReady();}
function noteMissed(){showNote('',false,true);}
/* the stylist's note landed after a wait: make it as hard to miss as the picture */
function noteReady(){void note.offsetWidth;note.classList.add('pop');clearTimeout(noteTimer);noteTimer=setTimeout(function(){note.classList.remove('pop');},4600);
 setTimeout(function(){var r=note.getBoundingClientRect();if(r.top<0||r.bottom>window.innerHeight)note.scrollIntoView({behavior:'smooth',block:'center'});},80);
 try{if(navigator.vibrate)navigator.vibrate([30,50,30]);}catch(e){}
 blinkTitle('💬 ');}
function blinkTitle(mark){if(!document.hidden)return;var old=document.title,n=0,tt=setInterval(function(){document.title=(n++%2?mark:'')+old;if(!document.hidden||n>20){clearInterval(tt);document.title=old;}},900);}
function pollCaption(id){if(!cfg.showNote)return;if(!id){noteMissed();return;}var end=Date.now()+120000;showNote('',true);
 var tick=function(){if(Date.now()>end){noteMissed();return;}
  fetch(cfg.api+'/api/caption/'+encodeURIComponent(id),{headers:auth()}).then(function(r){return r.ok?r.json():null;}).then(function(d){
   if(d&&d.status==='ready'){showNote(d.caption);return;}if(d&&d.status==='none'){noteMissed();return;}captionTimer=setTimeout(tick,2000);}).catch(function(){captionTimer=setTimeout(tick,2500);});};
 captionTimer=setTimeout(tick,1500);}
/* make the finished picture impossible to miss: scroll to it, pulse the frame, badge, a short buzz on phones */
var flashTimer=null;
function celebrate(){stage.classList.remove('flash');void stage.offsetWidth;stage.classList.add('flash');clearTimeout(flashTimer);flashTimer=setTimeout(function(){stage.classList.remove('flash');},3400);
 var box=$('.fit-stage .box');setTimeout(function(){box.scrollIntoView({behavior:'smooth',block:'center'});},80);
 try{if(navigator.vibrate)navigator.vibrate([40,60,40]);}catch(e){}
 blinkTitle('✓ ');}
/* recolour test (?recolor=1): one Gemini picture, the other colourways recoloured on the laptop */
var rcOn=/[?&]recolor=1/.test(location.search),rcBox=$('.fit-colors'),rcOrig='',rcCache={};
function rcShow(){if(!rcBox)return;var c=coatKey&&cfg.coats[coatKey],cols=c&&c.colors||[];
 if(!rcOn||cols.length<2||!rcOrig){rcBox.classList.remove('on');rcBox.innerHTML='';return;}
 rcBox.innerHTML='<h4>換色測試（zbook）</h4><div class="row">'+cols.map(function(x,i){return '<button type="button" data-i="'+i+'"'+(i===0?' class="cur"':'')+'><i style="background:'+x.hex+'"></i>'+x.name+(i===0?'（原圖）':'')+'</button>';}).join('')+'</div><p></p>';
 rcBox.classList.add('on');
 rcBox.querySelectorAll('button').forEach(function(b){b.onclick=function(){rcPick(+b.dataset.i);};});}
function rcFetch(i){var c=cfg.coats[coatKey],cols=c.colors,key=coatKey+':'+i,src=rcOrig;
 if(!rcCache[key])rcCache[key]=Promise.all([compress(src,1024,.9),dog?compress(dog,800,.82):null]).then(function(a){var t0=Date.now();return fetch(cfg.api+'/api/recolor',{method:'POST',headers:auth({'Content-Type':'application/json'}),body:JSON.stringify({image:a[0],from:cols[0].hex,to:cols[i].hex,original:a[1]})})
  .then(function(r){if(!r.ok)throw new Error('HTTP '+r.status);return r.json();}).then(function(d){d.rt=Date.now()-t0;return d;});}).catch(function(e){delete rcCache[key];throw e;});
 return rcCache[key];}
function rcAsk(){var c=rcOn&&coatKey&&cfg.coats[coatKey];if(!c||!c.colors||c.colors.length<2)return null;return {from:c.colors[0].hex,to:c.colors.slice(1).map(function(x){return x.hex;})};}
function rcTake(v){var c=coatKey&&cfg.coats[coatKey];if(!c||!c.colors||!v||!v.length)return;
 c.colors.forEach(function(x,i){if(!i)return;var hit=v.filter(function(y){return y&&y.hex===x.hex&&y.image;})[0];if(hit){hit.withPicture=true;rcCache[coatKey+':'+i]=Promise.resolve(hit);}});}
function rcPrefetch(){var c=coatKey&&cfg.coats[coatKey];if(!rcOn||!c||!c.colors)return;var i=1,n=c.colors.length,orig=rcOrig;
 (function next(){if(i>=n||rcOrig!==orig)return;rcFetch(i++).catch(function(){}).then(next);})();}
function rcPick(i){var c=cfg.coats[coatKey],cols=c.colors,info=rcBox.querySelector('p');
 rcBox.querySelectorAll('button').forEach(function(b){b.classList.toggle('cur',+b.dataset.i===i);});
 if(i===0){shot.src=rcOrig;resultUrl=rcOrig;info.textContent='';return;}
 info.textContent='換色中…';var t0=Date.now(),orig=rcOrig;
 rcFetch(i).then(function(d){if(rcOrig!==orig)return;shot.src=d.image;resultUrl=d.image;var wait=Date.now()-t0;
   info.textContent=cols[i].name+'：zbook 換色 '+d.ms+' ms'+(d.withPicture?'（和試穿圖一起送來）':wait<150?'（已預先換好，立即顯示）':'，等了 '+wait+' ms')+(d.share<0.01?'（幾乎沒找到原本的衣服顏色）':'');})
  .catch(function(e){info.textContent='換色失敗：'+(e&&e.message||e);});}
function finish(){if(running){clearInterval(running.poll);clearInterval(running.tick);clearTimeout(running.tm);running=null;}update();}
go.addEventListener('click',function(){
 if(!dog||!coat){setErr(t('err.pickFirst'));return;}if(online===false){setErr(t('err.offline'));return;}
 if(!warnOk){var mf=misfit();if(mf){showWarn(mf);return;}}
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
   if(d.key==='srv.queued'){var pos=d.vars&&+d.vars.pos||0;step(0,pos>0?t('srv.queued',{pos:pos}):t('srv.queuedNext'));return;}
   if(d.key==='srv.retrying'){progT.textContent=txt;return;}
   if(st>=6)step(2,txt||t('step.draw'));else if(st>=3)step(1,txt||t('step.send'));else if(txt&&st>=2)progT.textContent=txt;}).catch(function(){});},1000);
  return fetch(cfg.api+'/api/stylist',{method:'POST',signal:ctl.signal,headers:auth({'Content-Type':'application/json'}),
   body:JSON.stringify({dogImage:imgs[0],clothesImage:imgs[1],lang:cfg.serverLang,jobId:jobId,coat:coatKey||null,coatName:(coatKey&&cfg.coats[coatKey]&&cfg.coats[coatKey].name)||null,product:(coatKey&&cfg.coats[coatKey]&&cfg.coats[coatKey].product)||null,recolor:rcAsk()})});
 }).then(function(r){
  if(!r.ok){return r.json().catch(function(){return {};}).then(function(d){
   if(r.status===429)throw new Error(t(d.errorKey||'err.busy'));if(r.status===503)throw new Error(t(d.errorKey||'err.allAccountsExhausted'));
   if(r.status===401)throw new Error(t('err.unauthorized'));if(d.errorKey&&S[d.errorKey])throw new Error(t(d.errorKey));throw new Error(d.error||('HTTP '+r.status));});}
  return r.json();
 }).then(function(d){
  if(running!==run)return;var src=d&&d.image;if(!src||!(/^data:image|^https?:/.test(src)))throw new Error(t('err.noImage'));
  step(3,t('step.done'));return loadImg(src).then(function(){resultUrl=src;shot.src=src;stage.dataset.state='done';finish();sizeOut();celebrate();rcOrig=src;rcCache={};rcTake(d.variants);rcShow();rcPrefetch();
   try{document.dispatchEvent(new CustomEvent('apetto:fitdone',{detail:{image:src,dog:dog,coat:coatKey,coatName:(coatKey&&cfg.coats[coatKey]&&cfg.coats[coatKey].name)||''}}));}catch(e){}
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
function locked(){return !!(window.apNeedLogin&&window.apNeedLogin());}
shot.addEventListener('contextmenu',function(e){if(stage.classList.contains('mem-out')){e.preventDefault();locked();}});
shot.addEventListener('dragstart',function(e){if(stage.classList.contains('mem-out'))e.preventDefault();});
dl.addEventListener('click',function(){if(!resultUrl||locked())return;var a=document.createElement('a');a.href=resultUrl;a.download=t('file.name');document.body.appendChild(a);a.click();a.remove();});
function toFile(){return fetch(resultUrl).then(function(r){return r.blob();}).then(function(b){return new File([b],t('file.name'),{type:b.type||'image/jpeg'});});}
if(navigator.share){share.addEventListener('click',function(){if(locked())return;toFile().then(function(f){var d={files:[f],text:t('share.text')};
 if(navigator.canShare&&!navigator.canShare(d))d={text:t('share.text'),url:location.href};return navigator.share(d);}).catch(function(){});});}else{share.style.display='none';}
again.addEventListener('click',function(){stage.dataset.state='empty';resultUrl='';rcOrig='';rcShow();showNote('');setErr('');coat=null;coatKey=null;
 document.querySelectorAll('.fit-coat').forEach(function(x){x.classList.remove('cur');});update();guessOut();$('.fit-coats').scrollIntoView({behavior:'smooth',block:'center'});});
})();"""

ICON_UP = ('<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">'
           '<path d="M4 16v2a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-2M12 4v12M7 9l5-5 5 5"/></svg>')
ICON_PIC = ('<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">'
            '<rect x="3" y="4" width="18" height="16" rx="3"/><circle cx="9" cy="10" r="2"/><path d="m21 16-5-5-9 9"/></svg>')
ICON_DL = ('<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">'
           '<path d="M12 4v11M7 10l5 5 5-5M4 19h16"/></svg>')
ICON_CHECK = '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M5 12l5 5L20 7"/></svg>'


def config_json(data, lang):
    import theme as th
    strings = {k: v.get(lang) or v["zh"] for k, v in STR.items()}
    ui = {"connecting": "連線中…", "online": "試衣間運作中", "offline": "試衣間暫停服務中，請稍後再來。"}
    ui = {k: (UI[v].get(lang) if lang != "zh" else v) or v for k, v in ui.items()}
    charts = th.sb.load_image_text().get("charts", {})
    by_id = {p["id"]: p for p in data["products"]}
    coats = {}
    for coat in load_coats():
        p = by_id.get(coat.get("product"))
        chart_key = coat.get("chart") or ""
        c = charts.get(chart_key)
        coats[coat["key"]] = {"url": th.link(th.rel_dir(PAGE), th.sb.product_page(p), lang) if p and p.get("visible", True) else "",
                              "name": p["name"] if p else coat_label(coat, "zh"), "product": coat.get("product"),
                              "chart": {"rows": c["rows"], "offset": CHART_OFFSET.get(chart_key, 8)} if c else None,
                              "label": coat_label(coat, lang),
                              "colors": [{"name": n, "hex": h, "url": (th.link(th.rel_dir(PAGE), th.sb.product_page(by_id[pid]), lang) if pid in by_id else "")}
                                         for n, h, pid in COLORWAYS.get(coat["key"], [])]}
        fit = coat_fit(coat, charts, lang)
        if fit:
            coats[coat["key"]].update(kind=fit["kind"], min=fit["min"], max=fit["max"], cut=fit["cut"])
    return json.dumps({"api": API_BASE, "key": API_KEY, "serverLang": SERVER_LANG.get(lang, "zh"),
                       "showNote": SHOW_NOTE.get(lang, False), "strings": strings, "ui": ui, "coats": coats}, ensure_ascii=False)


def render(data, lang):
    import theme as th
    d = th.rel_dir(PAGE)
    by_id = {p["id"]: p for p in data["products"]}
    demo = "".join(f'<button type="button" data-dog="{th.esc(g["key"])}" data-src="{img_url(d, g["image"])}"><img src="{img_url(d, g["image"])}" alt="">{th.esc(coat_label(g, lang))}</button>'
                   for g in load_dogs())
    coats, links = "", ""
    charts = th.sb.load_image_text().get("charts", {})
    for coat in load_coats():
        p = by_id.get(coat.get("product"))
        k, src, colour = coat["key"], img_url(d, coat["image"]), coat_label(coat, lang)
        sub = f'<span class="sub">{th.esc(p["name"])}</span>' if p else ""
        fit = coat_fit(coat, charts, lang)
        fitfor = f'<span class="fitfor"><b>{th.esc(fit["kind"])}</b><i>{th.esc(fit["range"])}</i></span>' if fit else ""
        coats += (f'<button type="button" class="fit-coat" data-coat="{th.esc(k)}" data-src="{src}">'
                  f'<span class="chk">{ICON_CHECK}</span><span class="rec">建議款</span><span class="img"><img src="{src}" alt="{th.esc(colour)}" loading="lazy"></span>'
                  f'<span class="nm">{th.esc(colour)}</span>{sub}{fitfor}</button>')
        if p and p.get("visible", True):
            links += f'<a href="{th.link(d, th.sb.product_page(p), lang)}">{th.esc(colour)}<span aria-hidden="true"> · </span>查看商品</a>'
    import member as mem
    mcfg = mem.config()
    crumbs = f'<li><a href="{th.link(d, "index.html", lang)}">首頁</a></li><li>試衣間</li>'
    body = f"""<div class="wrap"><ol class="breadcrumb">{crumbs}</ol>
<div class="fit-head rv in"><span class="eyebrow">試衣間</span><h1>讓毛孩先試穿，再決定</h1>
 <p class="lead">上傳一張毛孩的照片，挑一件 apetto，AI 會畫出牠穿上的樣子。</p>
 <div class="fit-status" role="status"><i></i><span>連線中…</span></div>{mem.fit_bar() if mcfg else ""}</div>
<div class="fit-grid">
 <div class="fit-col rv in">
  <section class="fit-card"><h2><b>1</b>毛孩照片</h2>
   <label class="fit-drop"><input type="file" accept="image/*" aria-label="毛孩照片">
    <div class="ph">{ICON_UP}<b>點這裡選照片，或把照片拖進來</b><span>全身、側面、光線清楚的照片效果最好。支援 JPG、PNG、WEBP。</span></div>
    <div class="pv"><img alt="毛孩照片"><span>更換照片</span></div></label>
   {f'<div class="fit-demo"><p>沒有照片？先用示範狗狗試試</p><div class="row">{demo}</div></div>' if demo else ''}
   <div class="fit-ai" hidden></div>
  </section>
  <section class="fit-card"><h2><b>2</b>選一件 apetto</h2>
   <div class="fit-coats">{coats}</div>
   <div class="fit-coat-links">{links}</div>
   <div class="fit-guess" role="status"></div>
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
  <div class="fit-colors" aria-live="polite"></div>
  <div class="fit-size"><h3>喜歡嗎？量一下毛孩，看該選哪一號</h3><p class="hint">背長：從脖子根部（約前腳的位置）量到尾巴根。領圍與腹圍為圈量，可以不填。</p>
   <div class="fields"><label><span>背長</span><div><input type="number" inputmode="decimal" min="10" max="120" step="0.5" data-m="back"><em>cm</em></div></label>
    <label><span>領圍</span><div><input type="number" inputmode="decimal" min="10" max="120" step="0.5" data-m="neck"><em>cm</em></div></label>
    <label><span>腹圍</span><div><input type="number" inputmode="decimal" min="10" max="150" step="0.5" data-m="belly"><em>cm</em></div></label></div>
   <div class="fit-size-out"></div></div>
  <div class="fit-note" aria-live="polite"><b><i class="led" aria-hidden="true"></i><span>AI 造型師的話</span><span class="new">造型師寫好了</span></b><p></p></div>
  <div class="fit-actions"><button type="button" class="btn fit-dl">{ICON_DL}下載照片</button><button type="button" class="btn ghost fit-share">分享</button><button type="button" class="btn ghost fit-again">再試一件</button></div>
  <p class="fit-fine">試穿圖由 AI 生成，顏色與版型以實際商品為準。</p>
 </section>
</div>{mem.history_block() if mcfg else ""}</div>
<script id="apt-fit" type="application/json">{config_json(data, lang)}</script>
<script src="{th.asset(d, 'assets/fitstudio.js')}?v={th.ASSET_VER['fit']}" defer></script>{mem.script_tag(d, mcfg, lang) if mcfg else ""}"""
    title = {"zh": "試衣間", "en": "Fitting Studio", "ja": "試着室", "de": "Anprobe"}[lang]
    return th.page(data, PAGE, lang, f"{title} | {th.BRAND}", body, "上傳一張毛孩的照片，挑一件 apetto，AI 會畫出牠穿上的樣子。",
                   og_image=(load_coats() or [{"image": ASSET_DIR + COATS[1][1]}])[0]["image"], current=PAGE,
                   extra_head=f'<link rel="preconnect" href="{API_BASE}">')


def home_promo(d, lang):
    import theme as th
    pics = "".join(f'<img src="{th.asset(d, c["image"])}" alt="" loading="lazy">' for c in load_coats()[:3])
    return (f'<section class="sec tight"><div class="wrap"><div class="fit-promo rv"><div><span class="eyebrow">新功能</span><h2>AI 試衣間：先看牠穿上的樣子</h2>'
            f'<p>上傳一張照片，挑一件 apetto，約 30 秒就能看到試穿效果。</p></div>'
            f'<div class="side"><div class="coats">{pics}</div><a class="btn" href="{th.link(d, PAGE, lang)}">去試衣間</a></div></div></div></section>')
