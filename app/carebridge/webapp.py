"""The local app: a small web server on 127.0.0.1 that only this computer can reach.

Packet pages and reviews stay in memory and are gone when the app closes. Nothing is written to
disk except settings, and nothing is sent anywhere except the Claude API calls a review makes.
"""

import json
import mimetypes
import os
import re
import secrets
import sys
import threading
import time
import traceback
from datetime import datetime, timedelta
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from . import APP_NAME, __version__, auth, config, critical, drafts, gateway, guard, handout, hospital, intake, kipu_check, llm, mail, mcp, phi, resources, rules, staff, store, tracker
from .pages import load_packet
from .paths import BUNDLE, DEMO_DIR, FROZEN, LOGO, load_json, packets_dir

if not FROZEN:
    sys.path.insert(0, str(BUNDLE.parent))  # app/, so `demo` imports in a source checkout

TRACK = tracker.Tracker()
TRACK.overnight_clock = config.load_settings().get("overnight_clock") or "arrival"
PACKETS: dict[str, tuple[bytes, str]] = {}  # card id -> (file bytes, filename), in memory only
REVIEWS: dict[str, intake.Review] = {}  # card id -> running or finished review
SAMPLES: dict[str, dict] = {}
LOCK = threading.Lock()


def _demo_samples() -> dict:
    """Practice reviews for the synthetic patients, built from the organizers' answer key."""
    if not SAMPLES:
        try:
            from demo import synthetic

            SAMPLES.update(synthetic.sample_reports())
        except Exception:
            traceback.print_exc()
    return SAMPLES


def _demo_packet(pid: str) -> tuple[bytes, str] | None:
    """A synthetic practice patient (S01...), or a de-identified event packet (R01...) read by path."""
    if not re.fullmatch(r"[RS]\d\d", pid or ""):
        return None  # it becomes a file name below
    if pid.startswith("R"):
        d = packets_dir()
        p = d / f"{pid}.pdf" if d else None
    else:
        from demo import synthetic

        p = synthetic.packet_path(pid)
    return (p.read_bytes(), f"{pid}.pdf") if p and p.is_file() else None


def send_profile(pid: str) -> dict:
    """Put one synthetic patient on the board now, as a practice referral with its practice review."""
    from demo import synthetic

    prof = next((p for p in synthetic.profiles() if p["id"] == pid), None)
    if not prof:
        raise KeyError(pid)
    cm = prof["case_manager"]
    case = f"{pid}-{sum(1 for c in TRACK.cards if c.startswith(pid)) + 1}"
    card = TRACK.add({"id": case, "case_no": case, "channel": "fax", "hospital": prof["hospital"],
                      "packet_id": pid, "case_manager": f"{cm['name']}, {cm['title']}", "cm_email": cm["email"],
                      "cm_phone": cm["phone"], "practice": True, "synthetic": True})
    _on_land(card)
    return TRACK.view(card["id"])


def load_demo(start_hour: int = 16, speed: float = 60.0) -> dict:
    """The Monday 4:00 PM burst (docs/workflow-and-timing.md section 6), on a fast-forward clock."""
    inbox = load_json(DEMO_DIR / "inbox.json")
    TRACK.reset()
    REVIEWS.clear()
    PACKETS.clear()
    from . import notify

    notify.clear_practice()  # a restart is a new practice run: last run's alerts would block this one's
    today = datetime.now()
    monday = (today - timedelta(days=today.weekday())).replace(hour=start_hour, minute=0, second=0, microsecond=0)
    t0 = monday.timestamp()
    # Fast-forward until the last practice referral lands, then real time, so the 2-hour clocks
    # don't all run out while someone reads a card or a practice patient.
    last = max((r["arrives_min"] for r in inbox["referrals"]), default=0)
    TRACK.clock.set(sim_time=t0 - 30, speed=speed, real_from=t0 + (last + 1) * 60)
    def on_shift(s):
        a, b = (s.get("shift") or "00:00-24:00").split("-")
        mins = lambda x: int(x[:2]) * 60 + int(x[3:])
        return mins(a) <= start_hour * 60 < mins(b)

    if inbox.get("staff"):
        TRACK.staff = [{"name": s["name"], "role": s.get("role", "coordinator"), "on_shift": on_shift(s), "email": s.get("email", "")}
                       for s in inbox["staff"] if s.get("role") != "clinical_line"]
    contacts = {c["hospital"]: c for c in inbox.get("contacts", [])}
    for i, r in enumerate(inbox["referrals"]):
        c = contacts.get(r["hospital"], {})
        card = {"id": r["case_no"], "case_no": r["case_no"], "channel": r.get("channel"), "hospital": r["hospital"],
                "subject": r.get("subject"), "body": r.get("body"), "packet_id": r.get("packet"),
                "fallback_packet": r.get("fallback_packet"), "case_manager": c.get("case_manager"),
                "cm_email": c.get("cm_email"), "cm_phone": c.get("cm_phone"), "supervisor": c.get("supervisor"),
                "sup_email": c.get("sup_email"), "sup_phone": c.get("sup_phone"), "site": r.get("site", "Orange County"),
                "practice": True, "synthetic": r.get("packet", "").startswith("S")}
        TRACK.schedule(card, t0 + r["arrives_min"] * 60)
    arrivals = [r["arrives_min"] for r in inbox["referrals"]]
    walk = [r.get("withdraw_after_silence_min") for r in inbox["referrals"]]
    people = 1
    return {"manual": tracker.simulate(arrivals, 40, people, walk), "tool": tracker.simulate(arrivals, 10, people, walk),
            "minutes_manual": 40, "minutes_tool": 10, "people": people, "placeholder": True}


