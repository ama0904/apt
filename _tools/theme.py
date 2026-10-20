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

CDN = "_ext/image-cdn-flare.qdm.cloud/q60f738cbd6a9c/image/data/"
LOGO = CDN + "2020/02/13/763fe20710eca113bbeddcf52cc6339f.png"
IMG = {
    "hero": CDN + "2026/08/26/b2963b09f6f2a473a8f3367f8d8ac9e2.clean.jpg",      # two dogs in the forest (text area repaired)
    "story": CDN + "2026/08/26/cf1d3a5ae88219b7f6c3868005c2ff8d.clean.jpg",     # labrador, neon raincoat, picnic (shown zoomed: top-left had text)
    "rain": CDN + "2022/01/20/84765377d689a07961bcf145562ffd35.jpg",             # shiba splashing
    "cat1": CDN + "2026/08/26/2e2d960fcdd9a821b141df7d41b8f5c7.clean.jpg",      # frenchie, blue cape
    "cat2": CDN + "2022/02/05/e413d6bbc217658bf1a529f3b51c0a28.PNG",            # black dog, neon
    "cat3": CDN + "2022/02/05/314005a881b4008f09fb07335e50ed44.jpg",            # lime fleece lining
    "f_water": CDN + "2022/02/05/bd9fc68d2a8955f173b21fcc8aae271a.jpg",
    "f_leash": CDN + "1f9e72ac7a5d7e832966283819693d54.jpg",
    "f_snap": CDN + "2022/02/05/c787b7d57fbf0fa0941b63be70fac92f.PNG",
    "f_name": CDN + "2022/02/05/f1d2de57fe93927106c6a19350ea87b8.PNG",
}
CAT_IMG = {1: "cat1", 2: "cat2", 3: "cat3"}
CAT_BLURB = {1: "專為小型犬設計，穿脫簡易、外出便利", 2: "專為中、大型毛孩子設計", 3: "MIT 抗靜電刷毛布料，毛小孩寒流不用怕"}
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
    "瀏覽全系列": {"en": "Shop the collection", "ja": "全ラインナップを見る", "de": "Zur Kollektion"},
    "看暢銷商品": {"en": "See bestsellers", "ja": "人気商品を見る", "de": "Bestseller ansehen"},
    "探索系列": {"en": "Explore", "ja": "シリーズを見る", "de": "Entdecken"},
    "為什麼選擇 apetto": {"en": "Why apetto", "ja": "apetto が選ばれる理由", "de": "Warum apetto"},
    "機能細節": {"en": "Built for the weather", "ja": "機能のディテール", "de": "Funktion im Detail"},
    "耐水壓 10000mmH2O": {"en": "10,000 mmH2O waterproof", "ja": "耐水圧 10,000mmH2O", "de": "Wassersäule 10.000 mm"},
    "頂級防水防風布料，水滴輕易滑落，台灣多雨濕冷也不怕。": {
        "en": "Premium waterproof, windproof fabric. Drops roll right off, even in rainy, damp weather.",
        "ja": "高品質な防水・防風生地。水滴は転がり落ち、雨の多い湿った寒さでも安心です。",
        "de": "Hochwertiger wasser- und winddichter Stoff. Tropfen perlen einfach ab, auch bei nasskaltem Wetter."},
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
    "最新": {"en": "New", "ja": "新着", "de": "Neu"},
    "熱賣": {"en": "Bestseller", "ja": "人気", "de": "Bestseller"},
}

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


def buy_link(p, data):
    settings = data.get("settings") or {}
    return (p.get("buy_url") or "").strip() or (settings.get("shop_url") or "").strip() or f"{sb.ONLINE}product/product&product_id={p['id']}"


def clean_rich_html(fragment_html, page_dir):
    """Description HTML from the shop: real image sources, no inline fonts/sizes, no handlers."""
    frag = BeautifulSoup(fragment_html or "", "html.parser")
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
        if not tag.get_text(strip=True) and not tag.find("img") and not tag.find("iframe"):
            tag.decompose()
    for t in list(frag.find_all(string=True)):
        if " " in t or re.match(r"^\s{2,}", t):
            t.replace_with(NavigableString(re.sub(r"[\s ]+", " ", t)))
    return str(frag)


