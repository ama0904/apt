# -*- coding: utf-8 -*-
"""
Build _data/image_text.json: which images carry text, where it sits, and what it says.

Sources: _tools/ocr/ocr_flagged.json (Windows OCR boxes for the measurement diagrams)
plus hand-defined entries for the banners/hero and the size charts.
Text is stored as the Chinese source string; translations come from _data/i18n.json at build time.

  python _tools/make_image_text.py
"""
import json
import re
from pathlib import Path

from PIL import Image

HERE = Path(__file__).resolve().parent
SITE = HERE.parent / "www.apetto.com.tw"
DATA = SITE / "_data"
OCR = json.loads((HERE / "ocr" / "ocr_flagged.json").read_text(encoding="utf-8"))

LABEL_NECK = "領圍的位置\n(圈量)"
LABEL_CHEST = "腹圍的位置\n(圈量)"
LABEL_LEN = "衣長"

CHARTS = {
    "big_raincoat": {"title": "大汪雨衣", "sub_unit": False,
                     "rows": [["S", "35", "41", "48~67"], ["M", "40", "48", "50~71"], ["L", "45", "51", "55~78"],
                              ["XL", "50", "54", "56~80"], ["2XL", "55", "57", "57~86"]], "small": False},
    "big_jacket": {"title": "大汪保暖夾克（加毛）", "sub_unit": False,
                   "rows": [["S", "37", "42", "49~68"], ["M", "42", "49", "51~72"], ["L", "47", "52", "56~79"],
                            ["XL", "52", "55", "57~81"], ["2XL", "57", "58", "58~87"]], "small": False},
    "small_cape": {"title": "小汪防水斗篷", "sub_unit": True,
                   "rows": [["S", "28", "35", "45"], ["M", "32", "38", "50"], ["L", "36", "42", "55"], ["XL", "40", "45", "60"]],
                   "small": True},
    "small_warm_cape": {"title": "小汪保暖防水斗篷(加毛)", "sub_unit": True,
                        "rows": [["S", "29", "36", "47"], ["M", "33", "39", "52"], ["L", "37", "43", "57"], ["XL", "41", "46", "62"]],
                        "small": True},
}
UNIT = "單位為 cm，皆為圈量"
COLS = ["衣長", "領圍", "腹圍"]
NOTE_TOL = "※ 尺寸測量會因商品素材不同，可能會有 1~3 公分的誤差。"
NOTE_MEASURE = "※ 請先測量毛小孩的背長，從脖子最底部(建議再往後一點，約莫是前腳的位置)，一直量到尾巴。"
NOTE_BIG = "※ 建議選擇比背長短 10 公分的尺寸。例如背長 52 公分，M 號合身、L 號寬鬆。"
NOTE_SMALL = "※ 建議選擇比背長短 5-7 公分的尺寸。例如背長 32 公分，S 號合身、M 號寬鬆。"
for c in CHARTS.values():
    c["unit"] = UNIT
    c["cols"] = COLS
    c["notes"] = [NOTE_MEASURE, NOTE_SMALL if c["small"] else NOTE_BIG, NOTE_TOL]

# chart images -> chart key (by file name)
TABLE_IMAGES = {
    "8e3067ecf3aca73e3bdd771f5c52d703.png": "big_raincoat",
    "990faa9e8349f509257f4ecbd86a053c.png": "big_raincoat",
    "eec927e87fdb1b48d93122f1322df1a6.png": "big_raincoat",
    "468fcc8285fe4d50585d56a56ec5c841.png": "big_jacket",
    "6a0a0ba844c0c070427414e8abaf82b7.png": "big_jacket",
    "ea1fa9d335a6bdcd127954788f53d11e.png": "big_jacket",
    "919f432674bcc76362f51b584b7f38ec.png": "small_cape",
    "90910a5b996522454ade9eb9c3774b4d.png": "small_cape",
    "ac4afea4d2029b7ec1021487f8f25b51.png": "small_warm_cape",
}

