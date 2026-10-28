// Recolour the garment in a finished try-on picture, on the server, without AI (about 0.2-0.4 s on CPU). Version 3.
//
//   const { recolorHandler, recolorVariants } = await import('./recolor.mjs');
//   app.post('/api/recolor', recolorHandler);     // behind the same auth / CORS as /api/stylist
//
// POST {image: data URL, from: "#2346b5", to: "#cfe23f", original?: data URL of the customer's dog photo}
//   -> {image: JPEG data URL, ms, share, how: "diff" | "colour"}
//
// How the garment is found (v3): Gemini only changes the dog where the garment goes, so the difference between the
// customer's original photo and the try-on picture is the garment ("diff"). Inside that region the coloured fabric is
// recoloured in Lab around the target colour, keeping folds, shadows and highlights; black trim, reflective strips,
// the dog, and same-coloured things elsewhere (grass under a yellow cape, a pink tongue) are untouched.
// Without the original photo, or when Gemini changed the whole picture (difference region too big), it falls back to
// the colour-only mask of v2 (hue + chroma, biggest connected parts). All pixel work runs in one worker thread.
// Needs: sharp (comes with @huggingface/transformers).
import sharp from 'sharp';
import { Worker, isMainThread, parentPort } from 'node:worker_threads';

// ---------- colour maths
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
const clamp01 = v => v < 0 ? 0 : v > 1 ? 1 : v;

// ---------- small ops on float masks
function boxBlur(src, w, h, r) {
  const tmp = new Float32Array(src.length), dst = new Float32Array(src.length), n = 2 * r + 1;
  for (let y = 0; y < h; y++) { let s = 0; for (let x = -r; x <= r; x++) s += src[y * w + Math.min(w - 1, Math.max(0, x))];
    for (let x = 0; x < w; x++) { tmp[y * w + x] = s / n; s += src[y * w + Math.min(w - 1, x + r + 1)] - src[y * w + Math.max(0, x - r)]; } }
  for (let x = 0; x < w; x++) { let s = 0; for (let y = -r; y <= r; y++) s += tmp[Math.min(h - 1, Math.max(0, y)) * w + x];
    for (let y = 0; y < h; y++) { dst[y * w + x] = s / n; s += tmp[Math.min(h - 1, y + r + 1) * w + x] - tmp[Math.max(0, y - r) * w + x]; } }
  return dst;
}
// grow a mask by r pixels (square), separable max filter
function dilate(src, w, h, r) {
  const tmp = new Float32Array(src.length), dst = new Float32Array(src.length);
  for (let y = 0; y < h; y++) for (let x = 0; x < w; x++) { let m = 0; for (let k = -r; k <= r; k++) { const xx = x + k; if (xx >= 0 && xx < w) { const v = src[y * w + xx]; if (v > m) m = v; } } tmp[y * w + x] = m; }
  for (let x = 0; x < w; x++) for (let y = 0; y < h; y++) { let m = 0; for (let k = -r; k <= r; k++) { const yy = y + k; if (yy >= 0 && yy < h) { const v = tmp[yy * w + x]; if (v > m) m = v; } } dst[y * w + x] = m; }
  return dst;
}
// connected components of mask > thr: {label (0 = none), areas (index 1..n), n}
function components(mask, w, h, thr) {
  const N = w * h, label = new Int32Array(N), stack = new Int32Array(N), areas = [0];
  let n = 0;
  for (let s = 0; s < N; s++) {
    if (label[s] || mask[s] <= thr) continue;
    const id = ++n; let top = 0, area = 0; stack[top++] = s; label[s] = id;
    while (top) {
      const p = stack[--top]; area++;
      const x = p % w, y = (p - x) / w;
      if (x > 0 && !label[p - 1] && mask[p - 1] > thr) { label[p - 1] = id; stack[top++] = p - 1; }
      if (x < w - 1 && !label[p + 1] && mask[p + 1] > thr) { label[p + 1] = id; stack[top++] = p + 1; }
      if (y > 0 && !label[p - w] && mask[p - w] > thr) { label[p - w] = id; stack[top++] = p - w; }
      if (y < h - 1 && !label[p + w] && mask[p + w] > thr) { label[p + w] = id; stack[top++] = p + w; }
    }
    areas.push(area);
  }
  return { label, areas, n };
}
// keep only the big connected pieces of a mask (the garment, possibly split by straps), not small same-coloured blobs
function keepLargeParts(mask, w, h) {
  const N = w * h, { label, areas, n } = components(mask, w, h, 0.5);
  if (n === 0) return mask;
  const largest = Math.max(...areas), minArea = Math.max(0.08 * largest, 0.003 * N);
  const keep = areas.map(a => a >= minArea);
  let core = new Float32Array(N);
  for (let p = 0; p < N; p++) if (label[p] && keep[label[p]]) core[p] = 1;
  core = boxBlur(dilate(core, w, h, 2), w, h, 2);
  const out = new Float32Array(N);
  for (let p = 0; p < N; p++) out[p] = mask[p] * Math.min(1, core[p] * 1.5);
  return out;
}
const median = arr => { if (!arr.length) return NaN; const s = Float64Array.from(arr).sort(); return s[s.length >> 1]; };