# ----------------------------------------------------------------- static assets (CSS / JS)
CSS = r"""
:root{--bg:#fbfaf7;--card:#fff;--ink:#17181a;--ink2:#3d4047;--mute:#6f737b;--line:#e7e4dd;--line2:#d9d5cc;--brand:#ff2414;--brand-ink:#d41d0e;--brand-soft:#fff0ec;--sand:#f3efe6;--radius:18px;--max:1200px;--gutter:20px;--font:"Manrope","Noto Sans TC","PingFang TC","Microsoft JhengHei","Hiragino Sans",system-ui,sans-serif}
:lang(ja){--font:"Manrope","Noto Sans JP","Hiragino Sans","Noto Sans TC",system-ui,sans-serif}
*{box-sizing:border-box}html{-webkit-text-size-adjust:100%;scroll-behavior:smooth;overflow-x:clip}
body{margin:0;background:var(--bg);color:var(--ink);font:16px/1.7 var(--font);-webkit-font-smoothing:antialiased}
img{max-width:100%;height:auto;display:block}a{color:inherit;text-decoration:none}
h1,h2,h3,h4{margin:0;font-weight:700;line-height:1.25;letter-spacing:-.01em}
p{margin:0 0 1em}ul,ol{margin:0;padding:0;list-style:none}button{font:inherit}
.wrap{max-width:var(--max);margin:0 auto;padding:0 var(--gutter)}
.sr{position:absolute;width:1px;height:1px;overflow:hidden;clip:rect(0 0 0 0)}
.btn{display:inline-flex;align-items:center;justify-content:center;gap:8px;min-height:48px;padding:0 26px;border-radius:999px;border:1.5px solid var(--ink);background:var(--ink);color:#fff;font-weight:700;font-size:16px;cursor:pointer;transition:transform .15s,background .15s,color .15s,border-color .15s}
.btn:hover{background:#000;transform:translateY(-1px)}
.btn.ghost{background:transparent;color:var(--ink)}.btn.ghost:hover{background:var(--ink);color:#fff}
.btn.brand{background:var(--brand);border-color:var(--brand)}.btn.brand:hover{background:var(--brand-ink);border-color:var(--brand-ink)}
.btn.big{min-height:56px;padding:0 34px;font-size:17px}
.eyebrow{display:inline-block;color:var(--brand-ink);font-weight:700;font-size:14px;letter-spacing:.14em;text-transform:uppercase;margin-bottom:14px}
.sec{padding:72px 0}.sec.tight{padding:48px 0}.sec-head{display:flex;align-items:flex-end;justify-content:space-between;gap:20px;margin-bottom:28px}
.sec-head h2{font-size:clamp(26px,3vw,36px)}.sec-head p{margin:6px 0 0;color:var(--mute);font-size:16px}
.sec-head .more{white-space:nowrap;font-weight:700;color:var(--ink);border-bottom:2px solid var(--brand);padding-bottom:2px}
.js .rv{opacity:0;transform:translateY(16px);transition:opacity .6s ease,transform .6s ease}.js .rv.in{opacity:1;transform:none}
@media (prefers-reduced-motion:reduce){.rv{opacity:1;transform:none;transition:none}html{scroll-behavior:auto}}

/* header */
.hd{position:sticky;top:0;z-index:50;background:rgba(251,250,247,.86);backdrop-filter:saturate(1.4) blur(12px);-webkit-backdrop-filter:saturate(1.4) blur(12px);border-bottom:1px solid transparent;transition:border-color .2s,box-shadow .2s}
.hd.scrolled{border-color:var(--line);box-shadow:0 4px 24px rgba(0,0,0,.05)}
.hd-in{display:flex;align-items:center;gap:18px;min-height:72px}
.logo{display:flex;align-items:center;gap:10px;flex:0 0 auto}.logo img{height:44px;width:auto}
.nav{display:flex;gap:2px;flex:1;min-width:0}
.nav a{white-space:nowrap;padding:10px 12px;border-radius:999px;font-weight:600;font-size:15.5px;color:var(--ink2)}.nav a:hover{background:var(--sand);color:var(--ink)}.nav a.cur{color:var(--brand-ink)}
.srch{display:flex;align-items:center;background:#fff;border:1.5px solid var(--line2);border-radius:999px;padding:0 6px 0 14px;height:44px;width:190px;flex:0 0 auto;transition:width .2s,border-color .2s}
.srch:focus-within{border-color:var(--ink);width:280px}.srch input{border:0;outline:0;background:none;flex:1;min-width:0;font:inherit;font-size:15px}
.srch button{border:0;background:none;width:34px;height:34px;border-radius:50%;display:grid;place-items:center;cursor:pointer;color:var(--ink)}.srch button:hover{background:var(--sand)}
.lang{display:flex;flex:0 0 auto;background:#fff;border:1.5px solid var(--line2);border-radius:999px;padding:4px;gap:2px}
.lang a{display:inline-flex;align-items:center;justify-content:center;min-width:56px;height:38px;padding:0 13px;white-space:nowrap;border-radius:999px;font-weight:700;font-size:15px;color:var(--ink2)}
.lang a:hover{background:var(--sand);color:var(--ink)}.lang a.cur{background:var(--ink);color:#fff}
.burger{display:none;border:0;background:none;width:44px;height:44px;border-radius:50%;cursor:pointer;color:var(--ink)}
.lang-row{display:none}
.mobile-menu{display:none}
@media (max-width:1180px){.nav a{font-size:14.5px;padding:10px 9px}.srch{width:160px}.lang a{min-width:0;padding:0 11px;font-size:14px}}
@media (max-width:980px){
 .nav,.srch,.hd-in>.lang{display:none}.burger{display:grid;place-items:center;margin-left:auto}
 .hd-in{min-height:64px;gap:12px}.logo img{height:38px}
 .lang-row{display:flex;gap:6px;padding:0 var(--gutter) 10px}
 .lang-row a{flex:1;display:inline-flex;align-items:center;justify-content:center;height:44px;border:1.5px solid var(--line2);border-radius:999px;background:#fff;font-weight:700;font-size:15.5px;color:var(--ink2)}
 .lang-row a.cur{background:var(--ink);border-color:var(--ink);color:#fff}
 body.menu-open .mobile-menu{display:block;position:fixed;inset:0;z-index:60;background:var(--bg);padding:24px var(--gutter);overflow:auto;animation:mm-in .22s ease}
 @keyframes mm-in{from{transform:translateX(40px);opacity:0}to{transform:none;opacity:1}}body.menu-open{overflow:hidden}
 .mm-top{display:flex;justify-content:space-between;align-items:center;margin-bottom:24px}.mm-top img{height:38px}
 .mm-close{border:0;background:var(--sand);width:44px;height:44px;border-radius:50%;cursor:pointer;font-size:20px}
 .mm-search{display:flex;background:#fff;border:1.5px solid var(--line2);border-radius:999px;height:52px;padding:0 6px 0 18px;margin-bottom:24px}
 .mm-search input{flex:1;border:0;outline:0;background:none;font:inherit;font-size:16px;min-width:0}.mm-search button{border:0;background:var(--ink);color:#fff;width:40px;height:40px;border-radius:50%;margin:5px 0;cursor:pointer;display:grid;place-items:center}
 .mm-nav a{display:block;padding:16px 0;border-bottom:1px solid var(--line);font-size:20px;font-weight:700}
 .mm-sub{margin-top:24px;display:flex;flex-wrap:wrap;gap:8px 20px}.mm-sub a{color:var(--mute);font-weight:600}
}

/* hero */
.hero{padding:40px 0 20px}
.hero-in{display:grid;grid-template-columns:1fr 1.15fr;gap:48px;align-items:center}
.hero h1{font-size:clamp(34px,4.6vw,60px);letter-spacing:-.02em;margin-bottom:18px}
.hero .lead{font-size:18px;color:var(--ink2);max-width:46ch;margin-bottom:28px}
.hero .cta{display:flex;gap:12px;flex-wrap:wrap}
.hero-img{position:relative;border-radius:28px;overflow:hidden;aspect-ratio:16/10;background:var(--sand)}
.hero-img img{width:100%;height:100%;object-fit:cover;object-position:70% 50%}
.hero-badges{display:flex;gap:10px;flex-wrap:wrap;margin-top:28px}
.badge{display:inline-flex;align-items:center;gap:8px;padding:8px 14px;border-radius:999px;background:#fff;border:1px solid var(--line);font-size:14px;font-weight:600;color:var(--ink2)}
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
.band .btn{background:#fff;color:var(--ink);border-color:#fff}.band .btn:hover{background:var(--brand);border-color:var(--brand);color:#fff}
@media (max-width:980px){.band{grid-template-columns:1fr;padding:36px 26px;border-radius:22px}}

/* page header / breadcrumb */
.ph{padding:36px 0 8px}.ph h1{font-size:clamp(30px,4vw,44px);margin-bottom:8px}.ph p{color:var(--mute);font-size:17px;margin:0}
.breadcrumb{display:flex;flex-wrap:wrap;gap:6px;align-items:center;font-size:14px;color:var(--mute);padding:20px 0 0}
.breadcrumb li+li:before{content:"/";margin-right:6px;color:var(--line2)}.breadcrumb a:hover{color:var(--ink)}
.chips{display:flex;gap:8px;flex-wrap:wrap;margin:18px 0 28px}
.chips a{display:inline-flex;align-items:center;height:40px;padding:0 16px;border-radius:999px;border:1.5px solid var(--line2);background:#fff;font-weight:600;font-size:15px;color:var(--ink2)}
.chips a:hover{border-color:var(--ink);color:var(--ink)}.chips a.cur{background:var(--ink);border-color:var(--ink);color:#fff}
.pagination{color:var(--mute);font-size:15px;margin-bottom:18px}.pagination .results{margin:0}

/* product page */
.pd{display:grid;grid-template-columns:1.15fr 1fr;gap:48px;padding:24px 0 48px;align-items:start}.pd>*{min-width:0}
.gallery{position:sticky;top:92px}
.gal-main{border-radius:24px;overflow:hidden;background:#fff;border:1px solid var(--line);aspect-ratio:4/3}
.gal-main img{width:100%;height:100%;object-fit:contain}
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
#options label.checkbox,#options label.radio{display:inline-flex;align-items:center;justify-content:center;min-width:52px;height:44px;padding:0 16px;margin:0 8px 8px 0;border-radius:12px;border:1.5px solid var(--line2);background:#fff;font-weight:600;font-size:15px;cursor:pointer;user-select:none}
#options label.checkbox:has(input:checked){background:var(--ink);border-color:var(--ink);color:#fff}
#options label.checkbox:hover{border-color:var(--ink)}#options input{position:absolute;opacity:0;width:0;height:0}
.showcase #options label.checkbox{cursor:default;pointer-events:none}
.buy{margin-top:24px;display:flex;flex-direction:column;gap:10px}.buy .btn{width:100%}.buy-note{margin:0;font-size:14px;color:var(--mute);text-align:center}
.showcase-note{margin:24px 0 0;padding:16px 18px;background:var(--sand);border-radius:14px;font-size:15px;color:var(--ink2)}
.showcase-note a{font-weight:700;color:var(--brand-ink);white-space:nowrap}
.pd-desc{padding:16px 0 64px;border-top:1px solid var(--line)}
.pd-desc h2{font-size:24px;margin:40px 0 20px}
.rich{max-width:860px;margin:0 auto;font-size:16px}.rich p,.rich li{margin:0 0 1em;line-height:1.8}.rich ul{list-style:disc;padding-left:1.3em}
.rich img{margin:0 auto 1.5em;border-radius:16px}.rich strong,.rich b{font-weight:700}.rich h2,.rich h3{margin:1.4em 0 .6em}
.rich p:empty{display:none}
.apt-chart{font-family:inherit!important;color:var(--ink)!important}
@media (max-width:980px){.pd{grid-template-columns:1fr;gap:24px;padding-top:12px}.gallery{position:static}.gal-main{border-radius:18px}.pi .product-sell-price{font-size:22px}}

/* article */
.article{max-width:760px;margin:0 auto;padding:0 0 64px;font-size:17px}
.article h1{font-size:clamp(28px,3.4vw,40px);margin:0 0 10px}.article .date{color:var(--mute);font-size:15px;margin-bottom:28px}
.article p{line-height:1.9;margin:0 0 1.1em}.article h2,.article h3{font-size:22px;margin:1.8em 0 .6em}
.article a{color:var(--brand-ink);font-weight:600}.article hr{border:0;border-top:1px solid var(--line);margin:32px 0}
.article .contact{background:var(--card);border:1px solid var(--line);border-radius:var(--radius);padding:22px 24px;margin-top:36px;font-size:16px}
.article .contact p{margin:0 0 .4em}
.news-list{display:grid;gap:14px;max-width:760px;margin:0 auto 64px}
.news-list a{display:flex;gap:20px;align-items:baseline;background:var(--card);border:1px solid var(--line);border-radius:var(--radius);padding:20px 24px;transition:transform .2s,box-shadow .2s}
.news-list a:hover{transform:translateY(-2px);box-shadow:0 12px 30px rgba(0,0,0,.06)}
.news-list time{flex:0 0 auto;color:var(--mute);font-size:15px;font-variant-numeric:tabular-nums}.news-list b{font-size:17px;font-weight:700}
@media (max-width:640px){.news-list a{flex-direction:column;gap:6px}}

/* footer */
.ft{background:#fff;border-top:1px solid var(--line);margin-top:24px}
.ft-in{display:grid;grid-template-columns:1.4fr 1fr 1fr 1.2fr;gap:36px;padding:56px 0 40px}
.ft .brand img{height:42px;margin-bottom:14px}.ft .brand p{color:var(--mute);font-size:15px;max-width:34ch}
.ft h4{font-size:14px;letter-spacing:.12em;text-transform:uppercase;color:var(--mute);margin-bottom:14px}
.ft li{margin:0 0 10px}.ft li a{font-weight:600;color:var(--ink2)}.ft li a:hover{color:var(--brand-ink)}
.ft .social{display:flex;gap:10px;margin-top:14px}.ft .social a{display:inline-flex;align-items:center;gap:6px;padding:8px 14px;border-radius:999px;border:1.5px solid var(--line2);font-weight:600;font-size:14px}
.ft .social a:hover{border-color:var(--ink)}
.ft-bottom{border-top:1px solid var(--line);padding:18px 0;display:flex;justify-content:space-between;gap:12px;flex-wrap:wrap;font-size:13.5px;color:var(--mute)}
@media (max-width:980px){.ft-in{grid-template-columns:1fr 1fr;gap:28px;padding:40px 0 28px}.ft .brand{grid-column:1/-1}}
"""