def _on_land(card: dict):
    """When a card lands: attach its packet and, for invented demo packets, the sample review."""
    pid = card.get("packet_id")
    if not pid or card["id"] in PACKETS:
        return
    got = _demo_packet(pid) or (_demo_packet(card["fallback_packet"]) if card.get("fallback_packet") else None)
    if got:
        PACKETS[card["id"]] = got
    used = pid if not card.get("fallback_packet") or (got and got[1].startswith(pid)) else card["fallback_packet"]
    card["packet_used"] = used
    sample = _demo_samples().get(used)
    if sample:
        TRACK.cards[card["id"]]["sample"] = True
        TRACK.attach_review(card["id"], sample)
        REVIEWS[card["id"]] = None  # sample, not a live run


def arrive(cid: str, data: bytes, name: str) -> None:
    """Every packet goes through here the moment it lands, with or without an API key: the file scan runs
    first, a blocked file is dropped from memory (never rendered, never sent), a held one is marked."""
    threat = guard.scan_file(data, name)
    TRACK.cards[cid]["security"] = threat["verdict"]
    TRACK.cards[cid]["security_findings"] = [f["code"] for f in threat["findings"]]
    if threat["verdict"] != guard.OK:
        TRACK.log(cid, "system", f"security {threat['verdict']}", ", ".join(TRACK.cards[cid]["security_findings"]))
    if threat["verdict"] == guard.BLOCK:
        return
    PACKETS[cid] = (data, name)
    if config.get_api_key():
        start_review(cid)


def start_review(cid: str, full: bool = False) -> None:
    data, name = PACKETS[cid]
    threat = guard.scan_file(data, name)
    seen = TRACK.cards[cid].get("security")
    TRACK.cards[cid]["security"] = threat["verdict"]
    if threat["verdict"] == guard.BLOCK:
        # Isolate: the file is dropped from memory, never rendered and never sent anywhere.
        PACKETS.pop(cid, None)
        review = intake.Review([], name, TRACK.cards[cid]["arrived_at"], threat)
        review.error, review.stage = "security_block", "error"
        REVIEWS[cid] = review
        TRACK.cards[cid]["review_state"] = "error"
        TRACK.log(cid, "system", "security block", ", ".join(f["code"] for f in threat["findings"]))
        return
    if threat["verdict"] == guard.HOLD and seen != guard.HOLD:
        TRACK.log(cid, "system", "security hold", ", ".join(f["code"] for f in threat["findings"]))
    review = intake.Review(load_packet(data, name), name, TRACK.cards[cid]["arrived_at"], threat)
    # Every step the AI takes goes in the audit log. The messages are counts and page numbers, never chart text.
    review.on_log = lambda stage, msg: TRACK.log(cid, "Claude", f"AI step: {stage}", msg, role="ai")
    review.full_read = full
    REVIEWS[cid] = review
    TRACK.cards[cid]["sample"] = False
    TRACK.cards[cid]["review_state"] = "running"
    TRACK.log(cid, "system", "review started", f"{len(review.pages)} pages")

    def work():
        try:
            rep = intake.run(review)
            TRACK.attach_review(cid, rep)
        except Exception as e:
            review.error = str(e)
            review.stage = "error"
            TRACK.cards[cid]["review_state"] = "error"
            # The kind of error only: its message can carry text from the packet or the model.
            TRACK.log(cid, "system", "review failed", type(e).__name__)
            if not isinstance(e, llm.LLMError):
                traceback.print_exc()

    threading.Thread(target=work, daemon=True).start()


def add_email(raw: bytes, name: str, arrived_at: float | None = None, case: str = "") -> dict:
    """An .eml referral becomes a card like a fax: body pages first, then the attachments."""
    got = mail.packet_from_eml(raw)
    case = case or f"REF-{len(TRACK.cards) + 1:03d}"
    card = TRACK.add({"id": case, "case_no": case, "channel": "email", "hospital": "unknown",
                      "subject": got["subject"], "sender": got["sender"], "packet_used": name,
                      "email_skipped": got["skipped"], "email_body_set_aside": got["body_set_aside"]},
                     arrived_at=arrived_at or got["sent_at"])
    for s in got["skipped"]:
        TRACK.log(card["id"], "system", "email attachment not used", f"{s['name']}: {s['reason']}")
    if got["body_set_aside"]:
        TRACK.log(card["id"], "system", "security hold", "email text gives orders to the AI; not used")
    if got["pdf"]:
        arrive(card["id"], got["pdf"], Path(name).stem + ".pdf")
    return card


