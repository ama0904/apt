# -*- coding: utf-8 -*-
"""Self-test: add a fake admin product (with generated images), build, check output, then restore."""
import json, re, shutil, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import site_builder as sb
from bs4 import BeautifulSoup
from PIL import Image

backup = sb.DATA_FILE.read_text(encoding="utf-8")
try:
    data = sb.load_data()
    sb.UPLOADS.mkdir(parents=True, exist_ok=True)
    pid = sb.next_id(data)
    Image.new("RGB", (900, 600), (200, 80, 80)).save(sb.UPLOADS / "_selftest.jpg")
    with open(sb.UPLOADS / "_selftest.jpg", "rb") as f:
        img = sb.save_images(f, pid, "main")
    with open(sb.UPLOADS / "_selftest.jpg", "rb") as f:
        g1 = sb.save_images(f, pid, "g1")
    hidden_id = data["products"][0]["id"]
    data["products"][0]["visible"] = False
    data["products"].append({
        "id": pid, "name": "測試斗篷 Test's \"Cape\"", "price": 1234, "categories": [1, 3], "sections": ["all", "latest"],
        "summary": "測試用商品", "feature_html": sb.text_to_html("第一行\n第二行 <b>粗體</b>?"),
        "description_html": sb.text_to_html("介紹一\n介紹二"), "image": img, "gallery": [{"full": g1["full"], "small": g1["small"]}],
        "options": sb.parse_options("尺寸: S, M, L\n顏色：紅, 藍"), "visible": True, "source": "admin",
        "i18n": {"en": {"name": "Test Cape EN", "summary": "Test summary EN",
                        "description_html": "<p>English override description</p>"},
                 "ja": {"feature_html": "<p>日本語の特徴テスト</p>"}},
    })
    sb.save_data(data)
    print("build:", sb.build_all(data))
    S = sb.SITE
    pp = BeautifulSoup((S / f"product/product&product_id={pid}.html").read_text(encoding="utf-8"), "lxml")
    out = str(pp)
    checks = {
        "title": pp.title.string.startswith("測試斗篷"),
        "h1": pp.select_one("h1").get_text(strip=True) == "測試斗篷 Test's \"Cape\"",
        "price": pp.select_one(".product-sell-price").get_text(strip=True) == "NT$1,234",
        "main img": pp.select_one("#main-defer-image")["src"] == f"../_data/uploads/p{pid}_main.jpg",
        "gallery li": len(pp.select("#image-additional li")) == 2,
        "option groups": len(pp.select("#options .control-group")) == 2,
        "option labels": len(pp.select("#options label.checkbox")) == 5,
        "pid input": pp.select_one("#product_id")["value"] == str(pid),
        "no template id left": not re.search(r"product_id=7\b", out),
        "ldjson": f'"productID": "{pid}"' in out,
        "feature html kept": "<b>粗體</b>" in out,
        "plain text wrapped": "<p>介紹一</p>" in out,
    }
    hp = BeautifulSoup((S / "index.html").read_text(encoding="utf-8"), "lxml")
    checks["search lists new"] = f"product_id={pid}.html" in (S / "search.html").read_text(encoding="utf-8")
    checks["home latest has new"] = f"product_id={pid}.html" in str(hp.select_one("#latest-products"))
    checks["home has news"] = hp.select_one("#home-news .news-list a") is not None
    checks["home hides hidden"] = f"product_id={hidden_id}.html" not in str(hp)
    cat = BeautifulSoup((S / "product/category&path=1.html").read_text(encoding="utf-8"), "lxml")
    checks["cat1 has new"] = f"product_id={pid}.html" in str(cat.select_one(".product-grid"))
    checks["cat1 thumb path"] = f"../_data/uploads/p{pid}_main-627.jpg" in str(cat)
    checks["hidden page removed"] = not (S / f"product/product&product_id={hidden_id}.html").exists()
    checks["sitemap has new"] = f"product_id={pid}" in (S / "sitemap.xml").read_text(encoding="utf-8")
    en = BeautifulSoup((S / f"product/product&product_id={pid}.en.html").read_text(encoding="utf-8"), "lxml")
    ja = (S / f"product/product&product_id={pid}.ja.html").read_text(encoding="utf-8")
    checks["en name override"] = en.select_one("h1").get_text(strip=True) == "Test Cape EN"
    checks["en description override"] = "English override description" in str(en.select_one("#tab-description"))
    checks["en keeps zh feature (no override)"] = "第一行" in str(en.select_one(".product-feature-content"))
    checks["ja feature override"] = "日本語の特徴テスト" in ja
    checks["en card uses en name"] = "Test Cape EN" in (S / "product/category&path=1.en.html").read_text(encoding="utf-8")
    checks["no tracker ids"] = "G-8CRMWS8GBK" not in out and "G-8CRMWS8GBK" not in ja
    checks["search target set"] = 'data-apt-search="../search.en.html"' in str(en)
    checks["en has no buy button"] = "立即購買" not in str(en) and "Buy now" not in str(en) and en.select_one(".showcase-note") is not None
    checks["en ui translated"] = "You may also like" in str(en)
    checks["404 pages"] = all((S / f).exists() for f in ("404.html", "404.en.html"))
    checks["theme assets"] = (S / "assets/theme.css").exists() and 'href="../assets/theme.css' in str(en)
    fit_en = (S / "fitstudio.en.html").read_text(encoding="utf-8")
    checks["fitting room pages"] = all((S / f"fitstudio{x}.html").exists() for x in ("", ".en", ".ja", ".de")) and (S / "assets/fitstudio.js").exists()
    checks["fitting room translated + configured"] = "Try it on" in fit_en and '"serverLang": "en"' in fit_en and "assets/fitstudio/yellow_coat.jpg" in fit_en
    checks["fitting room in nav + home"] = 'href="fitstudio.en.html"' in str(en.select_one(".nav")).replace("../", "") and hp.select_one(".fit-promo a.btn") is not None
    for k, v in checks.items():
        print(("OK  " if v else "FAIL"), k)
    print("ALL PASS" if all(checks.values()) else "SOME FAILED")
finally:
    sb.DATA_FILE.write_text(backup, encoding="utf-8")
    sb.delete_uploads(pid)
    (sb.UPLOADS / "_selftest.jpg").unlink(missing_ok=True)
    sb.build_all()
    print("restored; products:", len(sb.load_data()["products"]), "| product pages:", len(list(sb.SITE.glob("product/product&*.html"))))
