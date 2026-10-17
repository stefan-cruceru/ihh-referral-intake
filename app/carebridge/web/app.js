"use strict";
// Care Bridge front end. Plain JS, no build step. Every on-screen string comes from strings.json.

let S = {}; // strings
let LANG = "en";
let STATE = {};
let OPEN = null; // card id open in the drawer
let DRAFT_TAB = "missing_items";
let RULES = null;

const $ = (s, el = document) => el.querySelector(s);
const $$ = (s, el = document) => [...el.querySelectorAll(s)];
const esc = (v) => String(v ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const t = (k, vars) => {
  let s = (S[k] && (S[k][LANG] ?? S[k].en)) ?? k;
  for (const [a, b] of Object.entries(vars || {})) s = s.replaceAll(`{${a}}`, b);
  return s;
};

async function api(path, opts = {}) {
  const r = await fetch(path, { headers: { "Content-Type": "application/json" }, ...opts });
  const j = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(j.error || r.statusText);
  return j;
}
const post = (path, body) => api(path, { method: "POST", body: JSON.stringify(body || {}) });

function toast(msg) {
  const el = $("#toast");
  el.textContent = msg;
  el.classList.remove("hidden");
  clearTimeout(toast._t);
  toast._t = setTimeout(() => el.classList.add("hidden"), 2600);
}

function applyI18n() {
  document.documentElement.lang = LANG;
  $$("[data-i18n]").forEach((el) => (el.textContent = t(el.dataset.i18n)));
  $$("[data-i18n-ph]").forEach((el) => (el.placeholder = t(el.dataset.i18nPh)));
  $$(".lang button").forEach((b) => b.classList.toggle("on", b.dataset.lang === LANG));
  $("#situation").placeholder = t("res_ph");
}

async function setLang(l) {
  LANG = l;
  applyI18n();
  post("/api/settings", { lang: l }).catch(() => {});
  renderQueue(LAST_Q);
  if (OPEN) openCard(OPEN, true);
  renderRules();
  loadScenarios();
  if (!$("#jottings").value || Object.values(EXAMPLES.note || {}).includes($("#jottings").value)) $("#jottings").value = (EXAMPLES.note || {})[LANG] || "";
}

// ---------------------------------------------------------------- tabs
$$(".tabs button").forEach((b) =>
  b.addEventListener("click", () => {
    $$(".tabs button").forEach((x) => x.classList.toggle("on", x === b));
    $$(".tab").forEach((x) => x.classList.toggle("on", x.id === "tab-" + b.dataset.tab));
  })
);
const goTab = (name) => $(`.tabs button[data-tab="${name}"]`).click();
$$(".lang button").forEach((b) => b.addEventListener("click", () => setLang(b.dataset.lang)));

// ---------------------------------------------------------------- referrals board
let LAST_Q = null;

function fmtClock(ts) {
  const d = new Date(ts * 1000);
  return d.toLocaleString(LANG === "es" ? "es-US" : "en-US", { weekday: "short", hour: "numeric", minute: "2-digit" });
}

function statusChip(st) {
  return `<span class="chip st-${esc(st)}">${esc(t("st_" + st))}</span>`;
}

function renderQueue(q) {
  if (!q) return;
  $("#clock-time").textContent = fmtClock(q.now);
  $("#speed").value = q.speed >= 30 ? "60" : "1";
  $("#speed").classList.toggle("hidden", !(q.speed >= 30 || q.cards.some((c) => c.sample)));
  const rep = q.report;
  const wd = Object.values(q.withdraw_reasons || {}).reduce((a, b) => a + b, 0);
  $("#stats").innerHTML = rep.total
    ? `<span class="pill">${rep.within_2h}/${rep.decided} ${esc(t("within_2h"))}</span><span class="pill">${wd} ${esc(t("withdrawn_count"))}</span>` +
      (q.pending ? `<span class="pill">${q.pending} ${esc(t("arriving"))}</span>` : "")
    : "";
  const peak = q.peak;
  $("#peak").classList.toggle("hidden", !peak.at_risk.length);
  $("#peak").innerHTML = `${esc(t("peak_warn"))} <b>${peak.at_risk.map(esc).join(", ")}</b>`;
  if (!q.cards.length) {
    $("#queue").innerHTML = `<div class="empty">${esc(t("queue_empty"))}</div>`;
    return;
  }
  $("#queue").innerHTML = q.cards
    .map((c) => {
      const left = c.left_min;
      const timer = c.color === "done" ? `<b>✓</b><span>${c.elapsed_min} ${t("min")}</span>` : left >= 0 ? `<b>${left}</b><span>${t("min")} ${t("left")}</span>` : `<b>+${-left}</b><span>${t("min")} ${t("over")}</span>`;
      const review =
        c.review_stage && c.review_stage !== "done" && c.review_stage !== "sample" && c.review_stage !== "error"
          ? `<span class="chip info"><span class="spinner" style="width:12px;height:12px;border-width:2px;display:inline-block;vertical-align:-2px"></span> ${esc(c.review_progress || t("reviewing"))}</span>`
          : "";
      const alerts = (c.alerts || []).map((a) => `<span class="chip alert">${esc(t("al_" + a.code))}</span>`).join("");
      const silent = c.hospital_silent_min ? `<span class="chip">${esc(t("silent_for"))}: ${c.hospital_silent_min} ${t("min")}</span>` : "";
      const pct = c.color === "done" || left < 0 ? 1 : Math.max(0, Math.min(1, left / 120)); // late: a full red ring
      return `<div class="card c-${c.color}" data-id="${esc(c.id)}" tabindex="0">
        <div class="bar"></div>
        <div class="timer" style="--pct:${pct}">${timer}</div>
        <div>
          <div class="title">${esc(c.case_no)} · ${esc(c.hospital || t("unknown"))}</div>
          <div class="meta">${esc(t("channel_" + (c.channel || "upload")))} · ${esc(t("owner"))}: <b>${esc(c.owner)}</b></div>
          <div class="chips">${statusChip(c.status)}${review}${alerts}${silent}${c.sample ? `<span class="chip">${esc(t("sample_badge"))}</span>` : ""}</div>
        </div>
        <div class="side">${fmtClock(c.arrived_at)}</div>
      </div>`;
    })
    .join("");
  $$(".card").forEach((el) => {
    el.addEventListener("click", () => openCard(el.dataset.id));
    el.addEventListener("keydown", (e) => e.key === "Enter" && openCard(el.dataset.id));
  });
}

async function poll() {
  try {
    LAST_Q = await api("/api/queue");
    renderQueue(LAST_Q);
    if (OPEN) refreshOpen();
  } catch (e) {}
  setTimeout(poll, 1500);
}

$("#speed").addEventListener("change", (e) => post("/api/clock", { speed: Number(e.target.value) }));

function renderSim(sim) {
  const max = Math.max(150, ...sim.manual.map((r) => r.done), ...sim.tool.map((r) => r.done));
  const lane = (rows) =>
    rows
      .map((r, i) => {
        const cls = r.withdrawn ? "walk" : r.missed ? "miss" : "ok";
        const lbl = r.withdrawn ? t("sim_walked") : r.missed ? t("sim_missed") : t("sim_ok");
        return `<div class="sim-bar ${cls}" title="${esc(lbl)}" style="left:${(r.start / max) * 100}%;width:${((r.done - r.start) / max) * 100}%">#${i + 1} ${esc(lbl)}</div>`;
      })
      .join("") + `<div class="sim-limit" style="left:${(120 / max) * 100}%"></div>`;
  const count = (rows) => `${rows.filter((r) => !r.missed && !r.withdrawn).length}/${rows.length} ${t("sim_ok")}`;
  $("#sim").innerHTML = `<h3>${esc(t("sim_title"))}</h3>
    <div class="sim-row"><b>${esc(t("sim_manual"))}<br><span class="muted small">${esc(count(sim.manual))}</span></b><div class="sim-track">${lane(sim.manual)}</div></div>
    <div class="sim-row"><b>${esc(t("sim_tool"))}<br><span class="muted small">${esc(count(sim.tool))}</span></b><div class="sim-track">${lane(sim.tool)}</div></div>`;
  $("#sim").classList.remove("hidden");
}

$("#start-demo").addEventListener("click", async () => {
  const sim = await post("/api/demo", { speed: 60 });
  renderSim(sim);
  toast(t("start_demo"));
});

async function upload(file) {
  if (!file) return;
  const r = await fetch("/api/upload", { method: "POST", headers: { "X-Filename": file.name }, body: file });
  const j = await r.json();
  if (!r.ok) return toast(j.error ? t(j.error) : t("error"));
  if (!STATE.has_key) toast(t("need_key"));
  openCard(j.card.id);
}
$("#file-input").addEventListener("change", (e) => upload(e.target.files[0]));
$('label[for="file-input"]').addEventListener("keydown", (e) => {
  if (e.key === "Enter" || e.key === " ") { e.preventDefault(); $("#file-input").click(); }
});
const drop = $("#drop");
drop.addEventListener("click", () => $("#file-input").click());
["dragenter", "dragover"].forEach((ev) => drop.addEventListener(ev, (e) => { e.preventDefault(); drop.classList.add("over"); }));
["dragleave", "drop"].forEach((ev) => drop.addEventListener(ev, (e) => { e.preventDefault(); drop.classList.remove("over"); }));
drop.addEventListener("drop", (e) => upload(e.dataTransfer.files[0]));

// ---------------------------------------------------------------- referral detail
let DETAIL = null;
let DRAFTS = null;

async function openCard(id, force) {
  OPEN = id;
  $("#detail").classList.remove("hidden");
  DETAIL = await api(`/api/cards/${encodeURIComponent(id)}`);
  DRAFTS = await api(`/api/cards/${encodeURIComponent(id)}/drafts?lang=${LANG}`);
  renderDetail();
  if (!force && !DETAIL.card.opened) act("open");
}

async function refreshOpen() {
  const d = await api(`/api/cards/${encodeURIComponent(OPEN)}`).catch(() => null);
  if (!d) return;
  const changed = JSON.stringify([d.card.status, d.card.review_state, d.progress.length, d.card.alerts, d.card.left_min, !!d.report]) !==
    JSON.stringify([DETAIL.card.status, DETAIL.card.review_state, DETAIL.progress.length, DETAIL.card.alerts, DETAIL.card.left_min, !!DETAIL.report]);
  if (changed) {
    const hadReport = !!DETAIL.report;
    DETAIL = d;
    if (!hadReport && d.report) DRAFTS = await api(`/api/cards/${encodeURIComponent(OPEN)}/drafts?lang=${LANG}`);
    const y = $(".drawer-inner").scrollTop;
    renderDetail();
    $(".drawer-inner").scrollTop = y;
  }
}

function closeDetail() {
  OPEN = null;
  $("#detail").classList.add("hidden");
}
$("#detail").addEventListener("click", (e) => e.target.id === "detail" && closeDetail());
document.addEventListener("keydown", (e) => {
  if (e.key !== "Escape") return;
  if (!$("#viewer").classList.contains("hidden")) return $("#viewer").classList.add("hidden");
  if (!$("#settings").classList.contains("hidden")) return $("#settings").classList.add("hidden");
  closeDetail();
});

function showPage(n) {
  $("#viewer-title").textContent = `${t("page")} ${n}`;
  $("#viewer-img").src = `/api/cards/${encodeURIComponent(OPEN)}/pages/${n}.jpg`;
  $("#viewer").classList.remove("hidden");
}
$("#viewer-close").addEventListener("click", () => $("#viewer").classList.add("hidden"));

function quoteHtml(f) {
  if (!f) return "";
  const v = f.verify === "found" ? "" : f.verify === "paraphrase" ? ` <span class="note">${esc(t("paraphrase"))}</span>` : ` <span class="note">${esc(t("unverified"))}</span>`;
  const tr = LANG === "es" && f.statement_es ? `<div class="tr">${esc(t("translation"))}: ${esc(f.statement_es)}</div>` : "";
  return `<div class="quote"><button class="btn sm ghost pg" data-page="${f.page}">${esc(t("page"))} ${f.page}</button><q>${esc(f.quote)}</q>${v}</div>${tr}`;
}

function notesHtml(notes) {
  return (notes || []).map((n) => `<span class="note">${esc(t(n))}</span>`).join("");
}

function renderDetail() {
  const { card, report: rep, progress, error, audit } = DETAIL;
  const facts = Object.fromEntries((rep?.facts || []).map((f) => [f.id, f]));
  const es = LANG === "es";
  let h = `<div class="d-head"><div><h2>${esc(card.case_no)} · ${esc(card.hospital || t("unknown"))}</h2>
    <div class="muted">${esc(t("channel_" + (card.channel || "upload")))} · ${fmtClock(card.arrived_at)} · ${esc(t("owner"))}: <b>${esc(card.owner)}</b>
    · ${card.left_min >= 0 ? `${card.left_min} ${t("min")} ${t("left")}` : `+${-card.left_min} ${t("min")} ${t("over")}`}</div>
    <div class="chips">${statusChip(card.status)}${(card.alerts || []).map((a) => `<span class="chip alert">${esc(t("al_" + a.code))}</span>`).join("")}</div></div>
    <button class="btn ghost" id="d-close">${esc(t("close"))}</button></div>`;

  if (rep?.flags?.phi_pages?.length) h += `<div class="stop">${esc(t("phi_stop"))} (${esc(t("page"))} ${rep.flags.phi_pages.join(", ")})</div>`;
  const sec = rep?.security;
  if (sec && sec.verdict !== "ok") {
    const iso = sec.isolated_pages.length ? ` ${esc(t("security_isolated"))}: ${esc(t("page"))} ${sec.isolated_pages.map(esc).join(", ")}.` : "";
    h += `<div class="stop">${esc(t("security_stop"))}${iso}<ul>${sec.findings.map((f) => `<li>${esc(t("sec_" + f.code))}</li>`).join("")}</ul></div>`;
  }

  if (!rep) {
    if (card.review_state === "running") {
      h += `<div class="panel"><div class="progress"><div class="spinner"></div><b>${esc(t("reviewing"))}</b></div><ul>${progress.map((p) => `<li>${esc(p)}</li>`).join("")}</ul></div>`;
    } else {
      h += `<div class="panel">${error ? `<div class="phi">${esc(t(error))}</div>` : ""}
        ${card.has_packet !== false ? `<button class="btn primary" id="run-review" ${STATE.has_key ? "" : "disabled"}>${esc(t("run_review"))}</button>` : ""}
        ${STATE.has_key ? "" : `<p class="muted">${esc(t("need_key"))}</p>`}</div>`;
    }
  } else {
    const rec = rep.recommendation;
    h += `<div class="route ${rec.code}"><div><b>${esc(t("route_" + rec.code))}</b><div class="muted">${esc(t("route_note"))}</div></div>
      <span class="badge">${esc(rep.sample ? t("sample_badge") : t("live_badge"))}</span></div>`;
    if (rep.flags.no_referral_form) h += `<div class="phi">${esc(t("no_referral_form"))}</div>`;
    h += `<p class="muted">${esc(t("gates_why"))}</p><div class="gates">`;
    for (const g of ["self_care", "behavior"]) {
      const gs = rep.gates[g];
      const rs = rep.rules.filter((r) => r.gate === g && !r.superseded_by && r.status !== "not_applicable" && r.status !== "met");
      h += `<div class="gate ${gs.status}"><div class="muted">${esc(t("gate_" + g))}</div><div class="g-status">${esc(t("s_" + gs.status))}</div>
        ${rs.map((r) => `<div class="flag ${r.status}"><span class="rid">${esc(r.rule_id)}</span><span class="status ${r.status}">${esc(t("s_" + r.status))}</span>${notesHtml(r.notes)}
          <div>${esc(es ? r.explanation_es : r.explanation)}</div>${r.fact_ids.map((i) => quoteHtml(facts[i])).join("")}</div>`).join("")}</div>`;
    }
    h += `</div>`;
    h += `<div class="panel"><h3>${esc(t("h_summary"))}</h3><p>${esc(es ? rep.summary_es : rep.summary)}</p>
      <table class="kv"><tr><td>${esc(t("reason_for_referral"))}</td><td>${esc((es ? rep.reason_for_referral_es : rep.reason_for_referral) || t("unknown"))}</td></tr>
      <tr><td>${esc(t("preferred_language"))}</td><td>${esc(rep.preferred_language || t("unknown"))}</td></tr></table></div>`;

    const other = rep.rules.filter((r) => !r.gate && (r.status === "not_met" || (r.status === "cant_tell" && ["must", "exclude", "conditional", "document"].includes(r.kind))));
    if (other.length) {
      h += `<div class="panel"><h3>${esc(t("h_flags"))}</h3>${other
        .sort((a, b) => (a.status === "not_met" ? -1 : 1) - (b.status === "not_met" ? -1 : 1))
        .map((r) => `<div class="flag ${r.status}"><span class="rid">${esc(r.rule_id)}</span><span class="status ${r.status}">${esc(t("s_" + r.status))}</span>${notesHtml(r.notes)}
          <div class="muted small">${esc(r.text)}</div><div>${esc(es ? r.explanation_es : r.explanation)}</div>${r.fact_ids.map((i) => quoteHtml(facts[i])).join("")}</div>`)
        .join("")}</div>`;
    }
    if (rep.diagnoses.length) {
      h += `<div class="panel"><h3>${esc(t("h_diagnoses"))}</h3>${rep.diagnoses
        .map((d) => `<div class="flag ${d.ineligible ? "not_met" : "met"}"><span class="rid">${esc(d.rule_id)}</span>${d.verified ? "" : `<span class="note">${esc(t("unverified"))}</span>`}
          <div class="muted small">${esc(d.text)}</div><div>${esc(es ? d.explanation_es : d.explanation)}</div>${d.fact_ids.map((i) => quoteHtml(facts[i])).join("")}</div>`)
        .join("")}</div>`;
    }
    if (rep.conflicts.length) {
      h += `<div class="panel"><h3>${esc(t("h_conflicts"))}</h3>${rep.conflicts
        .map((c) => `<div class="flag cant_tell"><b>${esc(c.topic)}</b><div>${esc(es ? c.description_es : c.description)}</div>${c.fact_ids.map((i) => quoteHtml(facts[i])).join("")}</div>`)
        .join("")}</div>`;
    }
    if (rep.conditions.length) {
      h += `<div class="panel"><h3>${esc(t("h_conditions"))}</h3>${rep.conditions.map((c) => `<div class="flag cant_tell"><span class="rid">${esc(c.rule_id)}</span>${esc(c.text)}</div>`).join("")}</div>`;
    }
    h += `<div class="panel"><h3>${esc(t("h_docs"))}</h3><div class="doclist">${rep.checklist
      .map((c) => `<div class="doc"><span class="status ${c.status === "present" ? "present" : c.status === "missing" ? "missing" : "cant_tell"}">${esc(c.doc_id)}</span>
        <span>${esc(c.text)}${c.pages.length ? ` <span class="muted small">(${esc(t("page"))} ${c.pages.join(", ")})</span>` : ""}${notesHtml(c.notes)}</span></div>`)
      .join("")}</div></div>`;
    if (rep.questions.length) {
      h += `<div class="panel"><h3>${esc(t("h_questions"))}</h3><ul>${rep.questions.map((q) => `<li>${esc(q[LANG])} <span class="muted small">${esc(q.rule_ids.join(", "))}</span></li>`).join("")}</ul></div>`;
    }
    const qc = rep.qc;
    h += `<div class="panel"><h3>${esc(t("h_qc"))}</h3><p>${esc(t("qc_line", { v: qc.verified, n: qc.facts, p: qc.paraphrase, x: qc.not_found, d: qc.downgrades.length }))}</p>
      ${qc.downgrades.length ? `<div class="chips">${qc.downgrades.map((d) => `<span class="chip">${esc(d.rule_id)}: ${esc(t("s_" + d.from))} → ${esc(t("s_" + d.to))} (${esc(t(d.reason))})</span>`).join("")}</div>` : ""}
      ${rep.cost ? `<details class="admin"><summary>${esc(t("for_admins"))}</summary><p>${esc(t("cost"))}: $${Number(rep.cost.usd).toFixed(2)} · ${rep.cost.calls} calls · ${rep.cost.input_tokens.toLocaleString()} in / ${rep.cost.output_tokens.toLocaleString()} out · ${esc(rep.model || "")}</p></details>` : ""}
      <h3>${esc(t("h_pages"))}</h3><div class="thumbs">${rep.pages
        .map((p) => `<button data-page="${p.page}" class="${p.duplicate_of ? "dup" : ""} ${p.blank ? "blank" : ""}" title="${esc(p.summary || "")}">${p.page}: ${esc(p.page_type.replaceAll("_", " "))}${p.rotation ? ` ↻${p.rotation}°` : ""}${p.duplicate_of ? ` = ${p.duplicate_of}` : ""}</button>`)
        .join("")}</div></div>`;

    h += `<div class="panel"><h3>${esc(t("h_all_rules"))}</h3><details><summary class="muted">${rep.rules.length}</summary>${rep.rules
      .map((r) => `<div class="rule-item"><b>${esc(r.rule_id)}</b><span class="status ${r.status}">${esc(t("s_" + r.status))}</span>${notesHtml(r.notes)} <span class="muted small">${esc(r.text)}</span></div>`)
      .join("")}</details></div>`;
  }

  // Drafts
  if (DRAFTS) {
    const tabs = ["missing_items", "chase_nudge", "chase_supervisor", "clinical", "intake_cleared", "accepted", "more_time", "handoffs"].filter((k) => DRAFTS[k]);
    if (!tabs.includes(DRAFT_TAB)) DRAFT_TAB = tabs[0];
    h += `<div class="panel"><h3>${esc(t("h_drafts"))}</h3><div class="drafts-tabs">${tabs.map((k) => `<button data-draft="${k}" class="${k === DRAFT_TAB ? "on" : ""}">${esc(t("d_" + k))}</button>`).join("")}</div>`;
    const d = DRAFTS[DRAFT_TAB];
    if (DRAFT_TAB === "handoffs") {
      h += `<h3>${esc(t("kipu_fields"))}</h3><table class="kv">${d.kipu_fields.map(([k, v]) => `<tr><td>${esc(k)}</td><td>${esc(v)}</td></tr>`).join("")}</table>
        <h3>${esc(t("census_row"))} · ${esc(d.census_tab)}</h3><pre class="draft">${esc(d.census_csv)}</pre><button class="btn sm" data-copy="${esc(d.census_csv)}">${esc(t("copy"))}</button>
        <h3>${esc(t("ops_email"))}</h3><pre class="draft">${esc(d.ops_email)}</pre><button class="btn sm" data-copy="${esc(d.ops_email)}">${esc(t("copy"))}</button>
        <p class="draft-note">${esc(d.note)}</p>`;
    } else if (d) {
      h += `<div class="muted small">${esc(t("to"))}: ${esc(d.to || t("unknown"))}</div><pre class="draft">${esc(d.text)}</pre>
        <div class="row"><button class="btn sm" data-copy="${esc(d.text)}">${esc(t("copy"))}</button><span class="draft-note">${esc(d.note)}</span></div>`;
    }
    h += `</div>`;
  }

  // Actions
  const closed = ["accepted", "denied", "withdrawn"].includes(card.status);
  h += `<div class="panel"><h3>${esc(t("h_actions"))}</h3>`;
  if (!closed) {
    h += `<div class="actions">
      <button class="btn" data-act="info_sent">${esc(t("a_info_sent"))}</button>
      <button class="btn" data-act="hospital_replied">${esc(t("a_hospital_replied"))}</button>
      <button class="btn" data-act="chase_sent">${esc(t("a_chase_sent"))}</button>
      <button class="btn" data-act="clinical_pickup">${esc(t("a_clinical_pickup"))}</button>
      <button class="btn" data-act="intake_cleared">${esc(t("a_intake_cleared"))}</button>
      <button class="btn primary" data-act="accepted">${esc(t("a_accepted"))}</button></div>
      ${["likely_no", "clinical_check", "security_hold"].includes(card.suggested_route) ? `<div class="row"><input id="override-why" placeholder="${esc(t("override_ph"))}"></div>` : ""}
      <div class="row"><select id="handoff-to">${(LAST_Q?.staff || []).map((s) => `<option ${s.name === card.owner ? "selected" : ""}>${esc(s.name)}</option>`).join("")}</select>
        <button class="btn" data-act="handoff">${esc(t("hand_off"))}</button></div>
      <div class="row"><input id="deny-reason" placeholder="${esc(t("deny_reason_ph"))}"><button class="btn danger" data-act="denied">${esc(t("a_denied"))}</button></div>
      <div class="row"><select id="withdraw-reason">${["left_ama", "other_facility", "someones_home", "hospital_couldnt_wait", "no_reply", "other"].map((w) => `<option value="${w}">${esc(t("w_" + w))}</option>`).join("")}</select>
        <button class="btn" data-act="withdrawn">${esc(t("a_withdrawn"))}</button></div>`;
  } else {
    h += `<p>${statusChip(card.status)} ${esc(card.decision_reason || "")}</p>`;
    if (card.status === "accepted") {
      h += card.patient_arrived == null
        ? `<div class="actions"><button class="btn" data-act="patient_arrived" data-why="yes">${esc(t("a_arrived_yes"))}</button><button class="btn" data-act="patient_arrived" data-why="no">${esc(t("a_arrived_no"))}</button></div>`
        : `<p>${esc(t(card.patient_arrived ? "a_arrived_yes" : "a_arrived_no"))}</p>`;
    }
  }
  h += `<h3>${esc(t("h_audit"))}</h3><div class="audit">${audit.map((a) => `<div>${fmtClock(a.t)} · <b>${esc(a.who)}</b> · ${esc(a.what)} ${esc(a.detail)}</div>`).join("")}</div></div>`;

  $("#detail-body").innerHTML = h;
  $("#d-close").addEventListener("click", closeDetail);
  $("#run-review")?.addEventListener("click", async () => {
    try { await post(`/api/cards/${encodeURIComponent(OPEN)}/review`); refreshOpen(); } catch (e) { toast(e.message === "no_key" ? t("need_key") : e.message); }
  });
  $$("[data-page]", $("#detail-body")).forEach((b) => b.addEventListener("click", () => showPage(b.dataset.page)));
  $$("[data-draft]").forEach((b) => b.addEventListener("click", () => { DRAFT_TAB = b.dataset.draft; renderDetail(); }));
  $$("[data-copy]").forEach((b) => b.addEventListener("click", () => { navigator.clipboard.writeText(b.dataset.copy); toast(t("copied")); }));
  $$("[data-act]").forEach((b) => b.addEventListener("click", () => {
    const a = b.dataset.act;
    if (a === "denied") return act(a, "Clinical line", $("#deny-reason").value);
    if (a === "withdrawn") return act(a, "", $("#withdraw-reason").value);
    if (a === "handoff") return act(a, $("#handoff-to").value);
    if (a === "patient_arrived") return act(a, "", b.dataset.why);
    if (a === "accepted" && $("#override-why")) {
      if (!$("#override-why").value.trim()) { $("#override-why").focus(); return toast(t("override_need")); }
      return act(a, "", $("#override-why").value.trim());
    }
    if (a === "chase_sent") return act(a, "", (DETAIL.card.alerts.find((x) => x.code.startsWith("chase_"))?.code || "chase_nudge").replace("chase_", ""));
    act(a);
  }));
}

async function act(action, who = "", reason = "") {
  try {
    await post(`/api/cards/${encodeURIComponent(OPEN)}/act`, { action, who, reason });
    DETAIL = await api(`/api/cards/${encodeURIComponent(OPEN)}`);
    DRAFTS = await api(`/api/cards/${encodeURIComponent(OPEN)}/drafts?lang=${LANG}`);
    renderDetail();
  } catch (e) {
    toast(e.message);
  }
}

// ---------------------------------------------------------------- resources
let SCEN = [];
let EXAMPLES = {};
async function loadScenarios() {
  if (!SCEN.length) {
    const j = await api("/api/scenarios");
    SCEN = j.scenarios;
    EXAMPLES = j.examples;
    if (!$("#jottings").value) $("#jottings").value = EXAMPLES.note[LANG];
  }
  $("#scenarios").innerHTML = SCEN.map((s) => `<button class="chip" data-s="${esc(s.id)}">${esc(s.id)} · ${esc(s.title)}</button>`).join("");
  $$("#scenarios [data-s]").forEach((b) => b.addEventListener("click", () => {
    const s = SCEN.find((x) => x.id === b.dataset.s);
    $("#situation").value = `${s.client}\n"${s.in_their_words}"\n${(s.constraints || []).join("; ")}`;
    $("#situation").dataset.needs = (s.needs || []).join(",");
    phiLive($("#situation"), $("#phi-live"));
  }));
}

let phiTimer;
function phiLive(input, out) {
  clearTimeout(phiTimer);
  phiTimer = setTimeout(async () => {
    const r = await post("/api/phi-check", { text: input.value });
    out.classList.toggle("hidden", r.ok);
    if (!r.ok) out.innerHTML = `${esc(t("blocked"))} <b>${[...new Set(r.hits.map((h) => h.kind))].map(esc).join(", ")}</b><div class="small">${esc(r.masked)}</div>`;
  }, 350);
}
$("#situation").addEventListener("input", (e) => { delete e.target.dataset.needs; phiLive(e.target, $("#phi-live")); });
$("#jottings").addEventListener("input", (e) => phiLive(e.target, $("#phi-jot")));

function resCard(c) {
  const row = (k, v) => (v ? `<span>${esc(t(k))}</span><span>${esc(v)}</span>` : "");
  return `<div class="res-card"><h3>${esc(c.name)}</h3><div class="muted small">${esc(c.organization || "")}</div>
    ${c.why ? `<p>${esc(c.why)}</p>` : `<p class="muted">${esc(c.description || "")}</p>`}
    ${c.first_step ? `<p><b>${esc(t("res_first_step"))}:</b> ${esc(c.first_step)}</p>` : ""}
    ${c.watch_out ? `<p><b>${esc(t("res_watch"))}:</b> ${esc(c.watch_out)}</p>` : ""}
    <div class="facts">${row("res_phone", c.phone || t("unknown"))}${row("res_hours", c.hours || t("unknown"))}
      ${row("res_checked", c.verified_date)}<span>${esc(t("res_source"))}</span><span><a href="${esc(c.source_url)}" target="_blank" rel="noopener">${esc(c.source_url)}</a></span></div>
    ${c.referral_required ? `<span class="chip alert">${esc(t("res_referral_only"))}</span>` : ""}</div>`;
}

async function findResources(useAi) {
  const out = $("#res-out");
  out.innerHTML = `<div class="progress"><div class="spinner"></div></div>`;
  try {
    const needs = $("#situation").dataset.needs ? $("#situation").dataset.needs.split(",") : null;
    const r = await post("/api/resources", { situation: $("#situation").value, lang: LANG, needs, use_ai: useAi });
    if (r.blocked) {
      out.innerHTML = `<div class="phi">${esc(t("blocked"))} <b>${[...new Set(r.phi.hits.map((h) => h.kind))].map(esc).join(", ")}</b></div>`;
      return;
    }
    LAST_RES = r;
    let h = r.cards.length ? `<div class="row end"><button class="btn" id="print-handout">${esc(t("res_print"))}</button></div>` : "";
    if (r.danger) h += `<div class="safety"><b>${esc(t("res_safety"))}</b>${r.safety.map(resCard).join("")}</div>`;
    if (r.plan_today) h += `<div class="panel"><h3>${esc(t("res_plan"))}</h3><p>${esc(r.plan_today)}</p></div>`;
    h += r.cards.map(resCard).join("");
    if (r.ask_staff?.length) h += `<div class="panel"><h3>${esc(t("res_ask_staff"))}</h3><ul>${r.ask_staff.map((x) => `<li>${esc(x)}</li>`).join("")}</ul></div>`;
    if (r.cost) h += `<details class="admin"><summary>${esc(t("for_admins"))}</summary><p>${esc(t("cost"))}: $${r.cost.usd.toFixed(3)}</p></details>`;
    h += `<p class="muted small">${esc(r.disclaimer)}</p>`;
    out.innerHTML = h;
    $("#print-handout")?.addEventListener("click", printHandout);
  } catch (e) {
    out.innerHTML = `<div class="phi">${esc(e.message)}</div>`;
  }
}
$("#find").addEventListener("click", () => {
  if (!STATE.has_key) toast(t("need_key"));
  findResources(true);
});
$("#find-offline").addEventListener("click", () => findResources(false));

// ---------------------------------------------------------------- staff
$$(".role").forEach((b) => b.addEventListener("click", () => {
  if (b.dataset.role === "cm") return goTab("resources");
  $$(".role").forEach((x) => x.classList.toggle("on", x === b));
  $("#role-lvn").classList.toggle("hidden", b.dataset.role !== "lvn");
  $("#role-coord").classList.toggle("hidden", b.dataset.role !== "coord");
}));

$("#make-note").addEventListener("click", async () => {
  const out = $("#note-out");
  if (!STATE.has_key) return toast(t("need_key"));
  out.innerHTML = `<div class="progress"><div class="spinner"></div></div>`;
  try {
    const r = await post("/api/staff/note", { jottings: $("#jottings").value, lang: LANG });
    if (r.blocked) return (out.innerHTML = `<div class="phi">${esc(t("blocked"))}</div>`);
    out.innerHTML = `<div class="panel">${r.sentences
      .map((s) => `<div class="sentence ${s.supported ? "" : "bad"}">${esc(s.text)}${s.supported ? "" : ` <b class="note">${esc(t("not_in_jottings"))}</b>`}<div class="src">“${esc(s.source)}”</div></div>`)
      .join("")}
      ${r.missing.length ? `<h3>${esc(t("note_missing"))}</h3><ul>${r.missing.map((m) => `<li>${esc(m)}</li>`).join("")}</ul>` : ""}
      <p class="draft-note">${esc(t("draft_not_sent"))}</p>
      <details><summary>${esc(t("sent_to_ai"))}</summary><pre class="draft">${esc(r.sent_to_ai)}</pre></details>
      <p class="muted small">${esc(t("cost"))}: $${r.cost.usd.toFixed(4)}</p></div>`;
  } catch (e) {
    out.innerHTML = `<div class="phi">${esc(e.message)}</div>`;
  }
});

$("#explain").addEventListener("click", async () => {
  const out = $("#explain-out");
  if (!STATE.has_key) return toast(t("need_key"));
  out.innerHTML = `<div class="progress"><div class="spinner"></div></div>`;
  try {
    const r = await post("/api/staff/explain", { rule_id: $("#explain-id").value, lang: LANG });
    if (r.error) return (out.innerHTML = `<div class="phi">${esc(r.error)}</div>`);
    out.innerHTML = `<div class="panel"><div class="muted small">${esc(t("rule_text"))} · ${esc(r.rule.id)}</div><p><i>${esc(r.rule.text)}</i></p>
      ${r.gap ? `<p class="phi">${esc(t("gap"))}: ${esc(r.gap)}</p>` : ""}
      <p>${esc(r.plain)}</p><h3>${esc(t("look_in"))}</h3><ul>${r.look_in.map((x) => `<li>${esc(x)}</li>`).join("")}</ul>
      <h3>${esc(t("trap"))}</h3><p>${esc(r.trap)}</p>
      <details><summary>${esc(t("sent_to_ai"))}</summary><pre class="draft">${esc(r.sent_to_ai)}</pre></details>
      <p class="muted small">${esc(t("cost"))}: $${r.cost.usd.toFixed(4)}</p></div>`;
  } catch (e) {
    out.innerHTML = `<div class="phi">${esc(e.message)}</div>`;
  }
});

// ---------------------------------------------------------------- rules browser
async function renderRules() {
  if (!RULES) RULES = await api("/api/rules");
  const q = ($("#rule-search").value || "").toLowerCase();
  const gaps = Object.fromEntries(RULES.gaps);
  $("#rule-ids").innerHTML = RULES.rules.map((r) => `<option value="${esc(r.id)}">`).join("");
  let section = null;
  $("#rules-out").innerHTML = RULES.rules
    .filter((r) => !q || `${r.id} ${r.section} ${r.text}`.toLowerCase().includes(q))
    .map((r) => {
      const head = r.section !== section ? `<h3>${esc((section = r.section))}</h3>` : "";
      return `${head}<div class="rule-item"><b>${esc(r.id)}</b><span class="pill">${esc(r.kind)}</span> ${esc(r.text)}
        ${r.superseded_by ? `<span class="note">→ ${esc(r.superseded_by)}</span>` : ""}${gaps[r.id] ? `<div class="phi small">${esc(t("gap"))}: ${esc(gaps[r.id])}</div>` : ""}</div>`;
    })
    .join("");
}
$("#rule-search").addEventListener("input", renderRules);

// ---------------------------------------------------------------- settings
async function loadState() {
  STATE = await api("/api/state");
  $("#key-status").textContent = STATE.has_key ? t("key_saved") : t("key_none");
  $("#key-status").style.background = STATE.has_key ? "var(--green-soft)" : "var(--yellow-soft)";
  $("#version").textContent = `${STATE.app} ${STATE.version} · ${STATE.model} + ${STATE.fast_model} · log: ${STATE.db}`;
  $("#provider").value = STATE.provider;
  $("#foundry-resource").value = STATE.foundry_resource || "";
  $("#foundry-resource").classList.toggle("hidden", STATE.provider !== "foundry");
  $("#inbox-dir").value = STATE.inbox_dir || "";
}
$("#provider").addEventListener("change", (e) => $("#foundry-resource").classList.toggle("hidden", e.target.value !== "foundry"));
$("#loop-save").addEventListener("click", async () => {
  await post("/api/settings", { provider: $("#provider").value, foundry_resource: $("#foundry-resource").value.trim(), inbox_dir: $("#inbox-dir").value.trim() });
  await loadState();
  toast(t("save"));
});

async function loadReport() {
  try {
    const r = await api(`/api/report?practice=${$("#rep-practice").checked ? 1 : 0}`);
    const reasons = Object.entries(r.withdraw_reasons).map(([k, v]) => `${t("w_" + k)}: ${v}`).join(", ");
    $("#report").innerHTML = `<span class="pill">${r.referrals} ${esc(t("rep_referrals"))}</span>
      <span class="pill">${r.within_2h}/${r.decided} ${esc(t("rep_in_2h"))}</span>
      <span class="pill">${r.withdrawn} ${esc(t("rep_lost"))}${reasons ? ` (${esc(reasons)})` : ""}</span>
      <span class="pill">${r.arrived}/${r.accepted} ${esc(t("rep_arrived"))}</span>
      <span class="pill">${r.overrides.length} ${esc(t("rep_overrides"))}</span>
      <span class="pill">$${r.review_usd.toFixed(2)} ${esc(t("rep_cost"))}</span>`;
  } catch (e) {}
  setTimeout(loadReport, 5000);
}
$("#rep-practice").addEventListener("change", loadReport);
$("#open-settings").addEventListener("click", () => { loadState(); $("#settings").classList.remove("hidden"); });
$("#settings-close").addEventListener("click", () => $("#settings").classList.add("hidden"));
$("#settings").addEventListener("click", (e) => e.target.id === "settings" && $("#settings").classList.add("hidden"));
$("#key-save").addEventListener("click", async () => {
  try {
    await post("/api/key", { key: $("#key-input").value });
    $("#key-input").value = "";
    await loadState();
    toast(t("key_saved"));
  } catch (e) {
    toast(e.message);
  }
});
$("#key-clear").addEventListener("click", async () => { await post("/api/key/clear"); loadState(); });

// ---------------------------------------------------------------- first-run walkthrough
const store = {
  get: (k) => { try { return localStorage.getItem(k); } catch { return null; } },
  set: (k, v) => { try { localStorage.setItem(k, v); } catch {} },
};
let OB = { step: 0, role: store.get("cb_role") || "coord" };
const OB_ROLES = ["coord", "clinical", "lvn", "cm"];

function renderOnboard() {
  const m = 3;
  const dots = `<div class="ob-dots">${[0, 1, 2].map((i) => `<span class="${i === OB.step ? "on" : ""}"></span>`).join("")}</div>`;
  let h = `<div class="ob-step">${esc(t("ob_step", { n: OB.step + 1, m }))}</div>`;
  if (OB.step === 0) {
    h += `<h2 id="ob-title">${esc(t("ob_welcome"))} · Bienvenido</h2><p>${esc(t("ob_lang"))}</p>
      <div class="ob-choices"><button data-ob-lang="en" class="${LANG === "en" ? "on" : ""}">English</button><button data-ob-lang="es" class="${LANG === "es" ? "on" : ""}">Español</button></div>
      <p class="muted">${esc(t("ob_lang_note"))}</p>`;
  } else if (OB.step === 1) {
    h += `<h2 id="ob-title">${esc(t("ob_role"))}</h2><div class="ob-choices">${OB_ROLES.map((r) => `<button data-ob-role="${r}" class="${OB.role === r ? "on" : ""}">${esc(t("ob_role_" + r))}</button>`).join("")}</div>`;
  } else {
    h += `<h2 id="ob-title">${esc(t("ob_how"))}</h2><ul class="ob-list"><li>${esc(t("ob_how_1"))}</li><li>${esc(t("ob_how_2"))}</li><li>${esc(t("ob_how_3"))}</li></ul>
      <h2>${esc(t("ob_safe"))}</h2><ul class="ob-list"><li>${esc(t("ob_safe_1"))}</li><li>${esc(t("ob_safe_2"))}</li><li>${esc(t("ob_safe_3"))}</li></ul>`;
  }
  h += `<div class="row" style="justify-content:space-between">${dots}<div class="row">
    ${OB.step ? `<button class="btn ghost" id="ob-back">${esc(t("ob_back"))}</button>` : ""}
    <button class="btn primary big" id="ob-next">${esc(t(OB.step === 2 ? "ob_start" : "ob_next"))}</button></div></div>`;
  $("#onboard-body").innerHTML = h;
  $$("[data-ob-lang]").forEach((b) => b.addEventListener("click", async () => { await setLang(b.dataset.obLang); renderOnboard(); }));
  $$("[data-ob-role]").forEach((b) => b.addEventListener("click", () => { OB.role = b.dataset.obRole; renderOnboard(); }));
  $("#ob-back")?.addEventListener("click", () => { OB.step--; renderOnboard(); });
  $("#ob-next").addEventListener("click", () => {
    if (OB.step < 2) { OB.step++; return renderOnboard(); }
    store.set("cb_onboarded", "1");
    store.set("cb_role", OB.role);
    $("#onboard").classList.add("hidden");
    if (OB.role === "cm") goTab("resources");
    else if (OB.role === "lvn") { goTab("staff"); $('.role[data-role="lvn"]').click(); }
    else goTab("referrals");
  });
  $("#ob-next").focus();
}
function startOnboard() {
  OB.step = 0;
  $("#settings").classList.add("hidden");
  $("#onboard").classList.remove("hidden");
  renderOnboard();
}
$("#ob-again").addEventListener("click", startOnboard);

// ---------------------------------------------------------------- printable client handout
let LAST_RES = null;
// The client's take-home PDF: built server-side so phones, addresses and hours come only from
// the sourced list. Opens in the browser's PDF viewer, ready to print.
async function printHandout() {
  if (!LAST_RES) return;
  const r = LAST_RES;
  const items = r.cards.map((c) => ({ resource_id: c.id, why: c.why, first_step: c.first_step, watch_out: c.watch_out }));
  const resp = await fetch("/api/handout", { method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ items, plan_today: r.plan_today, lang: LANG, danger: r.danger }) });
  if (!resp.ok) return toast(t("error"));
  const url = URL.createObjectURL(await resp.blob());
  window.open(url, "_blank");
}

// ---------------------------------------------------------------- boot
(async function boot() {
  S = await (await fetch("/static/strings.json")).json();
  await loadState();
  LANG = STATE.lang || "en";
  applyI18n();
  loadScenarios();
  renderRules();
  poll();
  loadReport();
  if (!store.get("cb_onboarded")) startOnboard();
})();
