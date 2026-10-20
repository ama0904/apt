# -*- coding: utf-8 -*-
"""
Make lightweight WebP copies of the site's photos and record them in _data/image_opt.json.

  python _tools/optimize_images.py

Every JPG/PNG under the image CDN mirror and _data/uploads that is wider than MAX_W or heavier than
MIN_BYTES gets a sibling "<name>.opt.webp" (max 1600 px wide). site_builder.py swaps <img> sources to
these copies; the originals stay in place for the zoom / full-size links. Existing copies are reused,
so re-running only processes new images (e.g. ones uploaded from the admin).
"""
import json
import sys
from pathlib import Path

from PIL import Image, ImageOps

HERE = Path(__file__).resolve().parent
SITE = HERE.parent / "www.apetto.com.tw"
OUT = SITE / "_data" / "image_opt.json"
ROOTS = ["_ext/image-cdn-flare.qdm.cloud", "_ext/image-cdn.qdm.cloud", "_data/uploads"]
MAX_W = 1600
MIN_BYTES = 60 * 1024
QUALITY = 78


def main():
    mapping, made, saved = {}, 0, 0
    for root in ROOTS:
        base = SITE / root
        if not base.exists():
            continue
        for f in base.rglob("*"):
            if f.suffix.lower() not in (".jpg", ".jpeg", ".png") or ".opt." in f.name:
                continue
            rel = f.relative_to(SITE).as_posix()
            dst = f.with_name(f.stem + ".opt.webp")
            if not dst.exists():
                try:
                    im = Image.open(f)
                    im = ImageOps.exif_transpose(im)
                    if im.width <= MAX_W and f.stat().st_size < MIN_BYTES:
                        continue
                    if im.mode not in ("RGB", "RGBA"):
                        im = im.convert("RGBA" if "transparency" in im.info or im.mode in ("LA", "P") else "RGB")
                    if im.width > MAX_W:
                        im = im.resize((MAX_W, round(im.height * MAX_W / im.width)), Image.LANCZOS)
                    im.save(dst, "WEBP", quality=QUALITY, method=6)
                    made += 1
                except Exception as e:  # unreadable file: keep using the original
                    print("skip", rel, e)
                    continue
            if dst.exists():
                if dst.stat().st_size >= f.stat().st_size:  # no gain: drop the copy
                    dst.unlink()
                    continue
                saved += f.stat().st_size - dst.stat().st_size
                mapping[rel] = dst.relative_to(SITE).as_posix()
    OUT.write_text(json.dumps(mapping, ensure_ascii=False, indent=0, sort_keys=True), encoding="utf-8")
    print(f"optimized copies: {len(mapping)} (new {made}), bytes saved per full load: {saved / 1048576:.1f} MB")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
