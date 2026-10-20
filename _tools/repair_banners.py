# -*- coding: utf-8 -*-
"""
Rebuild the text-free copies (*.clean.jpg) of the two homepage photos by copying nearby texture over the
area where the original has baked-in slogans. OpenCV inpainting left a smear there; a plain copy of an
adjacent band of foliage looks natural. Run after changing the boxes below, then optimize_images.py.
"""
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

SITE = Path(__file__).resolve().parent.parent / "www.apetto.com.tw"
DIR = SITE / "_ext/image-cdn-flare.qdm.cloud/q60f738cbd6a9c/image/data/2026/08/26"
# (x0, y0, x1, y1, dx, dy, mirror): fill the box with the band found dx/dy away, optionally mirrored
JOBS = {
    "cf1d3a5ae88219b7f6c3868005c2ff8d.jpg": [(60, 82, 492, 152, 430, 0, True), (60, 152, 484, 212, 0, 64, False)],
    "b2963b09f6f2a473a8f3367f8d8ac9e2.jpg": [(66, 172, 506, 306, 0, 200, False)],
}


def repair(src_path, out_path, jobs, seam=6):
    im = Image.open(src_path).convert("RGB")
    a = np.asarray(im).astype(np.float32)
    out = a.copy()
    for (x0, y0, x1, y1, dx, dy, mirror) in jobs:
        band = a[y0 + dy:y1 + dy, x0 + dx:x1 + dx]
        out[y0:y1, x0:x1] = band[:, ::-1] if mirror else band
    img = Image.fromarray(out.clip(0, 255).astype(np.uint8))
    blurred = img.filter(ImageFilter.GaussianBlur(2))  # soften only the seams
    mask = Image.new("L", img.size, 0)
    d = ImageDraw.Draw(mask)
    for (x0, y0, x1, y1, *_) in jobs:
        d.rectangle((x0 - seam, y0 - seam, x1 + seam, y1 + seam), fill=255)
        d.rectangle((x0 + seam, y0 + seam, x1 - seam, y1 - seam), fill=0)
    img.paste(blurred, (0, 0), mask)
    img.save(out_path, quality=92)


if __name__ == "__main__":
    for name, jobs in JOBS.items():
        src = DIR / name
        out = src.with_name(src.stem + ".clean.jpg")
        repair(src, out, jobs)
        webp = src.with_name(src.stem + ".clean.opt.webp")
        if webp.exists():
            webp.unlink()
        print("repaired", out.name)
    print("now run: python _tools/optimize_images.py")