JS = r"""(function(){
var b=document.querySelector('.burger'),mm=document.querySelector('.mobile-menu');
function closeMenu(){document.body.classList.remove('menu-open');if(b)b.setAttribute('aria-expanded','false');}
if(b&&mm){b.addEventListener('click',function(){var o=document.body.classList.toggle('menu-open');b.setAttribute('aria-expanded',o?'true':'false');});
 mm.querySelectorAll('.mm-close,a').forEach(function(el){el.addEventListener('click',closeMenu);});
 document.addEventListener('keydown',function(e){if(e.key==='Escape')closeMenu();});}
var hd=document.querySelector('.hd');function sh(){if(hd)hd.classList.toggle('scrolled',window.scrollY>8);}
window.addEventListener('scroll',sh,{passive:true});sh();
var main=document.getElementById('main-defer-image');
document.querySelectorAll('#image-additional a').forEach(function(a){a.addEventListener('click',function(e){e.preventDefault();var img=a.querySelector('img');
 if(main&&img)main.src=a.getAttribute('href')||img.src;document.querySelectorAll('#image-additional li').forEach(function(l){l.classList.remove('cur');});a.parentNode.classList.add('cur');});});
if('IntersectionObserver' in window){var io=new IntersectionObserver(function(es){es.forEach(function(e){if(e.isIntersecting){e.target.classList.add('in');io.unobserve(e.target);}});},{rootMargin:'0px 0px -6% 0px'});
 document.querySelectorAll('.rv').forEach(function(el){io.observe(el);});}else{document.querySelectorAll('.rv').forEach(function(el){el.classList.add('in');});}
})();"""

