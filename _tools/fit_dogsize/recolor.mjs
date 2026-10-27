// Recolour the garment in a finished try-on picture, on the server, without AI (about 0.1-0.3 s on CPU).
//
//   const { recolorHandler } = await import('./recolor.mjs');
//   app.post('/api/recolor', recolorHandler);     // behind the same auth / CORS as /api/stylist
//
// POST {image: data URL (jpeg/png/webp), from: "#2346b5", to: "#cfe23f"} -> {image: JPEG data URL, ms, share}
// The garment is found by colour: pixels whose colour direction (Lab a/b angle) is close to the garment's known colour
// and clearly saturated. They are recoloured in Lab around the target colour, keeping the original lightness variation
// (folds, shadows, highlights) and leaving black trim, reflective strips, the dog and the background alone.
// share = part of the picture recoloured (0..1); near 0 means the garment colour was not found.
// Needs: sharp (comes with @huggingface/transformers).
import sharp from 'sharp';
import { Worker, isMainThread, parentPort } from 'node:worker_threads';

const WHITE = [0.95047, 1.0, 1.08883];
function toLab(r, g, b, out, i) {
  const lin = v => (v /= 255, v <= 0.04045 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4));
  const R = lin(r), G = lin(g), B = lin(b);
  const x = (0.4124 * R + 0.3576 * G + 0.1805 * B) / WHITE[0], y = 0.2126 * R + 0.7152 * G + 0.0722 * B, z = (0.0193 * R + 0.1192 * G + 0.9505 * B) / WHITE[2];
  const f = t => t > 0.008856 ? Math.cbrt(t) : 7.787 * t + 16 / 116;
  const fx = f(x), fy = f(y), fz = f(z);
  out[i] = 116 * fy - 16; out[i + 1] = 500 * (fx - fy); out[i + 2] = 200 * (fy - fz);
}
function fromLab(L, a, b, out, i) {
  const fy = (L + 16) / 116, fx = fy + a / 500, fz = fy - b / 200;
  const inv = t => (t * t * t > 0.008856 ? t * t * t : (t - 16 / 116) / 7.787);
  const x = inv(fx) * WHITE[0], y = inv(fy), z = inv(fz) * WHITE[2];
  const gam = c => { c = c <= 0.0031308 ? 12.92 * c : 1.055 * Math.pow(Math.max(c, 0), 1 / 2.4) - 0.055; return Math.max(0, Math.min(255, c * 255)); };
  out[i] = gam(3.2406 * x - 1.5372 * y - 0.4986 * z); out[i + 1] = gam(-0.9689 * x + 1.8758 * y + 0.0415 * z); out[i + 2] = gam(0.0557 * x - 0.2040 * y + 1.0570 * z);
}
function hexLab(h) {
  const m = /^#?([0-9a-f]{6})$/i.exec(h || ''); if (!m) return null;
  const n = parseInt(m[1], 16), o = new Float64Array(3);
  toLab(n >> 16 & 255, n >> 8 & 255, n & 255, o, 0); return o;
}
// separable box blur of a float mask (radius r), run twice ~ gaussian
function boxBlur(src, w, h, r) {
  const tmp = new Float32Array(src.length), dst = new Float32Array(src.length), n = 2 * r + 1;
  for (let y = 0; y < h; y++) { let s = 0; for (let x = -r; x <= r; x++) s += src[y * w + Math.min(w - 1, Math.max(0, x))];
    for (let x = 0; x < w; x++) { tmp[y * w + x] = s / n; s += src[y * w + Math.min(w - 1, x + r + 1)] - src[y * w + Math.max(0, x - r)]; } }
  for (let x = 0; x < w; x++) { let s = 0; for (let y = -r; y <= r; y++) s += tmp[Math.min(h - 1, Math.max(0, y)) * w + x];
    for (let y = 0; y < h; y++) { dst[y * w + x] = s / n; s += tmp[Math.min(h - 1, y + r + 1) * w + x] - tmp[Math.max(0, y - r) * w + x]; } }
  return dst;
}
function dilate3(src, w, h) {
  const out = new Float32Array(src.length);
  for (let y = 0; y < h; y++) for (let x = 0; x < w; x++) {
    let m = 0; for (let dy = -1; dy <= 1; dy++) for (let dx = -1; dx <= 1; dx++) { const yy = y + dy, xx = x + dx; if (yy >= 0 && yy < h && xx >= 0 && xx < w) { const v = src[yy * w + xx]; if (v > m) m = v; } }
    out[y * w + x] = m;
  }
  return out;
}
// keep only the big connected pieces of the mask: the garment (possibly split by straps or legs), not small blobs of a
// similar colour elsewhere (a pink tongue, a red collar, a flower in the grass)
function keepLargeParts(mask, w, h) {
  const N = w * h, label = new Int32Array(N), stack = new Int32Array(N), areas = [0];
  let n = 0;
  for (let s = 0; s < N; s++) {
    if (label[s] || mask[s] <= 0.5) continue;
    const id = ++n; let top = 0, area = 0; stack[top++] = s; label[s] = id;
    while (top) {
      const p = stack[--top]; area++;
      const x = p % w, y = (p - x) / w;
      if (x > 0 && !label[p - 1] && mask[p - 1] > 0.5) { label[p - 1] = id; stack[top++] = p - 1; }
      if (x < w - 1 && !label[p + 1] && mask[p + 1] > 0.5) { label[p + 1] = id; stack[top++] = p + 1; }
      if (y > 0 && !label[p - w] && mask[p - w] > 0.5) { label[p - w] = id; stack[top++] = p - w; }
      if (y < h - 1 && !label[p + w] && mask[p + w] > 0.5) { label[p + w] = id; stack[top++] = p + w; }
    }
    areas.push(area);
  }
  if (n === 0) return mask;
  const largest = Math.max(...areas), minArea = Math.max(0.08 * largest, 0.003 * N);
  const keep = areas.map(a => a >= minArea);
  let core = new Float32Array(N);
  for (let p = 0; p < N; p++) if (label[p] && keep[label[p]]) core[p] = 1;
  core = boxBlur(dilate3(dilate3(core, w, h), w, h), w, h, 2);   // soft edge around the kept pieces
  const out = new Float32Array(N);
  for (let p = 0; p < N; p++) out[p] = mask[p] * Math.min(1, core[p] * 1.5);
  return out;
}
const median = arr => { if (!arr.length) return NaN; const s = Float64Array.from(arr).sort(); return s[s.length >> 1]; };

