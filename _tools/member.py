"""Google sign-in (Firebase Auth + Firestore, all in the browser): a member page with the visitor's dogs, and the
fitting room remembers which dog is being dressed and keeps the finished pictures.

Off until _data/firebase.json exists ({"apiKey", "authDomain", "projectId", "appId"}; public values by design, access is
limited by FIRESTORE_RULES below, which the owner pastes into the Firebase console).

Data: users/{uid}                = {name, email, updated, dog: id of the dog last used}
      users/{uid}/dogs/{id}      = {name, back, neck, belly, created}            (cm; neck and belly may be 0)
      users/{uid}/fits/{id}      = {img, dog (thumb), dogId, dogName, coat, coatName, created}   (JPEG data URLs)
A new account is asked for its first dog right after signing in. fitstudio.js announces a finished picture with the
DOM event "apetto:fitdone".
"""
import json

PAGE = "pages/member.html"
FIREBASE_VER = "10.12.2"

FIRESTORE_RULES = """rules_version = '2';
service cloud.firestore {
  match /databases/{database}/documents {
    // admin Google accounts: can read every member and delete data (admin page 會員). Add more emails to the list.
    function isAdmin() {
      return request.auth != null && request.auth.token.email_verified == true
             && request.auth.token.email in ['shover1027@gmail.com'];
    }
    function isOwner(uid) { return request.auth != null && request.auth.uid == uid; }
    match /users/{uid} {
      allow read: if isOwner(uid) || isAdmin();
      allow create, update: if isOwner(uid);
      allow delete: if isOwner(uid) || isAdmin();
      match /dogs/{dogId} {
        allow read, delete: if isOwner(uid) || isAdmin();
        allow create, update: if isOwner(uid)
                              && request.resource.data.name is string && request.resource.data.name.size() <= 40
                              && request.resource.data.back is number && request.resource.data.back > 0 && request.resource.data.back < 150;
      }
      match /fits/{fitId} {
        allow read, delete: if isOwner(uid) || isAdmin();
        allow create: if isOwner(uid)
                      && request.resource.data.img is string && request.resource.data.img.size() < 600000
                      && request.resource.data.dog is string && request.resource.data.dog.size() < 120000;
      }
    }
  }
}"""


