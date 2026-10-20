# -*- coding: utf-8 -*-
"""Check that every local href/src in site HTML and url() in CSS points at an existing file."""
import glob, html, os, posixpath, re, sys
from collections import Counter
from urllib.parse import unquote

root = sys.argv[1]
os.chdir(root)
SKIP_DIRS = ("_raw_html", "_templates")


def target(f, v):
    d = posixpath.dirname(f.replace("\\", "/"))
    return posixpath.normpath(posixpath.join(d, unquote(v.split("#")[0].split("?")[0])))


miss, total, cdn_left = Counter(), 0, 0
examples = {}
for f in glob.glob("**/*.html", recursive=True):
    if f.startswith(SKIP_DIRS):
        continue
    s = open(f, encoding="utf-8").read()
    for m in re.finditer(r'(?:href|src|data-src)="([^"]+)"', s):
        v = html.unescape(m.group(1))
        if v.startswith(("http", "data:", "mailto:", "#", "javascript", "tel:", "'")):
            if "qdm.cloud" in v or "cdnjs" in v or "googleapis" in v:
                cdn_left += 1
            continue
        total += 1
        if not os.path.exists(target(f, v)):
            key = re.sub(r"\d+", "N", v)[:100]
            miss[key] += 1
            examples.setdefault(key, (f, v))
print("HTML local refs:", total, "| missing:", sum(miss.values()), "| CDN refs left (preconnect etc):", cdn_left)
for k, n in miss.most_common(15):
    print(f"   {n:4d}  {k}   e.g. {examples[k]}")

cm, ct = [], 0
for f in glob.glob("**/*.css", recursive=True):
    s = open(f, encoding="utf-8", errors="replace").read()
    for m in re.finditer(r"url\(\s*['\"]?([^'\")]+)['\"]?\s*\)", s):
        v = m.group(1).strip()
        if v.startswith("data:"):
            continue
        if v.startswith(("http", "//")):
            cm.append((f, v[:100]))
            continue
        ct += 1
        if not os.path.exists(target(f, v)):
            cm.append((f, v))
print("CSS local refs:", ct, "| unresolved or still remote:", len(cm))
for x in cm[:10]:
    print("   ", x)