ICON_SEARCH = ('<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" aria-hidden="true">'
               '<circle cx="11" cy="11" r="7"/><path d="m20 20-3.5-3.5"/></svg>')
ICON_MENU = ('<svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" aria-hidden="true">'
             '<path d="M4 7h16M4 12h16M4 17h16"/></svg>')
ICON_ARROW = ('<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">'
              '<path d="M5 12h14M13 6l6 6-6 6"/></svg>')


# ----------------------------------------------------------------- shell
def nav_links(data, page_dir, lang, current=""):
    items = [(sb.category_page(c["id"]), c["name"]) for c in data["categories"]]
    items += [("bestsellers.html", "暢銷商品"), ("pages/4.html", "關於我們")]
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
    search = link(d, "search.html", lang)
    return f"""<header class="hd">
 <div class="wrap hd-in">
  <a class="logo" href="{link(d, 'index.html', lang)}" aria-label="apetto"><img src="{asset(d, LOGO)}" alt="apetto" width="143" height="106"></a>
  <nav class="nav" aria-label="主選單">{nav_links(data, d, lang, current)}</nav>
  <form class="srch" action="{search}" role="search"><input type="search" name="q" placeholder="商品關鍵字" aria-label="搜尋商品"><button type="submit" aria-label="搜尋">{ICON_SEARCH}</button></form>
  <div class="lang" aria-label="語言">{lang_links(site_rel, lang)}</div>
  <button class="burger" aria-label="選單" aria-expanded="false">{ICON_MENU}</button>
 </div>
 <div class="lang-row" aria-label="語言">{lang_links(site_rel, lang)}</div>
</header>
<div class="mobile-menu" role="dialog" aria-label="選單">
  <div class="mm-top"><img src="{asset(d, LOGO)}" alt="apetto"><button class="mm-close" aria-label="關閉">✕</button></div>
  <form class="mm-search" action="{search}" role="search"><input type="search" name="q" placeholder="商品關鍵字" aria-label="搜尋商品"><button type="submit" aria-label="搜尋">{ICON_SEARCH}</button></form>
  <nav class="mm-nav">{nav_links(data, d, lang, current)}</nav>
  <div class="mm-sub"><a href="{link(d, 'search.html', lang)}">全系列</a><a href="{link(d, 'information/news.html', lang)}">最新消息</a><a href="{link(d, 'information/notice.html', lang)}">最新公告</a><a href="{link(d, 'pages/5.html', lang)}">服務條款</a></div>
</div>"""