// where the try-on differs from the customer's photo = where the garment was painted. null when unusable.
async function changedRegion(original, w, h, tryon) {
  const a = await sharp(original).rotate().resize(w, h, { fit: 'fill' }).blur(3).removeAlpha().raw().toBuffer();
  const b = await sharp(tryon, { raw: { width: w, height: h, channels: 3 } }).blur(3).raw().toBuffer();
  const N = w * h, m = new Float32Array(N);
  let hot = 0;
  for (let p = 0; p < N; p++) {
    const d = Math.abs(a[p * 3] - b[p * 3]) + Math.abs(a[p * 3 + 1] - b[p * 3 + 1]) + Math.abs(a[p * 3 + 2] - b[p * 3 + 2]);
    m[p] = clamp01((d - 40) / 64);
    if (m[p] > 0.5) hot++;
  }
  const share = hot / N;
  if (share < 0.004 || share > 0.35) return null;   // nothing changed, or Gemini redrew the whole picture (a real garment is ~5-20 %)
  // the garment is one or two big pieces; scattered specks are regenerated texture (grass, bokeh) and are dropped
  const cs = components(boxBlur(dilate(m, w, h, 2), w, h, 1), w, h, 0.5), big = new Float32Array(N);
  if (!cs.n) return null;
  const largest = Math.max(...cs.areas), minArea = Math.max(0.15 * largest, 0.004 * N);
  for (let p = 0; p < N; p++) if (cs.label[p] && cs.areas[cs.label[p]] >= minArea) big[p] = 1;
  return boxBlur(dilate(big, w, h, 2), w, h, 2);   // the blurred difference already reaches past the garment edge
}

