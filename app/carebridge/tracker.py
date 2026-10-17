"""The 2-hour tracker: one queue, clock from arrival, clear owner, escalation and chase ladders.

Timings are placeholders from docs/workflow-and-timing.md sections 3 and 4 until IHH gives real
numbers. The tracker never approves or denies to beat the clock: a late correct answer beats an
on-time wrong one.
"""

import itertools
import threading
import time

from . import store

CLOCK_MIN = 120
STAGE_BUDGET = {"review": 5, "coordinator": 60, "hospital": 90, "decision": 105}  # minutes after arrival
LADDER = {"lead_unopened": 60, "clinical_repage": 30, "more_time": 15, "nudge": 30, "supervisor": 60}

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


class Tracker:
    def __init__(self):
        self.clock = Clock()
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
                "withdraw_reason": None, "chase": [], "suggested_route": None, "patient_arrived": None,
                "override": 0, "override_reason": None, "review_usd": None, **card,
            }
            card["id"] = cid
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
        c["status"] = {"likely_no": "likely_no", "clinical_check": "clinical_check", "needs_info": "needs_info"}.get(code, "reviewing")
        self.log(cid, "Claude", "flagged", f"route {code}; blockers {report['recommendation']['blockers']}")
        if report["recommendation"]["route_clinical"]:
            c["clinical_sent_at"] = self.clock.now()
            self.log(cid, "system", "sent to clinical line", "in parallel with the coordinator")
        self.persist(cid)

    # ---- actions -------------------------------------------------------------------------
    def act(self, cid: str, action: str, who: str = "", reason: str = "", role: str | None = None) -> dict:
        """role comes from the signed-in staff list (auth.py). Without sign-in, the old name check stands."""
        c = self.cards[cid]
        now = self.clock.now()
        if action == "open":
            c["opened"] = True
        elif action == "handoff":
            c["owner"] = who or self.assign()
        elif action == "info_sent":
            c["info_requested_at"], c["status"] = now, "needs_info"
        elif action == "hospital_replied":
            c["hospital_replied_at"] = now
        elif action == "chase_sent":
            c["chase"].append({"t": now, "step": reason})
        elif action == "clinical_pickup":
            c["clinical_picked_up"] = True
        elif action == "intake_cleared":
            c["status"] = "intake_cleared"
        elif action in ("accepted", "denied", "withdrawn"):
            clinical = role == "clinical" if role is not None else who.lower().startswith("clinic")
            if action == "denied" and not clinical:
                raise ValueError("Only the clinical line can deny a referral.")
            c["status"], c["decision"] = action, action
            c["decision_reason"] = reason
            c["decided_at"] = now
            if action == "withdrawn":
                c["withdraw_reason"] = reason
            route = c.get("suggested_route")
            if (action == "accepted" and route in ("likely_no", "clinical_check")) or \
                    (action == "denied" and route in ("likely_yes", "needs_info")):
                # A person went against the suggested route: keep the reason so the checks improve.
                c["override"], c["override_reason"] = 1, reason or None
        elif action == "patient_arrived":
            c["patient_arrived"] = 0 if reason == "no" else 1
        else:
            raise ValueError(f"unknown action {action}")
        self.log(cid, who or c["owner"], action, reason)
        self.persist(cid)
        return c

    # ---- the clock -----------------------------------------------------------------------
    def view(self, cid: str) -> dict:
        c = self.cards[cid]
        now = self.clock.now()
        end = c.get("decided_at") or now
        elapsed = (end - c["arrived_at"]) / 60
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
        return {**c, "elapsed_min": round(elapsed), "left_min": round(left), "color": color,
                "alerts": alerts, "hospital_silent_min": silent,
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

    def queue(self) -> list[dict]:
        views = [self.view(cid) for cid in self.cards]
        # Sorted by time left, not arrival. Closed cards sink.
        return sorted(views, key=lambda v: (v["status"] in CLOSED, v["left_min"]))

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
        }
