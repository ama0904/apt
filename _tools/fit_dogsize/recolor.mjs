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
// zbook 2026-10-28: pull the chroma in until the colour exists in sRGB. A grey coat's deep folds asked for "dark neon
// yellow", which does not exist, so fromLab's channel clamp turned them black; the shiny highlights asked for light navy.
function fitLab(L, a, b, out, i) {
  for (let n = 0; n < 6; n++) {
    const fy = (L + 16) / 116, fx = fy + a / 500, fz = fy - b / 200;
    const inv = t => (t * t * t > 0.008856 ? t * t * t : (t - 16 / 116) / 7.787);
    const x = inv(fx) * WHITE[0], y = inv(fy), z = inv(fz) * WHITE[2];
    const r = 3.2406 * x - 1.5372 * y - 0.4986 * z, g = -0.9689 * x + 1.8758 * y + 0.0415 * z, bl = 0.0557 * x - 0.2040 * y + 1.0570 * z;
    if (Math.min(r, g, bl) >= -0.01 && Math.max(r, g, bl) <= 1.01) break;
    a *= 0.7; b *= 0.7;
  }
  fromLab(L, a, b, out, i);
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
// shrink a mask by r pixels (square): what survives was at least 2r+1 wide
function erode(src, w, h, r) {
  const inv = new Float32Array(src.length); for (let i = 0; i < src.length; i++) inv[i] = 1 - src[i];
  const d = dilate(inv, w, h, r); for (let i = 0; i < d.length; i++) d[i] = 1 - d[i];
  return d;
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
// tiny k-means on Lab samples (flat array of L,a,b triples); lightness counts half, the colour direction matters more
const labDist = (L1, a1, b1, L2, a2, b2) => Math.hypot(0.5 * (L1 - L2), a1 - a2, b1 - b2);
function kmeans(samples, k, iters = 8) {
  const n = samples.length / 3; if (n < k) return [];
  const C = []; for (let j = 0; j < k; j++) { const i = Math.floor((j + 0.5) * n / k) * 3; C.push([samples[i], samples[i + 1], samples[i + 2]]); }
  for (let it = 0; it < iters; it++) {
    const S = C.map(() => [0, 0, 0, 0]);
    for (let i = 0; i < samples.length; i += 3) { let best = 0, bd = Infinity;
      for (let j = 0; j < k; j++) { const d = labDist(samples[i], samples[i + 1], samples[i + 2], C[j][0], C[j][1], C[j][2]); if (d < bd) { bd = d; best = j; } }
      const s = S[best]; s[0] += samples[i]; s[1] += samples[i + 1]; s[2] += samples[i + 2]; s[3]++; }
    S.forEach((s, j) => { if (s[3]) C[j] = [s[0] / s[3], s[1] / s[3], s[2] / s[3]]; });
  }
  return C;
}
const median = arr => { if (!arr.length) return NaN; const s = Float64Array.from(arr).sort(); return s[s.length >> 1]; };

// where the try-on differs from the customer's photo = where the garment was painted. null when unusable.
const DAB_LO = 10, DAB_HI = 22, DAB_L0 = 25;   // colour-change gate: chroma-plane distance photo vs try-on (0 at <=10, full at >=22), applied from L 25 (full at 35) up
const CHW = 16, DKL = 10;   // grey garment, deep inside the region: chroma gate widens by CHW (full to 28, off at 40), dark cut-off drops by DKL (L >= 2 is fabric)
const SATW = 1.5;   // weight of the saturation change in the "what changed" measure below (zbook, tested on 83 pairs)
async function changedRegion(original, w, h, tryon) {
  const a = await sharp(original).rotate().resize(w, h, { fit: 'fill' }).blur(3).removeAlpha().raw().toBuffer();
  const b = await sharp(tryon, { raw: { width: w, height: h, channels: 3 } }).blur(3).raw().toBuffer();
  const N = w * h, m = new Float32Array(N);
  let hot = 0;
  for (let p = 0; p < N; p++) {
    // zbook 2026-10-28: a dark navy coat over black fur differs little in plain rgb (black 20,20,25 -> navy 2,24,63 is 60,
    // below the 0.5 point); the shaded half of a 普魯士藍 cape stayed blue on a black shih tzu (ux4). A change of
    // saturation (max - min) counts too: fur has none, fabric of any colour has plenty.
    const sa = Math.max(a[p * 3], a[p * 3 + 1], a[p * 3 + 2]) - Math.min(a[p * 3], a[p * 3 + 1], a[p * 3 + 2]);
    const sb = Math.max(b[p * 3], b[p * 3 + 1], b[p * 3 + 2]) - Math.min(b[p * 3], b[p * 3 + 1], b[p * 3 + 2]);
    const d = Math.abs(a[p * 3] - b[p * 3]) + Math.abs(a[p * 3 + 1] - b[p * 3 + 1]) + Math.abs(a[p * 3 + 2] - b[p * 3 + 2]) + SATW * Math.abs(sa - sb);
    m[p] = clamp01((d - 40) / 64);
    if (m[p] > 0.5) hot++;
  }
  const share = hot / N;
  if (process.env.REGION_DEBUG) console.log('[region] changed share', share.toFixed(3), w + 'x' + h);
  if (share < 0.004 || share > 0.35) return null;   // nothing changed, or Gemini redrew the whole picture (a real garment is ~5-20 %)
  // thin strips are not a garment: a leash, lead or harness that Gemini painted away leaves a narrow band of "changed"
  // background (pavement, sky). Opening the mask (erode, then grow back) drops anything narrower than ~2 % of the picture.
  const bin = new Float32Array(N); for (let p = 0; p < N; p++) bin[p] = m[p] > 0.5 ? 1 : 0;
  const ro = Math.max(3, Math.round(0.009 * Math.max(w, h)));
  const opened = dilate(erode(bin, w, h, ro), w, h, ro);
  // the garment is one or two big pieces; scattered specks are regenerated texture (grass, bokeh) and are dropped
  const bigParts = src => {
    const cs = components(boxBlur(dilate(src, w, h, 2), w, h, 1), w, h, 0.5), big = new Float32Array(N);
    if (!cs.n) return null;
    const largest = Math.max(...cs.areas), minArea = Math.max(0.15 * largest, 0.004 * N);
    for (let p = 0; p < N; p++) if (cs.label[p] && cs.areas[cs.label[p]] >= minArea) big[p] = 1;
    return boxBlur(dilate(big, w, h, 2), w, h, 2);   // the blurred difference already reaches past the garment edge
  };
  // zbook 2026-10-28: two regions. Coloured garments keep the un-opened one (the opening ate cape tips, hem bands and
  // straps on uc2/q95/64q, leaving them in the old colour; their colour gate already rejects a removed leash's background).
  // Grey garments, whose gate is only "low chroma", use the opened one so the leash strip is gone.
  const region = bigParts(m);
  if (!region) return null;
  region.open = bigParts(opened) || region;
  region.diff = m;   // per-pixel "how much changed", for grey garments (white fur next to them did not change)
  // zbook 2026-10-28 (mbv, 萊姆綠 jacket in a rapeseed field): Gemini redraws the flowers next to the garment, so they count
  // as "changed" and the region holds a fringe of them; their yellow is within the hue tolerance of lime green, so the
  // fringe was recoloured. A garment always changes a pixel's COLOUR a lot (fur -> fabric); redrawn background keeps its
  // colour and only moves texture. region.dab = chroma-plane (a,b) distance between the blurred photo and the blurred
  // try-on; coloured garments fade their mask out below DAB_LO and keep it fully above DAB_HI.
  const dab = new Float32Array(N), la = new Float64Array(3), lb = new Float64Array(3);
  const Lb = new Float32Array(N), Ab = new Float32Array(N), Bb = new Float32Array(N);
  for (let p = 0; p < N; p++) {
    toLab(a[p * 3], a[p * 3 + 1], a[p * 3 + 2], la, 0); toLab(b[p * 3], b[p * 3 + 1], b[p * 3 + 2], lb, 0);
    dab[p] = Math.hypot(la[1] - lb[1], la[2] - lb[2]);
    Lb[p] = lb[0]; Ab[p] = lb[1]; Bb[p] = lb[2];
  }
  region.dab = boxBlur(dab, w, h, 2);
  // zbook 2026-10-28 (s1b, 萊姆綠 jacket, labrador held on a lead): Gemini painted the handler away and filled the hole with
  // grass. That grass is a big "changed" area, its colour changed a lot (jeans -> grass, so the dab gate keeps it) and
  // its yellow-green passes the lime hue gate, so a tall band of grass turned 冰川藍 / 芬達桔. Repainted background looks
  // like the UNCHANGED background around it; a garment never does. region.bgsim[p] = 1 when the try-on at p looks like
  // the mean colour of the unchanged pixels nearby (reach 5 % of the long side, 15 % deep inside a wide band): both the
  // local mean over region pixels (radius 8, L weighted half: grass varies in L) within 14..26 and the pixel itself
  // within 24..38 (full L weight: the lit rim of a coat is 35 L lighter than the grass behind it). Coloured garments
  // multiply their mask by 1 - bgsim, except next to the garment's confident body (see recolor).
  {
    const S = Math.max(w, h), bg = new Float32Array(N);
    for (let p = 0; p < N; p++) bg[p] = region[p] < 0.05 ? 1 : 0;
    const est = r => {
      const c = boxBlur(bg, w, h, r), L = new Float32Array(N), A = new Float32Array(N), B = new Float32Array(N);
      for (let p = 0; p < N; p++) if (bg[p]) { L[p] = Lb[p]; A[p] = Ab[p]; B[p] = Bb[p]; }
      return { c, L: boxBlur(L, w, h, r), A: boxBlur(A, w, h, r), B: boxBlur(B, w, h, r) };
    };
    const e1 = est(Math.round(0.05 * S)), e2 = est(Math.round(0.15 * S));
    const fg = new Float32Array(N), fL = new Float32Array(N), fA = new Float32Array(N), fB = new Float32Array(N);
    for (let p = 0; p < N; p++) if (!bg[p]) { fg[p] = 1; fL[p] = Lb[p]; fA[p] = Ab[p]; fB[p] = Bb[p]; }
    const fc = boxBlur(fg, w, h, 8), mL = boxBlur(fL, w, h, 8), mA = boxBlur(fA, w, h, 8), mB = boxBlur(fB, w, h, 8);
    const sim = new Float32Array(N);
    for (let p = 0; p < N; p++) {
      if (bg[p]) continue;
      const e = e1.c[p] >= 0.08 ? e1 : (e2.c[p] >= 0.03 ? e2 : null);
      if (!e || fc[p] < 0.05) continue;
      const c = e.c[p], eL = e.L[p] / c, eA = e.A[p] / c, eB = e.B[p] / c, k = fc[p];
      const dMean = Math.hypot(0.5 * (mL[p] / k - eL), mA[p] / k - eA, mB[p] / k - eB);
      const dPix = Math.hypot(Lb[p] - eL, Ab[p] - eA, Bb[p] - eB);
      sim[p] = Math.min(1 - clamp01((dMean - 14) / 12), 1 - clamp01((dPix - 24) / 14));
    }
    // strips of similarity along the garment's edge (the grass-like blend Gemini paints there, x69/v41) are not repainted
    // background: only patches of at least 1 % of the picture count (the handler-shaped hole on s1b/pp9 is 10-20 %)
    const cs = components(sim, w, h, 0.5), minArea = 0.01 * N;
    for (let p = 0; p < N; p++) if (cs.label[p] && cs.areas[cs.label[p]] < minArea) sim[p] = 0;
    region.bgsim = sim;   // no blur: it bled 4 px of "grass" into the coat's top edge (x69, v41)
  }
  // zbook: deep inside the opened region everything is garment, however little it differs from the fur it covers (a grey
  // coat over grey/white fur); the per-pixel diff gate is only needed near the region's edge, where fur can be
  const ob = new Float32Array(N); for (let p = 0; p < N; p++) ob[p] = region.open[p] > 0.5 ? 1 : 0;
  region.core = boxBlur(erode(ob, w, h, 2 * ro), w, h, 2);
  return region;
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
  // a grey garment (太空灰) has no hue to look for: the fabric is the low-chroma pixels near its lightness, inside the region
  const neutral = sc < 10;
  const hueTol = region ? 40 : tol, hueSoft = region ? 15 : 10, chromaMin = region ? 0.10 : 0.18, chromaSoft = region ? 0.10 : 0.12;
  let mask = new Float32Array(N);
  const R = neutral && region && region.open ? region.open : region;   // grey: the opened region (no leash strips)
  // zbook 2026-10-28: Gemini paints the garment's outline as a blend with the background (grass-like, half the chroma,
  // 20-30 px wide along a lime coat; its lit rim is pale too), and the background-similarity gate (region.bgsim) would
  // eat that. The garment's confident body = pixels of the swatch's hue (within 10°) with chroma >= 0.8 of the swatch,
  // inside the region, opened by 4 px so single grass blades of that colour don't count; everything within 1.5 % of the
  // long side of that body is exempt from the gate.
  let protect = null;
  if (region && !neutral && region.bgsim) {
    const conf = new Float32Array(N);
    for (let p = 0; p < N; p++) {
      if (region[p] < 0.5) continue;
      const a = lab[p * 3 + 1], b = lab[p * 3 + 2], ch = Math.hypot(a, b);
      let d = Math.abs(Math.atan2(b, a) - sang); if (d > Math.PI) d = 2 * Math.PI - d;
      // the lit rim / top of a coat is near-white with a third of the swatch's chroma; grass never gets that light
      if (d < 10 * Math.PI / 180 && (ch >= 0.8 * sc || (lab[p * 3] >= 88 && ch >= 0.35 * sc))) conf[p] = 1;
    }
    protect = dilate(dilate(erode(conf, w, h, 4), w, h, 4), w, h, Math.max(6, Math.round(0.015 * Math.max(w, h))));
    if (process.env.BGSIM_DEBUG) { const u = Buffer.alloc(N * 3); for (let p = 0; p < N; p++) { u[p * 3] = Math.round(region.bgsim[p] * 255); u[p * 3 + 1] = Math.round(protect[p] * 255); u[p * 3 + 2] = conf[p] ? 255 : (region[p] >= 0.5 ? 90 : 0); } await sharp(u, { raw: { width: w, height: h, channels: 3 } }).png().toFile(process.env.BGSIM_DEBUG); }
  }
  for (let p = 0; p < N; p++) {
    if (R && R[p] < 0.01) continue;
    const a = lab[p * 3 + 1], b = lab[p * 3 + 2], ch = Math.hypot(a, b);
    let d = Math.abs(Math.atan2(b, a) - sang); if (d > Math.PI) d = 2 * Math.PI - d;
    const ang = d * 180 / Math.PI;
    // grey inside the painted region: any low-chroma pixel from deep shadow to the shiny highlights (they span ~10-95 L);
    // without a region only pixels near the swatch's lightness
    // and only where the picture really changed: unchanged white or grey fur along the coat stays as it was
    // zbook 2026-10-28 (qwj, labrador in 太空灰): Gemini paints the grey with a blue cast (chroma 16-24), where (24-ch)/8 gives
    // half a mask, so the whole coat came out mottled and translucent; the dark spots of a camo lining (L < 6) stayed black.
    // Deep inside the garment (region.core) everything is garment: the chroma gate widens to CHW more and the dark cut-off
    // drops by DKL there. At the edge the strict gates stay (fur, grass).
    const cc = neutral && region && region.core ? region.core[p] : 0;
    let g = neutral ? (region ? clamp01((24 + CHW * cc - ch) / (8 + 4 * cc)) * clamp01((97 - lab[p * 3]) / 6) * clamp01((lab[p * 3] - 6 + DKL * cc) / 6) * (region.diff ? Math.max(cc, clamp01(region.diff[p] * 2)) : 1)
                              : clamp01((14 - ch) / 6) * clamp01((42 - Math.abs(lab[p * 3] - src[0])) / 14))
                    : clamp01((hueTol - ang) / hueSoft) * clamp01((ch - chromaMin * sc) / (chromaSoft * sc));
    if (region && !neutral) g *= clamp01((65 - Math.abs(lab[p * 3] - src[0])) / 15);   // deep folds of a fluorescent cape are ~55 L darker than the swatch
    // see changedRegion: redrawn same-colour background (flowers, grass) is not garment. Only for mid/light pixels: a dark
    // navy fold over black fur is also a small colour change, and those folds are what the dark-coat fix above recovers.
    if (region && !neutral && region.dab) g *= 1 - clamp01((lab[p * 3] - DAB_L0) / 10) * (1 - clamp01((region.dab[p] - DAB_LO) / (DAB_HI - DAB_LO)));
    // see changedRegion: repainted background that looks like the unchanged background next to it, away from the body
    if (protect) g *= 1 - clamp01((lab[p * 3] - DAB_L0) / 10) * region.bgsim[p] * (1 - protect[p]);
    mask[p] = R ? g * Math.min(1, R[p] * 1.5) : g;
  }
  mask = boxBlur(boxBlur(dilate(mask, w, h, 1), w, h, 1), w, h, 1);
  if (!region) {
    mask = keepLargeParts(mask, w, h);
    // zbook 2026-10-28 (stress test, border terrier on a lawn): when Gemini re-frames the whole picture there is no usable
    // region, and the colour gate alone painted the entire field 冰川藍. A garment is 5-30 % of the picture; a bigger mask
    // is background, and no variant is better than a blue lawn (the caller skips that colour).
    let big = 0; for (let p = 0; p < N; p++) if (mask[p] > 0.5) big++;
    if (big > 0.35 * N) throw Object.assign(new Error('garment not found (mask ' + (big / N).toFixed(2) + ' of the picture)'), { status: 422 });
  }
  let surround = null;   // colour clusters of what surrounds the garment (grass, fur), learnt below
  // edge check: what surrounds the garment (grass, fur) is learnt from a ring just outside it; an edge pixel that looks
  // more like those surroundings than like the fabric is not recoloured. Yellow-green capes on grass otherwise paint a
  // frame of the new colour onto the grass and the fur along the garment's outline.
  {
    const sc2 = Math.max(1, Math.round(Math.max(w, h) / 640));
    const core0 = new Float32Array(N); for (let p = 0; p < N; p++) core0[p] = mask[p] > 0.5 ? 1 : 0;
    const inner = dilate(core0, w, h, 4 * sc2), outer = dilate(core0, w, h, 12 * sc2);
    const fab = [], sur = [];
    for (let p = 0; p < N; p += 2) {
      if (mask[p] > 0.85 && fab.length < 60000) fab.push(lab[p * 3], lab[p * 3 + 1], lab[p * 3 + 2]);
      else if (outer[p] > 0 && inner[p] === 0 && sur.length < 60000) sur.push(lab[p * 3], lab[p * 3 + 1], lab[p * 3 + 2]);
    }
    const F = kmeans(fab, 3);
    if (F.length) {
      // surroundings that are really fabric the mask missed must not count as "surroundings"
      const sur2 = []; for (let i = 0; i < sur.length; i += 3) { let df = Infinity; for (const c of F) df = Math.min(df, labDist(sur[i], sur[i + 1], sur[i + 2], c[0], c[1], c[2])); if (df > 14) sur2.push(sur[i], sur[i + 1], sur[i + 2]); }
      const B = kmeans(sur2, 4);
      if (B.length) surround = B;
      // opts.edge: 0 (default) = off. Tested on 11 real pairs on the laptop, the check left a ragged dark outline on a
      // cape's hem, a yellow seam where a bright specular edge looked like white fur, and blotches where hem shadows looked
      // like fur. 1 = apply it. The clusters are still learnt: the spill pass needs them.
      if (B.length && (opts.edge || 0) === 1) for (let p = 0; p < N; p++) {
        if (mask[p] < 0.004 || mask[p] > 0.97) continue;
        const L = lab[p * 3], a = lab[p * 3 + 1], b = lab[p * 3 + 2];
        let df = Infinity, db = Infinity;
        for (const c of F) df = Math.min(df, labDist(L, a, b, c[0], c[1], c[2]));
        for (const c of B) db = Math.min(db, labDist(L, a, b, c[0], c[1], c[2]));
        mask[p] *= clamp01((db - df) / 12 + 0.5);
      }
      // opts.edge 5: the same check, but only against coloured surroundings (grass, foliage: chroma > 12) and only for
      // pixels clearly closer to them than to the fabric. Neutral clusters (white fur, specular edges, shadows) never
      // remove fabric, which is where mode 1 went wrong; grass next to a yellow-green cape still stays grass.
      const Bc = B.filter(c => Math.hypot(c[1], c[2]) > 12);
      if (Bc.length && (opts.edge || 0) === 5) for (let p = 0; p < N; p++) {
        if (mask[p] < 0.004 || mask[p] > 0.97) continue;
        const L = lab[p * 3], a = lab[p * 3 + 1], b = lab[p * 3 + 2];
        let df = Infinity, db = Infinity;
        for (const c of F) df = Math.min(df, labDist(L, a, b, c[0], c[1], c[2]));
        for (const c of Bc) db = Math.min(db, labDist(L, a, b, c[0], c[1], c[2]));
        mask[p] *= clamp01((db - df) / 10 + 1);
      }
      // opts.edge 6: mode 5, but a pixel whose hue is within ~12° of the fabric's own measured hue is always fabric, however
      // dark (hem shadows of a yellow cape are dark olive, of a pink coat dark pink); only pixels of another hue (grass is
      // ~20-30° greener than a yellow-green cape) can be given back to the surroundings.
      let fh = 0, fn = 0, fx = 0, fy = 0;
      for (let p = 0; p < N; p += 3) if (mask[p] > 0.85) { const a = lab[p * 3 + 1], b = lab[p * 3 + 2], c = Math.hypot(a, b); if (c > 5) { fx += a / c; fy += b / c; fn++; } }
      fh = Math.atan2(fy, fx);
      if (fn && Bc.length && (opts.edge || 0) === 6) for (let p = 0; p < N; p++) {
        if (mask[p] < 0.004 || mask[p] > 0.97) continue;
        const L = lab[p * 3], a = lab[p * 3 + 1], b = lab[p * 3 + 2];
        let d = Math.abs(Math.atan2(b, a) - fh); if (d > Math.PI) d = 2 * Math.PI - d;
        const keep = clamp01((16 - d * 180 / Math.PI) / 8);   // 1 within 8°, 0 beyond 16°
        if (keep >= 1) continue;
        let df = Infinity, db = Infinity;
        for (const c of F) df = Math.min(df, labDist(L, a, b, c[0], c[1], c[2]));
        for (const c of Bc) db = Math.min(db, labDist(L, a, b, c[0], c[1], c[2]));
        const m5 = clamp01((db - df) / 10 + 1);
        mask[p] *= keep + (1 - keep) * m5;
      }
    }
  }
  const Ls = [], Cs = []; let cnt = 0;
  for (let p = 0; p < N; p++) if (mask[p] > 0.5) { cnt++; if ((p & 3) === 0) { Ls.push(lab[p * 3]); Cs.push(Math.hypot(lab[p * 3 + 1], lab[p * 3 + 2])); } }
  const Lm = Ls.length ? median(Ls) : src[0], cm = Math.max(1, Cs.length ? median(Cs) : sc);
  // inside the region, fade out pixels far less saturated than the fabric: white fur tinted by JPEG bleed would otherwise get a halo
  // zbook 2026-10-28: the background-similarity gate removes low-chroma junk from the mask, which raises this median and
  // made the fade eat the garment's own outline (a blend of half the fabric's chroma, x69/s1b). Next to the confident
  // body (protect) the fade starts at 0.2 instead of 0.35.
  if (region && !neutral) for (let p = 0; p < N; p++) if (mask[p] > 0) mask[p] *= clamp01((Math.hypot(lab[p * 3 + 1], lab[p * 3 + 2]) / cm - (protect && protect[p] ? 0.2 : 0.35)) / 0.2);
  // zbook 2026-10-28: holes inside the fabric. The deepest folds of a dark coat (L < ~15, a faint tint of the old hue) are
  // too dull for that fade and were left as navy blobs in a yellow coat (black shih tzu, ux4). A dark pixel of the old hue
  // that lies inside the fabric's outline (closing of the mask, ~2 % of the picture) is fabric; at the outline it is left
  // alone, so black fur with a little blue bleed along the edge is not lifted.
  if (region && !neutral) {
    const mc = new Float32Array(N); for (let p = 0; p < N; p++) mc[p] = mask[p] > 0.5 ? 1 : 0;
    const rc = Math.max(4, Math.round(0.02 * Math.max(w, h)));
    const closed = erode(dilate(mc, w, h, rc), w, h, rc);
    for (let p = 0; p < N; p++) {
      if (closed[p] < 0.5 || mask[p] > 0.9) continue;
      const L = lab[p * 3]; if (L >= 18) continue;
      const a = lab[p * 3 + 1], b = lab[p * 3 + 2], ch = Math.hypot(a, b); if (ch < 5) continue;
      let d = Math.abs(Math.atan2(b, a) - sang); if (d > Math.PI) d = 2 * Math.PI - d;
      const g = clamp01((hueTol - d * 180 / Math.PI) / hueSoft) * clamp01((ch - 5) / 5) * clamp01((18 - L) / 6) * Math.min(1, region[p] * 1.5);
      if (g > mask[p]) mask[p] = g;
    }
  }
  // much lighter target: compress the shading (a shiny grey coat spans ~60 L; on neon yellow that would blow out to white)
  const k = dst[0] > Lm + 25 ? (neutral ? 0.5 : 0.85) : 1.0;
  // colour spill: Gemini lets the garment colour glow onto the fur and the seam just outside the garment. Those light,
  // faintly tinted pixels are left out of the mask, so after recolouring they would draw a ring of the old colour.
  // In a thin band around the garment, light pixels tinted like the old colour get the same faint tint of the new one.
  const core = new Float32Array(N); for (let p = 0; p < N; p++) core[p] = mask[p] > 0.3 ? 1 : 0;
  const band = boxBlur(dilate(core, w, h, Math.max(3, Math.round(Math.max(w, h) / 160))), w, h, 2);
  // Only the tint a pixel has beyond its surroundings' own colour is swapped (cream fur stays cream; its yellow glow goes).
  const dc = Math.hypot(dst[1], dst[2]), spillK = Math.min(1, dc / Math.max(1, sc));
  const ux = src[1] / Math.max(1, sc), uy = src[2] / Math.max(1, sc), vx = dst[1] / Math.max(1, dc), vy = dst[2] / Math.max(1, dc);
  const refs = surround && surround.length ? surround : [[70, 0, 0]];
  // zbook 2026-10-28: the deepest folds of a dark coat (L < ~15, a faint tint of the old hue) are too dull for the chroma
  // fade above, and on black fur they cannot be told from fur anyway. They are not lifted to the new colour, but their
  // tint is turned to the new hue at their own lightness: a near-black fold stays a near-black fold instead of a navy blob
  // on a yellow coat. Black fur with a little blue bleed stays black.
  const dark = new Float32Array(N);
  if (region && !neutral) for (let p = 0; p < N; p++) {
    const L = lab[p * 3]; if (L >= 18 || mask[p] > 0.6 || region[p] < 0.2) continue;
    const a = lab[p * 3 + 1], b = lab[p * 3 + 2], ch = Math.hypot(a, b); if (ch < 5) continue;
    let d = Math.abs(Math.atan2(b, a) - sang); if (d > Math.PI) d = 2 * Math.PI - d;
    const g = clamp01((hueTol - d * 180 / Math.PI) / hueSoft) * clamp01((ch - 5) / 5) * clamp01((18 - L) / 6);
    if (g > 0) dark[p] = g * Math.min(1, region[p] * 1.5) * (1 - mask[p]);
  }
  const spill = new Float32Array(N), spillAB = new Float32Array(N * 2);
  for (let p = 0; p < N; p++) {
    if (neutral || band[p] < 0.02 || mask[p] > 0.98) continue;   // a grey garment casts no coloured glow
    const L = lab[p * 3], a = lab[p * 3 + 1], b = lab[p * 3 + 2];
    if (L < 45) continue;
    let c = refs[0], bd = Infinity;
    for (const r of refs) { const d = Math.hypot(a - r[1], b - r[2]) + 0.25 * Math.abs(L - r[0]); if (d < bd) { bd = d; c = r; } }
    const ex = Math.min(0.6 * cm, (a - c[1]) * ux + (b - c[2]) * uy);   // how far the pixel leans toward the old colour
    if (ex < 1.5) continue;
    // opts.spill: 2 (default) = only where the nearest surroundings are neutral and light (fur, skin, walls), never grass:
    // grass next to a yellow-green cape also leans toward the old colour and got a light halo. 1 = any surroundings.
    if ((opts.spill || 2) === 2 && (Math.hypot(c[1], c[2]) > 12 || L < 55)) continue;   // zbook: the PIXEL must be light (c[0] < 55 left the pink glow on the dachshund's leg, 64q)
    spill[p] = band[p] * clamp01((L - 45) / 10) * clamp01((ex - 1.5) / 3) * (1 - mask[p]);
    spillAB[p * 2] = a - ex * ux + ex * spillK * vx; spillAB[p * 2 + 1] = b - ex * uy + ex * spillK * vy;
  }
  const out = Buffer.alloc(N * 3), px = new Float64Array(3);
  for (let p = 0; p < N; p++) {
    const m = mask[p]; let r = data[p * 3], g = data[p * 3 + 1], b = data[p * 3 + 2];
    if (dark[p] > 0.004) {   // deep fold: same lightness and chroma, new hue (see above)
      const dk = dark[p], ch = Math.hypot(lab[p * 3 + 1], lab[p * 3 + 2]) * spillK;
      fromLab(lab[p * 3], ch * vx, ch * vy, px, 0);
      r = r * (1 - dk) + px[0] * dk; g = g * (1 - dk) + px[1] * dk; b = b * (1 - dk) + px[2] * dk;
    }
    if (spill[p] > 0.004) {   // the faint glow: same lightness, same faint chroma, new hue
      const sp = spill[p];
      fromLab(lab[p * 3], spillAB[p * 2], spillAB[p * 2 + 1], px, 0);
      out[p * 3] = r * (1 - sp) + px[0] * sp; out[p * 3 + 1] = g * (1 - sp) + px[1] * sp; out[p * 3 + 2] = b * (1 - sp) + px[2] * sp;
      if (m < 0.004) continue;
      const r2 = out[p * 3], g2 = out[p * 3 + 1], b2 = out[p * 3 + 2], L = lab[p * 3], a = lab[p * 3 + 1], bb = lab[p * 3 + 2];
      const sat = 0.85 * Math.min(1.4, Math.max(0.15, Math.hypot(a, bb) / cm)) * (neutral ? 0 : 1) + (neutral ? 0.9 : 0);
      (neutral ? fitLab : fromLab)(neutral ? Math.min(96, dst[0] + (L - Lm) * k) : dst[0] + (L - Lm) * k, dst[1] * sat, dst[2] * sat, px, 0);
      out[p * 3] = r2 * (1 - m) + px[0] * m; out[p * 3 + 1] = g2 * (1 - m) + px[1] * m; out[p * 3 + 2] = b2 * (1 - m) + px[2] * m;
      continue;
    }
    if (m < 0.004) { out[p * 3] = r; out[p * 3 + 1] = g; out[p * 3 + 2] = b; continue; }
    const L = lab[p * 3], a = lab[p * 3 + 1], bb = lab[p * 3 + 2];
    const sat = 0.85 * Math.min(1.4, Math.max(0.15, Math.hypot(a, bb) / cm)) * (neutral ? 0 : 1) + (neutral ? 0.9 : 0);   // Gemini paints fabric at ~0.85 of the swatch's chroma
    (neutral ? fitLab : fromLab)(neutral ? Math.min(96, dst[0] + (L - Lm) * k) : dst[0] + (L - Lm) * k, dst[1] * sat, dst[2] * sat, px, 0);   // zbook: a glossy highlight above L 100 came out white
    out[p * 3] = r * (1 - m) + px[0] * m; out[p * 3 + 1] = g * (1 - m) + px[1] * m; out[p * 3 + 2] = b * (1 - m) + px[2] * m;
  }
  const jpg = await sharp(out, { raw: { width: w, height: h, channels: 3 } }).jpeg({ quality: 88 }).toBuffer();
  return opts.debug ? { jpg, share: cnt / N, how, region, mask, spill, w, h } : { jpg, share: cnt / N, how, region };
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
