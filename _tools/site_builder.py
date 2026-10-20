# -*- coding: utf-8 -*-
"""
Product data + static site builder for the mirrored apetto site.

  python site_builder.py extract   # one-time: pull products out of the mirror into _data/products.json
  python site_builder.py build     # regenerate index / category / product / search / bestseller pages

Data lives in  <site>/_data/products.json
Templates in   <site>/_templates/   (pristine copies of the mirrored pages, created by `extract`)
Uploads in     <site>/_data/uploads/
"""
import copy
import json
import posixpath
import re
import shutil
import sys
from pathlib import Path

from bs4 import BeautifulSoup, NavigableString

HERE = Path(__file__).resolve().parent
SITE = Path(sys.argv[sys.argv.index("--site") + 1]) if "--site" in sys.argv else HERE.parent / "www.apetto.com.tw"
DATA_DIR = SITE / "_data"
DATA_FILE = DATA_DIR / "products.json"
TPL = SITE / "_templates"
UPLOADS = DATA_DIR / "uploads"

TITLE_SUFFIX = " | apetto | 高機能寵物時裝：專業防水防風、專為毛孩設計的機能衣服"
SECTIONS = [("all", "全系列"), ("bestseller", "暢銷商品"), ("latest", "推薦商品")]
ONLINE = "https://www.apetto.com.tw/"


# ----------------------------------------------------------------- helpers
def soup_of(path: Path) -> BeautifulSoup:
    return BeautifulSoup(path.read_text(encoding="utf-8"), "lxml")


