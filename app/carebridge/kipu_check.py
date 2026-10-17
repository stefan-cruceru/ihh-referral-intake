"""Kipu readiness, checked in the background. Never writes to Kipu.

For every referral on the board, this builds what the three Kipu steps would send (the chart, the
packet, the intake note: kipu.create_chart, file_documents, add_intake_note) and checks it, so staff
see before they click whether a step would go through and, if not, why. Writing still takes a
person's click (gateway._kipu). The only thing that leaves this module is one signed, read-only
request to the practice Kipu to show the signed connection works; live Kipu is never called here.

Each check is ok, wait (a person still has to do something) or fail (it would be refused).
"""

import threading
import time

from . import drafts, guard, kipu

LOCK = threading.Lock()
CONNECTION: dict = {}  # the last connection check
LOG: list[dict] = []  # recent results, newest first: what the Kipu page shows
LOG_MAX = 60
INTERVAL = 8.0

# label: (English, Spanish)
LABELS = {
    "case_no": ("Referral number", "Número de referido"),
    "hospital": ("Referring hospital is known", "Se sabe el hospital que refiere"),
    "contact": ("Hospital contact is known", "Se sabe el contacto del hospital"),
    "reason": ("Reason for referral is filled in", "El motivo del referido está lleno"),
    "identity": ("Name and birth date: typed in Kipu by a person (blacked out in the packet)",
                 "Nombre y fecha de nacimiento: los escribe una persona en Kipu (tachados en el paquete)"),
    "returning": ("Returning-client check done", "Revisión de cliente anterior hecha"),
    "no_duplicate": ("No Kipu chart yet for this referral", "Todavía no hay expediente en Kipu para este referido"),
    "packet": ("Packet on file", "Paquete guardado"),
    "packet_type": ("Packet is a PDF or image within the size limit", "El paquete es PDF o imagen dentro del límite"),
    "security": ("Security scan passed", "Pasó la revisión de seguridad"),
    "reviewed": ("Packet has been read", "El paquete ya se leyó"),
    "decision": ("A person decided", "Una persona decidió"),
    "who_denied": ("Only the clinical line said no", "Solo la línea clínica dijo que no"),
    "note_clean": ("Intake note holds rule IDs and pages only, no quotes", "La nota tiene solo reglas y páginas, sin citas"),
}
GROUPS = {"chart": ("Chart", "Expediente"), "documents": ("Packet", "Paquete"), "note": ("Intake note", "Nota de admisión")}


def _item(group: str, key: str, state: str, detail: str = "") -> dict:
    en, es = LABELS[key]
    return {"group": group, "key": key, "state": state, "label_en": en, "label_es": es, "detail": detail}


def _known(v) -> bool:
    return bool(v) and str(v).strip().lower() not in ("unknown", "no se sabe", "not known")


def check_card(card: dict, report: dict | None, packet: tuple[bytes, str] | None) -> dict:
    """The checks for one referral. Pure: builds the payloads and checks them, sends nothing."""
    items = []
    # ---- chart: the fields kipu.create_chart would send (drafts.handoffs) ----
    fields = dict(drafts.handoffs(card, report, "en")["kipu_fields"])
    items.append(_item("chart", "case_no", "ok" if _known(fields.get("Referral number")) else "fail"))
    items.append(_item("chart", "hospital", "ok" if _known(card.get("hospital")) else "fail",
                       "" if _known(card.get("hospital")) else "Add it on the card or ask the hospital."))
    items.append(_item("chart", "contact", "ok" if _known(card.get("case_manager") or card.get("cm_email")) else "wait"))
    items.append(_item("chart", "reason", "ok" if _known(fields.get("Reason for referral")) else "wait",
                       "" if report else "Comes from the packet review."))
    # Blacked out in every packet; the person making the chart types them, so it never blocks.
    items.append(_item("chart", "identity", "ok"))
    returning = (card.get("staff_checks") or {}).get("returning_client")
    items.append(_item("chart", "returning", "ok" if returning else "wait",
                       f"{returning['result']}, by {returning['who']}" if returning else "A person checks Kipu by name and birth date."))
    items.append(_item("chart", "no_duplicate", "fail" if card.get("kipu_id") else "ok",
                       f"Chart {card['kipu_id']} already linked: file into it instead." if card.get("kipu_id") else ""))
    # ---- documents: what kipu.file_documents would send ----
    if packet:
        data, name = packet
        # By what the file really is (its first bytes), not its name; same limit as the security scan.
        ok_type = guard.kind_of(data) in ("pdf", "tiff", "png", "jpeg") and len(data) <= guard.MAX_BYTES
        items.append(_item("documents", "packet", "ok", name))
        items.append(_item("documents", "packet_type", "ok" if ok_type else "fail", f"{len(data) // 1024} KB"))
    else:
        items.append(_item("documents", "packet", "wait", "No file yet (it came in by email text or Kipu)."))
    verdict = card.get("security")
    sec_hold = verdict in (guard.HOLD, guard.BLOCK) or card.get("suggested_route") == "security_hold"
    items.append(_item("documents", "security", "fail" if sec_hold else "ok" if verdict == guard.OK or report else "wait",
                       "Held for a person: do not file it." if sec_hold else ""))
    # ---- intake note: what kipu.add_intake_note would send ----
    items.append(_item("note", "reviewed", "ok" if report else "wait"))
    decision = card.get("decision")
    items.append(_item("note", "decision", "ok" if decision in ("accepted", "denied") else "wait",
                       decision or "The note is added after a person decides."))
    if decision == "denied":
        items.append(_item("note", "who_denied", "ok"))  # tracker.act refuses a denial from anyone else
    items.append(_item("note", "note_clean", "ok"))  # add_intake_note sends route, gates, rule IDs, doc IDs only
    states = {i["state"] for i in items}
    status = "fail" if "fail" in states else "wait" if "wait" in states else "ok"
    # What a person could send right now, step by step.
    can = {
        "create_chart": not card.get("kipu_id") and all(i["state"] != "fail" for i in items if i["group"] == "chart"),
        "file_documents": bool(card.get("kipu_id")) and bool(packet) and not sec_hold,
        "intake_note": bool(card.get("kipu_id")) and bool(report) and decision in ("accepted", "denied"),
    }
    return {"status": status, "items": items, "ready_steps": can, "checked_at": time.time(),
            "writes": "none: checking only"}


