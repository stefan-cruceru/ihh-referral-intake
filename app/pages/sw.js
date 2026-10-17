// The GitHub Pages demo: this service worker is the "server". It runs the real Lamplight Python
// code in the browser (Pyodide) and answers every request under app/ with it. Practice mode only.
// A service worker may only load scripts while it starts, so both Pyodide scripts load here.
importScripts("https://cdn.jsdelivr.net/pyodide/v0.27.7/full/pyodide.js", "https://cdn.jsdelivr.net/pyodide/v0.27.7/full/pyodide.asm.js");

const SCOPE = new URL(self.registration.scope).pathname; // e.g. /ihh-referral-intake/
const APP = SCOPE + "app/";
const HOME = "/home/pyodide/repo";
let ready = null;
const jar = new Map(); // practice sign-in cookies; a service worker cannot set real ones

function boot() {
  return (async () => {
    const py = await loadPyodide();
    await py.loadPackage(["pillow", "sqlite3", "ssl", "micropip"]); // fpdf2 imports urllib HTTPS names
    await py.pyimport("micropip").install(["fpdf2"]);
    const zip = await (await fetch(SCOPE + "carebridge.zip", { cache: "no-cache" })).arrayBuffer();
    py.unpackArchive(zip, "zip", { extractDir: HOME });
    py.runPython(`import sys; sys.path[:0] = ["${HOME}/app", "${HOME}/app/pages"]`);
    return py.pyimport("bridge").handle;
  })();
}

self.addEventListener("install", (e) => { self.skipWaiting(); });
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
  const text = /text\/|javascript|json/.test(type);
  return new Response(text ? fix(new TextDecoder().decode(raw)) : raw, { status, headers: h });
}

self.addEventListener("fetch", (e) => {
  const url = new URL(e.request.url);
  if (url.origin !== location.origin || !url.pathname.startsWith(APP)) return;
  e.respondWith(answer(e.request).catch((err) =>
    new Response(`Lamplight demo error: ${err}`, { status: 500, headers: { "Content-Type": "text/plain" } })));
});