def footer(data, site_rel, lang):
    d = rel_dir(site_rel)
    cats = "".join(f'<li><a href="{link(d, sb.category_page(c["id"]), lang)}">{esc(c["name"])}</a></li>' for c in data["categories"])
    return f"""<footer class="ft">
 <div class="wrap">
  <div class="ft-in">
   <div class="brand"><img src="{asset(d, LOGO)}" alt="apetto"><p>為專業、機能狗衣而生</p><p>阻擋風雨，擁抱無憂的舒適時光</p>
    <div class="social"><a href="{INSTAGRAM}" target="_blank" rel="noopener">Instagram</a><a href="{PINKOI}" target="_blank" rel="noopener">Pinkoi</a></div></div>
   <div><h4>商品</h4><ul>{cats}<li><a href="{link(d, 'bestsellers.html', lang)}">暢銷商品</a></li><li><a href="{link(d, 'search.html', lang)}">全系列</a></li></ul></div>
   <div><h4>商店訊息</h4><ul><li><a href="{link(d, 'pages/4.html', lang)}">關於我們</a></li><li><a href="{link(d, 'pages/5.html', lang)}">服務條款</a></li><li><a href="{link(d, 'information/news.html', lang)}">最新消息</a></li><li><a href="{link(d, 'information/notice.html', lang)}">最新公告</a></li></ul></div>
   <div><h4>聯絡我們</h4><ul><li><a href="mailto:info@hweider.url.tw">客服信箱：info@hweider.url.tw</a></li><li><a href="tel:+886289915001">連絡電話: 02-89915001</a></li><li>服務時間：週一~週五 10:00-12:00、14:00-18:00</li><li>LINE @apetto</li></ul></div>
  </div>
  <div class="ft-bottom"><span>Copyright ©2026 apetto 機能寵物衣</span><span>apetto © 匯得興業有限公司</span></div>
 </div>
</footer>"""


