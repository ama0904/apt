# -*- coding: utf-8 -*-
"""Mirror www.apetto.com.tw into a local folder with rewritten links."""
import hashlib, json, os, posixpath, re, sys, time, threading
from collections import deque
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import urljoin, urlsplit, urlunsplit, unquote, quote

import requests
from bs4 import BeautifulSoup

SITE = "https://www.apetto.com.tw/"
SITE_HOSTS = {"www.apetto.com.tw", "apetto.com.tw"}
OUT = sys.argv[1] if len(sys.argv) > 1 else r"C:\Users\shove\apt\www.apetto.com.tw"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/130.0 Safari/537.36")

# never localize these (tracking / social widgets / dynamic APIs)
SKIP_HOSTS = ("googletagmanager.com", "google-analytics.com", "connect.facebook.net",
              "facebook.com", "google.com", "google.com.tw", "doubleclick.net",
              "googleadservices.com", "googlesyndication.com", "line.me", "youtube.com")
# same-site paths that are session/dynamic and not worth mirroring
SKIP_PATH_RE = re.compile(r"^/(admin|account/logout|checkout|index\.php\?route=checkout)", re.I)
SKIP_QUERY_RE = re.compile(r"(^|&)(sort|order|limit)=", re.I)

ASSET_EXT = {".css", ".js", ".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg", ".ico", ".woff",
             ".woff2", ".ttf", ".otf", ".eot", ".mp4", ".webm", ".pdf", ".xml", ".txt", ".json",
             ".mp3", ".avif", ".bmp"}
URL_ATTRS = ["src", "data-src", "data-original", "data-lazy", "data-lazy-src", "data-bg",
             "data-background", "poster", "href"]
SRCSET_ATTRS = ["srcset", "data-srcset"]
CSS_URL_RE = re.compile(r"url\(\s*(['\"]?)([^'\")]+)\1\s*\)", re.I)
CSS_IMPORT_RE = re.compile(r"@import\s+(?!url\()(['\"])([^'\"]+)\1", re.I)

session = requests.Session()
session.headers.update({"User-Agent": UA, "Accept-Language": "zh-TW,zh;q=0.9,en;q=0.8"})
lock = threading.Lock()
log_lines = []


def log(msg):
    with lock:
        print(msg, flush=True)
        log_lines.append(msg)


def norm(url, base=None):
    """Absolute, fragment-free, &amp;-decoded URL or None."""
    if not url:
        return None
    url = url.strip().replace("&amp;", "&")
    # malformed "https:////host/..." or "///host/..." -> protocol-relative
    url = re.sub(r"^(https?:)?/{3,}", r"//", url)
    if url.startswith(("data:", "mailto:", "tel:", "javascript:", "blob:", "#", "about:")):
        return None
    if base:
        url = urljoin(base, url)
    if url.startswith("//"):
        url = "https:" + url
    p = urlsplit(url)
    if p.scheme not in ("http", "https"):
        return None
    host = p.netloc.lower()
    if host == "apetto.com.tw":
        host = "www.apetto.com.tw"
    path = p.path or "/"
    # the site uses '&' inside the path; sitemap encodes it as %26 -> unify
    path = path.replace("%26", "&")
    scheme = "https" if host == "www.apetto.com.tw" else p.scheme
    return urlunsplit((scheme, host, path, p.query, ""))


def is_site(url):
    return urlsplit(url).netloc.lower() in SITE_HOSTS


def skip_host(url):
    h = urlsplit(url).netloc.lower()
    return any(h == s or h.endswith("." + s) for s in SKIP_HOSTS)


def ext_of(url):
    return posixpath.splitext(urlsplit(url).path)[1].lower()


def is_page_url(url):
    """Same-site URL that should be crawled as an HTML page."""
    if not is_site(url):
        return False
    p = urlsplit(url)
    full = p.path + ("?" + p.query if p.query else "")
    if SKIP_PATH_RE.search(full) or SKIP_QUERY_RE.search(p.query):
        return False
    return ext_of(url) not in ASSET_EXT


