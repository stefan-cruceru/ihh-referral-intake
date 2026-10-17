"""The 2-hour tracker: one queue, clock from arrival, clear owner, escalation and chase ladders.

Timings are placeholders from docs/workflow-and-timing.md sections 3 and 4 until IHH gives real
numbers. The tracker never approves or denies to beat the clock: a late correct answer beats an
on-time wrong one.
"""

import itertools
import threading
import time
from datetime import datetime, timedelta

from . import store

CLOCK_MIN = 120
STAGE_BUDGET = {"review": 5, "coordinator": 60, "hospital": 90, "decision": 105}  # minutes after arrival
LADDER = {"lead_unopened": 60, "clinical_repage": 30, "more_time": 15, "nudge": 30, "supervisor": 60}

# After hours (docs/workflow-and-timing.md, "What the intake director told us"): the team is on site until
# 8:30 PM, then two people cover by phone and the morning shift works what came in overnight. The morning
# start is a placeholder. Whether the 2 hours count from arrival or from the morning shift is IHH's call
# (open question 5), so it is a setting: "arrival" (default) or "morning".
TEAM_UNTIL = (20, 30)
MORNING_START = (7, 0)

# Steps only a person does (the director's step-by-step). The tool keeps who did it and when, never what
# they found: no names, no court records. "look" sends it to the lead to judge, as today.
STAFF_CHECKS = {"returning_client": ("new", "returning"), "background": ("clear", "look")}

# Why referrals walk, from IHH's own look at withdrawals (docs/workflow-and-timing.md section 4).
# Match IHH's exact categories once we see them.
WITHDRAW_REASONS = ["left_ama", "other_facility", "someones_home", "hospital_couldnt_wait", "no_reply", "other"]


def simulate(arrivals_min: list[float], minutes_each: float, people: int, withdraw_after: list[float | None] | None = None) -> list[dict]:
    """First-free-person queue: when each referral is decided, and whether it misses 2 hours or walks.

    withdraw_after: minutes after arrival a hospital stops waiting (None = it waits)."""
    free = [0.0] * people
    out = []
    for i, a in enumerate(arrivals_min):
        k = free.index(min(free))
        start = max(a, free[k])
        done = start + minutes_each
        free[k] = done
        walk = (withdraw_after or [None] * len(arrivals_min))[i]
        walked = walk is not None and done - a > walk
        out.append({"arrive": a, "start": start, "done": done, "minutes": done - a,
                    "missed": done - a > CLOCK_MIN, "withdrawn": walked})
    return out


STATUSES = ["received", "reviewing", "needs_info", "clinical_check", "likely_no", "intake_cleared",
            "accepted", "denied", "withdrawn"]
CLOSED = {"accepted", "denied", "withdrawn"}
VIEWING_SEC = 30  # someone counts as "has it open" for this long after their screen last checked in (real seconds)


def queue_key(v: dict) -> tuple:
    """Open before closed. A red safety flag or a security hold first, whatever the clock says. Then the
    2-hour clock in bands (red, yellow, green) and, inside a band, the best odds on paper, then least time left.
    Odds only order the list: a likely no still gets its answer inside 2 hours."""
    band = {"red": 0, "yellow": 1, "green": 2}.get(v["color"], 3)
    urgent = v.get("danger") == "red" or v.get("suggested_route") == "security_hold"
    odds = v.get("odds")
    return (v["status"] in CLOSED, not urgent, band, -(odds if odds is not None else -1), v["left_min"])


class Clock:
    """Real time by default. The demo can fast-forward (speed 60 = one second is one minute)."""

    def __init__(self):
        self.speed = 1.0
        self._real0 = time.time()
        self._sim0 = self._real0

    def now(self) -> float:
        return self._sim0 + (time.time() - self._real0) * self.speed

    def set(self, sim_time: float | None = None, speed: float | None = None):
        now = self.now()
        self._real0 = time.time()
        self._sim0 = sim_time if sim_time is not None else now
        if speed is not None:
            self.speed = speed


def is_overnight(ts: float) -> bool:
    d = datetime.fromtimestamp(ts)
    return (d.hour, d.minute) >= TEAM_UNTIL or (d.hour, d.minute) < MORNING_START


def morning_after(ts: float) -> float:
    """The next morning-shift start at or after ts."""
    d = datetime.fromtimestamp(ts)
    m = d.replace(hour=MORNING_START[0], minute=MORNING_START[1], second=0, microsecond=0)
    return (m if m >= d else m + timedelta(days=1)).timestamp()


