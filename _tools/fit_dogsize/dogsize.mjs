// Dog breed + size guess for the fitting room, run on the server (CPU, about 0.1-0.3 s per photo). Version 3.
//
//   const { dogSizeHandler, warmup } = await import('./dogsize.mjs');
//   app.post('/api/dogsize', dogSizeHandler);   // behind the same auth / CORS as /api/stylist
//
// Model files (not downloaded automatically): unzip dogsize-v2.zip from _tools/fit_dogsize in the repo into FIT_MODEL_DIR
// (default: ./models next to this file) so that <FIT_MODEL_DIR>/dogsize-v2/onnx/model_quantized.onnx exists.
// It is facebook/convnext-tiny-224 (ImageNet-1k, Apache-2.0), 8-bit ONNX by Xenova, with one extra output: the 768
// pooled image features. Two small classifiers next to this file, both trained on labelled dog photos:
//   size_head.json  - breed scores + image features -> small / medium / large (S = small capes, L = big raincoat)
//   breed_head.json - image features -> ~55 breeds common in Taiwan, including dachshund, shiba and Taiwan dog,
//                     which the ImageNet model does not know (optional: without it the ImageNet breed names are used)
// Needs: @huggingface/transformers (3.7+) and onnxruntime-node (comes with it).
import { AutoProcessor, RawImage, env } from '@huggingface/transformers';
import ort from 'onnxruntime-node';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const MODEL_DIR = process.env.FIT_MODEL_DIR || path.join(HERE, 'models');
const MODEL = 'dogsize-v2';
env.allowRemoteModels = false;
env.allowLocalModels = true;
env.localModelPath = MODEL_DIR.replace(/[\\/]?$/, '/');

const head = JSON.parse(fs.readFileSync(path.join(HERE, 'size_head.json'), 'utf8'));
const FIRST = head.first || 151, ND = head.nDog || 125;       // ImageNet dog classes 151..275
if (head.mu.length !== ND + 768) throw new Error('size_head.json does not match this module');
let breedHead = null;
try { breedHead = JSON.parse(fs.readFileSync(path.join(HERE, 'breed_head.json'), 'utf8')); } catch (e) { /* optional */ }
if (breedHead && breedHead.mu.length !== 768) throw new Error('breed_head.json does not match this module');
const ZH = ("吉娃娃 日本狆 馬爾濟斯 北京犬 西施犬 查理士王小獵犬 蝴蝶犬 玩具㹴 羅德西亞背脊犬 阿富汗獵犬 巴吉度獵犬 米格魯 尋血獵犬 藍斑獵浣熊犬 黑褐獵浣熊犬 "
  + "沃克獵浣熊犬 英國獵狐犬 紅骨獵浣熊犬 俄羅斯獵狼犬 愛爾蘭獵狼犬 義大利靈緹 惠比特犬 依比沙獵犬 挪威獵麋犬 奧達獵犬 薩路基獵犬 蘇格蘭獵鹿犬 威瑪獵犬 "
  + "斯塔福郡鬥牛㹴 美國斯塔福郡㹴 貝林登㹴 邊境㹴 凱利藍㹴 愛爾蘭㹴 諾福克㹴 諾威奇㹴 約克夏㹴 剛毛獵狐㹴 湖畔㹴 西里漢㹴 萬能㹴 凱恩㹴 澳洲㹴 "
  + "丹第丁蒙㹴 波士頓㹴 迷你雪納瑞 巨型雪納瑞 標準雪納瑞 蘇格蘭㹴 西藏㹴 絲毛㹴 愛爾蘭軟毛㹴 西高地白㹴 拉薩犬 平毛尋回犬 捲毛尋回犬 黃金獵犬 拉布拉多 "
  + "乞沙比克獵犬 德國短毛指示犬 維茲拉犬 英國雪達犬 愛爾蘭雪達犬 戈登雪達犬 布列塔尼獵犬 克倫伯獵犬 英國史賓格犬 威爾斯史賓格犬 可卡犬 蘇塞克斯獵犬 "
  + "愛爾蘭水獵犬 庫瓦茲犬 舒柏奇犬 比利時牧羊犬 比利時瑪利諾犬 伯瑞犬 澳洲卡爾比犬 可蒙犬 古代牧羊犬 喜樂蒂牧羊犬 柯利牧羊犬 邊境牧羊犬 法蘭德斯畜牧犬 "
  + "羅威那 德國牧羊犬 杜賓犬 迷你品 大瑞士山地犬 伯恩山犬 阿彭策爾山犬 恩特雷布赫山犬 拳師犬 鬥牛獒 藏獒 法國鬥牛犬 大丹犬 聖伯納犬 愛斯基摩犬 "
  + "阿拉斯加雪橇犬 西伯利亞哈士奇 大麥町 猴㹴 巴仙吉犬 巴哥犬 蘭伯格犬 紐芬蘭犬 大白熊犬 薩摩耶 博美 鬆獅犬 荷蘭毛獅犬 布魯塞爾格林芬犬 "
  + "柯基（潘布魯克） 柯基（卡提根） 玩具貴賓 迷你貴賓 標準貴賓 墨西哥無毛犬 灰狼 白狼 紅狼 郊狼 澳洲野犬 豺 非洲野犬").split(' ');