def config():
    import theme as th
    f = th.sb.DATA_DIR / "firebase.json"
    try:
        c = json.loads(f.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if not all(c.get(k) for k in ("apiKey", "authDomain", "projectId", "appId")):
        return None
    return {k: c[k] for k in ("apiKey", "authDomain", "projectId", "appId")}


def script_tag(d, cfg, lang, data=None):
    import theme as th
    import fitstudio as fit
    # saved try-ons can be recoloured on the laptop (same colours as the fitting room)
    colors = fit.member_colors(data, lang) if data else {}
    conf = {"fb": cfg, "ver": FIREBASE_VER, "member": th.link(d, PAGE, lang), "api": fit.API_BASE, "key": fit.API_KEY, "colors": colors}
    return (f'<script id="apt-member" type="application/json">{json.dumps(conf, ensure_ascii=False)}</script>'
            f'<script type="module" src="{th.asset(d, "assets/member.js")}?v={th.digest(JS)}"></script>')


def fit_bar():
    """Under the fitting-room heading: sign-in button, or the chosen dog."""
    return '<div class="fit-member" hidden></div>'


def history_block():
    return ('<section class="fit-history" hidden><div class="fit-history-head"><h2>我的試穿紀錄</h2><p>只有你自己看得到，可以隨時刪除。</p></div>'
            '<div class="fit-history-grid"></div></section>')


def render_page(data, lang):
    import theme as th
    d = th.rel_dir(PAGE)
    cfg = config()
    crumbs = f'<li><a href="{th.link(d, "index.html", lang)}">首頁</a></li><li><span>會員專區</span></li>'
    body = f"""<div class="wrap"><ol class="breadcrumb">{crumbs}</ol><div class="ph"><h1>會員專區</h1></div>
<div class="mem" data-state="loading">
 <div class="mem-loading">載入中…</div>
 <div class="mem-out"><p>用 Google 登入，保存毛孩的尺寸和試穿紀錄，下次試穿不用再量。</p><div class="mem-login"></div>
  <p class="mem-fine">我們只會取得你的名字、Email 和大頭貼，用來辨識你的帳號。</p></div>
 <div class="mem-in">
  <div class="mem-who"></div>
  <section class="mem-dogs"><div class="mem-head"><h2>我的毛孩</h2><button type="button" class="btn ghost mem-add">＋ 新增毛孩</button></div><div class="mem-list"></div>
   <div class="mem-go"><a class="btn brand" href="{th.link(d, "fitstudio.html", lang)}">去試衣間</a></div></section>
  {history_block()}
 </div>
</div></div>
{script_tag(d, cfg, lang, data) if cfg else ''}"""
    return th.page(data, PAGE, lang, f"會員專區 | {th.BRAND}", body, "用 Google 登入 apetto，保存毛孩的尺寸和試穿紀錄。", current=PAGE)


# markup strings, translated by theme.translate_soup through theme.UI
UI = {
    "會員專區": {"en": "My account", "ja": "マイページ", "de": "Mein Konto"},
    "會員": {"en": "Account", "ja": "マイページ", "de": "Konto"},
    "載入中…": {"en": "Loading…", "ja": "読み込み中…", "de": "Wird geladen…"},
    "用 Google 登入，保存毛孩的尺寸和試穿紀錄，下次試穿不用再量。": {"en": "Sign in with Google to keep your dog's measurements and try-on pictures, so you don't have to measure again next time.", "ja": "Google でログインすると、愛犬のサイズと試着画像が保存され、次回は測り直す必要がありません。", "de": "Melde dich mit Google an, dann bleiben die Maße deines Hundes und deine Anprobe-Bilder gespeichert und du musst nicht neu messen."},
    "我們只會取得你的名字、Email 和大頭貼，用來辨識你的帳號。": {"en": "We only receive your name, email and profile picture, to recognise your account.", "ja": "取得するのはお名前・メール・プロフィール画像のみで、アカウントの識別に使います。", "de": "Wir erhalten nur Name, E-Mail und Profilbild, um dein Konto zu erkennen."},
    "我的毛孩": {"en": "My dogs", "ja": "うちの子", "de": "Meine Hunde"},
    "＋ 新增毛孩": {"en": "+ Add a dog", "ja": "＋ わんちゃんを追加", "de": "+ Hund hinzufügen"},
    "去試衣間": {"en": "Go to the fitting room", "ja": "試着室へ", "de": "Zur Anprobe"},
    "我的試穿紀錄": {"en": "My try-ons", "ja": "試着の記録", "de": "Meine Anproben"},
    "只有你自己看得到，可以隨時刪除。": {"en": "Only you can see these, and you can delete them anytime.", "ja": "あなただけが見られます。いつでも削除できます。", "de": "Nur du siehst sie, und du kannst sie jederzeit löschen."},
}

CSS = r"""
/* Google sign-in: member page and fitting room */
.gbtn{display:inline-flex;align-items:center;gap:10px;min-height:46px;padding:0 18px 0 14px;border-radius:999px;border:1.5px solid var(--line2);background:var(--card);color:var(--ink);font:inherit;font-weight:700;font-size:15px;cursor:pointer}
.gbtn:hover{border-color:var(--ink2)}.gbtn svg{width:20px;height:20px;flex:0 0 auto}
.mem{margin:18px 0 48px}.mem>div{display:none}.mem[data-state=loading] .mem-loading,.mem[data-state=out] .mem-out,.mem[data-state=in] .mem-in{display:block}
.mem-loading{color:var(--mute);padding:30px 0}
.mem-out{max-width:520px;background:var(--card);border:1px solid var(--line);border-radius:20px;padding:26px}.mem-out p{margin:0 0 16px;font-size:16px;color:var(--ink2);line-height:1.6}.mem-out .mem-fine{margin:16px 0 0;font-size:13px;color:var(--mute)}
.mem-who{display:flex;align-items:center;gap:12px;flex-wrap:wrap;margin-bottom:22px;font-size:15px}.mem-who img{width:44px;height:44px;border-radius:50%;object-fit:cover}.mem-who b{display:block;font-size:17px;color:var(--ink)}.mem-who span{color:var(--mute);font-size:13.5px}
.mem-who .out{margin-left:auto;display:inline-flex;align-items:center;gap:7px;min-height:42px;padding:0 16px;border:1.5px solid var(--line2);border-radius:999px;background:var(--card);font:inherit;font-size:14.5px;font-weight:600;color:var(--ink);cursor:pointer}.mem-who .out svg{width:17px;height:17px}.mem-who .out:hover{border-color:var(--brand);color:var(--brand-ink)}
.mem-head{display:flex;align-items:center;justify-content:flex-start;gap:16px;margin-bottom:12px}.mem-head h2{margin:0;font-size:22px}.mem-head .btn{min-height:42px;padding:0 16px;font-size:14.5px}
.mem-list{display:grid;grid-template-columns:repeat(auto-fill,minmax(230px,1fr));gap:12px}
.mem-dog{border:1px solid var(--line);border-radius:16px;background:var(--card);padding:16px 18px;display:grid;gap:8px}
.mem-dog h3{margin:0;font-size:18px;display:flex;align-items:center;gap:8px}.mem-dog h3 em{font-style:normal;font-size:12px;font-weight:700;color:#fff;background:var(--brand);border-radius:999px;padding:2px 8px}
.mem-dog dl{display:grid;grid-template-columns:auto 1fr;gap:2px 12px;margin:0;font-size:14px}.mem-dog dt{color:var(--mute)}.mem-dog dd{margin:0;color:var(--ink)}
.mem-dog .acts{display:flex;gap:12px;font-size:13.5px}.mem-dog .acts button{background:none;border:0;padding:0;font:inherit;color:var(--ink2);text-decoration:underline;cursor:pointer}
.mem-go{margin:18px 0 0}
.fit-member{display:flex;flex-wrap:wrap;align-items:center;gap:10px 14px;margin:14px 0 0;font-size:14px;color:var(--ink2)}
.fit-member:has(.top){display:grid;gap:10px;max-width:460px;padding:14px 16px;border:1px solid var(--line);border-radius:16px;background:var(--card)}
.fit-member .top{display:flex;align-items:center;justify-content:space-between;gap:10px}
.fit-member .who b{font-weight:700}
.fit-member .pick{display:grid;gap:6px;font-size:13px;color:var(--mute);font-weight:600}
.fit-member .pick select{width:100%;min-height:44px;font-size:16px;padding:0 14px}
.fit-member .why{color:var(--mute);font-size:13.5px;max-width:42ch}
.fit-member .who{display:inline-flex;align-items:center;gap:8px;font-weight:600;color:var(--ink)}.fit-member .who img{width:30px;height:30px;border-radius:50%;object-fit:cover}
.fit-member select{min-height:38px;border-radius:999px;border:1.5px solid var(--line2);background:var(--card);color:var(--ink);font:inherit;font-weight:600;padding:0 12px}
.fit-member a,.fit-member .lnk{color:var(--ink2);font-size:13.5px;text-decoration:underline;background:none;border:0;padding:0;font-family:inherit;cursor:pointer}
.fit-stage.mem-out .fit-dl::after,.fit-stage.mem-out .fit-share::after{content:"🔒";margin-left:6px;font-size:.85em}
.fit-stage.mem-out .shot{-webkit-touch-callout:none;-webkit-user-select:none;user-select:none}
.fit-saved{margin:10px 0 0;font-size:13.5px;color:var(--ink2);display:flex;align-items:center;gap:8px;flex-wrap:wrap}.fit-saved button{background:none;border:0;padding:0;font:inherit;color:var(--brand-ink);text-decoration:underline;cursor:pointer}
.fit-history{margin:40px 0 16px;padding:22px 24px 24px;border:1px solid var(--line);border-radius:20px;background:var(--card)}.fit-history-head{display:grid;gap:4px;margin-bottom:16px}
.fit-history-head h2{margin:0;font-size:22px}.fit-history-head p{margin:0;font-size:14px;color:var(--mute)}
.fit-history-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(200px,1fr));gap:14px}@media (max-width:560px){.fit-history{padding:16px}.fit-history-grid{grid-template-columns:1fr 1fr;gap:10px}}
.fit-history .item{position:relative;border:1px solid var(--line);border-radius:14px;overflow:hidden;background:var(--bg)}
.fit-history .item a{display:block;aspect-ratio:1;background:#fff}.fit-history .item img{width:100%;height:100%;object-fit:cover;display:block}
.fit-history .item .meta{padding:10px 12px 12px;font-size:13.5px;line-height:1.45}.fit-history .item .meta b{display:block;color:var(--ink)}.fit-history .item .meta span{color:var(--mute);font-size:12px}
.fit-history .item .del{position:absolute;top:6px;right:6px;width:30px;height:30px;border-radius:50%;border:0;background:rgba(0,0,0,.55);color:#fff;font-size:15px;line-height:30px;cursor:pointer}
.fit-history .empty{color:var(--mute);font-size:14px}
.fit-viewer{position:fixed;inset:0;z-index:80;display:flex;align-items:center;justify-content:center;padding:16px;background:rgba(15,16,18,.94);overflow:auto}
.fit-viewer figure{margin:0;display:flex;flex-direction:column;align-items:center;gap:12px;max-width:100%}
.fit-viewer img{display:block;max-width:min(900px,100%);max-height:calc(100vh - 170px);border-radius:14px;background:#fff;object-fit:contain}
.fit-viewer figcaption{color:#fff;font-size:14px;text-align:center;line-height:1.5}.fit-viewer figcaption span{opacity:.75;font-size:13px}
.fit-viewer .cols{display:flex;flex-direction:column;align-items:center;gap:8px}.fit-viewer .cols .row{display:flex;gap:8px;flex-wrap:wrap;justify-content:center}
.fit-viewer .cols button{display:inline-flex;align-items:center;gap:7px;min-height:38px;padding:0 13px 0 7px;border-radius:999px;border:1.5px solid rgba(255,255,255,.35);background:rgba(255,255,255,.08);color:#fff;font:inherit;font-size:13.5px;font-weight:600;cursor:pointer}
.fit-viewer .cols button i{width:22px;height:22px;border-radius:50%;border:1.5px solid rgba(255,255,255,.7)}.fit-viewer .cols button.cur{border-color:#fff;background:rgba(255,255,255,.2)}
.fit-viewer .cols small{color:rgba(255,255,255,.7);font-size:12px;min-height:1.2em;text-align:center}
.fit-viewer .acts{display:flex;gap:10px;flex-wrap:wrap;justify-content:center}
.fit-viewer .acts a,.fit-viewer .acts button{display:inline-flex;align-items:center;min-height:44px;padding:0 20px;border-radius:999px;font:inherit;font-size:15px;font-weight:600;cursor:pointer;text-decoration:none}
.fit-viewer .acts a{background:#fff;color:#17181a;border:0}.fit-viewer .acts button{background:none;color:#fff;border:1.5px solid rgba(255,255,255,.6)}
.dog-modal{position:fixed;inset:0;z-index:70;display:flex;align-items:center;justify-content:center;padding:16px;background:rgba(23,24,26,.55)}
.dog-modal form{width:min(460px,100%);max-height:calc(100vh - 32px);overflow:auto;background:var(--card);border-radius:20px;padding:22px;box-shadow:0 24px 60px rgba(0,0,0,.25)}
.dog-modal h3{margin:0 0 6px;font-size:20px}.dog-modal .sub{margin:0 0 16px;color:var(--ink2);font-size:14.5px;line-height:1.55}
.dog-modal label{display:grid;gap:5px;margin-bottom:12px;font-size:14px;font-weight:600;color:var(--ink2)}
.dog-modal input{min-height:44px;border-radius:12px;border:1.5px solid var(--line2);background:var(--bg);color:var(--ink);font:inherit;font-size:16px;padding:0 12px}
.dog-modal input:focus{outline:none;border-color:var(--ink)}
.dog-modal .row{display:grid;grid-template-columns:1fr 1fr 1fr;gap:10px}.dog-modal .row label{margin-bottom:6px}
.dog-modal .help{margin:0 0 14px;font-size:13px;color:var(--mute);line-height:1.55}
.dog-modal .err{color:var(--brand-ink);font-size:13.5px;min-height:1em;margin:0 0 8px}
.dog-modal .acts{display:flex;gap:10px;justify-content:flex-end;flex-wrap:wrap}.dog-modal .acts .btn{min-height:44px;padding:0 20px;font-size:15px}
@media (max-width:420px){.dog-modal .row{grid-template-columns:1fr 1fr}}
"""

JS = r"""/* Google sign-in: Firebase Auth + Firestore, loaded on the member page and the fitting room when the site has a Firebase config */
const cfgEl = document.getElementById('apt-member');
const L = (document.documentElement.lang || 'zh').slice(0, 2);
const T = {
  login: { zh: '用 Google 登入', en: 'Sign in with Google', ja: 'Google でログイン', de: 'Mit Google anmelden' },
  why: { zh: '登入後，毛孩的尺寸和試穿照片會幫你保存。', en: 'Sign in to keep your dog\'s measurements and try-on pictures.', ja: 'ログインすると、愛犬のサイズと試着画像が保存されます。', de: 'Anmelden, um Maße und Anprobe-Bilder zu behalten.' },
  vDl: { zh: '下載照片', en: 'Download', ja: 'ダウンロード', de: 'Herunterladen' },
  vColor: { zh: '換個顏色看看', en: 'Try another colour', ja: 'ほかの色も見る', de: 'Andere Farbe ansehen' },
  vBusy: { zh: '換色中…', en: 'Changing colour…', ja: '色を変えています…', de: 'Farbe wird geändert…' },
  vFail: { zh: '換色暫時無法使用，請稍後再試。', en: 'Colour change is unavailable right now. Please try again later.', ja: '色の変更は現在ご利用いただけません。しばらくしてからお試しください。', de: 'Farbwechsel ist gerade nicht verfügbar. Bitte später erneut versuchen.' },
  vNote: { zh: '換色由電腦自動處理，顏色以實際商品為準。', en: 'Recoloured automatically; actual colours may differ.', ja: '色は自動で変えています。実際の商品の色とは異なる場合があります。', de: 'Automatisch umgefärbt; die echten Farben können abweichen.' },
  vClose: { zh: '關閉', en: 'Close', ja: '閉じる', de: 'Schließen' },
  out: { zh: '登出', en: 'Sign out', ja: 'ログアウト', de: 'Abmelden' },
  dogFor: { zh: '幫誰試穿：', en: 'Dressing:', ja: '試着する子：', de: 'Für:' },
  manage: { zh: '管理毛孩', en: 'Manage dogs', ja: 'うちの子を管理', de: 'Hunde verwalten' },
  addDog: { zh: '新增毛孩', en: 'Add a dog', ja: 'わんちゃんを追加', de: 'Hund hinzufügen' },
  welcome: { zh: '歡迎！先告訴我們你的毛孩', en: 'Welcome! Tell us about your dog first', ja: 'ようこそ！まずはわんちゃんのことを教えてください', de: 'Willkommen! Erzähl uns zuerst von deinem Hund' },
  welcomeSub: { zh: '填好尺寸，試衣間就會直接推薦合身的款式和尺寸。之後可以在「會員專區」修改或新增其他毛孩。', en: 'With the measurements, the fitting room suggests the right style and size straight away. You can edit them or add more dogs in "My account".', ja: 'サイズを入れると、試着室でぴったりの型とサイズをすぐ提案します。マイページでいつでも変更・追加できます。', de: 'Mit den Maßen schlägt die Anprobe gleich Modell und Größe vor. In „Mein Konto“ kannst du sie ändern oder weitere Hunde hinzufügen.' },
  editDog: { zh: '修改毛孩資料', en: 'Edit dog', ja: 'わんちゃんの情報を編集', de: 'Hund bearbeiten' },
  name: { zh: '名字', en: 'Name', ja: '名前', de: 'Name' },
  back: { zh: '背長 *', en: 'Back length *', ja: '背丈 *', de: 'Rückenlänge *' },
  neck: { zh: '領圍', en: 'Neck', ja: '首回り', de: 'Hals' },
  belly: { zh: '腹圍', en: 'Girth', ja: '胴回り', de: 'Bauch' },
  help: { zh: '單位 cm。背長：從脖子根部（約前腳的位置）量到尾巴根；領圍、腹圍為圈量，可以不填。', en: 'In cm. Back length: from the base of the neck (about where the front legs are) to the base of the tail. Neck and girth are around the body and optional.', ja: '単位 cm。背丈：首の付け根（前足のあたり）から尻尾の付け根まで。首回り・胴回りは一周の長さで、空欄でも構いません。', de: 'In cm. Rückenlänge: vom Halsansatz (etwa bei den Vorderbeinen) bis zum Rutenansatz. Hals und Bauch sind Umfänge und optional.' },
  save: { zh: '儲存', en: 'Save', ja: '保存', de: 'Speichern' },
  later: { zh: '之後再填', en: 'Later', ja: 'あとで', de: 'Später' },
  cancel: { zh: '取消', en: 'Cancel', ja: 'キャンセル', de: 'Abbrechen' },
  needName: { zh: '請輸入名字', en: 'Please enter a name', ja: '名前を入力してください', de: 'Bitte einen Namen eingeben' },
  needBack: { zh: '請輸入背長（cm）', en: 'Please enter the back length (cm)', ja: '背丈（cm）を入力してください', de: 'Bitte die Rückenlänge (cm) eingeben' },
  edit: { zh: '修改', en: 'Edit', ja: '編集', de: 'Bearbeiten' },
  remove: { zh: '刪除', en: 'Delete', ja: '削除', de: 'Löschen' },
  removeQ: { zh: '刪除這隻毛孩的資料？', en: 'Delete this dog?', ja: 'この子の情報を削除しますか？', de: 'Diesen Hund löschen?' },
  last: { zh: '上次試穿', en: 'Last used', ja: '前回', de: 'Zuletzt' },
  noDogs: { zh: '還沒有毛孩資料，按「新增毛孩」開始。', en: 'No dogs yet; tap "Add a dog" to start.', ja: 'まだ登録がありません。「わんちゃんを追加」からどうぞ。', de: 'Noch keine Hunde; tippe auf „Hund hinzufügen“.' },
  saved: { zh: '已保存到「我的試穿紀錄」', en: 'Saved to "My try-ons"', ja: '「試着の記録」に保存しました', de: 'In „Meine Anproben“ gespeichert' },
  saveFail: { zh: '保存失敗，請稍後再試', en: 'Could not save, please try again later', ja: '保存できませんでした', de: 'Speichern fehlgeschlagen' },
  loginToDl: { zh: '登入會員才能下載或分享照片。', en: 'Sign in to download or share the picture.', ja: '画像のダウンロード・共有は会員ログインが必要です。', de: 'Zum Herunterladen oder Teilen bitte anmelden.' },
  loginDlNow: { zh: '用 Google 登入', en: 'Sign in with Google', ja: 'Google でログイン', de: 'Mit Google anmelden' },
  dlReady: { zh: '已登入，可以下載照片了。', en: 'Signed in: you can download the picture now.', ja: 'ログインしました。画像をダウンロードできます。', de: 'Angemeldet: Das Bild kann jetzt heruntergeladen werden.' },
  loginToSave: { zh: '想保存這張？', en: 'Want to keep this one?', ja: 'この画像を保存しますか？', de: 'Dieses Bild behalten?' },
  loginNow: { zh: '用 Google 登入並保存', en: 'Sign in with Google and save', ja: 'Google でログインして保存', de: 'Mit Google anmelden und speichern' },
  delFit: { zh: '刪除這張試穿紀錄？', en: 'Delete this try-on?', ja: 'この記録を削除しますか？', de: 'Diese Anprobe löschen?' },
  none: { zh: '還沒有試穿紀錄，試穿完會自動保存在這裡。', en: 'No try-ons yet; finished pictures are saved here automatically.', ja: 'まだ記録はありません。試着すると自動でここに保存されます。', de: 'Noch keine Anproben; fertige Bilder landen automatisch hier.' },
  popup: { zh: '登入視窗被瀏覽器擋住了，請允許彈出視窗後再試一次。', en: 'The sign-in window was blocked; allow pop-ups and try again.', ja: 'ログイン画面がブロックされました。ポップアップを許可してもう一度お試しください。', de: 'Das Anmeldefenster wurde blockiert; Pop-ups erlauben und erneut versuchen.' },
  fail: { zh: '登入失敗，請稍後再試。', en: 'Sign-in failed, please try again later.', ja: 'ログインできませんでした。', de: 'Anmeldung fehlgeschlagen.' },
  dogDefault: { zh: '我的毛孩', en: 'My dog', ja: 'うちの子', de: 'Mein Hund' },
};
const t = k => (T[k] && (T[k][L] || T[k].zh)) || k;
const esc = s => String(s == null ? '' : s).replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
const G = '<svg viewBox="0 0 48 48" aria-hidden="true"><path fill="#FFC107" d="M43.6 20.5H42V20H24v8h11.3C33.7 32.7 29.2 36 24 36c-6.6 0-12-5.4-12-12s5.4-12 12-12c3.1 0 5.8 1.2 7.9 3.1l5.7-5.7C34 6.1 29.3 4 24 4 12.9 4 4 12.9 4 24s8.9 20 20 20 20-8.9 20-20c0-1.3-.1-2.4-.4-3.5z"/><path fill="#FF3D00" d="M6.3 14.7l6.6 4.8C14.7 15.1 19 12 24 12c3.1 0 5.8 1.2 7.9 3.1l5.7-5.7C34 6.1 29.3 4 24 4 16.3 4 9.7 8.3 6.3 14.7z"/><path fill="#4CAF50" d="M24 44c5.2 0 9.9-2 13.4-5.2l-6.2-5.2C29.2 35.1 26.7 36 24 36c-5.2 0-9.6-3.3-11.3-7.9l-6.5 5C9.5 39.6 16.2 44 24 44z"/><path fill="#1976D2" d="M43.6 20.5H42V20H24v8h11.3c-.8 2.2-2.2 4.2-4.1 5.6l6.2 5.2C37 39.2 44 34 44 24c0-1.3-.1-2.4-.4-3.5z"/></svg>';
const loginBtn = () => `<button type="button" class="gbtn">${G}<span>${t('login')}</span></button>`;

const memPage = document.querySelector('.mem'), bar = document.querySelector('.fit-member'), hist = document.querySelector('.fit-history');
let fits = {};
let fb = null, user = null, conf = null, dogs = [], curDog = null, pending = null, asked = false, lastFit = null, dlWait = false;

if (cfgEl && (memPage || bar)) start(JSON.parse(cfgEl.textContent)).catch(e => {
  console.warn('sign-in unavailable', e);
  if (bar) bar.hidden = true;
  if (memPage) { memPage.dataset.state = 'out'; memPage.querySelector('.mem-login').textContent = t('fail'); }
});

async function start(c) {
  conf = c;
  const base = `https://www.gstatic.com/firebasejs/${c.ver}/`;
  const [{ initializeApp }, A, F] = await Promise.all([import(base + 'firebase-app.js'), import(base + 'firebase-auth.js'), import(base + 'firebase-firestore.js')]);
  const app = initializeApp(c.fb);
  const auth = A.getAuth(app);
  auth.languageCode = { zh: 'zh-TW', en: 'en', ja: 'ja', de: 'de' }[L] || 'zh-TW';
  fb = { A, F, auth, db: F.getFirestore(app) };
  A.onAuthStateChanged(auth, onUser);
  if (bar) {
    document.addEventListener('apetto:fitdone', e => { const d = e.detail || {}; lastFit = d; if (user) saveFit(d); else offerSave(d); });
    /* the fitting room asks before download / share: members only */
    window.apNeedLogin = () => {
      if (user) return false;
      const el = savedLine(`<span>${t('loginToDl')}</span><button type="button">${t('loginDlNow')}</button>`);
      if (el) el.querySelector('button').onclick = () => { pending = lastFit; dlWait = true; login(); };
      return true;
    };
    let tm = null;
    document.querySelectorAll('.fit-size input[data-m]').forEach(i => i.addEventListener('input', ev => { if (ev.isTrusted) { clearTimeout(tm); tm = setTimeout(saveSizes, 1200); } }));
  }
}

async function onUser(u) {
  user = u; dogs = []; curDog = null;
  if (u) {
    try {
      const [prof, snap] = await Promise.all([fb.F.getDoc(fb.F.doc(fb.db, 'users', u.uid)), fb.F.getDocs(fb.F.query(fb.F.collection(fb.db, 'users', u.uid, 'dogs'), fb.F.orderBy('created')))]);
      dogs = snap.docs.map(s => ({ id: s.id, ...s.data() }));
      const last = prof.exists() && prof.data().dog;
      curDog = dogs.find(x => x.id === last) || dogs[0] || null;
      fb.F.setDoc(fb.F.doc(fb.db, 'users', u.uid), { name: u.displayName || '', email: u.email || '', photo: u.photoURL || '', updated: fb.F.serverTimestamp() }, { merge: true }).catch(() => {});
    } catch (e) { console.warn('profile', e); }
  }
  render();
  checkAdmin(u);
  if (u && !dogs.length && !asked) { asked = true; dogForm(null, true); }      // new account: ask for the first dog
  if (u && pending) { const p = pending; pending = null; saveFit(p); }
  if (u && dlWait) { dlWait = false; if (!pending) setTimeout(() => savedLine(`<span>✓ ${t('dlReady')}</span>`), 1500); }
  const st = document.querySelector('.fit-stage'); if (st && bar) st.classList.toggle('mem-out', !u);
}

/* admins (the accounts the Firestore rules let read the member list) get a 後台 link in the menu on every page */
async function checkAdmin(u) {
  let admin = false;
  if (u) { try { await fb.F.getDocs(fb.F.query(fb.F.collection(fb.db, 'users'), fb.F.limit(1))); admin = true; } catch (e) { admin = false; } }
  try { if (admin) localStorage.setItem('apetto_admin', '1'); else localStorage.removeItem('apetto_admin'); } catch (e) {}
  if (window.apAdminLink) window.apAdminLink();
}

function render() {
  if (memPage) renderMember();
  if (bar) { renderBar(); applyDog(); }
  renderHistory();
}

async function login() {
  try { await fb.A.signInWithPopup(fb.auth, new fb.A.GoogleAuthProvider()); }
  catch (e) {
    const c = (e && e.code) || '';
    if (/popup-blocked/.test(c)) alert(t('popup'));
    else if (!/popup-closed|cancelled-popup/.test(c)) { console.warn('sign-in failed', e); alert(t('fail')); }
  }
}

/* ---------- member page */
function renderMember() {
  if (!user) {
    memPage.dataset.state = 'out';
    const box = memPage.querySelector('.mem-login'); box.innerHTML = loginBtn(); box.querySelector('.gbtn').onclick = login; return;
  }
  memPage.dataset.state = 'in';
  const who = memPage.querySelector('.mem-who');
  who.innerHTML = `${user.photoURL ? `<img src="${esc(user.photoURL)}" alt="" referrerpolicy="no-referrer">` : ''}<div><b>${esc(user.displayName || '')}</b><span>${esc(user.email || '')}</span></div><button type="button" class="out"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"/><path d="M16 17l5-5-5-5"/><path d="M21 12H9"/></svg>${t('out')}</button>`;
  who.querySelector('.out').onclick = () => fb.A.signOut(fb.auth);
  memPage.querySelector('.mem-add').onclick = () => dogForm(null, false);
  const list = memPage.querySelector('.mem-list');
  if (!dogs.length) { list.innerHTML = `<p class="mem-empty">${t('noDogs')}</p>`; return; }
  const v = x => x ? `${x} cm` : '—';
  list.innerHTML = dogs.map(x => `<div class="mem-dog" data-id="${esc(x.id)}"><h3>${esc(x.name)}${curDog && curDog.id === x.id ? `<em>${t('last')}</em>` : ''}</h3>`
    + `<dl><dt>${t('back').replace(' *', '')}</dt><dd>${v(x.back)}</dd><dt>${t('neck')}</dt><dd>${v(x.neck)}</dd><dt>${t('belly')}</dt><dd>${v(x.belly)}</dd></dl>`
    + `<div class="acts"><button type="button" data-a="edit">${t('edit')}</button><button type="button" data-a="del">${t('remove')}</button></div></div>`).join('');
  list.querySelectorAll('.mem-dog').forEach(el => {
    const x = dogs.find(d => d.id === el.dataset.id);
    el.querySelector('[data-a=edit]').onclick = () => dogForm(x, false);
    el.querySelector('[data-a=del]').onclick = async () => {
      if (!confirm(t('removeQ'))) return;
      try { await fb.F.deleteDoc(fb.F.doc(fb.db, 'users', user.uid, 'dogs', x.id)); dogs = dogs.filter(d => d.id !== x.id); if (curDog && curDog.id === x.id) curDog = dogs[0] || null; render(); } catch (e) { console.warn('delete dog', e); }
    };
  });
}

/* add / edit a dog; first=true is the welcome form of a new account */
function dogForm(x, first) {
  const old = document.querySelector('.dog-modal'); if (old) old.remove();
  const m = document.createElement('div'); m.className = 'dog-modal'; m.setAttribute('role', 'dialog'); m.setAttribute('aria-modal', 'true');
  const num = (k, v) => `<label>${t(k)}<input type="number" inputmode="decimal" min="10" max="${k === 'belly' ? 150 : 120}" step="0.5" name="${k}" value="${v ? esc(v) : ''}"></label>`;
  m.innerHTML = `<form novalidate><h3>${first ? t('welcome') : x ? t('editDog') : t('addDog')}</h3>${first ? `<p class="sub">${t('welcomeSub')}</p>` : ''}`
    + `<label>${t('name')}<input type="text" name="name" maxlength="40" value="${esc(x ? x.name : (dogs.length ? '' : t('dogDefault')))}" autocomplete="off"></label>`
    + `<div class="row">${num('back', x && x.back)}${num('neck', x && x.neck)}${num('belly', x && x.belly)}</div><p class="help">${t('help')}</p><p class="err"></p>`
    + `<div class="acts"><button type="button" class="btn ghost" data-a="no">${first ? t('later') : t('cancel')}</button><button type="submit" class="btn brand">${t('save')}</button></div></form>`;
  document.body.appendChild(m);
  const f = m.querySelector('form'), err = m.querySelector('.err');
  if (!x) { const sz = currentSizes(); ['back', 'neck', 'belly'].forEach(k => { if (sz[k] && !f[k].value) f[k].value = sz[k]; }); }
  m.querySelector('[data-a=no]').onclick = () => m.remove();
  m.addEventListener('click', e => { if (e.target === m) m.remove(); });
  f.onsubmit = async e => {
    e.preventDefault();
    const name = f.name.value.trim(), back = parseFloat(f.back.value), neck = parseFloat(f.neck.value) || 0, belly = parseFloat(f.belly.value) || 0;
    if (!name) { err.textContent = t('needName'); f.name.focus(); return; }
    if (!(back > 0 && back < 150)) { err.textContent = t('needBack'); f.back.focus(); return; }
    const data = { name, back, neck, belly };
    try {
      if (x) { await fb.F.updateDoc(fb.F.doc(fb.db, 'users', user.uid, 'dogs', x.id), data); Object.assign(x, data); curDog = x; }
      else { const r = await fb.F.addDoc(fb.F.collection(fb.db, 'users', user.uid, 'dogs'), { ...data, created: fb.F.serverTimestamp() }); curDog = { id: r.id, ...data }; dogs.push(curDog); }
      rememberDog();
      m.remove(); render();
    } catch (e2) { console.warn('save dog', e2); err.textContent = t('saveFail'); }
  };
  setTimeout(() => (x || first ? f.back : f.name).focus(), 30);
}

function rememberDog() {
  if (user && curDog) fb.F.setDoc(fb.F.doc(fb.db, 'users', user.uid), { dog: curDog.id }, { merge: true }).catch(() => {});
}

/* ---------- fitting room */
function renderBar() {
  bar.hidden = false;
  if (!user) { bar.innerHTML = loginBtn() + `<span class="why">${t('why')}</span>`; bar.querySelector('.gbtn').onclick = login; return; }
  const who = `<span class="who">${user.photoURL ? `<img src="${esc(user.photoURL)}" alt="" referrerpolicy="no-referrer">` : ''}<b>${esc((user.displayName || '').split(' ')[0])}</b></span>`;
  const pick = dogs.length
    ? `<label class="pick"><span>${t('dogFor')}</span><select>${dogs.map(x => `<option value="${esc(x.id)}"${curDog && curDog.id === x.id ? ' selected' : ''}>${esc(x.name)}</option>`).join('')}<option value="+">＋ ${t('addDog')}</option></select></label>`
    : `<button type="button" class="lnk" data-a="add">＋ ${t('addDog')}</button>`;
  bar.innerHTML = `<div class="top">${who}<a href="${esc(conf.member)}">${t('manage')}</a></div>${pick}`;
  const sel = bar.querySelector('select');
  if (sel) sel.onchange = () => { if (sel.value === '+') { sel.value = curDog ? curDog.id : ''; dogForm(null, false); return; } curDog = dogs.find(x => x.id === sel.value) || null; rememberDog(); applyDog(true); };
  const add = bar.querySelector('[data-a=add]'); if (add) add.onclick = () => dogForm(null, false);
}

/* put the chosen dog's measurements into the size boxes (the page's size advice reacts to the input event) */
function applyDog(force) {
  if (!curDog) return;
  document.querySelectorAll('.fit-size input[data-m]').forEach(i => {
    const v = curDog[i.dataset.m];
    if (force || !i.value) { i.value = v ? v : ''; i.dispatchEvent(new Event('input')); }
  });
}
function currentSizes() {
  const s = {}; document.querySelectorAll('.fit-size input[data-m]').forEach(i => { const v = parseFloat(i.value); if (v > 0) s[i.dataset.m] = v; }); return s;
}
async function saveSizes() {   // typing in the size boxes updates the chosen dog
  if (!user || !curDog) return;
  const s = currentSizes(); if (!s.back) return;
  const data = { back: s.back, neck: s.neck || 0, belly: s.belly || 0 };
  try { await fb.F.updateDoc(fb.F.doc(fb.db, 'users', user.uid, 'dogs', curDog.id), data); Object.assign(curDog, data); } catch (e) { console.warn('sizes', e); }
}

/* pictures are shrunk to a JPEG data URL before saving (Firestore documents stay well under 1 MB) */
async function shrink(src, max, q) {
  const blob = await (await fetch(src)).blob();
  const bmp = await createImageBitmap(blob);
  const r = Math.min(1, max / Math.max(bmp.width, bmp.height));
  const c = document.createElement('canvas'); c.width = Math.round(bmp.width * r); c.height = Math.round(bmp.height * r);
  const g = c.getContext('2d'); g.fillStyle = '#fff'; g.fillRect(0, 0, c.width, c.height); g.drawImage(bmp, 0, 0, c.width, c.height);
  return c.toDataURL('image/jpeg', q);
}
function savedLine(html) {
  const host = document.querySelector('.fit-actions'); if (!host) return null;
  let el = document.querySelector('.fit-saved'); if (!el) { el = document.createElement('p'); el.className = 'fit-saved'; host.after(el); }
  el.innerHTML = html; return el;
}
function offerSave(d) {
  const el = savedLine(`<span>${t('loginToSave')}</span><button type="button">${t('loginNow')}</button>`);
  if (el) el.querySelector('button').onclick = () => { pending = d; login(); };
}
async function saveFit(d) {
  if (!d || !d.image || !user) return;
  try {
    const [img, dog] = await Promise.all([shrink(d.image, 640, .8), d.dog ? shrink(d.dog, 200, .75) : Promise.resolve('')]);
    await fb.F.addDoc(fb.F.collection(fb.db, 'users', user.uid, 'fits'), { img, dog, dogId: curDog ? curDog.id : '', dogName: curDog ? curDog.name : '', coat: d.coat || '', coatName: d.coatName || '', created: fb.F.serverTimestamp() });
    savedLine(`<span>✓ ${t('saved')}</span>`);
    renderHistory();
  } catch (e) { console.warn('save', e); savedLine(`<span>${t('saveFail')}</span>`); }
}

/* ---------- try-on history (member page and fitting room) */
/* saved pictures are data: URLs, which browsers refuse to open in a new tab: show them in a viewer on the page */
/* the other colours are recoloured on the laptop from the saved picture and dog photo (cached per picture) */
const rcCache = {};
function recolorFit(id, i) {
  const x = fits[id], cols = conf.colors[x.coat], k = id + ':' + i;
  if (!rcCache[k]) rcCache[k] = fetch(conf.api + '/api/recolor', { method: 'POST', headers: Object.assign({ 'Content-Type': 'application/json' }, conf.key ? { 'x-api-key': conf.key } : {}),
      body: JSON.stringify({ image: x.img, from: cols[0].hex, to: cols[i].hex, original: x.dog || undefined }) })
    .then(r => { if (!r.ok) throw new Error('HTTP ' + r.status); return r.json(); }).then(d => d.image)
    .catch(e => { delete rcCache[k]; throw e; });
  return rcCache[k];
}
function viewFit(id, coat, sub) {
  const x = fits[id]; if (!x) return;
  const src = x.img, cols = (conf.colors && conf.api && conf.colors[x.coat]) || [];
  const v = document.createElement('div'); v.className = 'fit-viewer'; v.setAttribute('role', 'dialog'); v.setAttribute('aria-modal', 'true');
  v.innerHTML = `<figure><img src="${esc(src)}" alt=""><figcaption><b>${esc(coat)}</b><br><span>${esc(sub)}</span></figcaption>`
    + (cols.length > 1 ? `<div class="cols"><div class="row">${cols.map((c, i) => `<button type="button" data-i="${i}"${i ? '' : ' class="cur"'}><i style="background:${esc(c.hex)}"></i>${esc(c.name)}</button>`).join('')}</div><small></small></div>` : '')
    + `<div class="acts"><a href="${esc(src)}" download="apetto-fit.jpg">${t('vDl')}</a><button type="button" class="x">${t('vClose')}</button></div></figure>`;
  const img = v.querySelector('img'), dl = v.querySelector('.acts a'), note = v.querySelector('.cols small');
  let want = 0;
  const show = (s) => { img.src = s; dl.href = s; };
  v.querySelectorAll('.cols button').forEach(b => b.onclick = () => {
    const i = +b.dataset.i; want = i;
    v.querySelectorAll('.cols button').forEach(o => o.classList.toggle('cur', o === b));
    if (!i) { show(src); note.textContent = ''; return; }
    note.textContent = t('vBusy');
    recolorFit(id, i).then(s => { if (want !== i) return; show(s); note.textContent = t('vNote'); })
      .catch(() => { if (want === i) note.textContent = t('vFail'); });
  });
  // get the other colours ready while the customer looks at the picture
  (async () => { for (let i = 1; i < cols.length; i++) { if (!v.isConnected) return; try { await recolorFit(id, i); } catch (e) { return; } } })();
  const close = () => { v.remove(); document.removeEventListener('keydown', key); };
  const key = e => { if (e.key === 'Escape') close(); };
  v.onclick = e => { if (e.target === v) close(); };
  v.querySelector('.x').onclick = close;
  document.addEventListener('keydown', key);
  document.body.appendChild(v); v.querySelector('.x').focus();
}
async function renderHistory() {
  if (!hist) return;
  if (!user) { hist.hidden = true; return; }
  const grid = hist.querySelector('.fit-history-grid');
  try {
    const snap = await fb.F.getDocs(fb.F.query(fb.F.collection(fb.db, 'users', user.uid, 'fits'), fb.F.orderBy('created', 'desc'), fb.F.limit(30)));
    hist.hidden = false;
    if (snap.empty) { grid.innerHTML = `<p class="empty">${t('none')}</p>`; return; }
    const fmt = new Intl.DateTimeFormat({ zh: 'zh-TW', en: 'en', ja: 'ja', de: 'de' }[L] || 'zh-TW', { dateStyle: 'medium' });
    fits = {}; snap.docs.forEach(s => { fits[s.id] = s.data(); });
    grid.innerHTML = snap.docs.map(s => { const x = s.data(), dt = x.created && x.created.toDate ? fmt.format(x.created.toDate()) : '';
      return `<div class="item" data-id="${esc(s.id)}"><a href="#" role="button"><img src="${esc(x.img)}" alt="" loading="lazy"></a>`
        + `<div class="meta"><b>${esc(x.coatName)}</b><span>${esc([x.dogName, dt].filter(Boolean).join(' · '))}</span></div><button type="button" class="del" aria-label="${t('delFit')}">✕</button></div>`; }).join('');
    grid.querySelectorAll('.item > a').forEach(a => a.onclick = ev => { ev.preventDefault(); const it = a.closest('.item');
      viewFit(it.dataset.id, it.querySelector('.meta b').textContent, it.querySelector('.meta span').textContent); });
    grid.querySelectorAll('.del').forEach(b => b.onclick = async () => {
      if (!confirm(t('delFit'))) return;
      const it = b.closest('.item');
      try { await fb.F.deleteDoc(fb.F.doc(fb.db, 'users', user.uid, 'fits', it.dataset.id)); it.remove(); if (!grid.querySelector('.item')) renderHistory(); } catch (e) { console.warn('delete', e); }
    });
  } catch (e) { console.warn('history', e); }
}
"""