export async function recolor(buf, fromHex, toHex, { tol = 34, maxSide = 1024 } = {}) {
  const src = hexLab(fromHex), dst = hexLab(toHex);
  if (!src || !dst) throw Object.assign(new Error('bad colour'), { status: 400 });
  const { data, info } = await sharp(buf).rotate().resize(maxSide, maxSide, { fit: 'inside', withoutEnlargement: true }).removeAlpha().raw().toBuffer({ resolveWithObject: true });
  const w = info.width, h = info.height, N = w * h;
  const lab = new Float64Array(N * 3);
  for (let p = 0; p < N; p++) toLab(data[p * 3], data[p * 3 + 1], data[p * 3 + 2], lab, p * 3);
  // mask
  const sc = Math.hypot(src[1], src[2]), sang = Math.atan2(src[2], src[1]);
  let mask = new Float32Array(N);
  for (let p = 0; p < N; p++) {
    const a = lab[p * 3 + 1], b = lab[p * 3 + 2], ch = Math.hypot(a, b);
    let d = Math.abs(Math.atan2(b, a) - sang); if (d > Math.PI) d = 2 * Math.PI - d;
    const ang = d * 180 / Math.PI;
    mask[p] = Math.min(1, Math.max(0, (tol - ang) / 10)) * Math.min(1, Math.max(0, (ch - 0.18 * sc) / (0.12 * sc)));
  }
  mask = boxBlur(boxBlur(dilate3(mask, w, h), w, h, 1), w, h, 1);
  mask = keepLargeParts(mask, w, h);
  // statistics of the garment
  const Ls = [], Cs = []; let cnt = 0;
  for (let p = 0; p < N; p++) if (mask[p] > 0.5) { cnt++; if ((p & 3) === 0) { Ls.push(lab[p * 3]); Cs.push(Math.hypot(lab[p * 3 + 1], lab[p * 3 + 2])); } }
  const Lm = Ls.length ? median(Ls) : src[0], cm = Math.max(1, Cs.length ? median(Cs) : sc);
  const k = dst[0] > Lm + 25 ? 0.85 : 1.0;
  const out = Buffer.alloc(N * 3), px = new Float64Array(3);
  for (let p = 0; p < N; p++) {
    const m = mask[p], r = data[p * 3], g = data[p * 3 + 1], b = data[p * 3 + 2];
    if (m < 0.004) { out[p * 3] = r; out[p * 3 + 1] = g; out[p * 3 + 2] = b; continue; }
    const L = lab[p * 3], a = lab[p * 3 + 1], bb = lab[p * 3 + 2];
    const sat = Math.min(1.4, Math.max(0.3, Math.hypot(a, bb) / cm));
    fromLab(dst[0] + (L - Lm) * k, dst[1] * sat, dst[2] * sat, px, 0);
    out[p * 3] = r * (1 - m) + px[0] * m; out[p * 3 + 1] = g * (1 - m) + px[1] * m; out[p * 3 + 2] = b * (1 - m) + px[2] * m;
  }
  const jpg = await sharp(out, { raw: { width: w, height: h, channels: 3 } }).jpeg({ quality: 88 }).toBuffer();
  return { jpg, share: cnt / N };
}

