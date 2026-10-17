// The GitHub Pages demo: this service worker is the "server". It runs the real Lamplight Python
// code in the browser (Pyodide) and answers every request under app/ with it. Practice mode only.
// A service worker may only load scripts while it starts, so both Pyodide scripts load here.
importScripts("https://cdn.jsdelivr.net/pyodide/v0.27.7/full/pyodide.js", "https://cdn.jsdelivr.net/pyodide/v0.27.7/full/pyodide.asm.js");

const SCOPE = new URL(self.registration.scope).pathname; // e.g. /ihh-referral-intake/
const APP = SCOPE + "app/";
const HOME = "/home/pyodide/repo";
let ready = null, started = false;
const jar = new Map(); // practice sign-in cookies; a service worker cannot set real ones

// If this worker ever stops answering (seen right after a new version is published), requests fall
// through to GitHub and get 404.html. HEAL drops the worker and reloads; 404.html installs it fresh.
const HEAL = `async function heal() { for (const r of await navigator.serviceWorker.getRegistrations()) await r.unregister(); location.reload(); }`;

// Added to every app page. The browser stops an idle service worker, and with it the board and the
// sign-in, so an open page pings it. If the sign-in is gone anyway, the page goes back to sign in.
const PAGE_JS = `<script>${HEAL}
fetch("${APP}__ready").then((r) => { if (r.status === 404) heal(); }, () => {});
setInterval(() => navigator.serviceWorker.controller && navigator.serviceWorker.controller.postMessage("ping"), 20000);
(() => { const f = window.fetch; window.fetch = async (...a) => { const r = await f(...a);
  if (r.status === 401 && !location.pathname.includes("/auth/")) {
    location.href = "${APP}auth/signin?next=" + encodeURIComponent(location.pathname.slice(${APP.length - 1}) + location.search); }
  return r; }; })();
</script>`;

// Shown instead of a blank tab while Python loads after the browser stopped the worker.
const WAIT = `<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Getting Lamplight ready</title><style>body{margin:0;min-height:100vh;display:grid;place-items:center;background:#fff8f0;color:#3b2b22;
font:17px/1.6 "Public Sans",system-ui,sans-serif;text-align:center;padding:16px}p{color:#715d50;margin:4px 0}
.d{width:40px;height:40px;margin:0 auto 16px;border:4px solid #fbe3cc;border-top-color:#e39235;border-radius:50%;animation:s 1s linear infinite}
@keyframes s{to{transform:rotate(1turn)}}@media (prefers-reduced-motion:reduce){.d{animation:none}}</style></head>
<body><div><div class="d"></div><b>Getting Lamplight ready…</b><p>This takes about 20 seconds.</p><p>Preparando Lamplight…</p></div>
<script>${HEAL}
setInterval(async () => { try { const r = await fetch("${APP}__ready");
  if (r.ok) location.replace(location.href); else if (r.status === 404) heal(); } catch (e) {} }, 2000);</script>
</body></html>`;

function boot() {
  return (async () => {
    const py = await loadPyodide();
    await py.loadPackage(["pillow", "sqlite3", "ssl", "micropip"]); // fpdf2 imports urllib HTTPS names
    await py.pyimport("micropip").install(["fpdf2"]);
    const zip = await (await fetch(SCOPE + "carebridge.zip", { cache: "no-cache" })).arrayBuffer();
    py.unpackArchive(zip, "zip", { extractDir: HOME });
    py.runPython(`import sys; sys.path[:0] = ["${HOME}/app", "${HOME}/app/pages"]`);
    const handle = py.pyimport("bridge").handle;
    started = true;
    return handle;
  })();
}

self.addEventListener("install", (e) => e.waitUntil(self.skipWaiting()));
self.addEventListener("activate", (e) => e.waitUntil(self.clients.claim()));
self.addEventListener("message", (e) => {
  if (e.data === "warm") { ready = ready || boot(); ready.then(() => e.source.postMessage("ready"), (err) => e.source.postMessage("error:" + err)); }
});

// The app was written to live at "/". Here it lives at APP, so absolute links in what it sends
// back are moved under APP. Anything already under it is left alone.
const LINK = /([\"'`(=\s])\/(static|api|auth|send|go)(?=[\/\"'`?\s)&#])/g;
const fix = (s) => s.replace(LINK, (m, a, b) => a + APP + b)
  .replace(/href="\/"/g, `href="${APP}"`)
  .replace(new RegExp(APP.replace(/\//g, "\\/") + APP.slice(1).replace(/\//g, "\\/"), "g"), APP);
const under = (loc) => (loc.startsWith("/") && !loc.startsWith(APP) ? APP + loc.slice(1) : loc);

function remember(set) {
  for (const c of set) {
    const [pair, ...attrs] = c.split(";");
    const i = pair.indexOf("=");
    const name = pair.slice(0, i).trim(), value = pair.slice(i + 1).trim();
    const gone = !value || attrs.some((a) => /max-age=0\b/i.test(a.trim()) || /expires=thu, 01 jan 1970/i.test(a.trim()));
    if (gone) jar.delete(name); else jar.set(name, value);
  }
}

async function answer(req) {
  const url = new URL(req.url);
  ready = ready || boot();
  const handle = await ready;
  const path = "/" + url.pathname.slice(APP.length) + url.search;
  const headers = {};
  req.headers.forEach((v, k) => { if (k !== "cookie") headers[k] = v; });
  if (jar.size) headers["Cookie"] = [...jar].map(([k, v]) => `${k}=${v}`).join("; ");
  const body = ["GET", "HEAD"].includes(req.method) ? new Uint8Array() : new Uint8Array(await req.arrayBuffer());
  const [status, hdrs, raw] = handle(req.method, path, headers, body);
  const h = new Headers();
  const cookies = [];
  for (const [k, v] of hdrs) {
    const key = k.toLowerCase();
    if (key === "set-cookie") cookies.push(v);
    else if (key === "location") h.set("Location", under(v));
    else if (key !== "content-length") h.append(k, v);
  }
  remember(cookies);
  if (status >= 300 && status < 400 && h.get("Location")) return Response.redirect(new URL(h.get("Location"), url).href, 303);
  const type = h.get("Content-Type") || "";
  if (!/text\/|javascript|json/.test(type)) return new Response(raw, { status, headers: h });
  let text = fix(new TextDecoder().decode(raw));
  // First thing in the page, so its own scripts already use the wrapped fetch.
  if (type.startsWith("text/html")) text = /<head(\s[^>]*)?>/i.test(text) ? text.replace(/<head(\s[^>]*)?>/i, (m) => m + PAGE_JS) : PAGE_JS + text;
  return new Response(text, { status, headers: h });
}

self.addEventListener("fetch", (e) => {
  const url = new URL(e.request.url);
  if (url.origin !== location.origin || !url.pathname.startsWith(APP)) return;
  if (url.pathname === APP + "__ready") { // the wait page asks this until Python is up
    ready = ready || boot();
    return e.respondWith(new Response(null, { status: started ? 204 : 503 }));
  }
  // GET only: a form sent while Python loads just waits for it, since reloading would send the form again.
  if (!started && e.request.mode === "navigate" && e.request.method === "GET") {
    ready = ready || boot();
    return e.respondWith(new Response(WAIT, { headers: { "Content-Type": "text/html; charset=utf-8" } }));
  }
  e.respondWith(answer(e.request).catch((err) =>
    new Response(`Lamplight demo error: ${err}`, { status: 500, headers: { "Content-Type": "text/plain" } })));
});