def page(data, site_rel, lang, title, body, desc="", og_image=None, current="", body_class="", extra_head=""):
    d = rel_dir(site_rel)
    base = posixpath.basename(site_rel)
    alts = "".join(f'<link rel="alternate" hreflang="{HTML_LANG[c]}" href="{sb.lang_variant(base, c)}">' for c in LANG_CODES)
    og = f'<meta property="og:image" content="{esc(PUBLIC + og_image)}">' if og_image else ""
    cls = f' class="{body_class}"' if body_class else ""
    return f"""<!DOCTYPE html>
<html lang="{HTML_LANG[lang]}">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(title)}</title>
<meta name="description" content="{esc(desc)}">
<meta property="og:title" content="{esc(title)}"><meta property="og:description" content="{esc(desc)}"><meta property="og:type" content="website">{og}
<link rel="icon" href="{asset(d, 'favicon.ico')}">
<script>document.documentElement.className+=" js"</script>
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
</body>
</html>"""


ASSET_VER = {"css": digest(CSS), "js": digest(JS)}


# ----------------------------------------------------------------- components
def product_card(p, page_dir, lang, tag=None):
    url = link(page_dir, sb.product_page(p), lang)
    thumb = asset(page_dir, p["image"]["thumb"] or p["image"]["full"])
    badge = ""
    if tag == "hot":
        badge = '<span class="tag hot">熱賣</span>'
    elif tag == "new":
        badge = '<span class="tag">最新</span>'
    return (f'<a class="grid-box" href="{url}" data-producttlid="{p["id"]}" data-zh-name="{esc(p["name"])}">'
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
    d = ""
    best = [p for p in visible if "bestseller" in p.get("sections", [])]
    latest = [p for p in visible if "latest" in p.get("sections", [])]
    tiles = ""
    for c in data["categories"]:
        img = IMG.get(CAT_IMG.get(c["id"], ""), "")
        img_html = f'<img src="{asset(d, img)}" alt="{esc(c["name"])}" loading="lazy">' if img else ""
        n = len([p for p in visible if c["id"] in p.get("categories", [])])
        tiles += (f'<a class="tile" href="{link(d, sb.category_page(c["id"]), lang)}"><div class="img">{img_html}</div>'
                  f'<div class="body"><h3>{esc(c["name"])}</h3><p>{esc(CAT_BLURB.get(c["id"], ""))}</p>'
                  f'<span class="go">探索系列 →</span></div></a>')
    feats = [("f_water", "耐水壓 10000mmH2O", "頂級防水防風布料，水滴輕易滑落，台灣多雨濕冷也不怕。"),
             ("f_leash", "穿著也能上牽繩", "領圍開口設計，穿上 apetto 仍然可以扣上牽繩。"),
             ("f_snap", "快速穿脫", "前扣式鈕扣與腹部插扣，扣上就能出門。"),
             ("f_name", "寫上名字", "專屬名牌，寫上毛孩的名字，衣服就是他的。")]
    feats_html = "".join(f'<div class="feat"><div class="img"><img src="{asset(d, IMG[k])}" alt="" loading="lazy"></div>'
                         f'<div class="body"><h3>{esc(t)}</h3><p>{esc(s)}</p></div></div>' for k, t, s in feats)
    body = f"""<section class="hero"><div class="wrap hero-in">
 <div class="rv in"><span class="eyebrow">{esc(BRAND)}</span><h1>阻擋風雨，擁抱無憂的舒適時光</h1>
  <p class="lead">專為毛孩設計的高機能雨衣與保暖夾克。防水、防風、穿脫快速，陪你走過每一個下雨的日子。</p>
  <div class="cta"><a class="btn big brand" href="{link(d, 'search.html', lang)}">瀏覽全系列</a><a class="btn big ghost" href="{link(d, 'bestsellers.html', lang)}">看暢銷商品</a></div>
  <div class="hero-badges"><span class="badge"><i></i>耐水壓 10000mmH2O</span><span class="badge"><i></i>3M 反光條</span><span class="badge"><i></i>台灣設計製造</span></div>
 </div>
 <div class="hero-img rv in"><img src="{asset(d, IMG['hero'])}" alt="大汪系列" fetchpriority="high"></div>
</div></section>
{section('三大系列', f'<div class="tiles">{tiles}</div>', sub='依毛孩體型與季節挑選', cls='tight', page_dir=d, lang=lang)}
{section('暢銷商品', product_grid(best, d, lang, tag='hot'), more=('bestsellers.html', '查看全部'), sid='bestseller-products', cls='tight', page_dir=d, lang=lang) if best else ''}
<section class="sec"><div class="wrap"><div class="story rv">
 <div class="story-img zoom"><img src="{asset(d, IMG['story'])}" alt="" loading="lazy"></div>
 <div><span class="eyebrow">為專業、機能狗衣而生</span><h2>陪你走過每一個下雨的日子</h2>
  <p>無論是春日裡的梅雨，還是冬日裡的綿綿細雨，每一個下雨的日子，apetto 狗衣系列，讓毛孩子盡情在戶外奔跑。</p>
  <p>apetto 提供高品質、防風保護，頂級布料耐水壓 10000mmH2O，水滴在布料上能輕易滑落，提供舒適的防水防護。</p>
  <a class="btn ghost" href="{link(d, 'pages/4.html', lang)}">關於我們</a></div>
</div></div></section>
{section('為什麼選擇 apetto', f'<div class="feats">{feats_html}</div>', sub='機能細節', cls='tight', page_dir=d, lang=lang)}
{section('推薦商品', product_grid(latest, d, lang, tag='new'), more=('search.html', '查看全部'), sid='latest-products', cls='tight', page_dir=d, lang=lang) if latest else ''}
<section class="sec tight"><div class="wrap"><div class="band rv"><div><h2>極致防水，奔跑不受限。</h2><p><span>有專業的製衣團隊，為毛小孩設計出高機能且時尚的衣服，具有防水、防風功能，</span><span>讓毛小孩們在下雨天也可以盡情奔跑</span></p></div><a class="btn" href="{link(d, 'search.html', lang)}">瀏覽全系列</a></div></div></section>"""
    return page(data, "index.html", lang, HOME_TITLE, body, HOME_DESC, og_image=IMG["hero"], current="index.html")


def category_chips(data, page_dir, lang, current):
    chips = f'<a href="{link(page_dir, "search.html", lang)}"{cur(current == "all")}>全系列</a>'
    for c in data["categories"]:
        chips += f'<a href="{link(page_dir, sb.category_page(c["id"]), lang)}"{cur(current == c["id"])}>{esc(c["name"])}</a>'
    chips += f'<a href="{link(page_dir, "bestsellers.html", lang)}"{cur(current == "best")}>暢銷商品</a>'
    return f'<div class="chips">{chips}</div>'


def render_listing(data, site_rel, lang, title, items, sub="", current="all", search=False):
    d = rel_dir(site_rel)
    count = f'<div class="pagination"><p class="results">共 {len(items)} 件商品</p></div>' if not search else '<div class="pagination"><p class="results"></p></div>'
    body = f"""<div class="wrap">
<ol class="breadcrumb"><li><a href="{link(d, 'index.html', lang)}">首頁</a></li><li><span>{esc(title)}</span></li></ol>
<div class="ph"><h1>{esc(title)}</h1>{f'<p>{esc(sub)}</p>' if sub else ''}</div>
{category_chips(data, d, lang, current)}
{count}
{product_grid(items, d, lang)}
<div style="height:48px"></div>
</div>"""
    nav_cur = site_rel if current in ("best",) else (sb.category_page(current) if isinstance(current, int) else "")
    return page(data, site_rel, lang, f"{title} | {BRAND}", body, sub or title, current=nav_cur)


def gallery_html(p, d):
    name = p["name"]
    full = asset(d, p["image"]["full"])
    items = [(p["image"]["full"], p["image"].get("small") or p["image"]["full"])] + [(g["full"], g.get("small") or g["full"]) for g in p.get("gallery", [])]
    lis = "".join(f'<li{cur(i == 0)}><a href="{asset(d, f)}" title="{esc(name)}"><img src="{asset(d, s)}" alt="{esc(name)}" loading="lazy"></a></li>'
                  for i, (f, s) in enumerate(items))
    thumbs = f'<ul id="image-additional" class="thumbs">{lis}</ul>' if len(items) > 1 else f'<ul id="image-additional" class="thumbs" hidden>{lis}</ul>'
    return f'<div class="gallery"><div class="gal-main"><img id="main-defer-image" src="{full}" alt="{esc(name)}"></div>{thumbs}</div>'


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
               f'<p class="buy-note">將前往官方賣場完成結帳</p></div>')
    else:
        buy = f'<p class="showcase-note">本站為商品介紹，購買請至台灣官方商店。 <a href="{esc(online_url)}" target="_blank" rel="noopener">前往官方商店 →</a></p>'
    related = [q for q in visible if q["id"] != p["id"] and (not cat or cat["id"] in q.get("categories", []))][:4]
    crumbs = f'<li><a href="{link(d, "index.html", lang)}">首頁</a></li>'
    if cat:
        crumbs += f'<li><a href="{link(d, sb.category_page(cat["id"]), lang)}">{esc(cat["name"])}</a></li>'
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
<section class="pd-desc"><h2>商品介紹</h2><div id="tab-description" class="rich">{clean_rich_html(description, d)}</div></section>
</div>
{section('相關商品', product_grid(related, d, lang), cls='tight', page_dir=d, lang=lang) if related else ''}"""
    extra = f'<script type="application/ld+json">{json.dumps(ld, ensure_ascii=False)}</script>\n'
    return page(data, site_rel, lang, f"{name} | {BRAND}", body, desc_text, og_image=p["image"]["full"],
                current=sb.category_page(cat["id"]) if cat else "", body_class="" if lang == "zh" else "showcase", extra_head=extra)


# ----------------------------------------------------------------- info pages (about / terms / news / announcements)
INFO_TITLES = {"pages/4.html": "關於我們", "pages/5.html": "服務條款", "information/news.html": "最新消息", "information/notice.html": "最新公告"}
INFO_PARENT = {"information/news&news_id=1.html": "information/news.html", "information/notice&notice_id=1.html": "information/notice.html"}


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
    if rel in ("information/news.html", "information/notice.html"):
        items = ""
        for li in soup.select("#content ul li"):
            a = li.select_one("a[href]")
            small = li.select_one("small")
            if not a:
                continue
            target = sb.to_site_path(d, a["href"].replace("&amp;", "&"))
            href_v = link(d, target, lang) if sb._LOCALIZED_RE.match(target) else a["href"]
            items += f'<a href="{href_v}"><time>{esc(small.get_text(strip=True) if small else "")}</time><b>{esc(a.get_text(strip=True))}</b></a>'
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
            for li in (_info_soup(parent) or BeautifulSoup("", "lxml")).select("#content ul li"):
                a = li.select_one("a[href]")
                if a and posixpath.basename(sb.to_site_path(d, a["href"].replace("&amp;", "&"))) == posixpath.basename(rel):
                    small = li.select_one("small")
                    date = small.get_text(strip=True) if small else ""
        body = (f'<div class="wrap"><ol class="breadcrumb">{crumbs}</ol><article class="article"><div class="ph"><h1>{esc(heading)}</h1></div>'
                f'{f"<p class=date>{esc(date)}</p>" if date else "<div style=height:20px></div>"}{inner}</article></div>')
    return page(data, rel, lang, f"{title} | {BRAND}", body, title, current=rel if rel in INFO_TITLES else "")


def render_404(data, lang):
    body = (f'<div class="wrap" style="padding:80px 0 120px;text-align:center"><div class="ph"><h1>找不到頁面</h1><p>這個頁面不存在或已被移除。</p></div>'
            f'<a class="btn" href="{sb.lang_variant("index.html", lang)}">回到首頁</a></div>')
    return page(data, "404.html", lang, f"找不到頁面 | {BRAND}", body, "")


# ----------------------------------------------------------------- finishing (translation, images, search) + writing
def finish(html_text, site_rel, lang, table):
    soup = BeautifulSoup(html_text, "lxml")
    d = rel_dir(site_rel)
    sb.apply_image_text(soup, d)
    if lang != "zh":
        sb.translate_soup(soup, lang, table)
    sb.use_optimized_images(soup, d)
    sb.add_search(soup, lang, site_rel)
    return str(soup)


def write_page(html_text, site_rel, lang, table):
    sb.write_text(sb.SITE / sb.lang_variant(site_rel, lang), finish(html_text, site_rel, lang, table))


def i18n_table(data):
    table = sb.load_i18n(data)
    for k, v in UI.items():
        table.setdefault(k, {}).update({kk: vv for kk, vv in v.items() if kk not in table.get(k, {})})
    return table


def build_all(data, visible):
    table = i18n_table(data)
    sb._PATTERN_CACHE.clear()
    assets = sb.SITE / "assets"
    assets.mkdir(exist_ok=True)
    (assets / "theme.css").write_text(CSS.strip() + "\n", encoding="utf-8")
    (assets / "theme.js").write_text(JS + "\n", encoding="utf-8")
    for lang in LANG_CODES:
        write_page(render_home(data, visible, lang), "index.html", lang, table)
        for c in data["categories"]:
            items = [p for p in visible if c["id"] in p.get("categories", [])]
            write_page(render_listing(data, sb.category_page(c["id"]), lang, c["name"], items, sub=CAT_BLURB.get(c["id"], ""), current=c["id"]),
                       sb.category_page(c["id"]), lang, table)
        write_page(render_listing(data, "search.html", lang, "全系列", visible, current="all", search=True), "search.html", lang, table)
        best = [p for p in visible if "bestseller" in p.get("sections", [])]
        write_page(render_listing(data, "bestsellers.html", lang, "暢銷商品", best, current="best"), "bestsellers.html", lang, table)
        for p in visible:
            write_page(render_product(data, visible, p, lang, sb.product_i18n(p)), sb.product_page(p), lang, table)
        for rel in sb.INFO_PAGES:
            out = render_info(data, rel, lang)
            if out:
                write_page(out, rel, lang, table)
        write_page(render_404(data, lang), "404.html", lang, table)