# banners / hero: hand-measured boxes [x, y, w, h] in source pixels
IMG = "_ext/image-cdn-flare.qdm.cloud/q60f738cbd6a9c/image/data/"
# Each banner is one text block (lines stack, so long translations wrap without colliding).
# "erase" boxes are the source-pixel regions to inpaint; "box" is where the block is anchored.
MANUAL = {
    IMG + "2026/08/26/2e2d960fcdd9a821b141df7d41b8f5c7.jpg": {
        "erase": [[396, 72, 226, 56], [300, 130, 550, 58]], "box": [300, 74, 550, 114], "align": "center", "center_x": 541,
        "color": None, "maxw": 70, "lines": [{"text": "阻擋風雨，", "size": 4.6, "weight": 400}, {"text": "擁抱無憂的舒適時光", "size": 4.6, "weight": 400}]},
    IMG + "2026/08/26/b2963b09f6f2a473a8f3367f8d8ac9e2.jpg": {
        "erase": [[76, 180, 420, 60], [76, 248, 410, 50]], "box": [76, 182, 420, 118], "align": "left",
        "color": "#ffffff", "lines": [{"text": "apetto 寵物機能衣", "size": 4.2, "weight": 400}, {"text": "極致防水，奔跑不受限。", "size": 3.3, "weight": 400}]},
    IMG + "2026/08/26/cf1d3a5ae88219b7f6c3868005c2ff8d.jpg": {
        "erase": [[70, 90, 410, 58], [70, 156, 400, 46]], "box": [70, 92, 410, 110], "align": "left",
        "color": "#2b2b2b", "lines": [{"text": "apetto 全天候機能衣", "size": 4.6, "weight": 400}, {"text": "亮眼防護，大狗自在奔馳", "size": 3.6, "weight": 400}]},
    IMG + "__4_1.jpg": {
        "erase": [[6140, 2350, 1720, 280], [6120, 2640, 1920, 270]], "box": [6150, 2370, 1900, 540], "align": "left",
        "color": "#111111", "lines": [{"text": "apetto 小汪系列", "size": 1.9, "weight": 700}, {"text": "不只可愛，更有帥氣", "size": 1.7, "weight": 700}]},
}


DARK = 205  # anything darker than this on the white studio background counts as ink (labels are light grey)


