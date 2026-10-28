// GitHub proxy for the admin page: admins sign in with Google, the laptop holds the GitHub token.
//
// The admin page sends every GitHub API call here instead of to api.github.com:
//   POST /api/admin/gh   Authorization: Bearer <Firebase ID token>
//   body: {"method": "GET|POST|PATCH|PUT", "path": "/repos/<owner>/<repo>/...", "body": <json or omitted>, "accept": "<optional Accept header>"}
// The laptop checks the ID token (signature, project, expiry, verified e-mail on the admin list), checks that the path
// belongs to an allowed repo, adds its own token and forwards the call. The answer comes back with GitHub's status and
// body (binary bodies, e.g. Accept: application/vnd.github.raw, are passed through with their content type).
//
// Wiring in fit/server.js (sketch):
//   import { ghProxyHandler, verifyAdmin } from './ghproxy.mjs';
//   if (req.method === 'POST' && url.pathname === '/api/admin/gh') return ghProxyHandler(req, res);
//   (CORS: the site's origin must be allowed to send the Authorization and Content-Type headers to this path.)
//   verifyAdmin(req) can also guard the other /api/admin/* endpoints (returns {email} or throws with .status 401/403).
//
// Settings (environment variables, all optional except the token file):
//   GH_TOKEN_FILE   file holding the GitHub token (fine-grained, limited to the repos below). Default: ./secrets/github-token.txt
//   ADMIN_FILE      file with one admin e-mail per line (same list as the Firestore rules). Default: ./secrets/admin-emails.txt
//   GH_REPOS        comma-separated repos the admin may touch. Default: ama0904/apt,ama0904/apt-fitlog
//   FIREBASE_PROJECT  Firebase project id. Default: apetto-930e7
// Nothing secret lives in this file or in the repo; both files are read on every request (cheap), so edits apply at once.
import crypto from 'node:crypto';
import fs from 'node:fs';
import path from 'node:path';

const HERE = path.dirname(new URL(import.meta.url).pathname.replace(/^\/([A-Za-z]:)/, '$1'));
const TOKEN_FILE = process.env.GH_TOKEN_FILE || path.join(HERE, 'secrets', 'github-token.txt');
const ADMIN_FILE = process.env.ADMIN_FILE || path.join(HERE, 'secrets', 'admin-emails.txt');
const REPOS = (process.env.GH_REPOS || 'ama0904/apt,ama0904/apt-fitlog').split(',').map(s => s.trim().toLowerCase()).filter(Boolean);
const PROJECT = process.env.FIREBASE_PROJECT || 'apetto-930e7';
const JWKS_URL = 'https://www.googleapis.com/service_accounts/v1/jwk/securetoken@system.gserviceaccount.com';
const MAX_BODY = 40 * 1024 * 1024;   // image uploads go through git/blobs as base64

const fail = (status, msg) => Object.assign(new Error(msg), { status });

