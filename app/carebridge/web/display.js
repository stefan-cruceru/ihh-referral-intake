// How the app looks: dark background, colorblind-safe colors, and an easy-to-see mode.
// Loaded in <head> on every page so the choice applies before the page paints (no white flash).
// Choices live in this browser only. Light, standard colors, normal size is the default:
// we do not follow the computer's dark-mode setting on purpose (many desk PCs are set to dark).
(() => {
  const KEY = "cb-display";
  const DEFAULTS = { theme: "light", colors: "standard", easy: "off" };
  const CHOICES = { theme: ["light", "dark"], colors: ["standard", "cvd"], easy: ["off", "on"] };
  const root = document.documentElement;

  function load() {
    let saved = {};
    try { saved = JSON.parse(localStorage.getItem(KEY) || "{}") || {}; } catch {}
    const d = { ...DEFAULTS };
    for (const k of Object.keys(CHOICES)) if (CHOICES[k].includes(saved[k])) d[k] = saved[k];
    return d;
  }
  function apply(d) {
    root.dataset.theme = d.theme;
    root.dataset.colors = d.colors;
    root.dataset.easy = d.easy;
  }
  let D = load();
  apply(D);

  // One language for every page, one at a time. A cookie (not localStorage) so the server-built
  // sign-in pages can read it too. get() is "" until someone picks; pages then fall back to the
  // app setting (/api/state) or English.
  window.cbLang = {
    get() {
      const m = document.cookie.match(/(?:^|;\s*)cb_lang=(en|es)\b/);
      return m ? m[1] : "";
    },
    set(l) {
      if (l !== "en" && l !== "es") return;
      document.cookie = `cb_lang=${l}; path=/; max-age=31536000; SameSite=Lax`;
      root.lang = l;
    },
  };
  function save() {
    try { localStorage.setItem(KEY, JSON.stringify(D)); } catch {}
    apply(D);
  }

  // ---- the Display button and its panel ----
  let S = null; // strings.json
  const t = (k) => (S && S[k] && (S[k][root.lang === "es" ? "es" : "en"] || S[k].en)) || "";
  // Words for a server error, in the page's language. The server sends a stable code ("err_<code>"
  // in strings.json); its English "error" text is only a fallback.
  window.cbError = (j, fallback) => {
    const k = "err_" + ((j && j.code) || "");
    let s = t(k);
    if (!s) return (j && j.error) || fallback || "";
    for (const [a, b] of Object.entries((j && j.vars) || {})) s = s.replaceAll(`{${a}}`, b);
    return s;
  };
  const ICON = '<svg viewBox="0 0 24 24" aria-hidden="true" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="9.5"/><circle cx="12" cy="7.2" r="1.3" fill="currentColor"/><path d="M7 10h10M12 10v4M12 14l-2.5 4.5M12 14l2.5 4.5"/></svg>';
  const GROUPS = [
    { key: "theme", label: "disp_theme", opts: [["light", "disp_light"], ["dark", "disp_dark"]] },
    { key: "colors", label: "disp_colors", help: "disp_colors_help", opts: [["standard", "disp_std"], ["cvd", "disp_cvd"]] },
    { key: "easy", label: "disp_easy", help: "disp_easy_help", opts: [["off", "disp_off"], ["on", "disp_on"]] },
  ];
  let btn, panel, skip;

  function render() {
    btn.setAttribute("aria-label", t("disp_title"));
    btn.title = t("disp_title");
    skip.textContent = t("skip_main");
    let h = `<h2 id="disp-h">${t("disp_title")}</h2>`;
    for (const g of GROUPS) {
      h += `<div class="disp-group" role="group" aria-labelledby="disp-${g.key}"><div class="disp-label" id="disp-${g.key}">${t(g.label)}</div>
        <div class="disp-seg">${g.opts.map(([v, k]) => `<button type="button" data-k="${g.key}" data-v="${v}" aria-pressed="${D[g.key] === v}">${t(k)}</button>`).join("")}</div>
        ${g.help ? `<p class="muted small">${t(g.help)}</p>` : ""}</div>`;
    }
    h += `<div class="row end"><button type="button" class="btn" data-close>${t("close")}</button></div>`;
    panel.innerHTML = h;
  }
  function open() {
    render();
    panel.classList.remove("hidden");
    btn.setAttribute("aria-expanded", "true");
    panel.querySelector("button[aria-pressed=true]")?.focus();
  }
  function close(refocus) {
    panel.classList.add("hidden");
    btn.setAttribute("aria-expanded", "false");
    if (refocus) btn.focus();
  }

  async function build() {
    // A "skip to the main part" link for keyboard and screen-reader users.
    const main = document.querySelector("main");
    if (main) {
      main.id ||= "main";
      main.tabIndex = -1;
      skip = document.createElement("a");
      skip.className = "skip-link";
      skip.href = "#" + main.id;
      document.body.prepend(skip);
    } else {
      skip = document.createElement("span");
    }

    btn = document.createElement("button");
    btn.type = "button";
    btn.className = "icon disp-btn";
    btn.setAttribute("aria-haspopup", "dialog");
    btn.setAttribute("aria-expanded", "false");
    btn.setAttribute("aria-controls", "display-panel");
    btn.innerHTML = ICON;
    // Main page: next to Settings. Other pages: at the end of the top bar, or by the language buttons.
    const settings = document.getElementById("open-settings");
    if (settings) settings.before(btn);
    else (document.querySelector("header") || document.querySelector(".langs"))?.append(btn);

    panel = document.createElement("div");
    panel.id = "display-panel";
    panel.className = "disp-panel hidden";
    panel.setAttribute("role", "dialog");
    panel.setAttribute("aria-labelledby", "disp-h");
    document.body.append(panel);

    btn.addEventListener("click", () => (panel.classList.contains("hidden") ? open() : close(false)));
    panel.addEventListener("click", (e) => {
      const b = e.target.closest("button");
      if (!b) return;
      if (b.hasAttribute("data-close")) return close(true);
      D[b.dataset.k] = b.dataset.v;
      save();
      render();
      panel.querySelector(`button[data-k="${b.dataset.k}"][data-v="${b.dataset.v}"]`)?.focus();
    });
    document.addEventListener("keydown", (e) => {
      if (e.key === "Escape" && !panel.classList.contains("hidden")) { e.stopPropagation(); close(true); }
    }, true);
    document.addEventListener("click", (e) => {
      // composedPath, not contains: the panel re-renders on each choice, so the clicked button is already detached.
      const path = e.composedPath();
      if (!panel.classList.contains("hidden") && !path.includes(panel) && !path.includes(btn)) close(false);
    });
    // Follow the page's language switch (every page sets <html lang>).
    new MutationObserver(() => render()).observe(root, { attributes: true, attributeFilter: ["lang"] });

    try { S = await (await fetch("/static/strings.json")).json(); } catch { S = {}; }
    render();
  }
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", build);
  else build();
})();