def _form_sidecar(packet: Path) -> dict:
    """The hospital form's details, when the intake flow (m365/flows.md) saves them next to the
    packet as <packet>.json: case code, hospital and who sent it. Missing fields stay unknown."""
    try:
        with open(packet.with_suffix(".json"), encoding="utf-8") as fh:
            form = json.load(fh)
    except (OSError, ValueError):
        return {}
    out = {"channel": "form"}
    if form.get("case_code"):
        out["id"] = out["case_no"] = str(form["case_code"])
    if form.get("hospital"):
        out["hospital"] = str(form["hospital"])
    who = ", ".join(str(form[k]) for k in ("submitter_name", "submitter_role") if form.get(k))
    if who:
        out["case_manager"] = who
    for src, dst in (("submitter_email", "cm_email"), ("submitter_phone", "cm_phone"), ("submitter_lang", "cm_lang")):
        if form.get(src):
            out[dst] = str(form[src])
    return out


def watch_inbox(interval: float = 5.0) -> None:
    """Step 1 of the closed loop: a referral saved into the inbox folder (fax PDF or email
    attachment) becomes a card. The clock starts from the file's arrival time, not when it is opened."""
    seen: set[str] = set()

    def loop():
        while True:
            folder = config.inbox_dir()
            if folder and Path(folder).is_dir():
                for f in sorted(Path(folder).iterdir()):
                    if f.suffix.lower() not in (".pdf", ".tif", ".tiff", ".eml") or str(f) in seen:
                        continue
                    seen.add(str(f))
                    try:
                        data = f.read_bytes()
                    except OSError:
                        seen.discard(str(f))  # still being written; try again next pass
                        continue
                    if f.suffix.lower() == ".eml":
                        # The clock starts when the email was received in the folder, never later.
                        try:
                            add_email(data, f.name, arrived_at=f.stat().st_mtime)
                        except Exception:
                            traceback.print_exc()
                        continue
                    case = f"REF-{len(TRACK.cards) + 1:03d}"
                    low = f.name.lower()
                    # Aidin referrals saved as a PDF into the same folder (unconfirmed with IHH) keep their channel.
                    channel = "aidin" if "aidin" in low else "fax" if "fax" in low else "email"
                    fields = {"id": case, "case_no": case, "channel": channel,
                              "hospital": "unknown", "packet_used": f.name}
                    fields.update(_form_sidecar(f))
                    card = TRACK.add(fields, arrived_at=f.stat().st_mtime)
                    arrive(card["id"], data, f.name)
            time.sleep(interval)

    threading.Thread(target=loop, daemon=True).start()


# What the person who sent a referral may see on the upload page: the status in their words, nothing
# from the packet and never "likely no" (m365/referrals-table.md, "Status: what IHH sees").
PUBLIC_STATUS = {"received": "received", "reviewing": "reviewing", "needs_info": "needs_info",
                 "clinical_check": "escalated", "likely_no": "escalated", "intake_cleared": "intake_cleared",
                 "accepted": "accepted", "denied": "not_accepted", "withdrawn": "closed"}
SOURCES = ("hospital", "snf", "community", "partner")


def _field(form: dict, k: str, n: int = 120) -> str:
    # Typed by whoever has the upload link: it lands in drafts, Kipu fields and staff alerts.
    v = guard.clean(re.sub(r"\s+", " ", str(form.get(k) or "")).strip()[:n])
    return "[set aside]" if guard.scan_text(v) else v


def send_page_upload(data: bytes, name: str, form: dict) -> dict:
    """The hospital upload page (IHH's QR-code plan): one front door, a receipt right away.
    More documents for an open case come in as their own packet, linked to it, and stop the reminders."""
    threat = guard.scan_file(data, name)
    if threat["verdict"] == guard.BLOCK:
        raise guard.Blocked(threat)
    lang = "es" if form.get("lang") == "es" else "en"
    parent = TRACK.cards.get(_field(form, "case_code", 24))
    if parent and not secrets.compare_digest(str(form.get("key") or ""), parent.get("receipt_key") or ""):
        parent = None  # a case code alone is not enough to add to someone else's referral
    if parent:
        case = f"{parent['case_no']}-M{sum(1 for c in TRACK.cards if c.startswith(parent['case_no'] + '-M')) + 1}"
    else:
        case = f"REF-{len(TRACK.cards) + 1:03d}"
    who = ", ".join(x for x in (_field(form, "name"), _field(form, "role")) if x)
    card = TRACK.add({"id": case, "case_no": case, "channel": "upload_page", "hospital": _field(form, "facility") or "unknown",
                      "source": form.get("source") if form.get("source") in SOURCES else None,
                      "case_manager": who or None, "cm_email": _field(form, "email") or None,
                      "cm_phone": _field(form, "phone", 40) or None, "cm_lang": lang, "packet_used": name,
                      "more_for": parent["id"] if parent else None, "receipt_key": secrets.token_urlsafe(9)})
    if parent:
        TRACK.act(parent["id"], "hospital_replied", "hospital", f"more documents: {case}")
    hospital.sync(TRACK)
    arrive(card["id"], data, name)
    receipt = next(m for m in TRACK.cards[case]["hospital_messages"] if m["kind"] == "received")
    return {"case_code": case, "key": card["receipt_key"], "arrived_at": card["arrived_at"],
            "deadline": TRACK.view(case)["deadline"], "receipt": {k: receipt[k] for k in ("subject", "body")}}