// ImageNet classes the breed classifier has no photos of, but whose size is never in doubt. When the ImageNet model is
// sure about one of them (>= 60 % of its dog probability), its name and size win over the trained heads.
const GIANT = new Set([160, 163, 170, 177, 222, 228, 229, 233, 238, 243, 244, 246, 247, 255, 256, 257]);   // hounds, mastiffs, mountain dogs
const TINY = new Set([151, 152, 153, 154, 155, 156, 157, 158, 185, 186, 187, 193, 194, 201, 252, 259, 262, 265]);   // toy breeds
const SURE = 0.6;

let modelP = null;
function load() {
  if (!modelP) modelP = (async () => {
    const dir = path.join(MODEL_DIR, MODEL);
    const labels = JSON.parse(fs.readFileSync(path.join(dir, 'config.json'), 'utf8')).id2label;
    const processor = await AutoProcessor.from_pretrained(MODEL);
    const session = await ort.InferenceSession.create(path.join(dir, 'onnx', 'model_quantized.onnx'),
      { intraOpNumThreads: 2, interOpNumThreads: 1 });     // leave CPU for the Gemini browser jobs
    return { processor, session, labels };
  })().catch(e => { modelP = null; throw e; });
  return modelP;
}
export const warmup = () => load().then(() => true);

function softmax(a) {
  let m = -Infinity; for (const v of a) if (v > m) m = v;
  const e = Array.from(a, v => Math.exp(v - m)); const s = e.reduce((x, y) => x + y, 0);
  return e.map(v => v / s);
}
// standardised linear layer: z = b + sum((x - mu) / sd * W)
function linear(h, x) {
  const z = h.b.slice(), n = h.mu.length;
  for (let i = 0; i < n; i++) {
    const v = (x[i] - h.mu[i]) / h.sd[i];
    if (v) { const w = h.W[i]; for (let c = 0; c < z.length; c++) z[c] += v * w[c]; }
  }
  return z;
}

function analyze(logits, pooled, labels) {
  const p = softmax(logits);
  let dog = 0; for (let i = 0; i < ND; i++) dog += p[FIRST + i];
  const inTop = [];
  for (let i = 0; i < ND; i++) inTop.push([FIRST + i, p[FIRST + i]]);
  inTop.sort((a, b) => b[1] - a[1]);
  const imagenet = inTop.slice(0, 3).map(([i, s]) => ({ id: i, name: String(labels[i]).split(',')[0], zh: ZH[i - FIRST], p: +(s / (dog || 1)).toFixed(3) }));
  const r = { dog: +dog.toFixed(3), top: imagenet, imagenet, P: null, guess: null };
  if (dog < head.minDog) return r;
  // breed (own classifier on the image features; knows dachshund / shiba / Taiwan dog)
  if (breedHead) {
    const bp = softmax(linear(breedHead, pooled));
    const order = bp.map((v, i) => i).sort((a, b) => bp[b] - bp[a]).slice(0, 3);
    r.top = order.map(i => ({ zh: breedHead.classes[i], name: (breedHead.classes_en || breedHead.classes)[i], p: +bp[i].toFixed(3) }));
    r.breedSure = bp[order[0]] >= 0.5;    // below this the photo may be a mixed breed or a breed we have no photos of
  }
  // size
  const x = new Float64Array(ND + 768);
  for (let i = 0; i < ND; i++) x[i] = Math.log(p[FIRST + i] / dog + head.eps);
  for (let i = 0; i < 768; i++) x[ND + i] = pooled[i];
  const z = linear(head, x);
  const m = Math.max(...z), e = z.map(v => Math.exp(v - m)), s = e[0] + e[1] + e[2];
  r.P = e.map(v => +(v / s).toFixed(3));
  r.guess = r.P[0] >= 0.7 ? 'S' : r.P[2] >= 0.7 ? 'L' : null;   // S = small capes, L = big raincoat, null = no hint
  const [tid, tp] = inTop[0], share = tp / dog;
  if (share >= SURE && (GIANT.has(tid) || TINY.has(tid))) {
    r.guess = GIANT.has(tid) ? 'L' : 'S';
    r.top = [imagenet[0], ...r.top.filter(x => x.zh !== imagenet[0].zh)].slice(0, 3);
    r.breedSure = true; r.byImagenet = true;
  }
  return r;
}

// one photo at a time, so a burst of uploads cannot starve the Gemini jobs
let chain = Promise.resolve();
export function dogSize(dataUrl) {
  const run = async () => {
    const m = /^data:image\/(jpeg|png|webp);base64,([A-Za-z0-9+/=]+)$/.exec(dataUrl || '');
    if (!m) throw Object.assign(new Error('bad image'), { status: 400 });
    const buf = Buffer.from(m[2], 'base64');
    if (buf.length > 800 * 1024) throw Object.assign(new Error('image too large'), { status: 413 });
    const { processor, session, labels } = await load();
    let img;
    try { img = await RawImage.fromBlob(new Blob([buf])); } catch (e) { throw Object.assign(new Error('bad image'), { status: 400 }); }
    const t0 = Date.now();
    const inputs = await processor(img);
    const pv = inputs.pixel_values;
    const out = await session.run({ pixel_values: new ort.Tensor('float32', pv.data, pv.dims) });
    return { ...analyze(out.logits.data, out.pooled.data, labels), ms: Date.now() - t0 };
  };
  const p = chain.then(run, run);
  chain = p.catch(() => {});
  return p;
}

export function dogSizeHandler(req, res) {
  dogSize(req.body && req.body.image)
    .then(r => res.json(r))
    .catch(e => res.status(e.status || 500).json({ error: e.status ? e.message : 'dog size unavailable' }));
}