def grow_box(gray, box, max_down=1.8, gap=10):
    """Extend an OCR box to swallow the whole label (e.g. the lighter '(圈量)' second line) on a light background."""
    W, H = gray.size
    x, y, w, h = box
    px = gray.load()
    x0, x1 = max(0, x - 6), min(W - 1, x + w + 6)

    def row_dark(yy):
        return any(px[cx, yy] < DARK for cx in range(x0, x1 + 1, 2))

    # downward: second line
    y_end = min(H - 1, y + h + 2)
    last_dark, yy, limit = y_end, y_end + 1, min(H - 1, int(y + h + max_down * h))
    while yy <= limit:
        if row_dark(yy):
            last_dark = yy
        elif yy - last_dark > gap:
            break
        yy += 1
    # upward: clipped glyph tops (tight gap so the arrow above is not swallowed)
    top, yy, first_dark = y, y - 1, y
    while yy >= max(0, int(y - 0.5 * h)):
        if row_dark(yy):
            first_dark = yy
        elif first_dark - yy > 2:
            break
        yy -= 1
    top = first_dark

    def col_dark(cx):
        return any(px[cx, cy] < DARK for cy in range(top, last_dark + 1, 2))

    lx = x0
    while lx > max(0, x - w // 2) and col_dark(lx - 1):
        lx -= 1
    rx = x1
    while rx < min(W - 1, x + w + w // 2) and col_dark(rx + 1):
        rx += 1
    X0, Y0 = max(0, lx - 3), max(0, top - 4)
    return [X0, Y0, min(W - 1, rx + 3) - X0, min(H - 1, last_dark + 4) - Y0]


def find_len_label(gray):
    """Locate the '衣長' label in the top band of a measurement diagram when OCR missed it.
    Text columns have several dark pixels; the thin arrow line through the label has only 1-2."""
    import cv2
    import numpy as np
    W, H = gray.size
    x_off, y_lim = int(W * 0.25), int(H * 0.35)
    region = np.array(gray)[0:y_lim, x_off:int(W * 0.75)]
    binary = (region < DARK).astype(np.uint8)
    n, labels, stats, _ = cv2.connectedComponentsWithStats(binary, connectivity=8)
    glyphs = []
    for i in range(1, n):
        x, y, w, h, area = stats[i]
        if 6 <= h <= 32 and 2 <= w <= 34 and area >= 8:   # stroke-sized pieces; arrow lines are thin, garment is huge
            glyphs.append((x, y, w, h))
    if not glyphs:
        return None
    glyphs.sort()
    groups, cur = [], [glyphs[0]]
    for g in glyphs[1:]:
        px_prev = cur[-1]
        if g[0] - (px_prev[0] + px_prev[2]) <= 12 and abs(g[1] - px_prev[1]) <= 14:
            cur.append(g)
        else:
            groups.append(cur)
            cur = [g]
    groups.append(cur)
    best = None
    for grp in groups:
        x0 = min(g[0] for g in grp)
        x1 = max(g[0] + g[2] for g in grp)
        y0 = min(g[1] for g in grp)
        y1 = max(g[1] + g[3] for g in grp)
        if 18 <= x1 - x0 <= 90 and 10 <= y1 - y0 <= 34:
            score = abs((x0 + x1) / 2 + x_off - W / 2)
            if best is None or score < best[0]:
                best = (score, [int(x0 + x_off), int(y0), int(x1 - x0), int(y1 - y0)])
    return best[1] if best else None


def text_color(img, box):
    """Median colour of the darkest/lightest 20% of pixels in the box, whichever contrasts with the median."""
    x, y, w, h = box
    crop = img.convert("RGB").crop((x, y, x + w, y + h))
    pixels = list(crop.getdata())
    if not pixels:
        return "#444444"
    lum = sorted(((0.299 * r + 0.587 * g + 0.114 * b), (r, g, b)) for r, g, b in pixels)
    med = lum[len(lum) // 2][0]
    n = max(1, len(lum) // 5)
    cand = lum[:n] if med > 128 else lum[-n:]
    r = sum(c[1][0] for c in cand) // n
    g = sum(c[1][1] for c in cand) // n
    b = sum(c[1][2] for c in cand) // n
    return "#%02x%02x%02x" % (r, g, b)


def item(text, box, W, H, align="center", color="#444444", weight=400, center_x=None, lines=1, size=None):
    """Overlay item in percent of the image. Centered items anchor on `cx`; left items on `left`."""
    x, y, w, h = box
    line_h = h / lines
    size = size or round(line_h / W * 100 * 0.88, 3)  # font-size in cqw (container width units)
    cx = center_x if center_x is not None else x + w / 2
    return {"text": text, "left": round(x / W * 100, 3), "cx": round(cx / W * 100, 3), "top": round(y / H * 100, 3),
            "size": size, "color": color, "align": align, "weight": weight}


def clean_path(site_path):
    root, ext = site_path.rsplit(".", 1)
    return f"{root}.clean.{ext}"


def main():
    out = {"charts": CHARTS, "tables": {}, "overlays": {}}
    for entry in OCR:
        name = entry["path"].rsplit("/", 1)[1]
        if name in TABLE_IMAGES:
            out["tables"][entry["path"]] = TABLE_IMAGES[name]
            continue
        if entry["path"] in MANUAL:
            continue
        img = Image.open(SITE / entry["path"])
        gray = img.convert("L")
        W, H = img.size
        items, erase = [], []
        lines = list(entry["lines"])
        if not any(("長" in l["text"] or l["text"].replace(" ", "").startswith("衣")) for l in lines):
            found = find_len_label(gray)
            if found:
                lines.append({"text": "衣長", "x": found[0], "y": found[1], "w": found[2], "h": found[3]})
                print("  + auto 衣長 box", found, "in", entry["path"].rsplit("/", 1)[1])
        for l in lines:
            t = l["text"].replace(" ", "")
            box = [l["x"], l["y"], l["w"], l["h"]]
            if not any(ch in t for ch in "領腹衣長圍位"):
                continue  # stray "(圈量)" second line: covered by the grown box of its label
            if "長" in t or t.startswith("衣"):
                text, lines = LABEL_LEN, 1
                g = [max(0, box[0] - 4), max(0, box[1] - 3), box[2] + 8, box[3] + 6]
            else:
                is_neck = "領" in t or (("圍" in t or "位" in t) and l["x"] < W / 2)
                text, lines = (LABEL_NECK if is_neck else LABEL_CHEST), 2
                g = grow_box(gray, box)
                if g[3] < box[3] * 1.6:  # second line not detected as dark pixels: still reserve room for it
                    g[3] = int(box[3] * 2.3)
            erase.append(g)
            items.append(item(text, [g[0], g[1], g[2], box[3] * lines + (6 if lines == 2 else 0)], W, H,
                              align="center", color=text_color(img, box), weight=400, lines=lines))
        out["overlays"][entry["path"]] = {"clean": clean_path(entry["path"]), "width": W, "height": H,
                                          "erase": erase, "items": items, "kind": "diagram"}
    for path, d in MANUAL.items():
        img = Image.open(SITE / path)
        W, H = img.size
        color = d["color"] or text_color(img, d["erase"][0])
        block = item("", d["box"], W, H, align=d["align"], color=color, center_x=d.get("center_x"), size=1)
        block.pop("text")
        block["lines"] = d["lines"]
        if d.get("maxw"):
            block["maxw"] = d["maxw"]
        out["overlays"][path] = {"clean": clean_path(path), "width": W, "height": H, "erase": d["erase"], "items": [block], "kind": "banner"}
    (DATA / "image_text.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"overlays={len(out['overlays'])} tables={len(out['tables'])} -> {DATA / 'image_text.json'}")


if __name__ == "__main__":
    main()