// ---------- the recolour itself
export async function recolor(buf, fromHex, toHex, opts = {}) {
  const src = hexLab(fromHex), dst = hexLab(toHex);
  if (!src || !dst) throw Object.assign(new Error('bad colour'), { status: 400 });
  const maxSide = opts.maxSide || 1024, tol = opts.tol || 34;
  const { data, info } = await sharp(buf).rotate().resize(maxSide, maxSide, { fit: 'inside', withoutEnlargement: true }).removeAlpha().raw().toBuffer({ resolveWithObject: true });
  const w = info.width, h = info.height, N = w * h;
  const lab = new Float64Array(N * 3);
  for (let p = 0; p < N; p++) toLab(data[p * 3], data[p * 3 + 1], data[p * 3 + 2], lab, p * 3);
  // the garment's region: from the original photo when we have one (computed once per picture, shared by all colours)
  let region = opts.region === undefined ? null : opts.region;
  if (opts.region === undefined && opts.original) { try { region = await changedRegion(opts.original, w, h, data); } catch (e) { region = null; } }
  const how = region ? 'diff' : 'colour';
  // colour gate: pixels whose colour direction is close to the garment's and clearly saturated; looser inside the region
  const sc = Math.hypot(src[1], src[2]), sang = Math.atan2(src[2], src[1]);
  const hueTol = region ? 40 : tol, hueSoft = region ? 15 : 10, chromaMin = region ? 0.10 : 0.18, chromaSoft = region ? 0.10 : 0.12;
  let mask = new Float32Array(N);
  for (let p = 0; p < N; p++) {
    if (region && region[p] < 0.01) continue;
    const a = lab[p * 3 + 1], b = lab[p * 3 + 2], ch = Math.hypot(a, b);
    let d = Math.abs(Math.atan2(b, a) - sang); if (d > Math.PI) d = 2 * Math.PI - d;
    const ang = d * 180 / Math.PI;
    let g = clamp01((hueTol - ang) / hueSoft) * clamp01((ch - chromaMin * sc) / (chromaSoft * sc));
    if (region) g *= clamp01((65 - Math.abs(lab[p * 3] - src[0])) / 15);   // deep folds of a fluorescent cape are ~55 L darker than the swatch
    mask[p] = region ? g * Math.min(1, region[p] * 1.5) : g;
  }
  mask = boxBlur(boxBlur(dilate(mask, w, h, 1), w, h, 1), w, h, 1);
  if (!region) mask = keepLargeParts(mask, w, h);
  const Ls = [], Cs = []; let cnt = 0;
  for (let p = 0; p < N; p++) if (mask[p] > 0.5) { cnt++; if ((p & 3) === 0) { Ls.push(lab[p * 3]); Cs.push(Math.hypot(lab[p * 3 + 1], lab[p * 3 + 2])); } }
  const Lm = Ls.length ? median(Ls) : src[0], cm = Math.max(1, Cs.length ? median(Cs) : sc);
  // inside the region, fade out pixels far less saturated than the fabric: white fur tinted by JPEG bleed would otherwise get a halo
  if (region) for (let p = 0; p < N; p++) if (mask[p] > 0) mask[p] *= clamp01((Math.hypot(lab[p * 3 + 1], lab[p * 3 + 2]) / cm - 0.35) / 0.2);
  const k = dst[0] > Lm + 25 ? 0.85 : 1.0;
  // colour spill: Gemini lets the garment colour glow onto the fur and the seam just outside the garment. Those light,
  // faintly tinted pixels are left out of the mask, so after recolouring they would draw a ring of the old colour.
  // In a thin band around the garment, light pixels tinted like the old colour get the same faint tint of the new one.
  const core = new Float32Array(N); for (let p = 0; p < N; p++) core[p] = mask[p] > 0.3 ? 1 : 0;
  const band = boxBlur(dilate(core, w, h, Math.max(3, Math.round(Math.max(w, h) / 160))), w, h, 2);
  const dc = Math.hypot(dst[1], dst[2]), dAng = Math.atan2(dst[2], dst[1]), spillK = Math.min(1, dc / Math.max(1, sc));
  const spill = new Float32Array(N);
  for (let p = 0; p < N; p++) {
    if (band[p] < 0.02 || mask[p] > 0.98) continue;
    const L = lab[p * 3], a = lab[p * 3 + 1], b = lab[p * 3 + 2], ch = Math.hypot(a, b);
    let d = Math.abs(Math.atan2(b, a) - sang); if (d > Math.PI) d = 2 * Math.PI - d;
    spill[p] = band[p] * clamp01((25 - d * 180 / Math.PI) / 10) * clamp01((ch - 2) / 3) * clamp01((L - 50) / 10) * clamp01((0.75 * cm - ch) / (0.15 * cm) + 1) * (1 - mask[p]);
  }
  const out = Buffer.alloc(N * 3), px = new Float64Array(3);
  for (let p = 0; p < N; p++) {
    const m = mask[p], r = data[p * 3], g = data[p * 3 + 1], b = data[p * 3 + 2];
    if (spill[p] > 0.004) {   // the faint glow: same lightness, same faint chroma, new hue
      const sp = spill[p], ch = Math.hypot(lab[p * 3 + 1], lab[p * 3 + 2]) * spillK;
      fromLab(lab[p * 3], Math.cos(dAng) * ch, Math.sin(dAng) * ch, px, 0);
      out[p * 3] = r * (1 - sp) + px[0] * sp; out[p * 3 + 1] = g * (1 - sp) + px[1] * sp; out[p * 3 + 2] = b * (1 - sp) + px[2] * sp;
      if (m < 0.004) continue;
      const r2 = out[p * 3], g2 = out[p * 3 + 1], b2 = out[p * 3 + 2], L = lab[p * 3], a = lab[p * 3 + 1], bb = lab[p * 3 + 2];
      const sat = 0.85 * Math.min(1.4, Math.max(0.15, Math.hypot(a, bb) / cm));
      fromLab(dst[0] + (L - Lm) * k, dst[1] * sat, dst[2] * sat, px, 0);
      out[p * 3] = r2 * (1 - m) + px[0] * m; out[p * 3 + 1] = g2 * (1 - m) + px[1] * m; out[p * 3 + 2] = b2 * (1 - m) + px[2] * m;
      continue;
    }
    if (m < 0.004) { out[p * 3] = r; out[p * 3 + 1] = g; out[p * 3 + 2] = b; continue; }
    const L = lab[p * 3], a = lab[p * 3 + 1], bb = lab[p * 3 + 2];
    const sat = 0.85 * Math.min(1.4, Math.max(0.15, Math.hypot(a, bb) / cm));   // Gemini paints fabric at ~0.85 of the swatch's chroma
    fromLab(dst[0] + (L - Lm) * k, dst[1] * sat, dst[2] * sat, px, 0);
    out[p * 3] = r * (1 - m) + px[0] * m; out[p * 3 + 1] = g * (1 - m) + px[1] * m; out[p * 3 + 2] = b * (1 - m) + px[2] * m;
  }
  const jpg = await sharp(out, { raw: { width: w, height: h, channels: 3 } }).jpeg({ quality: 88 }).toBuffer();
  return { jpg, share: cnt / N, how, region };
}