_bad = re.compile(r'[<>:"|?*\\\x00-\x1f]')


def sanitize_seg(seg):
    seg = _bad.sub("_", seg).strip(" .")
    if not seg:
        seg = "_"
    if len(seg) > 120:
        root, ext = os.path.splitext(seg)
        seg = root[:80] + "_" + hashlib.md5(seg.encode("utf-8")).hexdigest()[:10] + ext[:10]
    return seg


CTYPE_EXT = {"text/css": ".css", "application/javascript": ".js", "text/javascript": ".js",
             "image/png": ".png", "image/jpeg": ".jpg", "image/gif": ".gif",
             "image/webp": ".webp", "image/svg+xml": ".svg", "font/woff2": ".woff2",
             "font/woff": ".woff", "application/json": ".json", "text/plain": ".txt",
             "text/xml": ".xml", "application/xml": ".xml"}


def local_path(url, is_html=None, ctype=""):
    """Map a URL to a local relative POSIX path under OUT."""
    p = urlsplit(url)
    host = p.netloc.lower()
    path = unquote(p.path)
    if path.endswith("/"):
        path += "index.html" if (is_html or is_html is None) else "index"
    segs = [sanitize_seg(s) for s in path.split("/") if s]
    if p.query:
        q = sanitize_seg(unquote(p.query))
        last = segs[-1]
        root, ext = os.path.splitext(last)
        if is_html or ext.lower() not in ASSET_EXT:
            segs[-1] = f"{last}@{q}"
        else:
            segs[-1] = f"{root}@{q}{ext}"
    if is_html and not segs[-1].lower().endswith((".html", ".htm")):
        segs[-1] += ".html"
    elif is_html is False and not os.path.splitext(segs[-1])[1]:
        for k, v in CTYPE_EXT.items():
            if ctype.startswith(k):
                segs[-1] += v
                break
    rel = "/".join(segs)
    if host not in SITE_HOSTS:
        rel = "_ext/" + sanitize_seg(host) + "/" + rel
    return rel


def fetch(url, retries=3):
    for i in range(retries):
        try:
            return session.get(url, timeout=40, allow_redirects=True)
        except requests.RequestException as e:
            if i == retries - 1:
                log(f"  !! fetch failed {url}: {e}")
                return None
            time.sleep(1.5 * (i + 1))


# ------------------------------------------------------------------ crawl pages
pages = {}        # url -> raw html text
page_path = {}    # url -> local rel path
assets = {}       # url -> {"path": rel, "bytes": ..., "ctype": ...} or None
asset_queue = set()
redirects = {}    # requested url -> final url


def collect_from_html(url, html):
    soup = BeautifulSoup(html, "lxml")
    new_pages, new_assets = set(), set()
    for tag in soup.find_all(True):
        for a in URL_ATTRS:
            v = tag.get(a)
            if not v or isinstance(v, list):
                continue
            u = norm(v, url)
            if not u or skip_host(u):
                continue
            rel = [x.lower() for x in (tag.get("rel") or [])]
            if tag.name == "link" and any(x in rel for x in ("preconnect", "dns-prefetch", "alternate", "manifest")):
                continue
            is_link = tag.name == "a" or (tag.name == "link" and "canonical" in rel)
            if is_link:
                if is_page_url(u):
                    new_pages.add(u)
                elif is_site(u) and ext_of(u) in ASSET_EXT:
                    new_assets.add(u)
            elif tag.name in ("iframe", "frame", "form"):
                continue
            else:
                if is_page_url(u):
                    continue  # e.g. link rel=alternate pointing at pages
                new_assets.add(u)
        for a in SRCSET_ATTRS:
            v = tag.get(a)
            if v:
                for part in v.split(","):
                    u = norm(part.strip().split(" ")[0], url)
                    if u and not skip_host(u):
                        new_assets.add(u)
        st = tag.get("style")
        if st:
            for m in CSS_URL_RE.finditer(st):
                u = norm(m.group(2), url)
                if u and not skip_host(u):
                    new_assets.add(u)
    for style in soup.find_all("style"):
        for m in CSS_URL_RE.finditer(style.get_text()):
            u = norm(m.group(2), url)
            if u and not skip_host(u):
                new_assets.add(u)
    return new_pages, new_assets