def send_page_status(case: str, key: str, lang: str) -> dict | None:
    c = TRACK.cards.get(case)
    if not c or not key or not secrets.compare_digest(key, c.get("receipt_key") or ""):
        return None
    st = PUBLIC_STATUS.get(c["status"], "received")
    if st == "received" and REVIEWS.get(case) is not None:
        st = "reviewing"
    msg = hospital.templates()[st]["es" if lang == "es" else "en"]
    return {"case_code": case, "status": st, "subject": msg["subject"].format(case_code=case)}


def send_page_checklist() -> list[dict]:
    """IHH's own list of documents to include, so the sender can check before sending."""
    every = rules.all_rules()
    return [{"id": d, "en": every[d]["text"], "es": drafts.DOC_ES.get(d, every[d]["text"])} for d in rules.checklist_ids()]


def card_report(cid: str) -> dict | None:
    r = REVIEWS.get(cid)
    if r is None:
        if TRACK.cards[cid].get("sample"):
            return _demo_samples().get(TRACK.cards[cid].get("packet_used"))
        return None
    return r.report


class Handler(BaseHTTPRequestHandler):
    server_version = f"CareBridge/{__version__}"

    def log_message(self, fmt, *args):  # quiet console; no request paths that could carry text
        pass

    # ---- helpers ---------------------------------------------------------------------------
    def _send(self, code: int, body: bytes, ctype: str, extra: dict | None = None):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(body)

    def _json(self, obj, code: int = 200):
        self._send(code, json.dumps(obj, ensure_ascii=False, default=str).encode("utf-8"), "application/json; charset=utf-8")

    def _body(self) -> bytes:
        n = int(self.headers.get("Content-Length") or 0)
        if n < 0 or n > guard.MAX_BYTES:
            raise guard.Blocked({"verdict": guard.BLOCK, "kind": None, "pages": {},
                                 "findings": [{"code": "too_big", "level": guard.BLOCK}]})
        return self.rfile.read(n) if n else b""

    def _jbody(self) -> dict:
        try:
            return json.loads(self._body() or b"{}")
        except ValueError:
            return {}

    def _local_only(self) -> bool:
        # Refuse requests a web page on another site could forge against this local server.
        origin = self.headers.get("Origin")
        host = self.headers.get("Host", "")
        # The exact name, not a prefix: "localhost.evil.com" is a DNS-rebinding site, not this computer.
        try:
            name = urlparse("//" + host).hostname
        except ValueError:
            name = None
        if name not in ("127.0.0.1", "localhost", "::1"):
            self._json({"error": "forbidden"}, 403)
            return False
        if origin and urlparse(origin).netloc != host:
            self._json({"error": "forbidden"}, 403)
            return False
        return True

    # ---- routes ----------------------------------------------------------------------------
    def _practice_off(self, p: str) -> bool:
        """In production the practice patients, the demo board and its fast clock do not exist."""
        if config.production() and (p in ("/api/demo", "/api/clock", "/static/profiles.html")
                                    or p == "/api/profiles" or p.startswith("/api/profiles/")):
            self._json({"error": "practice_off"}, 404)
            return True
        return False

    def do_GET(self):
        if not self._local_only():
            return
        if not gateway.allowed(self, urlparse(self.path).path) or gateway.handle(self, "GET"):
            return
        if self._practice_off(urlparse(self.path).path):
            return
        u = urlparse(self.path)
        q = parse_qs(u.query)
        p = u.path
        try:
            if p in ("/", "/index.html"):
                return self._static("index.html")
            if p in ("/send", "/send/"):
                return self._static("send.html")
            if p == "/send/checklist":
                return self._json({"docs": send_page_checklist()})
            if p == "/send/status":
                got = send_page_status(q.get("case", [""])[0], q.get("key", [""])[0], q.get("lang", ["en"])[0])
                return self._json(got) if got else self._json(gateway.error("not found"), 404)
            if p.startswith("/static/"):
                return self._static(p[len("/static/"):])
            if p == "/api/state":
                s = config.load_settings()
                prod = config.production()
                real = sorted(x.stem for x in packets_dir().glob("R*.pdf")) if packets_dir() and not prod else []
                return self._json({"app": APP_NAME, "version": __version__, "has_key": bool(config.get_api_key()),
                                   "model": config.model(), "fast_model": config.fast_model(), "side_model": config.side_model(),
                                   "lang": s.get("lang", "en"), "real_packets": real, "provider": config.provider(),
                                   "foundry_resource": config.foundry_resource(), "inbox_dir": config.inbox_dir(), "kipu_url": config.kipu_url(),
                                   "overnight_clock": TRACK.overnight_clock, "auto_hospital_messages": hospital.auto(),
                                   "production": prod, "db": str(store.db_path())})
            if p == "/api/queue":
                land()
                q_ = TRACK.queue(owner=q.get("owner", [""])[0] or None)
                for v in q_:
                    r = REVIEWS.get(v["id"])
                    v["review_stage"] = r.stage if r else ("sample" if v.get("sample") else None)
                    v["review_progress"] = r.progress[-1] if r and r.progress else None
                    v["has_packet"] = v["id"] in PACKETS
                    v.pop("body", None)
                    v.pop("receipt_key", None)
                return self._json({"now": TRACK.clock.now(), "speed": TRACK.clock.speed, "cards": q_,
                                   "pending": len(TRACK.pending), "peak": TRACK.peak_warning(),
                                   "report": TRACK.report(), "withdraw_reasons": TRACK.report_withdrawals(),
                                   "staff": TRACK.staff})
            parts = p.strip("/").split("/")
            if parts[:2] == ["api", "cards"] and len(parts) >= 3:
                cid = parts[2]
                if cid not in TRACK.cards:
                    return self._json(gateway.error("not found"), 404)
                if len(parts) == 3:
                    r = REVIEWS.get(cid)
                    rep_ = card_report(cid)
                    critical.of(rep_)
                    view = {k: v for k, v in TRACK.view(cid).items() if k != "receipt_key"}
                    return self._json({"card": view, "report": rep_,
                                       "progress": r.progress if r else [], "error": r.error if r else None,
                                       "audit": [a for a in TRACK.audit if a["card"] == cid]})
                if parts[3] == "pages" and len(parts) == 5:
                    return self._page(cid, int(parts[4].split(".")[0]))
                if parts[3] == "drafts":
                    return self._json(self._drafts(cid, q.get("lang", ["en"])[0]))
            if p == "/api/rules":
                return self._json({"rules": list(rules.all_rules().values()), "gaps": rules.GAPS, "gates": rules.GATES})
            if p == "/api/scenarios":
                if config.production():  # made-up clients and jottings are practice material
                    return self._json({"scenarios": [], "examples": {}})
                return self._json({"scenarios": resources.scenarios(), "examples": staff.EXAMPLES})
            if p == "/api/profiles" or p.startswith("/api/profiles/"):
                return self._profiles(p.strip("/").split("/")[2:], q.get("lang", ["en"])[0], q.get("style", ["color"])[0])
            if p == "/api/report":
                return self._json(store.weekly_report(int(q.get("days", ["7"])[0]),
                                                      q.get("practice", ["0"])[0] == "1" and not config.production()))
            if p == "/api/audit":
                return self._json(TRACK.audit[-300:])
            if p.startswith("/api/notify"):
                return self._notify_get(p, q)
            return self._json(gateway.error("not found"), 404)
        except Exception as e:
            traceback.print_exc()
            return self._json(gateway.error(str(e), "server"), 500)

    def do_POST(self):
        if not self._local_only():
            return
        if not gateway.allowed(self, urlparse(self.path).path) or gateway.handle(self, "POST"):
            return
        if self._practice_off(urlparse(self.path).path):
            return
        p = urlparse(self.path).path
        try:
            if p == "/mcp":
                me = gateway.person(self)
                body = self._jbody()
                if isinstance(body, dict) and body.get("method") == "tools/call":
                    gateway.audit(self, "Copilot tool", str((body.get("params") or {}).get("name", ""))[:60])
                resp = mcp.handle(body, allow=lambda tool: auth.can(me, auth.MCP_TOOLS.get(tool, "staff_tools")))
                return self._json(resp) if resp else self._send(202, b"", "text/plain")
            if p == "/api/key":
                key = self._jbody().get("key", "").strip()
                if not key.startswith("sk-ant-"):
                    return self._json(gateway.error("That key doesn't look right. Copy it again from IT, all of it.", "bad_key"), 400)
                config.set_api_key(key)
                gateway.audit(self, "Claude API key set")
                return self._json({"ok": True})
            if p == "/api/key/clear":
                config.clear_api_key()
                gateway.audit(self, "Claude API key removed")
                return self._json({"ok": True})
            if p == "/send/upload":
                data = self._body()
                if not data:
                    return self._json(gateway.error("empty file"), 400)
                name = re.sub(r"[^\w .()-]", "_", Path(self.headers.get("X-Filename") or "packet.pdf").name)[:120]
                if not name.lower().endswith((".pdf", ".tif", ".tiff")):
                    return self._json({"error": "pdf_only"}, 400)
                form = {k: v[0] for k, v in parse_qs(urlparse(self.path).query).items()}
                return self._json(send_page_upload(data, name, form))
            if p == "/api/settings":
                b = self._jbody()
                keys = ("lang", "model", "fast_model", "side_model", "provider", "foundry_resource", "inbox_dir", "kipu_url",
                        "overnight_clock", "auto_hospital_messages")
                if "overnight_clock" in b:
                    if b["overnight_clock"] not in ("arrival", "morning"):
                        return self._json({"error": "overnight_clock is arrival or morning"}, 400)
                    TRACK.overnight_clock = b["overnight_clock"]
                if "auto_hospital_messages" in b:
                    b["auto_hospital_messages"] = bool(b["auto_hospital_messages"])
                changed = {k: v for k, v in b.items() if k in keys}
                gateway.audit(self, "settings changed", ", ".join(f"{k}={v}" for k, v in changed.items())[:300])
                return self._json(config.save_settings(changed))
            if p == "/api/demo":
                b = self._jbody()
                gateway.audit(self, "practice demo restarted")
                return self._json(load_demo(speed=float(b.get("speed", 60))))
            if p == "/api/clock":
                b = self._jbody()
                TRACK.clock.set(speed=float(b.get("speed", 1)))
                return self._json({"speed": TRACK.clock.speed})
            if p == "/api/upload":
                data = self._body()
                name = re.sub(r"[^\w .()-]", "_", Path(self.headers.get("X-Filename") or "packet.pdf").name)[:120]
                if not data:
                    return self._json(gateway.error("empty file"), 400)
                if name.lower().endswith(".eml"):
                    case = self.headers.get("X-Case") or ""
                    if not re.fullmatch(r"[A-Za-z0-9-]{1,24}", case) or case in TRACK.cards:
                        case = ""
                    return self._json({"card": TRACK.view(add_email(data, name, time.time(), case)["id"])})
                threat = guard.scan_file(data, name)
                if threat["verdict"] == guard.BLOCK:
                    raise guard.Blocked(threat)
                case = self.headers.get("X-Case") or ""
                if not re.fullmatch(r"[A-Za-z0-9-]{1,24}", case) or case in TRACK.cards:
                    case = f"REF-{len(TRACK.cards) + 1:03d}"
                card = TRACK.add({"id": case, "case_no": case, "channel": "upload",
                                  "hospital": _field({"h": self.headers.get("X-Hospital")}, "h") or "unknown",
                                  "packet_used": name})
                arrive(card["id"], data, name)
                return self._json({"card": TRACK.view(card["id"])})
            parts = p.strip("/").split("/")
            if parts[:2] == ["api", "cards"] and len(parts) == 4:
                cid, what = parts[2], parts[3]
                if cid not in TRACK.cards:
                    return self._json(gateway.error("not found"), 404)
                if what == "review":
                    if cid not in PACKETS:
                        return self._json(gateway.error("No packet file for this referral."), 400)
                    if not config.get_api_key():
                        return self._json({"error": "no_key"}, 400)
                    start_review(cid, full=bool(self._jbody().get("full")))
                    return self._json({"ok": True})
                if what == "act":
                    b = self._jbody()
                    try:
                        # With sign-in on, the person and role come from the session, not the request.
                        me = gateway.person(self) if auth.mode() != "off" else None
                        if me and not auth.can(me, b["action"]):
                            return self._json({"error": "not_allowed", "role": me.get("role"), "needs": f"act:{b['action']}"}, 403)
                        # For a hand-off, "who" in the request is the person it goes to, not the actor.
                        c = TRACK.act(cid, b["action"], me["name"] if me else b.get("who", ""), b.get("reason", ""),
                                      role=auth.act_role(me),
                                      target=b.get("who") if b["action"] == "handoff" else None)
                    except ValueError as e:
                        return self._json(gateway.error(str(e)), 400)
                    return self._json({"card": TRACK.view(c["id"])})
            if p == "/api/resources":
                b = self._jbody()
                return self._json(resources.find(b.get("situation", ""), b.get("lang", "en"), b.get("needs") or None,
                                                 use_ai=bool(b.get("use_ai", True)) and bool(config.get_api_key())))
            if p.startswith("/api/profiles/") and p.endswith("/send"):
                try:
                    return self._json({"card": send_profile(p.split("/")[3])})
                except KeyError:
                    return self._json(gateway.error("not found"), 404)
            if p == "/api/handout":
                b = self._jbody()
                # client_name goes onto the printed page only: not logged, not stored, not sent to Claude,
                # and not in the file name.
                pdf = handout.build(b.get("items") or [], b.get("plan_today", ""), b.get("lang", "en"), bool(b.get("danger")),
                                    b.get("style", "color"), b.get("client_name", ""))
                name = "sus-proximos-pasos.pdf" if b.get("lang") == "es" else "your-next-steps.pdf"
                return self._send(200, pdf, "application/pdf", {"Content-Disposition": f'inline; filename="{name}"'})
            if p == "/api/phi-check":
                return self._json(phi.check(self._jbody().get("text", "")))
            if p == "/api/staff/note":
                b = self._jbody()
                return self._json(staff.note_draft(b.get("jottings", ""), b.get("lang", "en")))
            if p == "/api/staff/explain":
                b = self._jbody()
                return self._json(staff.explain_rule(b.get("rule_id", ""), b.get("lang", "en")))
            if p.startswith("/api/notify"):
                return self._notify_post(p)
            return self._json(gateway.error("not found"), 404)
        except guard.Blocked as e:
            return self._json({"error": "security_block", "findings": e.threat["findings"]}, 422)
        except llm.LLMError as e:
            return self._json(gateway.error(str(e), "ai"), 502)
        except Exception as e:
            traceback.print_exc()
            return self._json(gateway.error(str(e), "server"), 500)

    def _static(self, rel: str):
        if rel == "lamplight-logo.svg":
            return self._send(200, LOGO.read_bytes(), "image/svg+xml")
        base = (BUNDLE / "web").resolve()
        f = (base / rel).resolve()
        if base not in f.parents and f != base or not f.is_file():
            return self._json(gateway.error("not found"), 404)
        ctype = mimetypes.guess_type(f.name)[0] or "application/octet-stream"
        if ctype.startswith("text/") or ctype in ("application/javascript", "application/json"):
            ctype += "; charset=utf-8"
        return self._send(200, f.read_bytes(), ctype)

    def _profiles(self, parts: list[str], lang: str = "en", style: str = "color"):
        """Synthetic practice patients: the list, one profile with its practice review, a page image,
        or the patient's take-home next-steps PDF."""
        from demo import synthetic

        if not parts:
            return self._json({"profiles": synthetic.profiles()})
        pid = parts[0]
        prof = next((x for x in synthetic.profiles() if x["id"] == pid), None)
        if not prof:
            return self._json(gateway.error("not found"), 404)
        if len(parts) == 1:
            return self._json({"profile": prof, "review": _demo_samples().get(pid)})
        if len(parts) == 2 and parts[1] == "handout.pdf":
            situation, needs = synthetic.client_situation(pid)
            res = resources.find(situation, lang, needs, use_ai=bool(config.get_api_key()))
            if res["blocked"]:
                return self._json({"error": "blocked"}, 400)
            items = [{"resource_id": c["id"], "why": c["why"], "first_step": c["first_step"], "watch_out": c["watch_out"]}
                     for c in res["cards"]]
            # The situation sent to Claude has no name; the (made-up) name goes on the printed page only.
            last, _, first = prof["patient"]["name"].partition(", ")
            pdf = handout.build(items, res.get("plan_today", ""), lang, res["danger"], style, f"{first} {last}".title().strip())
            name = f"{pid}-{'proximos-pasos' if lang == 'es' else 'next-steps'}{'-bw' if style == 'bw' else ''}.pdf"
            return self._send(200, pdf, "application/pdf", {"Content-Disposition": f'inline; filename="{name}"'})
        if len(parts) == 3 and parts[1] == "pages":
            n = int(parts[2].split(".")[0])
            path = synthetic.packet_path(pid)
            pages = load_packet(path.read_bytes(), path.name) if path else []
            if not 1 <= n <= len(pages):
                return self._json(gateway.error("not found"), 404)
            return self._send(200, pages[n - 1].jpeg(long_edge=1400), "image/jpeg")
        return self._json(gateway.error("not found"), 404)

    def _page(self, cid: str, n: int):
        r = REVIEWS.get(cid)
        pages = r.pages if r else None
        if pages is None and cid in PACKETS:
            data, name = PACKETS[cid]
            pages = load_packet(data, name)
            if TRACK.cards[cid].get("sample"):
                rep = card_report(cid) or {}
                for pg in pages:
                    meta = next((m for m in rep.get("pages", []) if m["page"] == pg.number), None)
                    if meta:
                        pg.rotation = meta["rotation"]
        if not pages or not 1 <= n <= len(pages):
            return self._json(gateway.error("not found"), 404)
        return self._send(200, pages[n - 1].jpeg(upright=True, long_edge=1400), "image/jpeg")

    def _drafts(self, cid: str, lang: str) -> dict:
        card = TRACK.view(cid)
        rep = card_report(cid)
        out = {"more_time": drafts.more_time(card, lang), "chase_nudge": drafts.chase(card, "nudge", lang),
               "chase_supervisor": drafts.chase(card, "supervisor", lang)}
        if card.get("clinical_sent_at"):
            m = hospital.render("escalated", card, lang)
            out["escalated"] = {"kind": "escalated", "to": m["to"], "text": f"Subject: {m['subject']}\n\n{m['body']}",
                                "note": drafts.AI_NOTE[lang]}
        if rep:
            out["missing_items"] = drafts.missing_items(card, rep, lang)
            out["clinical"] = drafts.clinical_handoff(card, rep, lang)
            out["accepted"] = drafts.decision_reply(card, rep, "accepted", "", lang)
            out["intake_cleared"] = drafts.decision_reply(card, rep, "intake_cleared", "", lang)
            out["handoffs"] = drafts.handoffs(card, rep, lang)
            out["markdown"] = mcp.report_markdown(rep, lang)
        return out

    # ---- staff alerts (notify.py): drafts in a local outbox, a person sends them ---------------
    def _app_url(self) -> str:
        return f"http://{self.headers.get('Host', '127.0.0.1')}/"

    def _notify_get(self, p: str, q: dict):
        from . import notify

        if p == "/api/notify/people":
            return self._json({"people": notify.people(TRACK.staff), "channels": notify.CHANNELS, "roles": notify.ROLES})
        notify.APP_URL = self._app_url()
        if p == "/api/notify/outbox":
            notify.sync(TRACK)
            return self._json({"outbox": notify.outbox(q.get("person", [None])[0], q.get("done", ["0"])[0] == "1",
                                                        staff=TRACK.staff)})
        parts = p.strip("/").split("/")
        if len(parts) >= 3 and parts[2].split(".")[0].isdigit():
            row = notify.get(int(parts[2].split(".")[0]), TRACK.staff)
            if not row:
                return self._json(gateway.error("not found"), 404)
            if parts[2].endswith(".eml") and row["channel"] == "email":
                return self._send(200, notify.eml(row), "message/rfc822",
                                  {"Content-Disposition": f'attachment; filename="{row["case_no"]}-{row["event"]}.eml"'})
            if len(parts) == 4 and parts[3] == "card.json" and row["channel"] == "teams":
                return self._send(200, json.dumps(row["card"] or {}, ensure_ascii=False).encode("utf-8"), "application/json; charset=utf-8",
                                  {"Content-Disposition": f'attachment; filename="{row["case_no"]}-{row["event"]}.json"'})
        return self._json(gateway.error("not found"), 404)

    def _notify_post(self, p: str):
        from . import notify

        b = self._jbody()
        try:
            if p == "/api/notify/people":
                return self._json({"person": notify.save_person(b)})
            parts = p.strip("/").split("/")
            if len(parts) == 4 and parts[2].isdigit() and parts[3] == "mark":
                # Who marked it comes from the sign-in, and only your own alerts unless you are a lead.
                me = gateway.person(self) if auth.mode() != "off" else None
                row = store.get_notification(int(parts[2]))
                if not row:
                    return self._json(gateway.error("not found"), 404)
                if me and row["person"] != me["name"] and not auth.can(me, "alert_mark_any"):
                    return self._json({"error": "not_allowed", "needs": "alert_mark_any"}, 403)
                notify.mark(int(parts[2]), b.get("status", ""), me["name"] if me else b.get("who", ""))
                return self._json({"ok": True})
        except ValueError as e:
            return self._json(gateway.error(str(e)), 400)
        return self._json(gateway.error("not found"), 404)


