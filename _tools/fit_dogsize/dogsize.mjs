// Dog breed + size guess for the fitting room, run on the server (CPU, about 0.1-0.3 s per photo).
//
//   import { dogSize, dogSizeHandler } from './dogsize.mjs';
//   app.post('/api/dogsize', express.json({ limit: '1mb' }), dogSizeHandler);   // behind the same auth / CORS as /api/stylist
//
// Model: facebook/convnext-tiny-224 (ImageNet-1k, Apache-2.0), 8-bit ONNX by Xenova (about 28 MB).
// Downloaded once from Hugging Face into FIT_MODEL_DIR (default: ./models next to this file), then loaded from disk.
// Needs: npm i @huggingface/transformers@3.7.2  (pulls onnxruntime-node; no GPU needed)
// size_head.json (next to this file) is a small classifier trained on ~2,300 labelled dog photos: breed scores -> S / M / L.
import { pipeline, env, RawImage } from '@huggingface/transformers';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const HERE = path.dirname(fileURLToPath(import.meta.url));
env.cacheDir = process.env.FIT_MODEL_DIR || path.join(HERE, 'models');
env.allowLocalModels = false;           // always resolve the Hugging Face id through the cache dir

const MODEL = 'Xenova/convnext-tiny-224';
const head = JSON.parse(fs.readFileSync(path.join(HERE, 'size_head.json'), 'utf8'));
const FIRST = head.first || 151, N = head.mu.length;    // ImageNet dog classes 151..275
// Chinese names for the 125 dog classes, same order as ImageNet
const ZH = ("吉娃娃 日本狆 馬爾濟斯 北京犬 西施犬 查理士王小獵犬 蝴蝶犬 玩具㹴 羅德西亞背脊犬 阿富汗獵犬 巴吉度獵犬 米格魯 尋血獵犬 藍斑獵浣熊犬 黑褐獵浣熊犬 "
  + "沃克獵浣熊犬 英國獵狐犬 紅骨獵浣熊犬 俄羅斯獵狼犬 愛爾蘭獵狼犬 義大利靈緹 惠比特犬 依比沙獵犬 挪威獵麋犬 奧達獵犬 薩路基獵犬 蘇格蘭獵鹿犬 威瑪獵犬 "
  + "斯塔福郡鬥牛㹴 美國斯塔福郡㹴 貝林登㹴 邊境㹴 凱利藍㹴 愛爾蘭㹴 諾福克㹴 諾威奇㹴 約克夏㹴 剛毛獵狐㹴 湖畔㹴 西里漢㹴 萬能㹴 凱恩㹴 澳洲㹴 "
  + "丹第丁蒙㹴 波士頓㹴 迷你雪納瑞 巨型雪納瑞 標準雪納瑞 蘇格蘭㹴 西藏㹴 絲毛㹴 愛爾蘭軟毛㹴 西高地白㹴 拉薩犬 平毛尋回犬 捲毛尋回犬 黃金獵犬 拉布拉多 "
  + "乞沙比克獵犬 德國短毛指示犬 維茲拉犬 英國雪達犬 愛爾蘭雪達犬 戈登雪達犬 布列塔尼獵犬 克倫伯獵犬 英國史賓格犬 威爾斯史賓格犬 可卡犬 蘇塞克斯獵犬 "
  + "愛爾蘭水獵犬 庫瓦茲犬 舒柏奇犬 比利時牧羊犬 比利時瑪利諾犬 伯瑞犬 澳洲卡爾比犬 可蒙犬 古代牧羊犬 喜樂蒂牧羊犬 柯利牧羊犬 邊境牧羊犬 法蘭德斯畜牧犬 "
  + "羅威那 德國牧羊犬 杜賓犬 迷你品 大瑞士山地犬 伯恩山犬 阿彭策爾山犬 恩特雷布赫山犬 拳師犬 鬥牛獒 藏獒 法國鬥牛犬 大丹犬 聖伯納犬 愛斯基摩犬 "
  + "阿拉斯加雪橇犬 西伯利亞哈士奇 大麥町 猴㹴 巴仙吉犬 巴哥犬 蘭伯格犬 紐芬蘭犬 大白熊犬 薩摩耶 博美 鬆獅犬 荷蘭毛獅犬 布魯塞爾格林芬犬 "
  + "柯基（潘布魯克） 柯基（卡提根） 玩具貴賓 迷你貴賓 標準貴賓 墨西哥無毛犬 灰狼 白狼 紅狼 郊狼 澳洲野犬 豺 非洲野犬").split(' ');

let clfP = null;
function load() {
  if (!clfP) clfP = pipeline('image-classification', MODEL, { dtype: 'q8' }).then(clf => {
    const id2 = clf.model.config.id2label, ids = {};
    for (const k in id2) ids[id2[k]] = +k;
    return { clf, ids, id2 };
  }).catch(e => { clfP = null; throw e; });
  return clfP;
}
export const warmup = () => load().then(() => true);

function analyze(out, ids, id2) {
  const p = new Float64Array(1000);
  for (const o of out) { const k = ids[o.label]; if (k != null) p[k] = o.score; }
  let dog = 0; for (let i = 0; i < N; i++) dog += p[FIRST + i];
  const top = [];
  for (let i = 0; i < N; i++) top.push([FIRST + i, p[FIRST + i]]);
  top.sort((a, b) => b[1] - a[1]);
  const r = { dog: +dog.toFixed(3), top: top.slice(0, 3).map(([i, s]) => ({ id: i, name: String(id2[i]).split(',')[0], zh: ZH[i - FIRST], p: +(s / (dog || 1)).toFixed(3) })), P: null, guess: null };
  if (dog < head.minDog) return r;
  const z = head.b.slice();
  for (let i = 0; i < N; i++) {
    const x = (Math.log(p[FIRST + i] / dog + head.eps) - head.mu[i]) / head.sd[i];
    if (x) for (let c = 0; c < 3; c++) z[c] += x * head.W[i][c];
  }
  const m = Math.max(...z), e = z.map(v => Math.exp(v - m)), s = e[0] + e[1] + e[2];
  r.P = e.map(v => +(v / s).toFixed(3));
  r.guess = r.P[0] >= 0.7 ? 'S' : r.P[2] >= 0.7 ? 'L' : null;   // S = small capes, L = big raincoat, null = no hint
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
    const { clf, ids, id2 } = await load();
    let img;
    try { img = await RawImage.fromBlob(new Blob([buf])); } catch (e) { throw Object.assign(new Error('bad image'), { status: 400 }); }
    const t0 = Date.now();
    const out = await clf(img, { top_k: 1000 });
    return { ...analyze(out, ids, id2), ms: Date.now() - t0 };
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