// ---------- worker plumbing: all pixel work lives in one worker thread, so the server's main thread is never blocked
if (!isMainThread && parentPort) {
  const regions = new Map();   // per batch (one try-on, several colours): the garment region, computed once
  parentPort.on('message', async ({ id, buf, original, from, to, batch }) => {
    try {
      const opts = { original: original ? Buffer.from(original) : null };
      if (batch && regions.has(batch)) opts.region = regions.get(batch);
      const r = await recolor(Buffer.from(buf), from, to, opts);
      if (batch && !regions.has(batch)) { regions.set(batch, r.region); setTimeout(() => regions.delete(batch), 60000); }
      parentPort.postMessage({ id, jpg: r.jpg, share: r.share, how: r.how });
    } catch (e) { parentPort.postMessage({ id, error: e.message, status: e.status || 0 }); }
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
function inWorker(buf, original, from, to, batch) {
  return new Promise((resolve, reject) => { const id = ++seq; waiting.set(id, { resolve, reject }); const wk = getWorker(); wk.ref(); wk.postMessage({ id, buf, original, from, to, batch }); });   // ref while busy
}
function decode(dataUrl, limit = 6) {
  const m = /^data:image\/(jpeg|png|webp);base64,([A-Za-z0-9+/=]+)$/.exec(dataUrl || '');
  if (!m) throw Object.assign(new Error('bad image'), { status: 400 });
  const buf = Buffer.from(m[2], 'base64');
  if (buf.length > limit * 1024 * 1024) throw Object.assign(new Error('image too large'), { status: 413 });
  return buf;
}
const maybeDecode = img => !img ? null : Buffer.isBuffer(img) ? img : (() => { try { return decode(img); } catch (e) { return null; } })();
const asResult = (r, t0) => ({ image: 'data:image/jpeg;base64,' + Buffer.from(r.jpg).toString('base64'), share: +r.share.toFixed(3), how: r.how, ms: Date.now() - t0 });

export async function recolorDataUrl(dataUrl, fromHex, toHex, original) {
  const buf = decode(dataUrl), t0 = Date.now();
  return asResult(await inWorker(buf, maybeDecode(original), fromHex, toHex, null), t0);
}

// For /api/stylist: recolour the finished picture into every colour the page asked for, in the same response.
// image: the try-on (data URL or Buffer); recolor: {from: "#hex", to: ["#hex", ...]} (at most 6);
// original: the customer's dog photo (data URL or Buffer), optional but what makes the garment region exact.
// Never throws; bad input -> [].
export async function recolorVariants(image, recolor, original) {
  try {
    if (!recolor || !recolor.from || !Array.isArray(recolor.to)) return [];
    const buf = Buffer.isBuffer(image) ? image : decode(image), orig = maybeDecode(original);
    const batch = 'b' + Date.now() + Math.random().toString(36).slice(2);   // the region is found once for all colours
    const out = [];
    for (const to of recolor.to.slice(0, 6)) {
      const t0 = Date.now();
      try { out.push({ hex: to, ...asResult(await inWorker(buf, orig, recolor.from, to, batch), t0) }); } catch (e) { /* skip that colour */ }
    }
    return out;
  } catch (e) { return []; }
}

export function recolorHandler(req, res) {
  const b = req.body || {};
  recolorDataUrl(b.image, b.from, b.to, b.original)
    .then(r => res.json(r))
    .catch(e => res.status(e.status || 500).json({ error: e.status ? e.message : 'recolor unavailable' }));
}