def crawl_pages(seeds):
    q = deque(seeds)
    seen = set(seeds)
    while q:
        url = q.popleft()
        r = fetch(url)
        if r is None:
            continue
        final = norm(r.url) or url
        if final != url:
            redirects[url] = final
            if final in pages or not is_page_url(final):
                continue
            url = final
            seen.add(url)
        ctype = r.headers.get("content-type", "")
        if r.status_code != 200:
            log(f"  -- {r.status_code} {url}")
            if r.status_code >= 400:
                continue
        if "html" not in ctype:
            asset_queue.add(url)
            continue
        if not r.encoding or r.encoding.lower() == "iso-8859-1":
            r.encoding = r.apparent_encoding
        html = r.text
        pages[url] = html
        page_path[url] = local_path(url, is_html=True)
        np_, na = collect_from_html(url, html)
        asset_queue.update(na)
        added = 0
        for u in np_:
            if u not in seen:
                seen.add(u)
                q.append(u)
                added += 1
        log(f"PAGE [{len(pages)}] {url}  (+{added} links, {len(na)} assets)  -> {page_path[url]}")
        time.sleep(0.3)


# ------------------------------------------------------------------ assets
def download_asset(url):
    r = fetch(url)
    if r is None or r.status_code != 200:
        return url, None
    ctype = r.headers.get("content-type", "").split(";")[0].strip().lower()
    return url, {"bytes": r.content, "ctype": ctype, "final": norm(r.url) or url}


def download_assets():
    rounds = 0
    while True:
        todo = [u for u in asset_queue if u not in assets]
        if not todo:
            break
        rounds += 1
        log(f"-- asset round {rounds}: {len(todo)} files")
        with ThreadPoolExecutor(max_workers=6) as ex:
            for fut in as_completed([ex.submit(download_asset, u) for u in todo]):
                url, res = fut.result()
                if res is None:
                    assets[url] = None
                    log(f"  !! asset failed {url}")
                    continue
                path = local_path(url, is_html=False, ctype=res["ctype"])
                res["path"] = path
                assets[url] = res
                if res["ctype"] == "text/css" or path.endswith(".css"):
                    css = res["bytes"].decode("utf-8", "replace")
                    for m in CSS_URL_RE.finditer(css):
                        u = norm(m.group(2), url)
                        if u and not skip_host(u):
                            asset_queue.add(u)
                    for m in CSS_IMPORT_RE.finditer(css):
                        u = norm(m.group(2), url)
                        if u and not skip_host(u):
                            asset_queue.add(u)


# ------------------------------------------------------------------ rewrite
def resolve_local(url):
    """Return local rel path for url if mirrored (follow redirects), else None."""
    for _ in range(5):
        if url in page_path:
            return page_path[url]
        a = assets.get(url)
        if a:
            return a["path"]
        if url in redirects:
            url = redirects[url]
        else:
            break
    return None


def rel_href(from_rel, to_rel):
    rel = posixpath.relpath(to_rel, posixpath.dirname(from_rel) or ".")
    return quote(rel, safe="/&=@+,;!$()*~")


def rewrite_css(css, css_url, from_rel):
    def sub_url(m):
        raw = m.group(2).strip()
        u = norm(raw, css_url)
        if u:
            loc = resolve_local(u)
            if loc:
                return f"url({m.group(1)}{rel_href(from_rel, loc)}{m.group(1)})"
        return m.group(0)

    def sub_imp(m):
        u = norm(m.group(2), css_url)
        loc = resolve_local(u) if u else None
        if loc:
            return f"@import {m.group(1)}{rel_href(from_rel, loc)}{m.group(1)}"
        return m.group(0)

    css = CSS_URL_RE.sub(sub_url, css)
    css = CSS_IMPORT_RE.sub(sub_imp, css)
    return css


