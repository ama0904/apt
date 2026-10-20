# -*- coding: utf-8 -*-
"""
Produce text-free copies of the images listed in _data/image_text.json (overlays).
The text regions are inpainted with OpenCV; the result is saved as <name>.clean.<ext>.

  python _tools/clean_images.py
"""
import json
from pathlib import Path

import cv2
import numpy as np

HERE = Path(__file__).resolve().parent
SITE = HERE.parent / "www.apetto.com.tw"
SPEC = json.loads((SITE / "_data" / "image_text.json").read_text(encoding="utf-8"))


def main():
    for src, info in SPEC["overlays"].items():
        path = SITE / src
        img = cv2.imdecode(np.fromfile(str(path), dtype=np.uint8), cv2.IMREAD_COLOR)
        if img is None:
            print("!! cannot read", src)
            continue
        H, W = img.shape[:2]
        mask = np.zeros((H, W), dtype=np.uint8)
        for x, y, w, h in info["erase"]:
            x0, y0 = max(0, x - 2), max(0, y - 2)
            x1, y1 = min(W, x + w + 2), min(H, y + h + 2)
            mask[y0:y1, x0:x1] = 255
        if info.get("kind") == "diagram":
            # white studio background: a plain fill is cleaner than inpainting
            out = img.copy()
            out[mask == 255] = (255, 255, 255)
        else:
            radius = 7 if W < 3000 else 25
            out = cv2.inpaint(img, mask, radius, cv2.INPAINT_TELEA)
        dst = SITE / info["clean"]
        ext = dst.suffix.lower()
        ok, buf = cv2.imencode(ext, out, [cv2.IMWRITE_JPEG_QUALITY, 90] if ext in (".jpg", ".jpeg") else [])
        buf.tofile(str(dst))
        print("clean ->", info["clean"])


if __name__ == "__main__":
    main()