def write_text(path: Path, text: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def href(page_dir: str, site_path: str) -> str:
    """Relative link from a page living in `page_dir` ('' = site root) to a site-root-relative path."""
    if not site_path or site_path.startswith(("http:", "https:", "//", "data:")):
        return site_path
    return posixpath.relpath(site_path, page_dir or ".")


def to_site_path(page_dir: str, rel: str) -> str:
    """Turn a link found inside a page in `page_dir` into a site-root-relative path."""
    if not rel or rel.startswith(("http:", "https:", "//", "data:")):
        return rel
    return posixpath.normpath(posixpath.join(page_dir, rel))


def fmt_price(n) -> str:
    return "$" + f"{int(n):,}"


def product_page(p) -> str:
    return f"product/product&product_id={p['id']}.html"


def category_page(cid) -> str:
    return f"product/category&path={cid}.html"


def set_first_text(tag, text):
    for c in tag.contents:
        if isinstance(c, NavigableString) and c.strip():
            c.replace_with(NavigableString(text))
            return
    tag.insert(0, NavigableString(text))


def set_inner_html(tag, html_str):
    tag.clear()
    frag = BeautifulSoup(html_str or "", "html.parser")
    for c in list(frag.contents):
        tag.append(c)


def inner_html(tag) -> str:
    return "".join(str(c) for c in tag.contents) if tag else ""


def set_meta(soup, content, name=None, prop=None):
    sel = f'meta[name="{name}"]' if name else f'meta[property="{prop}"]'
    for m in soup.select(sel):
        m["content"] = content


def text_to_html(text: str) -> str:
    """Plain text from the admin form -> paragraphs; already-HTML text is kept."""
    text = (text or "").strip()
    if not text:
        return ""
    if "<" in text and ">" in text:
        return text
    from html import escape
    return "\n".join(f"<p>{escape(line.strip())}</p>" for line in text.splitlines() if line.strip())


def parse_options(text: str):
    """'尺寸: S, M, L' per line -> [{'name':..., 'values':[...]}]"""
    out = []
    for line in (text or "").splitlines():
        if ":" in line or "：" in line:
            name, vals = re.split(r"[:：]", line, 1)
            values = [v.strip() for v in re.split(r"[,，、]", vals) if v.strip()]
            if name.strip() and values:
                out.append({"name": name.strip(), "values": values})
    return out


def options_to_text(options):
    return "\n".join(f"{o['name']}: {', '.join(o['values'])}" for o in options or [])


# ----------------------------------------------------------------- data
def load_data():
    return json.loads(DATA_FILE.read_text(encoding="utf-8"))


def save_data(data):
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    DATA_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")


def next_id(data):
    return max([p["id"] for p in data["products"]] + [16]) + 1


# ----------------------------------------------------------------- images
def save_images(fileobj, pid, slot):
    """Store an uploaded image as full / 627x627 / 120x120 jpgs. Returns site-root-relative paths."""
    from PIL import Image, ImageOps
    UPLOADS.mkdir(parents=True, exist_ok=True)
    im = Image.open(fileobj)
    im = ImageOps.exif_transpose(im)
    if im.mode in ("RGBA", "LA", "P"):
        im = im.convert("RGBA")
        bg = Image.new("RGB", im.size, (255, 255, 255))
        bg.paste(im, mask=im.split()[-1])
        im = bg
    else:
        im = im.convert("RGB")
    base = f"p{pid}_{slot}"
    full = im.copy()
    full.thumbnail((1200, 1200))
    full.save(UPLOADS / f"{base}.jpg", quality=88)
    ImageOps.fit(im, (627, 627)).save(UPLOADS / f"{base}-627.jpg", quality=88)
    ImageOps.fit(im, (120, 120)).save(UPLOADS / f"{base}-120.jpg", quality=85)
    rel = f"_data/uploads/{base}"
    return {"full": rel + ".jpg", "thumb": rel + "-627.jpg", "small": rel + "-120.jpg"}


def delete_uploads(pid):
    if UPLOADS.exists():
        for f in UPLOADS.glob(f"p{pid}_*"):
            f.unlink()


# ----------------------------------------------------------------- extract (one time)
def ensure_templates():
    if TPL.exists():
        return
    TPL.mkdir(parents=True)
    pairs = {
        "index.html": "index.html",
        "product/category&path=1.html": "category.html",
        "product/product&product_id=7.html": "product.html",
        "bestsellers.html": "bestsellers.html",
        "search.html": "search.html",
    }
    for src, dst in pairs.items():
        shutil.copyfile(SITE / src, TPL / dst)


def extract_initial():
    ensure_templates()
    manifest = json.loads((SITE / "_mirror_manifest.json").read_text(encoding="utf-8"))
    asset_local = {u: p for u, p in manifest["assets"].items()}

    def localize(url):
        if not url:
            return url
        u = url if not url.startswith("//") else "https:" + url
        return asset_local.get(u, url)

    # categories: from the three category pages
    categories = []
    for f in sorted(SITE.glob("product/category&path=*.html")):
        cid = int(re.search(r"path=(\d+)", f.name).group(1))
        sp = soup_of(f)
        name = sp.title.get_text(strip=True).split(" | ")[0]
        ids = [int(s["data-productid"]) for s in sp.select(".product-grid select[data-productid]")]
        categories.append({"id": cid, "name": name, "_ids": ids})
    categories.sort(key=lambda c: c["id"])

    # home sections
    home = soup_of(SITE / "index.html")
    sections = {}
    for key, sel in (("all", ".any-products"), ("bestseller", "#bestseller-products"), ("latest", "#latest-products")):
        sec = home.select_one(sel)
        sections[key] = [int(x) for x in re.findall(r"product_id=(\d+)", " ".join(a["href"] for a in sec.select("a[href]")))]

    # global order + summaries + card thumbs from the search page (lists everything)
    search = soup_of(SITE / "search.html")
    order, summary, thumb = [], {}, {}
    for box in search.select(".product-grid .grid-box"):
        sel = box.select_one("select[data-productid]")
        if not sel:
            continue
        pid = int(sel["data-productid"])
        order.append(pid)
        d = box.select_one("span[itemprop=description]")
        summary[pid] = d.get_text(" ", strip=True) if d else ""
        img = box.select_one(".image img")
        thumb[pid] = to_site_path("", img.get("src") or img.get("data-src"))

    products = []
    for f in SITE.glob("product/product&product_id=*.html"):
        pid = int(re.search(r"product_id=(\d+)", f.name).group(1))
        sp = soup_of(f)
        h1 = sp.select_one("h1.product-heading-title")
        name = next((c.strip() for c in h1.contents if isinstance(c, NavigableString) and c.strip()), "")
        price_el = sp.select_one(".product-sell-price")
        price = int(re.sub(r"\D", "", price_el.get("data-content") or price_el.get_text())) if price_el else 0
        feature = inner_html(sp.select_one(".product-feature-content")).strip()
        tab = sp.select_one("#tab-description")
        if tab:
            spin = tab.select_one("#defer-load-spin")
            if spin:
                spin.decompose()
        description = inner_html(tab).strip()
        main = sp.select_one("#main-defer-image")
        full = to_site_path("product", main["src"]) if main else ""
        lis = sp.select("#image-additional li")
        small = to_site_path("product", lis[0].select_one("img")["data-src"]) if lis else full
        gallery = []
        for li in lis[1:]:
            a, im = li.select_one("a"), li.select_one("img")
            gfull = localize(a.get("data-hd-image") or a.get("href"))
            gallery.append({"full": to_site_path("product", gfull), "small": to_site_path("product", im.get("data-src") or im.get("src"))})
        options = []
        for g in sp.select("#options .control-group"):
            vals = [re.sub(r"\s+", " ", lb.get_text(" ", strip=True)) for lb in g.select("label.checkbox, label.radio")]
            vals += [o.get_text(strip=True) for o in g.select("option") if o.get("value")]
            if g.get("data-option-name") and vals:
                options.append({"name": g["data-option-name"], "values": vals})
        products.append({
            "id": pid, "name": name, "price": price,
            "categories": [c["id"] for c in categories if pid in c["_ids"]],
            "sections": [k for k, ids in sections.items() if pid in ids],
            "summary": summary.get(pid, ""),
            "feature_html": feature, "description_html": description,
            "image": {"full": full, "thumb": thumb.get(pid, full), "small": small},
            "gallery": gallery, "options": options,
            "visible": True, "source": "original",
        })
    rank = {pid: i for i, pid in enumerate(order)}
    products.sort(key=lambda p: rank.get(p["id"], 999))
    for c in categories:
        c.pop("_ids", None)
    data = {"categories": categories, "sections": [{"key": k, "name": n} for k, n in SECTIONS], "products": products}
    save_data(data)
    return data


# ----------------------------------------------------------------- rendering
def fill_home_card(box, p, page_dir=""):
    pid = str(p["id"])
    for k in ("data-product-id", "data-producttlid"):
        if box.has_attr(k):
            box[k] = pid
    url = href(page_dir, product_page(p))
    for a in box.select("a"):
        a["href"] = url
    img = box.select_one("img")
    if img:
        img["alt"] = p["name"]
        thumb = href(page_dir, p["image"]["thumb"])
        if img.has_attr("data-src"):
            img["data-src"] = thumb
        else:
            img["src"] = thumb
    name = box.select_one(".name")
    if name:
        span = name.select_one("span[itemprop=name]")
        (span if span else name.select_one("a")).string = p["name"]
    price = box.select_one(".price")
    if price:
        if price.has_attr("data-price"):
            price["data-price"] = str(p["price"])
        lab = price.select_one(".price-label")
        (lab if lab else price).string = fmt_price(p["price"])


def fill_list_card(box, p, page_dir="product"):
    pid = str(p["id"])
    box["data-producttlid"] = pid
    url = href(page_dir, product_page(p))
    for a in box.select(".image a, .name a"):
        a["href"] = url
        if a.has_attr("title"):
            a["title"] = p["name"]
    img = box.select_one(".image img")
    if img:
        img["src"] = href(page_dir, p["image"]["thumb"])
        img["alt"] = img["title"] = p["name"]
        if img.has_attr("data-src"):
            img["data-src"] = img["src"]
    span = box.select_one(".name span[itemprop=name]")
    if span:
        span.string = p["name"]
    for el in box.select("[onclick]"):
        el["onclick"] = re.sub(r"'\d+'", f"'{pid}'", el["onclick"], count=1)
    d = box.select_one("span[itemprop=description]")
    if d:
        d.string = p.get("summary", "")
    pr = box.select_one(".price")
    if pr and pr.has_attr("data-price"):
        pr["data-price"] = str(p["price"])
    labs = box.select(".price-label")
    if labs:
        for s in labs:
            s.string = fmt_price(p["price"])
    elif pr:
        pr.string = fmt_price(p["price"])
    for sel in box.select("select[data-productid]"):
        sel["data-productid"] = pid


def rebuild_grid(container, items, fill, page_dir):
    tpl = container.select_one(".grid-box") or container.select_one("li")
    if tpl is None:
        return
    tpl = copy.copy(tpl)
    container.clear()
    for p in items:
        b = copy.copy(tpl)
        fill(b, p, page_dir)
        container.append(b)
        container.append("\n")


def set_pagination(soup, n):
    for r in soup.select(".pagination .results"):
        r.string = f"顯示第 1 至 {n} 個商品，共有 {n} 個商品 (分 1 頁顯示)" if n else "目前沒有商品"


def fix_legacy_links(html_str):
    return re.sub(r"product&(amp;)?path=\d+&(amp;)?product_id=", lambda m: f"product&{m.group(1) or ''}product_id=", html_str)


# ----------------------------------------------------------------- page builders
def build_index(data, visible):
    soup = soup_of(TPL / "index.html")
    targets = {
        "all": (".any-products", ".any-products .box-content .product-box"),
        "bestseller": ("#bestseller-products", "#bestseller-products .box-content .product-box"),
        "latest": ("#latest-products", "#latest-products ul.slides"),
    }
    for key, (sec_sel, cont_sel) in targets.items():
        sec, cont = soup.select_one(sec_sel), soup.select_one(cont_sel)
        if cont is None:
            continue
        items = [p for p in visible if key in p.get("sections", [])]
        rebuild_grid(cont, items, fill_home_card, "")
        if sec is not None:
            if items:
                if sec.has_attr("style"):
                    sec["style"] = re.sub(r"display\s*:\s*none;?", "", sec["style"])
            else:
                sec["style"] = (sec.get("style") or "") + ";display:none;"
    write_text(SITE / "index.html", fix_legacy_links(str(soup)))


def build_category(cat, items):
    soup = soup_of(TPL / "category.html")
    soup.title.string = cat["name"] + TITLE_SUFFIX
    set_meta(soup, cat["name"] + TITLE_SUFFIX, prop="og:title")
    canon = f"category&path={cat['id']}.html"
    for l in soup.select('link[rel="canonical"]'):
        l["href"] = canon
    crumbs = soup.select("ol.breadcrumb li")
    if crumbs:
        a = crumbs[-1].select_one("a")
        if a:
            a["href"] = canon
            sp = a.select_one("span")
            (sp if sp else a).string = cat["name"]
    for grid in soup.select(".product-grid"):
        rebuild_grid(grid, items, fill_list_card, "product")
    set_pagination(soup, len(items))
    write_text(SITE / category_page(cat["id"]), fix_legacy_links(str(soup)))


def build_listing(tpl_name, out_names, items):
    soup = soup_of(TPL / tpl_name)
    for grid in soup.select(".product-grid"):
        rebuild_grid(grid, items, fill_list_card, "")
    set_pagination(soup, len(items))
    html_str = fix_legacy_links(str(soup))
    for n in out_names:
        write_text(SITE / n, html_str)


def _fill_gallery_li(li, full, small, name, page_dir="product"):
    a, im = li.select_one("a"), li.select_one("img")
    f, s = href(page_dir, full), href(page_dir, small)
    for k in ("data-hd-image", "data-image", "data-zoom-image", "href"):
        if a.has_attr(k):
            a[k] = f
    a["title"] = name
    if im.has_attr("data-src"):
        im["data-src"] = s
    else:
        im["src"] = s
    im["alt"] = im["title"] = name


def build_product(p, data):
    soup = soup_of(TPL / "product.html")
    pid, name, page_dir = str(p["id"]), p["name"], "product"
    cat_names = [c["name"] for c in data["categories"] if c["id"] in p.get("categories", [])]
    desc_text = p.get("summary") or name
    tpl_pid = soup.select_one("#product_id")["value"]
    online_url = f"{ONLINE}product/product&product_id={pid}"
    full = href(page_dir, p["image"]["full"])
    small = href(page_dir, p["image"]["small"])

    soup.title.string = name + TITLE_SUFFIX
    set_meta(soup, desc_text, name="description")
    set_meta(soup, desc_text, prop="og:description")
    set_meta(soup, name + TITLE_SUFFIX, prop="og:title")
    set_meta(soup, online_url, prop="og:url")
    set_meta(soup, full, prop="og:image")
    set_meta(soup, full, prop="og:image:url")
    canon = f"product&product_id={pid}.html"
    for l in soup.select('link[rel="canonical"]'):
        l["href"] = canon
    crumbs = soup.select("ol.breadcrumb li")
    if crumbs:
        a = crumbs[-1].select_one("a")
        if a:
            a["href"] = canon
            sp = a.select_one("span")
            (sp if sp else a).string = name

    h1 = soup.select_one("h1.product-heading-title")
    if h1:
        qr = h1.select_one("a.screenshot")
        if qr:
            qr.decompose()
        set_first_text(h1, name)
    feat = soup.select_one(".product-feature-content")
    if feat:
        set_inner_html(feat, p.get("feature_html", ""))
    sp = soup.select_one(".product-sell-price")
    if sp:
        sp.string = fmt_price(p["price"])
        sp["data-content"] = str(p["price"])

    main = soup.select_one("#main-defer-image")
    if main:
        main["src"] = full
        main["data-rjs"] = full
        main["alt"] = name
    z = soup.select_one("#zoom1")
    if z:
        for k in ("data-src", "data-hd-image", "data-rjs", "data-zoom-image"):
            z[k] = full
        z["alt"] = name
    fb = soup.select_one("a.fancybox-product")
    if fb:
        fb["href"] = full
        fb["title"] = name
    ul = soup.select_one("#image-additional")
    if ul:
        lis = ul.select("li")
        li_main = copy.copy(lis[0])
        li_other = copy.copy(lis[1] if len(lis) > 1 else lis[0])
        if len(lis) == 1:
            li_other.select_one("a")["class"] = ["elevatezoom-gallery"]
        ul.clear()
        li = copy.copy(li_main)
        _fill_gallery_li(li, p["image"]["full"], p["image"]["small"], name)
        ul.append(li)
        for g in p.get("gallery", []):
            li = copy.copy(li_other)
            _fill_gallery_li(li, g["full"], g.get("small") or g["full"], name)
            ul.append(li)

    tab = soup.select_one("#tab-description")
    if tab:
        spin = tab.select_one("#defer-load-spin")
        spin = copy.copy(spin) if spin else None
        set_inner_html(tab, p.get("description_html", ""))
        if spin:
            tab.insert(0, spin)

    opts = soup.select_one("#options")
    if opts:
        groups = opts.select(".control-group")
        tpl_group = copy.copy(groups[0]) if groups else None
        for g in groups:
            g.decompose()
        if tpl_group is not None and p.get("options"):
            tpl_label = tpl_group.select_one("label.checkbox")
            tpl_label = copy.copy(tpl_label) if tpl_label else None
            for i, opt in enumerate(p["options"]):
                oid = 100 + i
                g = copy.copy(tpl_group)
                g["id"] = f"option-{oid}"
                g["data-option-id"] = str(oid)
                g["data-option-name"] = opt["name"]
                b = g.select_one(".control-label b")
                if b:
                    set_first_text(b, opt["name"] + " ")
                for lb in g.select("label.checkbox, label.radio"):
                    lb.decompose()
                for j, val in enumerate(opt["values"]):
                    vid = oid * 100 + j
                    if tpl_label is None:
                        continue
                    lb = copy.copy(tpl_label)
                    lb["for"] = f"option-value-{vid}"
                    lb["id"] = f"label-option-value-{vid}"
                    inp = lb.select_one("input")
                    inp["id"] = f"option-value-{vid}"
                    inp["name"] = f"option[{oid}][]"
                    inp["value"] = str(vid)
                    for c in list(lb.contents):
                        if isinstance(c, NavigableString):
                            c.extract()
                    lb.append(NavigableString(" " + val))
                    g.append(lb)
                opts.append(g)

    inp = soup.select_one("#product_id")
    if inp:
        inp["value"] = pid

    for sc in soup.select('script[type="application/ld+json"]'):
        try:
            obj = json.loads(sc.string or "")
        except Exception:
            continue
        t = obj.get("@type")
        if t == "Product":
            obj["productID"] = pid
            obj["name"] = name
            obj["description"] = desc_text
            obj["image"] = [p["image"]["full"]] + [g["full"] for g in p.get("gallery", [])]
            offers = obj.get("offers")
            for o in (offers if isinstance(offers, list) else [offers] if offers else []):
                if isinstance(o, dict):
                    o["price"] = str(p["price"])
                    if "url" in o:
                        o["url"] = online_url
            if "url" in obj:
                obj["url"] = online_url
        elif t == "BreadcrumbList":
            items = obj.get("itemListElement") or []
            if items:
                items[-1]["name"] = name
                items[-1]["item"] = online_url
        elif t == "WebPage":
            obj["name"] = name
            obj["url"] = online_url
        else:
            continue
        sc.string = json.dumps(obj, ensure_ascii=False, indent=1)

    out = str(soup)
    js_name = name.replace("\\", "\\\\").replace("'", "\\'")
    js_cat = (cat_names[0] if cat_names else "").replace("'", "\\'")
    out = re.sub(r"global_product_id = '\d+'", f"global_product_id = '{pid}'", out)
    out = re.sub(r"'(id|item_id)': '\d+'", lambda m: f"'{m.group(1)}': '{pid}'", out)
    out = re.sub(r"'(name|item_name)': '[^']*'", lambda m: f"'{m.group(1)}': '{js_name}'", out)
    out = re.sub(r"'price': '\d+'", f"'price': '{p['price']}'", out)
    out = re.sub(r"'(category|item_category)': '[^']*'", lambda m: f"'{m.group(1)}': '{js_cat}'", out)
    out = re.sub(rf"product_id={tpl_pid}\b", f"product_id={pid}", out)
    out = re.sub(rf"product_id%3D{tpl_pid}\b", f"product_id%3D{pid}", out)
    write_text(SITE / product_page(p), fix_legacy_links(out))


def build_sitemap(visible, data):
    urls = [ONLINE] + [f"{ONLINE}product/product&product_id={p['id']}" for p in visible]
    urls += [f"{ONLINE}product/category&path={c['id']}" for c in data["categories"]]
    body = "\n".join(f"<url><loc>{u.replace('&', '&amp;')}</loc></url>" for u in urls)
    write_text(SITE / "sitemap.xml", '<?xml version="1.0" encoding="UTF-8"?>\n'
               '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n' + body + "\n</urlset>\n")


def build_all(data=None):
    data = data or load_data()
    visible = [p for p in data["products"] if p.get("visible", True)]
    build_index(data, visible)
    for cat in data["categories"]:
        build_category(cat, [p for p in visible if cat["id"] in p.get("categories", [])])
    for p in visible:
        build_product(p, data)
    build_listing("search.html", ["search.html", "search@filter_name=&filter_tag=&filter_description=.html"], visible)
    build_listing("bestsellers.html", ["bestsellers.html"], [p for p in visible if "bestseller" in p.get("sections", [])])
    build_sitemap(visible, data)
    # remove pages of hidden/deleted products and the legacy path= duplicates
    keep = {product_page(p) for p in visible}
    for f in SITE.glob("product/product&*product_id=*.html"):
        rel = f.relative_to(SITE).as_posix()
        if rel not in keep:
            f.unlink()
    # legacy links in pages we do not regenerate
    for f in list(SITE.glob("*.html")) + list(SITE.glob("information/*.html")) + list(SITE.glob("pages/*.html")) + list(SITE.glob("account/**/*.html")):
        s = f.read_text(encoding="utf-8")
        s2 = fix_legacy_links(s)
        if s2 != s:
            f.write_text(s2, encoding="utf-8")
    return {"pages": len(visible), "categories": len(data["categories"])}


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    cmd = next((a for a in sys.argv[1:] if not a.startswith("--") and not a.startswith("C:") and not a.startswith("/")), "build")
    if cmd == "extract":
        d = extract_initial()
        print(f"extracted {len(d['products'])} products, {len(d['categories'])} categories -> {DATA_FILE}")
    elif cmd == "build":
        print("built", build_all())
    else:
        print(__doc__)