def check_connection() -> dict:
    """Is the Kipu connection set up, and does a signed request get through? Practice Kipu only;
    live Kipu is never called from the background."""
    m = kipu.mode()
    out = {"mode": m, "write_enabled": kipu.write_enabled(), "checked_at": time.time()}
    if m == "off":
        return {**out, "state": "off"}
    if m == "live":
        a, s, app = kipu.credentials()
        return {**out, "state": "ok" if (a and s and app) else "fail",
                "detail": "Credentials are set. Live Kipu is not called in the background." if (a and s and app)
                else "Live Kipu needs KIPU_ACCESS_ID, KIPU_SECRET_KEY and KIPU_APP_ID."}
    try:
        t0 = time.time()
        census = kipu.census()
        return {**out, "state": "ok", "detail": f"Signed request accepted by practice Kipu ({census['total']} in care)",
                "ms": round((time.time() - t0) * 1000)}
    except kipu.KipuError as e:
        return {**out, "state": "fail", "detail": str(e)}


def run_once(track, packets: dict, report_of) -> dict:
    """Check every referral on the board and the connection. Stores each result on its card."""
    conn = check_connection()
    results = {}
    for cid, card in list(track.cards.items()):
        res = check_card(card, report_of(cid), packets.get(cid))
        before = (card.get("kipu_check") or {}).get("status")
        card["kipu_check"] = res
        results[cid] = res
        if res["status"] != before:
            with LOCK:
                LOG.insert(0, {"t": res["checked_at"], "case_no": card.get("case_no"), "status": res["status"],
                               "fails": [i["key"] for i in res["items"] if i["state"] == "fail"],
                               "waits": [i["key"] for i in res["items"] if i["state"] == "wait"]})
                del LOG[LOG_MAX:]
    with LOCK:
        CONNECTION.clear()
        CONNECTION.update(conn)
    return results


def start(track, packets: dict, report_of, interval: float = INTERVAL) -> None:
    def loop():
        while True:
            try:
                run_once(track, packets, report_of)
            except Exception:  # a bad card must never stop the checks for the others
                import traceback

                traceback.print_exc()
            time.sleep(interval)

    threading.Thread(target=loop, daemon=True, name="kipu-check").start()


def summary(track) -> dict:
    cards = [c for c in track.cards.values() if c.get("kipu_check")]
    count = {s: sum(1 for c in cards if c["kipu_check"]["status"] == s) for s in ("ok", "wait", "fail")}
    with LOCK:
        return {"connection": dict(CONNECTION), "count": count, "labels": LABELS, "groups": GROUPS, "log": list(LOG),
                "cards": [{"id": c["id"], "case_no": c.get("case_no"), "status": c.get("status"),
                           "kipu_id": c.get("kipu_id"), "check": c["kipu_check"]} for c in cards]}
