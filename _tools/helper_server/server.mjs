// apetto helper server (ws1): semantic matching for the site's shop assistant, plus the question log.
// API (same as the old bridge):
//   GET  /api/health        -> {ok, helper:true, ready}
//   POST /api/helper/match  {q, lang, v} -> {v, th, ex:[{i,s}], docs:[{i,s}]}
//   POST /api/helper/log    {sid, q, lang, page, kind, via, score, ans, t}
import http from 'node:http';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { pipeline, env } from '@huggingface/transformers';

process.title = 'apetto-helper';
const HERE = path.dirname(fileURLToPath(import.meta.url));
const APP = process.env.APP || HERE;          // small files: code, logs, settings (home dir)
const RT = process.env.RT || HERE;            // big files: node_modules, model, caches (/tmp2)
const PORT = +process.env.PORT || 18787;
const SITE = process.env.SITE || 'https://ama0904.github.io/apt/';
const LOGDIR = path.join(APP, 'logs');
const CACHE = path.join(RT, 'cache');
fs.mkdirSync(LOGDIR, { recursive: true });
fs.mkdirSync(CACHE, { recursive: true });

// settings file: FITLOG_TOKEN=..., FITLOG_REPO=owner/repo
try {
  for (const line of fs.readFileSync(path.join(APP, '.env'), 'utf8').split(/\r?\n/)) {
    const m = line.match(/^\s*([A-Z_]+)\s*=\s*(.*?)\s*$/);
    if (m && !process.env[m[1]]) process.env[m[1]] = m[2];
  }
} catch { /* no settings file */ }
const FITLOG_TOKEN = process.env.FITLOG_TOKEN || '';
const FITLOG_REPO = process.env.FITLOG_REPO || 'ama0904/apt-fitlog';

const TH = { ex: 0.90, doc: 0.89, strong: 0.96, margin: 0.01 };
const LANGS = new Set(['zh', 'en', 'ja', 'de']);
const log = (...a) => console.log(new Date().toISOString(), ...a);

// ---- model ----
env.cacheDir = path.join(RT, 'models');
let embedder = null;
const ready = pipeline('feature-extraction', 'Xenova/multilingual-e5-small', {
  dtype: 'q8', session_options: { intraOpNumThreads: 4, interOpNumThreads: 1 },
}).then(p => { embedder = p; log('model ready'); });

async function embed(texts) {
  await ready;
  const out = [];
  for (let i = 0; i < texts.length; i += 32) {
    const t = await embedder(texts.slice(i, i + 32).map(x => 'query: ' + x), { pooling: 'mean', normalize: true });
    const [n, d] = t.dims;
    for (let j = 0; j < n; j++) out.push(t.data.slice(j * d, (j + 1) * d));
  }
  return out;
}
const dot = (a, b) => { let s = 0; for (let i = 0; i < a.length; i++) s += a[i] * b[i]; return s; };

// ---- knowledge base, per language, embedded once per version ----
const KB = {};        // lang -> {v, ex:[Float32Array], docs:[Float32Array]}
const loading = {};   // lang -> promise
const lastFetch = {}; // lang -> ms

