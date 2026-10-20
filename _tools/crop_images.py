# -*- coding: utf-8 -*-
"""
Uniform crops of every product photo (main image + gallery), so cards, thumbnails and the product
gallery all share the same shape no matter how the original was shot.

  python _tools/crop_images.py

For each image referenced by _data/products.json this writes
  <name>.sq.webp    1:1   (cards, thumbnails)      max 800 px
  <name>.w43.webp   4:3   (product page gallery)   max 1200 px
and records them in _data/image_crops.json. The crop window is placed where the picture has the
most detail and colour (the dog and the garment), not blindly in the centre. Existing crops are
reused, so re-running only handles new images (e.g. admin uploads).
"""
import json
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageFilter, ImageOps

HERE = Path(__file__).resolve().parent
SITE = HERE.parent / "www.apetto.com.tw"
DATA = SITE / "_data"
OUT = DATA / "image_crops.json"
SHAPES = {"sq": (1, 1, 800), "w43": (4, 3, 1200)}
QUALITY = 82


def energy_map(im):
    """Where the interesting stuff is: edges + colour saturation, blurred, with a mild centre bias."""
    small = im.copy()
    small.thumbnail((320, 320))
    g = np.asarray(small.convert("L")).astype(np.float32)
    gx = np.abs(np.diff(g, axis=1, prepend=g[:, :1]))
    gy = np.abs(np.diff(g, axis=0, prepend=g[:1, :]))
    edges = gx + gy
    hsv = np.asarray(small.convert("HSV")).astype(np.float32)
    sat = hsv[..., 1] * (hsv[..., 2] / 255.0)
    e = edges / (edges.max() + 1e-6) + 0.8 * sat / (sat.max() + 1e-6)
    e = np.asarray(Image.fromarray((e / e.max() * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(6))).astype(np.float32)
    h, w = e.shape
    yy, xx = np.mgrid[0:h, 0:w]
    centre = 1 - 0.35 * (((xx - w / 2) / (w / 2)) ** 2 + ((yy - h / 2) / (h / 2)) ** 2) / 2
    return e * centre, small.size


def best_window(im, ar_w, ar_h):
    """Crop box (in original pixels) with the given aspect ratio that captures the most energy."""
    e, (sw, sh) = energy_map(im)
    W, H = im.size
    target = ar_w / ar_h
    if W / H > target:  # too wide: full height, slide horizontally
        cw, ch = int(round(H * target)), H
    else:  # too tall: full width, slide vertically
        cw, ch = W, int(round(W / target))
    sx, sy = sw / W, sh / H
    kw, kh = max(1, int(cw * sx)), max(1, int(ch * sy))
    integral = np.pad(e, ((1, 0), (1, 0))).cumsum(0).cumsum(1)
    best, bx, by = -1.0, 0, 0
    for y in range(0, e.shape[0] - kh + 1, 2):
        for x in range(0, e.shape[1] - kw + 1, 2):
            s = integral[y + kh, x + kw] - integral[y, x + kw] - integral[y + kh, x] + integral[y, x]
            if s > best:
                best, bx, by = s, x, y
    x0, y0 = int(bx / sx), int(by / sy)
    x0, y0 = min(x0, W - cw), min(y0, H - ch)
    return (x0, y0, x0 + cw, y0 + ch)


def make(src, dst, ar_w, ar_h, max_px):
    im = ImageOps.exif_transpose(Image.open(src))
    if im.mode in ("RGBA", "LA", "P"):
        im = im.convert("RGBA")
        bg = Image.new("RGB", im.size, (255, 255, 255))
        bg.paste(im, mask=im.split()[-1])
        im = bg
    else:
        im = im.convert("RGB")
    box = best_window(im, ar_w, ar_h)
    out = im.crop(box)
    if out.width > max_px:
        out = out.resize((max_px, round(out.height * max_px / out.width)), Image.LANCZOS)
    out.save(dst, "WEBP", quality=QUALITY, method=6)


def main():
    data = json.loads((DATA / "products.json").read_text(encoding="utf-8"))
    paths = []
    for p in data["products"]:
        paths.append(p["image"]["full"])
        paths += [g["full"] for g in p.get("gallery", [])]
    mapping, made = {}, 0
    for rel in dict.fromkeys(paths):
        src = SITE / rel
        if not src.is_file() or rel.startswith(("http:", "https:")):
            continue
        entry = {}
        for key, (aw, ah, mx) in SHAPES.items():
            dst = src.with_name(src.stem + f".{key}.webp")
            if not dst.exists():
                try:
                    make(src, dst, aw, ah, mx)
                    made += 1
                except Exception as e:
                    print("skip", rel, key, e)
                    continue
            entry[key] = dst.relative_to(SITE).as_posix()
        if entry:
            mapping[rel] = entry
    OUT.write_text(json.dumps(mapping, ensure_ascii=False, indent=0, sort_keys=True), encoding="utf-8")
    print(f"crops: {len(mapping)} images (new files {made})")


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    main()