class Tracker:
    def __init__(self):
        self.clock = Clock()
        self.overnight_clock = "arrival"
        self.cards: dict[str, dict] = {}
        self.staff: list[dict] = [
            {"name": "Lead", "role": "lead", "on_shift": True},
            {"name": "Coordinator 1", "role": "coordinator", "on_shift": True},
            {"name": "Coordinator 2", "role": "coordinator", "on_shift": True},
            {"name": "Coordinator 3", "role": "coordinator", "on_shift": False},
        ]
        self.audit: list[dict] = []
        self.pending: list[tuple[float, dict]] = []
        self._rr = itertools.count()
        self._lock = threading.Lock()

    # ---- audit ---------------------------------------------------------------------------
    def log(self, card_id: str | None, who: str, what: str, detail: str = ""):
        """What came in, what Claude flagged, who decided and why. No patient text."""
        self.audit.append({"t": self.clock.now(), "card": card_id, "who": who, "what": what, "detail": detail})
        practice = bool(self.cards.get(card_id, {}).get("practice")) if card_id else False
        store.log_event(card_id, who, what, detail, practice)

    def persist(self, cid: str):
        c = self.cards[cid]
        end = c.get("decided_at")
        c["minutes"] = round((end - c["arrived_at"]) / 60) if end else None
        store.save_card(c)

    # ---- intake --------------------------------------------------------------------------
    def assign(self) -> str:
        on = [s["name"] for s in self.staff if s["on_shift"] and s["role"] == "coordinator"]
        if not on:
            on = [s["name"] for s in self.staff if s["on_shift"]] or ["On-call"]
        return on[next(self._rr) % len(on)]

    def add(self, card: dict, arrived_at: float | None = None) -> dict:
        with self._lock:
            cid = card.get("id") or f"c{len(self.cards) + 1}"
            card = {
                "id": cid, "status": "received", "owner": None, "opened": False,
                "review_id": None, "review_state": None, "arrived_at": arrived_at or self.clock.now(),
                "info_requested_at": None, "hospital_replied_at": None, "clinical_sent_at": None,
                "clinical_picked_up": False, "decision": None, "decision_reason": None,
                "withdraw_reason": None, "chase": [], "suggested_route": None, "patient_arrived": None, "kipu_id": None,
                "override": 0, "override_reason": None, "review_usd": None,
                "danger": None, "danger_flags": [], "odds": None, "odds_why": [], "illegible_pages": [],
                "viewers": {}, "clinical_notes": [], "clinical_asks": [], "clinical_done_at": None,
                "staff_checks": {}, "source": None, "hospital_messages": [], **card,
            }
            card["id"] = cid
            card["overnight"] = is_overnight(card["arrived_at"])
            card["owner"] = card["owner"] or self.assign()
            self.cards[cid] = card
            self.log(cid, "system", "received", f"{card.get('channel', '')} from {card.get('hospital', '')}; owner {card['owner']}")
            self.persist(cid)
            return card

    def attach_review(self, cid: str, report: dict):
        c = self.cards[cid]
        code = report["recommendation"]["code"]
        c["review_state"] = code
        c["suggested_route"] = code
        c["review_usd"] = (report.get("cost") or {}).get("usd")
        rec = report["recommendation"]
        c["odds"], c["odds_why"] = rec.get("odds"), rec.get("odds_why") or []
        c["illegible_pages"] = rec.get("illegible_pages") or []
        c["danger"] = (report.get("danger") or {}).get("level")
        c["danger_flags"] = (report.get("danger") or {}).get("flags") or []
        c["status"] = {"likely_no": "likely_no", "clinical_check": "clinical_check", "needs_info": "needs_info",
                       "security_hold": "clinical_check"}.get(code, "reviewing")
        self.log(cid, "Claude", "flagged", f"route {code}; blockers {report['recommendation']['blockers']}")
        if report["recommendation"]["route_clinical"]:
            c["clinical_sent_at"] = self.clock.now()
            self.log(cid, "system", "sent to clinical line", "in parallel with the coordinator")
        self.persist(cid)

    # ---- actions -------------------------------------------------------------------------
    def act(self, cid: str, action: str, who: str = "", reason: str = "", role: str | None = None,
            target: str | None = None) -> dict:
        """who is the person acting; role comes from the signed-in staff list (auth.py). Without sign-in,
        the old name check stands. target is the new owner for a hand-off (defaults to who, as before)."""
        c = self.cards[cid]
        now = self.clock.now()
        if action in ("viewing", "leave"):
            # Presence only: who has this referral open right now. Not logged, not saved.
            if who:
                if action == "viewing":
                    c["viewers"][who] = time.time()
                else:
                    c["viewers"].pop(who, None)
            return c
        if action == "claim":
            if not who:
                raise ValueError("Pick your name first.")
            c["owner"] = who
        elif action == "open":
            c["opened"] = True
        elif action == "handoff":
            c["owner"] = target or who or self.assign()
            reason = reason or f"to {c['owner']}"
        elif action == "info_sent":
            c["info_requested_at"], c["status"] = now, "needs_info"
        elif action == "hospital_replied":
            c["hospital_replied_at"] = now
        elif action == "chase_sent":
            c["chase"].append({"t": now, "step": reason})
        elif action == "clinical_pickup":
            c["clinical_picked_up"] = True
        elif action in ("clinical_note", "clinical_ask", "clinical_done"):
            # The clinical reviewer's notes, kept here instead of a shared Excel sheet and Teams pings.
            # Only the clinical reviewer writes them. Notes cite pages ("page 16 shows..."), never names.
            clinical = role == "clinical" if role is not None else who.lower().startswith("clinic")
            if not clinical:
                raise ValueError("Only the clinical reviewer writes clinical notes.")
            if action != "clinical_done" and not reason.strip():
                raise ValueError("Type the note first.")
            c["clinical_picked_up"] = True
            if action == "clinical_note":
                c["clinical_notes"].append({"t": now, "who": who, "text": reason.strip()[:1000]})
            elif action == "clinical_ask":
                c["clinical_asks"].append({"t": now, "who": who, "text": reason.strip()[:200]})
            else:
                c["clinical_done_at"] = now
                if reason.strip():
                    c["clinical_notes"].append({"t": now, "who": who, "text": reason.strip()[:1000]})
            # The log keeps that a note was added, not the note itself (it may hold chart details).
            reason = "" if action != "clinical_ask" else reason.strip()[:200]
        elif action == "staff_check":
            # reason is "<check>:<result>", e.g. "background:clear". Nothing else is kept.
            check, _, result = reason.partition(":")
            if result not in STAFF_CHECKS.get(check, ()):
                raise ValueError("Unknown check.")
            c["staff_checks"][check] = {"result": result, "who": who, "t": now}
        elif action == "intake_cleared":
            c["status"] = "intake_cleared"
        elif action in ("accepted", "denied", "withdrawn"):
            clinical = role == "clinical" if role is not None else who.lower().startswith("clinic")
            if action == "denied" and not clinical:
                raise ValueError("Only the clinical line can deny a referral.")
            # Hard gate: pages the AI could not read for sure need the clinical line before any yes.
            if action == "accepted" and c.get("illegible_pages") and not clinical and not c.get("clinical_done_at"):
                pages = ", ".join(str(p) for p in c["illegible_pages"])
                raise ValueError(f"A clinical reviewer must read page(s) {pages} before this can be accepted.")
            c["status"], c["decision"] = action, action
            c["decision_reason"] = reason
            c["decided_at"] = now
            if action == "withdrawn":
                c["withdraw_reason"] = reason
            route = c.get("suggested_route")
            if (action == "accepted" and route in ("likely_no", "clinical_check", "security_hold")) or \
                    (action == "denied" and route in ("likely_yes", "needs_info")):
                # A person went against the suggested route: keep the reason so the checks improve.
                c["override"], c["override_reason"] = 1, reason or None
        elif action == "patient_arrived":
            c["patient_arrived"] = 0 if reason == "no" else 1
        elif action == "kipu_id":
            # The client's record number in Kipu, typed by staff after they create it there.
            c["kipu_id"] = reason.strip() or None
        else:
            raise ValueError(f"unknown action {action}")
        self.log(cid, who or c["owner"], action, reason)
        self.persist(cid)
        return c

    # ---- the clock -----------------------------------------------------------------------
    def clock_start(self, c: dict) -> float:
        """When the 2 hours start: on arrival, or at the morning shift for an overnight packet if IHH
        picks that (Settings)."""
        if self.overnight_clock == "morning" and c.get("overnight"):
            return morning_after(c["arrived_at"])
        return c["arrived_at"]

    def view(self, cid: str) -> dict:
        c = self.cards[cid]
        now = self.clock.now()
        end = c.get("decided_at") or now
        start = self.clock_start(c)
        elapsed = max(0.0, (end - start) / 60)
        left = CLOCK_MIN - elapsed
        color = "done" if c["status"] in CLOSED else "green" if left > 60 else "yellow" if left > 30 else "red"
        alerts = []
        if c["status"] not in CLOSED:
            if left <= LADDER["lead_unopened"] and not c["opened"]:
                alerts.append({"code": "lead_unopened", "to": "Lead"})
            if c["clinical_sent_at"] and not c["clinical_picked_up"] and (now - c["clinical_sent_at"]) / 60 >= LADDER["clinical_repage"]:
                alerts.append({"code": "clinical_repage", "to": "Clinical line, then Lead"})
            if left <= LADDER["more_time"]:
                alerts.append({"code": "more_time", "to": "Hospital"})
            if c["info_requested_at"] and not c["hospital_replied_at"]:
                quiet = (now - c["info_requested_at"]) / 60
                steps = {s["step"] for s in c["chase"]}
                if quiet >= LADDER["supervisor"] and "supervisor" not in steps:
                    alerts.append({"code": "chase_supervisor", "to": c.get("supervisor") or "Supervisor"})
                elif quiet >= LADDER["nudge"] and "nudge" not in steps:
                    alerts.append({"code": "chase_nudge", "to": c.get("case_manager") or "Case manager"})
        silent = None
        if c["info_requested_at"] and not c["hospital_replied_at"]:
            silent = round((now - c["info_requested_at"]) / 60)
        real = time.time()
        viewers = sorted(w for w, t in c["viewers"].items() if real - t <= VIEWING_SEC)
        clinical_min = None
        if c["clinical_sent_at"]:
            clinical_min = round(((c["clinical_done_at"] or now) - c["clinical_sent_at"]) / 60)
        return {**c, "elapsed_min": round(elapsed), "left_min": round(left), "color": color,
                "clock_start": start, "deadline": start + CLOCK_MIN * 60, "clinical_min": clinical_min,
                "alerts": alerts, "hospital_silent_min": silent, "viewers": viewers,
                "withdraw_risk": bool(silent and silent >= LADDER["nudge"])}

    def schedule(self, card: dict, at: float):
        """A mock arrival that lands in the queue when the clock reaches `at`."""
        self.pending.append((at, card))
        self.pending.sort(key=lambda x: x[0])

    def tick(self) -> list[dict]:
        landed = []
        now = self.clock.now()
        while self.pending and self.pending[0][0] <= now:
            at, card = self.pending.pop(0)
            landed.append(self.add(card, arrived_at=at))
        return landed

    def reset(self):
        self.cards.clear()
        self.pending.clear()
        self.audit.clear()
        self._rr = itertools.count()

    def queue(self, owner: str | None = None) -> list[dict]:
        views = [self.view(cid) for cid in self.cards]
        if owner:
            views = [v for v in views if v["owner"] == owner]
        return sorted(views, key=queue_key)

    def peak_warning(self, minutes_per_referral: float = 10) -> dict:
        """With N waiting and M on shift, which referrals miss the clock if nothing changes."""
        q = [v for v in self.queue() if v["status"] not in CLOSED]
        people = max(1, sum(1 for s in self.staff if s["on_shift"]))
        finish = [0.0] * people
        at_risk = []
        for v in q:
            i = finish.index(min(finish))
            finish[i] += minutes_per_referral
            if finish[i] > v["left_min"]:
                at_risk.append(v["case_no"])
        return {"waiting": len(q), "on_shift": people, "minutes_per_referral": minutes_per_referral, "at_risk": at_risk}

    def report_withdrawals(self) -> dict:
        reasons = {}
        for c in self.cards.values():
            if c["status"] == "withdrawn":
                reasons[c["withdraw_reason"] or "unknown"] = reasons.get(c["withdraw_reason"] or "unknown", 0) + 1
        return reasons

    def report(self) -> dict:
        closed = [self.view(cid) for cid in self.cards if self.cards[cid]["status"] in CLOSED]
        decided = [v for v in closed if v["status"] != "withdrawn"]
        return {
            "total": len(self.cards),
            "decided": len(decided),
            "within_2h": sum(1 for v in decided if v["elapsed_min"] <= CLOCK_MIN),
            "withdrawn": [{"case_no": v["case_no"], "reason": v["withdraw_reason"]} for v in closed if v["status"] == "withdrawn"],
            "clinical": clinical_turnaround([self.view(cid) for cid in self.cards]),
        }


def clinical_turnaround(views: list[dict]) -> dict:
    """How long the clinical second check takes, from sent to the reviewer's "done". The director said
    usually 20 to 40 minutes, sometimes 24 hours; this is how IHH would see it for itself."""
    done = sorted(v["clinical_min"] for v in views if v.get("clinical_done_at") and v.get("clinical_min") is not None)
    waiting = sum(1 for v in views if v.get("clinical_sent_at") and not v.get("clinical_done_at") and v["status"] not in CLOSED)
    return {"done": len(done), "waiting": waiting,
            "median_min": done[len(done) // 2] if done else None, "longest_min": done[-1] if done else None}
