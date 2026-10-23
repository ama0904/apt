# -*- coding: utf-8 -*-
"""apetto 小幫手: a chat helper that runs entirely in the browser (no AI service, no server).

At build time it reads the finished pages of each language and writes a small knowledge base,
assets/assistant/kb.<lang>.json: products (name, price, sizes, colour, size chart), categories,
the size charts, and text sections from guides, features, the shopping-flow page, the brand story,
news, plus optional hand-written answers from _data/assistant.json.
In the browser, assets/assistant.js understands the common questions (size from back length or breed,
which coat, colours, prices, shipping, delivery time, payment, how to buy, fitting room), keeps
context between turns, and falls back to searching the site text."""
import json
import re

from bs4 import BeautifulSoup

import site_builder as sb

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
        for f in custom.get("faq", []):
            a = f.get("a", {})
            ans = a.get(lang) or a.get("zh") if isinstance(a, dict) else a
            if ans and f.get("q"):
                kb["faq"].append({"q": f["q"], "a": ans, "u": L(f["link"]) if f.get("link") and not f["link"].startswith("http") else f.get("link", "")})
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
var SC=document.currentScript, BASE=(SC.getAttribute('src')||'').replace(/assets\/assistant\.js.*$/,''), LANG=SC.getAttribute('data-lang')||'zh', LOGO=SC.getAttribute('data-logo')||'';
var TX={
zh:{name:'apetto 小幫手',status:'線上 · 通常幾秒內回覆',ph:'輸入問題，例如：柴犬穿幾號？',open:'開啟小幫手',close:'關閉',reset:'重新開始',send:'送出',
 foot:'小幫手依照 apetto 網站資料自動回答',tip:'尺寸不確定嗎？告訴我背長或品種，我幫你挑 🐾',
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
 sizeWord:'號',cm:'公分'},
en:{name:'apetto Helper',status:'Online · usually replies in seconds',ph:'Ask me, e.g. what size for a Shiba?',open:'Open the helper',close:'Close',reset:'Start over',send:'Send',
 foot:'Answers come from the apetto website',tip:'Not sure about the size? Tell me the back length or breed 🐾',
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
 sizeWord:'',cm:'cm'},
ja:{name:'apetto アシスタント',status:'オンライン · すぐにお返事します',ph:'例：柴犬は何サイズ？',open:'アシスタントを開く',close:'閉じる',reset:'最初から',send:'送信',
 foot:'apetto サイトの情報をもとに自動で回答します',tip:'サイズに迷ったら、背丈か犬種を教えてください 🐾',
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
 sizeWord:'',cm:'cm'},
de:{name:'apetto Assistent',status:'Online · antwortet meist sofort',ph:'z. B. Welche Größe für einen Shiba?',open:'Assistent öffnen',close:'Schließen',reset:'Neu starten',send:'Senden',
 foot:'Antworten basieren auf der apetto Website',tip:'Unsicher bei der Größe? Nenn mir Rückenlänge oder Rasse 🐾',
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
 sizeAsk:/(?:^|[^a-z])(xs|s|m|l|xl|2xl|xxl|3xl)(?:號|号|size)?(?=$|[^a-z])/,
 compare:/(差在|差別|差異|不同|比較|difference|differ|compare|vs|違い|比べ|unterschied|vergleich)/,
 weather:/(天氣|氣溫|下雨嗎|會下雨|weather|forecast|天気|wetter)/,
 thisOne:/(這件|這款|這個|它|this one|this coat|\bit\b|これ|この|dieses?)/,
 big:/(大汪|大型|中型|中大型|大狗|大隻|big|large|medium|大型犬|中型犬|große?n?\b|mittel)/
};
var COLORS={gray:/(灰|gr[ae]y|グレー|grau)/,blue:/(藍|blue|ブルー|青|blau)/,orange:/(桔|橘|orange|オレンジ)/,green:/(綠|green|グリーン|緑|grün)/,pink:/(桃|粉|pink|ピンク|rosa|beere)/,yellow:/(黃|黄|yellow|lemon|neon|イエロー|レモン|gelb)/};
var BREEDS=[[/(吉娃娃|chihuahua|チワワ)/,22],[/(約克夏|yorkshire|yorkie|ヨーキー|ヨークシャー)/,24],[/(博美|pomeranian|ポメ|zwergspitz)/,25],[/(馬爾濟斯|maltese|マルチーズ|malteser)/,27],
 [/(貴賓|泰迪|poodle|プードル|pudel)/,29],[/(比熊|bichon|ビション)/,30],[/(西施|shih ?tzu|シーズー)/,31],[/(巴哥|pug|パグ|mops)/,30],[/(瑪爾|蝴蝶犬|papillon|パピヨン)/,27],
 [/(法鬥|法國鬥牛|french bulldog|frenchie|フレブル|フレンチ・?ブルドッグ|französische bulldogge)/,34],[/(雪納瑞|schnauzer|シュナウザー)/,35],[/(傑克羅素|jack russell|ジャックラッセル)/,33],
 [/(臘腸|dachshund|ダックス|dackel)/,38],[/(柯基|corgi|コーギー)/,40],[/(柴犬|柴柴|shiba|しばいぬ|柴)/,40],[/(米格魯|beagle|ビーグル)/,40],[/(喜樂蒂|sheltie|シェルティ)/,40],
 [/(鬥牛犬|英國鬥牛|bulldog|ブルドッグ|bulldogge)/,40],[/(邊境牧羊|邊牧|border collie|ボーダーコリー)/,50],[/(哈士奇|husky|ハスキー)/,55],[/(拉布拉多|labrador|ラブラドール)/,58],
 [/(黃金|golden|ゴールデン)/,60],[/(德國狼犬|german shepherd|シェパード|schäferhund)/,63],[/(杜賓|doberman|ドーベルマン)/,62]];
var CAT_WORDS={3:/(浴袍|浴巾|bathrobe|robe|hoodie|バスローブ|bademantel)/,4:/(牽繩|頸圈|項圈|胸背|leash|collar|harness|リード|首輪|leine|halsband)/,5:/(領巾|圍巾|bandana|scarf|バンダナ|halstuch)/,6:/(鞋|shoe|boot|靴|シューズ|schuh)/,7:/(墊|睡墊|床|pad|mat|bed|マット|ベッド|matte|decke)/};
function norm(s){return String(s||'').normalize('NFKC').toLowerCase().replace(/[“”"'`]/g,'').replace(/\s+/g,' ').trim();}
function pick(a){return Array.isArray(a)?a[Math.floor(Math.random()*a.length)]:a;}
function fmt(s,v){return String(s).replace(/\{(\w+)\}/g,function(m,k){return v&&v[k]!=null?v[k]:(KB&&KB.links[k]!=null?KB.links[k]:(KB&&typeof KB[k]==='string'?KB[k]:m));});}
function money(n){return Number(n).toLocaleString('en-US');}
// tokens for search: CJK bigrams + words
var STOP={'請問':1,'什麼':1,'怎麼':1,'可以':1,'一下':1,'我們':1,'你們':1,'有沒':1,'沒有':1,'是不':1,'不是':1,'如何':1,'狗狗':1,'毛孩':1,'我家':1,'家的':1,'的話':1,'the':1,'a':1,'is':1,'do':1,'you':1,'my':1,'to':1,'of':1,'for':1,'what':1,'how':1,'can':1,'and':1,'in':1,'it':1,'dog':1,'der':1,'die':1,'das':1,'ist':1,'und':1,'ich':1,'mein':1};
function toks(s){var out=[];norm(s).replace(/[぀-ヿ㐀-鿿]+|[a-z0-9äöüß]+/g,function(w){
 if(/^[a-z0-9äöüß]+$/.test(w)){if(w.length>1&&!STOP[w])out.push(w.length>4?w.replace(/(es|en|s|e)$/,''):w);}
 else if(w.length===1)out.push(w);else for(var i=0;i<w.length-1;i++){var b=w.substr(i,2);if(!STOP[b])out.push(b);}return w;});return out;}
// ---------------------------------------------------------------- knowledge base + search index
var KB=null,IDX=null,kbP=null;
function loadKB(){if(!kbP)kbP=fetch(BASE+'assets/assistant/kb.'+LANG+'.json',{cache:'force-cache'}).then(function(r){return r.json();}).then(function(j){KB=j;buildIdx();
 var pm=location.pathname.match(/product_id=(\d+)/)||decodeURIComponent(location.href).match(/product_id=(\d+)/);if(pm&&prodById(pm[1]))ST.prod=pm[1];  // on a product page, "this one" means that product
 return j;});return kbP;}
function buildIdx(){var docs=KB.docs.slice();KB.faq.forEach(function(f){docs.push({t:'',x:f.a,u:f.u,faq:f});});
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
var ST={prod:null,ser:null,warm:null,back:null,chest:null,want:null,breed:null};
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
function breedOf(q){var s=norm(q);for(var i=0;i<BREEDS.length;i++){var x=s.match(BREEDS[i][0]);if(x)return {name:/^[a-z]/.test(x[1])?x[1].replace(/(^|\s)[a-z]/g,function(c){return c.toUpperCase();}):x[1],cm:BREEDS[i][1]};}return null;}
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
 var ls=lines(),head=fmt(T.sizeHead,{back:back,chest:chest?fmt(T.chestPart,{chest:chest}):''}),rows=[],tail=[];
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
 var s=norm(q),m=measures(q),br=breedOf(q),pp=pickProducts(q),cat=null,k,mentionsProduct=pp.any;
 Object.keys(CAT_WORDS).forEach(function(id){if(CAT_WORDS[id].test(s))cat=+id;});
 // hand-written answers win when they match well
 for(var i=0;i<KB.faq.length;i++){var f=KB.faq[i];if(f.q.some(function(w){return w&&s.indexOf(norm(w))>=0;}))return A(f.a+(f.u?'\n['+T.more+']('+f.u+')':''),{chips:T.chipsAfter});}
 if(R.who.test(s))return A(T.who,{chips:T.chips0.slice(0,3)});
 if(R.contact.test(s)&&!R.store.test(s))return A(T.contact,{chips:T.chipsAfter});
 if(R.greet.test(s)&&s.length<14)return A(pick(T.greet),{chips:T.chips0});
 if(R.thanks.test(s)&&s.length<20)return A(pick(T.thanks),{chips:T.chipsAfter});
 if(R.bye.test(s)&&s.length<16)return A(pick(T.bye));
 // categories that are not on sale yet
 var soonCat=null;if(cat){var c=KB.cats.filter(function(x){return x.id===cat;})[0];if(c&&!c.cnt){if(R.sell.test(s)||s.length<=4)return A(fmt(T.soon,{cat:c.n}),{chips:T.chipsAfter});soonCat=c;}}
 if(R.store.test(s))return A(T.store,{chips:T.chipsAfter});
 if(R.about.test(s)){var ab=KB.docs.filter(function(d){return d.u===KB.links.about;});if(ab.length)return A(ab.slice(0,2).map(function(d){return '**'+d.t+'**\n'+snippet(d,d.t);}).join('\n')+'\n['+T.more+']('+KB.links.about+')',{chips:T.chipsAfter});}
 var sz=s.match(R.sizeAsk);if(sz&&(R.sell.test(s)||/(嗎|\?|？|有)/.test(s))&&!m.back){var want=sz[1].replace('xxl','2xl').toUpperCase(),has=lines().filter(function(l){return l.ps[0].sz.some(function(z){return z.s===want;});});
  var lsz=function(l){var seen={},o=[];l.ps.forEach(function(p){p.sz.forEach(function(z){if(!seen[z.s]){seen[z.s]=1;o.push(z);}});});return o;};
  has=lines().filter(function(l){return lsz(l).some(function(z){return z.s===want;});});
  var row=function(l){var zs=lsz(l),x=zs.filter(function(z){return z.x;});return '• '+l.line+'：'+zs.map(function(z){return z.s;}).join(' / ')+(x.length?fmt(T.priceX,{s:x.map(function(z){return z.s;}).join('/'),x:money(x[0].x)}):'');};
  return A((has.length?T.sizeHas:fmt(T.sizeNone,{s:want}))+'\n'+lines().map(row).join('\n').replace(/：/g,LANG==='zh'?'：':': '),{chips:[T.chips0[0]].concat(T.chipsSize.slice(0,1))});}
 if(R.measure.test(s))return A(T.measure,{chips:T.chips0.slice(0,1).concat(T.chipsSize.slice(2))});
 // size: numbers, breed, or a size question
 if(m.chest)ST.chest=m.chest;
 var wantsSize=R.size.test(s)||(ST.want==='back'&&!!m.back);
 if(m.back||(br&&(wantsSize||!mentionsProduct))){var back=m.back||br.cm,src=!m.back&&br?fmt(T.breed,{breed:br.name,cm:br.cm}):'';
  if(!m.chest&&(br&&(!ST.breed||ST.breed.name!==br.name)||(ST.back&&Math.abs(back-ST.back)>4)))ST.chest=null;
  ST.back=back;ST.breed=br||null;ST.want=null;
  var narrow=pp.any?{ser:pp.ser,warm:pp.warm}:(curLine()&&R.thisOne.test(s)?{lk:curLine()}:null);return sizeAnswer(back,m.chest||ST.chest,src,narrow);}
 if(m.kg&&!m.back){ST.want='back';return A(fmt(T.kg,{kg:m.kg,series:m.kg<=9?T.serSmall:T.serBig}),{chips:[T.chips0[0]]});}
 if(wantsSize&&!R.ship.test(s)){if(ST.back&&(pp.any||curLine()))return sizeAnswer(ST.back,ST.chest,'',pp.any?{ser:pp.ser,warm:pp.warm}:{lk:curLine()});var again=ST.want==='back';ST.want='back';return A(again?T.askBack2:T.askBack,{chips:T.chipsBreed});}
 if(R.weather.test(s))return A(T.weather,{chips:T.chips0.slice(0,2)});
 if(R.compare.test(s)&&(R.warm.test(s)||R.rain.test(s)||R.small.test(s)||R.big.test(s)))return A(T.compare,{cards:lines().map(function(l){return l.ps[0].id;}),chips:[T.chips0[0]].concat(T.chipsSize.slice(0,2))});
 if(R.ship.test(s))return A(T.ship,{chips:T.chipsShip});
 if(R.time.test(s))return A(T.time,{chips:[T.chips0[2]].concat(T.chipsShip.slice(1))});
 if(R.pay.test(s))return A(T.pay,{chips:T.chipsShip.slice(0,1).concat(T.chips0.slice(2,3))});
 if(R.ret.test(s))return A(T.ret,{chips:[T.chips0[0]]});
 if(R.buy.test(s))return A(T.buy,{chips:T.chipsShip});
 if(R.fit.test(s))return A(T.fit,{chips:T.chipsAfter.slice(0,2)});
 // product questions
 if(R.price.test(s)){var ps=pp.any?pp.ps:(curLine()?[prodById(ST.prod)]:ST.ser?KB.products.filter(function(p){return p.ser===ST.ser;}):null);
  if(ps&&ps.length){var seen={},out=[];ps.forEach(function(p){if(!seen[p.lk]){seen[p.lk]=1;out.push('• '+priceLine(p));}});ST.prod=ps[0].id;return A(out.length===1?out[0].slice(2):out.join('\n'),{cards:ps.slice(0,6).map(function(p){return p.id;}),chips:T.chipsSize});}
  return A(T.priceAll+'\n'+lines().map(function(l){return '• '+l.line+(LANG==='zh'?'：':': ')+'NT$'+money(l.ps[0].p);}).join('\n'),{chips:T.chipsSize.slice(0,1).concat(T.chips0.slice(0,1))});}
 if(pp.col&&!R.reco.test(s)&&!R.price.test(s)){var cl=pp.ps.filter(function(p){return p.ck===pp.col;});if(cl.length){ST.prod=cl[0].id;return A(T.colorHit,{cards:cl.map(function(p){return p.id;}),chips:T.chipsSize.slice(1).concat(T.chips0.slice(0,1))});}}
 if(R.colors.test(s)&&!pp.col){var ls=lines().filter(function(l){return (!pp.ser||l.ser===pp.ser)&&(pp.warm==null||l.warm===pp.warm)&&(!curLine()||pp.any||l.lk===curLine());});
  if(!ls.length)ls=lines();
  return A((ls.length>1?T.colorsAll+'\n':'')+ls.map(function(l){return (ls.length>1?'• ':'')+fmt(T.colors,{line:l.line,list:l.ps.map(function(p){return p.c;}).join(LANG==='zh'||LANG==='ja'?'、':', ')});}).join('\n'),{cards:[].concat.apply([],ls.map(function(l){return l.ps.map(function(p){return p.id;});})).slice(0,8),chips:T.chipsSize.slice(1).concat(T.chips0.slice(0,1))});}
 if(R.care.test(s)&&!mentionsProduct){var hit=search(q).filter(function(h){return h.d.u===KB.links.care;})[0];if(hit)return docAnswer(hit.d,q);}
 if(R.reco.test(s)||mentionsProduct||R.rain.test(s)||R.warm.test(s)){
  if(!pp.any&&!ST.back){if(R.reco.test(s))return A(T.recoAsk,{chips:LANG==='zh'?['小型犬，下雨天穿','中大型犬，冬天保暖','先幫我挑尺寸']:T.chips0.slice(0,2)});}
  var list=pp.ps;if(!pp.ser&&ST.ser)list=list.filter(function(p){return p.ser===ST.ser;});if(!list.length)list=pp.ps;
  if(list.length&&list.length<KB.products.length){ST.prod=list[0].id;if(pp.ser)ST.ser=pp.ser;
   var intro=pp.warm===true?T.recoWarm:pp.warm===false?T.recoRain:pick(T.reco),extra=ST.back?'\n'+sizeAnswer(ST.back,ST.chest,'',{ser:list[0].ser,warm:pp.warm}).text.split('\n').slice(1,-1).join('\n'):'';
   return A(intro+extra,{cards:list.slice(0,6).map(function(p){return p.id;}),chips:ST.back?T.chipsSize:[T.chips0[0]].concat(T.chipsSize.slice(1,2))});}
 }
 // free text: search the site
 var hits=search(q);if(hits.length&&hits[0].s>2.2&&hits[0].cov>=.25)return docAnswer(hits[0].d,expand(q));
 if(soonCat)return A(fmt(T.soon,{cat:soonCat.n}),{chips:T.chipsAfter});
 return A(T.unknown,{chips:T.chips0.slice(0,4)});}
function docAnswer(d,q){if(d.faq)return A(d.faq.a+(d.faq.u?'\n['+T.more+']('+d.faq.u+')':''),{chips:T.chipsAfter});
 if(d.pid)ST.prod=d.pid;
 return A(fmt(pick(T.found),{t:d.t})+'\n'+snippet(d,q)+'\n['+T.more+']('+d.u+')',{cards:d.pid?[d.pid]:null,chips:T.chipsAfter});}
// ---------------------------------------------------------------- rendering (all text is escaped; links only to this site or known stores)
function esc(s){return String(s).replace(/[&<>"]/g,function(c){return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c];});}
function safeUrl(u){if(/^https:\/\/(www\.instagram\.com|www\.pinkoi\.com|www\.apetto\.com\.tw)\//.test(u))return u;if(/^[a-z0-9][\w\-\/.&=?#%]*$/i.test(u)&&!/^[a-z]+:/i.test(u))return BASE+u;return '';}
function md(t){var h=esc(t).replace(/\*\*(.+?)\*\*/g,'<strong>$1</strong>').replace(/\[([^\]]+)\]\(([^)\s]+)\)/g,function(m,a,u){var s=safeUrl(u.replace(/&amp;/g,'&'));return s?'<a href="'+esc(s)+'"'+(/^https?:/.test(s)?' target="_blank" rel="noopener"':'')+'>'+a+'</a>':a;});
 var out=[],ul=[];h.split('\n').forEach(function(l){if(/^• /.test(l))ul.push('<li>'+l.slice(2)+'</li>');else{if(ul.length){out.push('<ul>'+ul.join('')+'</ul>');ul=[];}if(l.trim())out.push('<p>'+l+'</p>');}});if(ul.length)out.push('<ul>'+ul.join('')+'</ul>');return out.join('');}
var root,log,chipsEl,ta,sendBtn,panel,fab,busy=false,HIST=[];
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
function typing(ms,cb){var t=document.createElement('div');t.className='ai-typing';t.innerHTML='<i></i><i></i><i></i>';log.appendChild(t);scroll();setTimeout(function(){t.remove();cb();},ms);}
function ask(q){q=String(q||'').trim();if(!q||busy)return;busy=true;sendBtn.disabled=true;ta.value='';grow();setChips([]);addMe(q);HIST.push({me:q});
 loadKB().then(function(){var a;try{a=answer(q);}catch(e){a=A(T.unknown,{chips:T.chips0});}
  typing(Math.min(1400,450+a.text.length*6+Math.random()*250),function(){addBot(a,false,function(){HIST.push({bot:a});save();setChips(a.chips);busy=false;sendBtn.disabled=!ta.value.trim();ta.focus({preventScroll:true});});});
 }).catch(function(){busy=false;sendBtn.disabled=false;});}
function grow(){ta.style.height='auto';var h=ta.scrollHeight+2;ta.style.height=Math.min(110,h)+'px';ta.style.overflowY=h>110?'auto':'hidden';}
function openPanel(){if(!root)build();var tip=document.querySelector('.ai-tip');if(tip)tip.remove();panel.hidden=false;fab.style.display='none';fab.setAttribute('aria-expanded','true');
 try{sessionStorage.setItem('apetto_ai_tip','1');}catch(e){}
 loadKB();if(matchMedia('(max-width:980px)').matches)document.documentElement.style.overflow='hidden';setTimeout(function(){ta.focus({preventScroll:true});},60);scroll();}
function closePanel(){panel.hidden=true;fab.style.display='';fab.setAttribute('aria-expanded','false');document.documentElement.style.overflow='';fab.focus({preventScroll:true});}
function reset(){HIST=[];for(var k in ST)ST[k]=null;save();log.innerHTML='';addBot(A(pick(T.hello)),true);setChips(T.chips0);}
function build(){root=document.createElement('div');
 root.innerHTML='<div class="ai-panel" role="dialog" aria-label="'+esc(T.name)+'" hidden><div class="ai-hd"><div class="ai-av">'+(LOGO?'<img src="'+esc(LOGO)+'" alt="">':'')+'</div><div><b>'+esc(T.name)+'</b><span><i></i>'+esc(T.status)+'</span></div>'
  +'<button type="button" class="ai-rs" title="'+esc(T.reset)+'" aria-label="'+esc(T.reset)+'"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M3 12a9 9 0 1 0 3-6.7L3 8"/><path d="M3 3v5h5"/></svg></button>'
  +'<button type="button" class="ai-x" aria-label="'+esc(T.close)+'"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M6 6l12 12M18 6 6 18"/></svg></button></div>'
  +'<div class="ai-log" aria-live="polite"></div><div class="ai-chips"></div>'
  +'<form class="ai-in"><textarea rows="1" placeholder="'+esc(T.ph)+'" aria-label="'+esc(T.ph)+'"></textarea><button type="submit" aria-label="'+esc(T.send)+'" disabled><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M5 12h14M13 6l6 6-6 6"/></svg></button></form>'
  +'<div class="ai-foot">'+esc(T.foot)+'</div></div>';
 document.body.appendChild(root);panel=root.querySelector('.ai-panel');log=root.querySelector('.ai-log');chipsEl=root.querySelector('.ai-chips');ta=root.querySelector('textarea');sendBtn=root.querySelector('.ai-in button');
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