async function loadKB(lang) {
  lastFetch[lang] = Date.now();
  const r = await fetch(`${SITE}assets/assistant/kb.${lang}.json?t=${Date.now()}`, { cache: 'no-store' });
  if (!r.ok) throw new Error(`kb ${lang} ${r.status}`);
  const kb = await r.json();
  if (KB[lang] && KB[lang].v === kb.v) return KB[lang];
  const file = path.join(CACHE, `${lang}-${kb.v}.json`);
  let vec;
  try { vec = JSON.parse(fs.readFileSync(file, 'utf8')); } catch { vec = null; }
  if (!vec) {
    const t0 = Date.now();
    const ex = await embed(kb.sem.ex.map(e => e[0]));
    const docs = await embed(kb.docs.map(d => `${d.t} ${String(d.x || '').slice(0, 300)}`));
    vec = { ex: ex.map(a => Array.from(a)), docs: docs.map(a => Array.from(a)) };
    fs.writeFileSync(file, JSON.stringify(vec));
    for (const f of fs.readdirSync(CACHE)) if (f.startsWith(lang + '-') && f !== path.basename(file)) fs.rmSync(path.join(CACHE, f), { force: true });
    log(`kb ${lang} ${kb.v}: ${ex.length} examples, ${docs.length} docs in ${Date.now() - t0} ms`);
  }
  KB[lang] = { v: kb.v, ex: vec.ex.map(a => Float32Array.from(a)), docs: vec.docs.map(a => Float32Array.from(a)) };
  return KB[lang];
}
function getKB(lang, v) {
  const cur = KB[lang];
  // the site may have a newer version than we have; check again at most every 30 s
  const want = !cur || (v && v !== cur.v && Date.now() - (lastFetch[lang] || 0) > 30e3);
  if (want && !loading[lang]) loading[lang] = loadKB(lang).catch(e => { log('kb error', e.message); return KB[lang]; }).finally(() => { loading[lang] = null; });
  if (!cur) return loading[lang];
  if (loading[lang] && v && v !== cur.v) return loading[lang]; // a newer version is on its way
  return cur;
}

function top(q, list, n) {
  return list.map((e, i) => ({ i, s: dot(q, e) })).sort((a, b) => b.s - a.s).slice(0, n).map(e => ({ i: e.i, s: +e.s.toFixed(4) }));
}

// ---- question log: local file always, GitHub (private repo) when a token is set ----
const PENDING = path.join(LOGDIR, 'pending.jsonl');
let flushing = false;
async function flushLog() {
  if (!FITLOG_TOKEN || flushing) return;
  let lines;
  try { lines = fs.readFileSync(PENDING, 'utf8').split('\n').filter(Boolean); } catch { return; }
  if (!lines.length) return;
  flushing = true;
  try {
    const byMonth = {};
    for (const l of lines) { try { const e = JSON.parse(l); (byMonth[String(e.t).slice(0, 7)] ||= []).push(e); } catch { } }
    for (const [m, es] of Object.entries(byMonth)) {
      if (!/^\d{4}-\d{2}$/.test(m)) continue;
      for (let tries = 0; tries < 3; tries++) {
        const url = `https://api.github.com/repos/${FITLOG_REPO}/contents/helper/${m}.json`;
        const h = { Authorization: `Bearer ${FITLOG_TOKEN}`, Accept: 'application/vnd.github+json', 'User-Agent': 'apetto-helper' };
        const g = await fetch(url, { headers: h });
        let old = [], sha;
        if (g.ok) { const j = await g.json(); sha = j.sha; old = JSON.parse(Buffer.from(j.content, 'base64').toString('utf8')); }
        else if (g.status !== 404) throw new Error('GitHub get ' + g.status);
        const all = old.concat(es).sort((a, b) => String(b.t).localeCompare(String(a.t)));
        const p = await fetch(url, {
          method: 'PUT', headers: h,
          body: JSON.stringify({ message: `helper log ${m} (+${es.length})`, content: Buffer.from(JSON.stringify(all, null, 0)).toString('base64'), ...(sha ? { sha } : {}) }),
        });
        if (p.ok) break;
        if (p.status !== 409 && p.status !== 422) throw new Error('GitHub put ' + p.status);
        if (tries === 2) throw new Error('GitHub conflict');
      }
    }
    // keep anything that arrived while uploading
    const now = fs.readFileSync(PENDING, 'utf8').split('\n').filter(Boolean);
    fs.writeFileSync(PENDING, now.slice(lines.length).map(l => l + '\n').join(''));
    log(`log uploaded ${lines.length}`);
  } catch (e) { log('log upload failed', e.message); }
  finally { flushing = false; }
}
setInterval(flushLog, 10 * 60e3).unref();
let sinceFlush = 0;