def rewrite_html(url, html):
    from_rel = page_path[url]
    soup = BeautifulSoup(html, "lxml")
    for b in soup.find_all("base"):
        b.decompose()
    for tag in soup.find_all(True):
        changed = False
        for a in URL_ATTRS:
            v = tag.get(a)
            if not v or isinstance(v, list):
                continue
            u = norm(v, url)
            if not u:
                continue
            loc = resolve_local(u)
            if loc:
                tag[a] = rel_href(from_rel, loc)
                changed = True
            elif v.startswith("//"):
                tag[a] = "https:" + v
            elif is_site(u):
                tag[a] = u  # unmirrored same-site link -> absolute online URL
        for a in SRCSET_ATTRS:
            v = tag.get(a)
            if not v:
                continue
            parts = []
            for part in v.split(","):
                bits = part.strip().split(" ", 1)
                u = norm(bits[0], url)
                loc = resolve_local(u) if u else None
                if loc:
                    bits[0] = rel_href(from_rel, loc)
                elif bits[0].startswith("//"):
                    bits[0] = "https:" + bits[0]
                parts.append(" ".join(bits))
            tag[a] = ", ".join(parts)
        st = tag.get("style")
        if st:
            tag["style"] = rewrite_css(st, url, from_rel)
        if changed:
            for drop in ("integrity", "crossorigin"):
                if tag.has_attr(drop):
                    del tag[drop]
    for style in soup.find_all("style"):
        if style.string:
            style.string = rewrite_css(style.string, url, from_rel)
    return str(soup)


def write(rel, data):
    fp = os.path.join(OUT, *rel.split("/"))
    os.makedirs(os.path.dirname(fp), exist_ok=True)
    if isinstance(data, (bytes, bytearray)):
        with open(fp, "wb") as f:
            f.write(data)
    else:
        with open(fp, "w", encoding="utf-8") as f:
            f.write(data)


def main():
    t0 = time.time()
    seeds = {SITE}
    sm = fetch(SITE + "sitemap.xml")
    if sm is not None and sm.status_code == 200:
        for m in re.finditer(r"<loc>([^<]+)</loc>", sm.text):
            u = norm(m.group(1))
            if u and is_page_url(u):
                seeds.add(u)
        asset_queue.add(SITE + "sitemap.xml")
    for extra in ("robots.txt", "llms.txt", "googlebase.xml", "favicon.ico"):
        asset_queue.add(SITE + extra)
    log(f"== crawling pages from {len(seeds)} seeds")
    crawl_pages(sorted(seeds))
    log(f"== {len(pages)} pages; downloading assets")
    download_assets()
    ok = {u: a for u, a in assets.items() if a}
    log(f"== {len(ok)} assets ok, {len(assets) - len(ok)} failed; writing files")
    # avoid path collisions between different asset URLs
    used = {}
    for u, a in ok.items():
        p = a["path"]
        if p in used and used[p] != u:
            root, ext = os.path.splitext(p)
            p = f"{root}_{hashlib.md5(u.encode()).hexdigest()[:8]}{ext}"
            a["path"] = p
        used[p] = u
    for u, a in ok.items():
        if a["ctype"] == "text/css" or a["path"].endswith(".css"):
            css = a["bytes"].decode("utf-8", "replace")
            write(a["path"], rewrite_css(css, u, a["path"]))
        else:
            write(a["path"], a["bytes"])
    for u, html in pages.items():
        write(page_path[u], rewrite_html(u, html))
        write("_raw_html/" + page_path[u], html)
    manifest = {
        "site": SITE, "crawled_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "pages": {u: page_path[u] for u in pages},
        "assets": {u: a["path"] for u, a in ok.items()},
        "failed_assets": [u for u, a in assets.items() if not a],
        "redirects": redirects,
    }
    write("_mirror_manifest.json", json.dumps(manifest, ensure_ascii=False, indent=1))
    write("_mirror_log.txt", "\n".join(log_lines))
    log(f"== done in {time.time()-t0:.0f}s: {len(pages)} pages, {len(ok)} assets -> {OUT}")


if __name__ == "__main__":
    main()
