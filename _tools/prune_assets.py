# -*- coding: utf-8 -*-
"""
Delete files under www.apetto.com.tw/_ext that nothing references any more (old theme CSS/JS, unused images).

  python _tools/prune_assets.py            # dry run: list what would go
  python _tools/prune_assets.py --delete   # really delete

References are collected from every HTML/CSS/JS/JSON file in the site (except _raw_html and _templates)
plus the admin page. Keys *and* values of _data/image_opt.json and the clean-image paths in
_data/image_text.json count as references.
"""
import json
import posixpath
import re
import sys
from pathlib import Path
from urllib.parse import unquote

HERE = Path(__file__).resolve().parent
SITE = HERE.parent / "www.apetto.com.tw"
SKIP = ("_raw_html", "_templates")


REF_RE = re.compile(r"""_ext/[^\s"'<>()?#\\]+""")
URL_RE = re.compile(r"""url\(\s*['"]?([^'")]+)['"]?\s*\)""")


def scan(f, refs, queue):
    """Collect _ext/... references in f; CSS/JS files under _ext are scanned transitively (fonts, images)."""
    text = f.read_text(encoding="utf-8", errors="replace")
    for m in REF_RE.finditer(text):
        r = unquote(m.group(0))
        if r not in refs:
            refs.add(r)
            queue.append(r)
    if f.suffix.lower() == ".css":  # relative url() inside a stylesheet
        base = f.relative_to(SITE).parent.as_posix()
        for m in URL_RE.finditer(text):
            v = m.group(1).strip()
            if v.startswith(("data:", "http", "//")):
                continue
            r = (Path(base) / v.split("?")[0].split("#")[0]).as_posix()
            r = str(Path(r).as_posix()).replace("\\", "/")
            import posixpath
            r = posixpath.normpath(r)
            if r not in refs:
                refs.add(r)
                queue.append(r)


def main():
    refs, queue = set(), []
    roots = [f for f in list(SITE.rglob("*.html")) + list(SITE.rglob("*.css")) + list(SITE.rglob("*.js")) + list(SITE.rglob("*.json"))
             if f.is_file() and "_ext" not in f.parts and not f.relative_to(SITE).as_posix().startswith(SKIP)
             and f.name != "_mirror_manifest.json"] + [HERE / "admin.html"]
    for f in roots:
        scan(f, refs, queue)
    opt = SITE / "_data" / "image_opt.json"
    if opt.exists():
        for k, v in json.loads(opt.read_text(encoding="utf-8")).items():
            for r in (k, v):
                if r not in refs:
                    refs.add(r)
                    queue.append(r)
    while queue:
        r = queue.pop()
        f = SITE / r
        if f.is_file() and f.suffix.lower() in (".css", ".js", ".html"):
            scan(f, refs, queue)
    victims = []
    for f in (SITE / "_ext").rglob("*"):
        if f.is_file() and f.relative_to(SITE).as_posix() not in refs:
            victims.append(f)
    size = sum(f.stat().st_size for f in victims)
    print(f"referenced: {len(refs)} | unreferenced files under _ext: {len(victims)} ({size / 1048576:.1f} MB)")
    for f in victims[:40]:
        print("  ", f.relative_to(SITE).as_posix())
    if "--delete" in sys.argv:
        for f in victims:
            f.unlink()
        for d in sorted((SITE / "_ext").rglob("*"), reverse=True):
            if d.is_dir() and not any(d.iterdir()):
                d.rmdir()
        print("deleted")


if __name__ == "__main__":
    main()