function writeLog(e) {
  const line = JSON.stringify(e) + '\n';
  fs.appendFileSync(path.join(LOGDIR, `${String(e.t).slice(0, 7)}.jsonl`), line);
  fs.appendFileSync(PENDING, line);
  if (++sinceFlush >= 20) { sinceFlush = 0; flushLog(); }
}

// ---- http ----
const hits = new Map(); // `${kind}:${ip}` -> {n, reset}
function limited(kind, ip, max) {
  const k = kind + ':' + ip, now = Date.now();
  let h = hits.get(k);
  if (!h || now > h.reset) { h = { n: 0, reset: now + 60e3 }; hits.set(k, h); }
  return ++h.n > max;
}
setInterval(() => { const now = Date.now(); for (const [k, h] of hits) if (now > h.reset) hits.delete(k); }, 60e3).unref();

const str = (x, n) => String(x ?? '').slice(0, n);
function send(res, code, obj) {
  res.writeHead(code, {
    'Content-Type': 'application/json; charset=utf-8', 'Access-Control-Allow-Origin': '*',
    'Access-Control-Allow-Methods': 'GET, POST, OPTIONS', 'Access-Control-Allow-Headers': 'Content-Type', 'Cache-Control': 'no-store',
  });
  res.end(JSON.stringify(obj));
}
function body(req) {
  return new Promise((ok, bad) => {
    let b = '';
    req.on('data', c => { b += c; if (b.length > 8192) { bad(new Error('too big')); req.destroy(); } });
    req.on('end', () => { try { ok(JSON.parse(b || '{}')); } catch { bad(new Error('bad json')); } });
    req.on('error', bad);
  });
}

http.createServer(async (req, res) => {
  const url = req.url.split('?')[0];
  const ip = String(req.headers['x-forwarded-for'] || req.socket.remoteAddress || '').split(',')[0].trim();
  try {
    if (req.method === 'OPTIONS') return send(res, 204, {});
    if (url === '/api/health' && req.method === 'GET') return send(res, 200, { ok: true, helper: true, ready: !!embedder });
    if (url === '/api/helper/match' && req.method === 'POST') {
      if (limited('m', ip, 60)) return send(res, 429, { error: 'slow down' });
      const b = await body(req), q = str(b.q, 300).trim(), lang = LANGS.has(b.lang) ? b.lang : 'zh';
      if (!q) return send(res, 400, { error: 'empty' });
      const kb = await getKB(lang, str(b.v, 40));
      if (!kb) return send(res, 503, { error: 'not ready' });
      const [qv] = await embed([q]);
      return send(res, 200, { v: kb.v, th: TH, ex: top(qv, kb.ex, 8), docs: top(qv, kb.docs, 3) });
    }
    if (url === '/api/helper/log' && req.method === 'POST') {
      if (limited('l', ip, 30)) return send(res, 429, { error: 'slow down' });
      const b = await body(req);
      const t = isNaN(Date.parse(b.t)) || Math.abs(Date.parse(b.t) - Date.now()) > 864e5 ? new Date().toISOString() : new Date(b.t).toISOString();
      const e = {
        t, sid: str(b.sid, 40), q: str(b.q, 300), lang: LANGS.has(b.lang) ? b.lang : '', page: str(b.page, 200),
        kind: str(b.kind, 40), via: str(b.via, 10), score: typeof b.score === 'number' ? b.score : null, ans: str(b.ans, 200),
      };
      if (e.q.trim()) writeLog(e);
      return send(res, 200, { ok: true });
    }
    send(res, 404, { error: 'not found' });
  } catch (e) {
    send(res, 400, { error: e.message });
  }
}).listen(PORT, '127.0.0.1', () => log(`listening on 127.0.0.1:${PORT}`));

// warm up: load the model and all four languages right away
ready.then(() => Promise.all([...LANGS].map(l => getKB(l, ''))));
process.on('SIGTERM', async () => { await flushLog(); process.exit(0); });