// ---------- Firebase ID token check (RS256, Google's rotating keys, cached by Cache-Control max-age)
let keys = null, keysUntil = 0;
async function googleKeys() {
  if (keys && Date.now() < keysUntil) return keys;
  const r = await fetch(JWKS_URL);
  if (!r.ok) throw fail(503, 'cannot fetch Google keys');
  const j = await r.json();
  const m = /max-age=(\d+)/.exec(r.headers.get('cache-control') || '');
  keys = new Map(j.keys.map(k => [k.kid, crypto.createPublicKey({ key: k, format: 'jwk' })]));
  keysUntil = Date.now() + 1000 * Math.min(Number(m && m[1]) || 3600, 6 * 3600);
  return keys;
}
const b64url = s => Buffer.from(s.replace(/-/g, '+').replace(/_/g, '/'), 'base64');
function adminList() {
  try { return new Set(fs.readFileSync(ADMIN_FILE, 'utf8').split(/\r?\n/).map(s => s.trim().toLowerCase()).filter(s => s && !s.startsWith('#'))); }
  catch (e) { return new Set(); }
}
export async function verifyIdToken(tok) {
  const parts = String(tok || '').split('.');
  if (parts.length !== 3) throw fail(401, 'not signed in');
  let head, claims;
  try { head = JSON.parse(b64url(parts[0])); claims = JSON.parse(b64url(parts[1])); } catch (e) { throw fail(401, 'bad token'); }
  if (head.alg !== 'RS256') throw fail(401, 'bad token');
  let key = (await googleKeys()).get(head.kid);
  if (!key) { keysUntil = 0; key = (await googleKeys()).get(head.kid); }   // keys rotated
  if (!key) throw fail(401, 'bad token');
  const ok = crypto.verify('RSA-SHA256', Buffer.from(parts[0] + '.' + parts[1]), key, b64url(parts[2]));
  if (!ok) throw fail(401, 'bad token');
  const now = Math.floor(Date.now() / 1000);
  if (claims.aud !== PROJECT || claims.iss !== 'https://securetoken.google.com/' + PROJECT) throw fail(401, 'bad token');
  if (!(claims.exp > now) || !(claims.iat <= now + 300) || !claims.sub) throw fail(401, 'sign-in expired');
  return claims;
}
export async function verifyAdmin(req) {
  const m = /^Bearer\s+(.+)$/i.exec(req.headers['authorization'] || '');
  const c = await verifyIdToken(m && m[1]);
  const email = String(c.email || '').toLowerCase();
  if (!c.email_verified || !adminList().has(email)) throw fail(403, 'not an admin account');
  return { email };
}

// ---------- the proxy
function readBody(req) {
  return new Promise((resolve, reject) => {
    const chunks = []; let n = 0;
    req.on('data', c => { n += c.length; if (n > MAX_BODY) { reject(fail(413, 'too large')); req.destroy(); } else chunks.push(c); });
    req.on('end', () => resolve(Buffer.concat(chunks))); req.on('error', reject);
  });
}
function allowedPath(p) {
  if (typeof p !== 'string' || !p.startsWith('/repos/') || p.includes('..') || /[\s#\\]/.test(p)) return false;
  const seg = p.split('?')[0].split('/');   // ['', 'repos', owner, repo, ...]
  return seg.length >= 4 && REPOS.includes((seg[2] + '/' + seg[3]).toLowerCase());
}
const send = (res, status, obj) => { res.writeHead(status, { 'Content-Type': 'application/json; charset=utf-8' }); res.end(JSON.stringify(obj)); };

export async function ghProxyHandler(req, res) {
  try {
    const who = await verifyAdmin(req);
    let q; try { q = JSON.parse((await readBody(req)).toString('utf8')); } catch (e) { throw fail(400, 'bad request'); }
    const method = String(q.method || 'GET').toUpperCase();
    if (!['GET', 'POST', 'PATCH', 'PUT'].includes(method)) throw fail(400, 'method not allowed');
    if (!allowedPath(q.path)) throw fail(403, 'path not allowed');
    let token = '';
    try { token = fs.readFileSync(TOKEN_FILE, 'utf8').trim(); } catch (e) { /* below */ }
    if (!token) throw fail(503, 'GitHub token not set up on the laptop');
    const accept = /^application\/vnd\.github(\.[a-z0-9.+-]+)?$|^application\/json$/i.test(q.accept || '') ? q.accept : 'application/vnd.github+json';
    const r = await fetch('https://api.github.com' + q.path, {
      method,
      headers: { Accept: accept, Authorization: 'Bearer ' + token, 'X-GitHub-Api-Version': '2022-11-28', 'User-Agent': 'apetto-admin-proxy',
                 ...(q.body !== undefined ? { 'Content-Type': 'application/json' } : {}) },
      body: q.body !== undefined && method !== 'GET' ? JSON.stringify(q.body) : undefined,
    });
    if (method !== 'GET') console.log(new Date().toISOString(), 'admin-gh', who.email, method, q.path.split('?')[0], r.status);
    const buf = Buffer.from(await r.arrayBuffer());
    res.writeHead(r.status, { 'Content-Type': r.headers.get('content-type') || 'application/octet-stream', 'Cache-Control': 'no-store' });
    res.end(buf);
  } catch (e) {
    send(res, e.status || 500, { message: e.status ? e.message : 'proxy error' });
    if (!e.status) console.warn('admin-gh', e);
  }
}