_LAND = threading.Lock()


def land() -> None:
    """Referrals whose arrival time has come join the board. Called by the board and by the alert
    loop, so alerts for new arrivals are drafted even when nobody has the board open."""
    with _LAND:
        for c in TRACK.tick():
            _on_land(c)


def notify_loop(interval: float = 10.0) -> None:
    """Draft staff alerts as the clock runs, even when nobody has the outbox open."""
    from . import notify

    def loop():
        while True:
            try:
                land()
                notify.sync(TRACK)
                hospital.sync(TRACK)
            except Exception:
                traceback.print_exc()
            time.sleep(interval)

    threading.Thread(target=loop, daemon=True).start()


def serve(port: int = 0, open_browser: bool = True) -> None:
    import webbrowser

    # Inside the Docker container the server binds 0.0.0.0 so the port mapping can reach it; the
    # compose file publishes it on the host's 127.0.0.1 only, and _local_only still checks Host.
    host = os.environ.get("CAREBRIDGE_HOST") or "127.0.0.1"
    httpd = ThreadingHTTPServer((host, port), Handler)
    url = f"http://127.0.0.1:{httpd.server_address[1]}/"
    if host == "127.0.0.1":
        print(f"{APP_NAME} {__version__} is running at {url}")
        print("Only this computer can open it. Close this window to quit; reviews are not saved.")
    else:
        print(f"{APP_NAME} {__version__} is listening on {host}:{httpd.server_address[1]} in the container.")
        print("Open the host port from compose.yaml (default http://localhost:8780/). Reviews are not saved.")
    watch_inbox()
    kipu_check.start(TRACK, PACKETS, card_report)
    from . import notify

    notify.APP_URL = url
    notify_loop()
    if open_browser:
        threading.Timer(0.6, lambda: webbrowser.open(url)).start()
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        httpd.server_close()