// The pixel work runs in one worker thread, so the server's main thread (Gemini browser jobs) is never blocked.
if (!isMainThread && parentPort) {
  parentPort.on('message', async ({ id, buf, from, to }) => {
    try { const r = await recolor(Buffer.from(buf), from, to); parentPort.postMessage({ id, jpg: r.jpg, share: r.share }); }
    catch (e) { parentPort.postMessage({ id, error: e.message, status: e.status || 0 }); }
  });
}
let worker = null, seq = 0;
const waiting = new Map();
function getWorker() {
  if (worker) return worker;
  worker = new Worker(new URL(import.meta.url));
  worker.on('message', m => { const w = waiting.get(m.id); if (!w) return; waiting.delete(m.id); if (!waiting.size && worker) worker.unref(); m.error ? w.reject(Object.assign(new Error(m.error), { status: m.status || undefined })) : w.resolve(m); });
  worker.on('error', e => { for (const w of waiting.values()) w.reject(e); waiting.clear(); worker = null; });
  worker.on('exit', () => { worker = null; });
  worker.unref();
  return worker;
}
function inWorker(buf, from, to) {
  return new Promise((resolve, reject) => { const id = ++seq; waiting.set(id, { resolve, reject }); const wk = getWorker(); wk.ref(); wk.postMessage({ id, buf, from, to }); });   // ref while busy, so a short-lived process waits for the answer
}
function decode(dataUrl) {
  const m = /^data:image\/(jpeg|png|webp);base64,([A-Za-z0-9+/=]+)$/.exec(dataUrl || '');
  if (!m) throw Object.assign(new Error('bad image'), { status: 400 });
  const buf = Buffer.from(m[2], 'base64');
  if (buf.length > 6 * 1024 * 1024) throw Object.assign(new Error('image too large'), { status: 413 });
  return buf;
}
const asResult = (r, t0) => ({ image: 'data:image/jpeg;base64,' + Buffer.from(r.jpg).toString('base64'), share: +r.share.toFixed(3), ms: Date.now() - t0 });

export async function recolorDataUrl(dataUrl, fromHex, toHex) {
  const buf = decode(dataUrl), t0 = Date.now();
  return asResult(await inWorker(buf, fromHex, toHex), t0);
}

// For /api/stylist: recolour the finished picture into every colour the page asked for, in the same response.
// image: data URL or Buffer; recolor: {from: "#hex", to: ["#hex", ...]} (at most 6). Never throws; bad input -> [].
export async function recolorVariants(image, recolor) {
  try {
    if (!recolor || !recolor.from || !Array.isArray(recolor.to)) return [];
    const buf = Buffer.isBuffer(image) ? image : decode(image);
    const out = [];
    for (const to of recolor.to.slice(0, 6)) {
      const t0 = Date.now();
      try { out.push({ hex: to, ...asResult(await inWorker(buf, recolor.from, to), t0) }); } catch (e) { /* skip that colour */ }
    }
    return out;
  } catch (e) { return []; }
}

export function recolorHandler(req, res) {
  const b = req.body || {};
  recolorDataUrl(b.image, b.from, b.to)
    .then(r => res.json(r))
    .catch(e => res.status(e.status || 500).json({ error: e.status ? e.message : 'recolor unavailable' }));
}
