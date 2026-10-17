"""A fake Kipu on 127.0.0.1 for demos and tests. It never touches IHH's real Kipu.

It answers the same paths kipu.py calls, checks the APIAuth signature and app_id the same way, and
is loaded with the invented practice patients in demo/synthetic: S01-S04 are "in care" at three
practice sites, S05-S10 are pre-admission referrals with their faxed packet attached. Everything
written to it is kept in memory so the demo can show what would have gone into the chart.
"""

import base64
import email.utils
import hashlib
import hmac
import json
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

ACCESS_ID = "practice-access-id"
SECRET = "practice-secret-not-real"
APP_ID = "practice-app"
SITES = ["Santa Ana site (practice)", "Anaheim site (practice)", "Riverside site (practice)"]

_server = None
_lock = threading.Lock()
WRITES: list[dict] = []


def _records() -> dict[str, dict]:
    from demo import synthetic

    out = {}
    for i, p in enumerate(synthetic.profiles()):
        last, _, first = p["patient"]["name"].partition(", ")
        kid = f"K-{1001 + i}"
        in_care = i < 4
        out[kid] = {
            "id": kid, "practice_id": p["id"], "first_name": first.title(), "last_name": last.title(),
            "dob": p["patient"]["dob"], "mr_number": p["patient"]["mrn"], "sex": p["patient"]["sex"],
            "preferred_language": p["patient"]["language"],
            "status": "admitted" if in_care else "pre_admission",
            "location_name": SITES[i % len(SITES)] if in_care else None,
            "referral_source": p["hospital"], "diagnosis": p["diagnosis"],
            "care_team": [{"role": "Case manager (referring)", "name": p["case_manager"]["name"]}],
        }
    return out


def _verify(handler, method: str, body: bytes) -> str | None:
    """Same check a real APIAuth server makes. Returns an error string, or None if the request is good."""
    auth = handler.headers.get("Authorization", "")
    date = handler.headers.get("Date", "")
    if not auth.startswith(f"APIAuth {ACCESS_ID}:"):
        return "bad access id"
    try:
        sent = email.utils.parsedate_to_datetime(date).timestamp()
    except (TypeError, ValueError):
        return "bad date"
    if abs(time.time() - sent) > 900:
        return "date too old"
    if parse_qs(urlparse(handler.path).query).get("app_id", [None])[0] != APP_ID:
        return "bad app_id"
    if method == "GET":
        canonical = f",,{handler.path},{date}"
    else:
        md5 = base64.b64encode(hashlib.md5(body).digest()).decode()
        if handler.headers.get("Content-MD5") != md5:
            return "bad content md5"
        canonical = f"{handler.headers.get('Content-Type', '')},{md5},{handler.path},{date}"
    want = base64.b64encode(hmac.new(SECRET.encode(), canonical.encode(), hashlib.sha1).digest()).decode()
    return None if hmac.compare_digest(auth.split(":", 1)[1], want) else "bad signature"


class _Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _json(self, obj, code=200):
        b = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(b)))
        self.end_headers()
        self.wfile.write(b)

    def do_GET(self):
        p = urlparse(self.path).path
        if p == "/mock/writes":  # unsigned, local only: what the demo would have written to the chart
            return self._json({"writes": WRITES})
        err = _verify(self, "GET", b"")
        if err:
            return self._json({"error": err}, 401)
        recs = self.server.records
        parts = p.strip("/").split("/")
        if p == "/api/patients/census":
            return self._json({"patients": [r for r in recs.values() if r["status"] == "admitted"]})
        if p in ("/api/patients/latest", "/api/patients/admissions"):
            return self._json({"patients": [r for r in recs.values() if r["status"] == "pre_admission"]})
        if p == "/api/locations":
            return self._json({"locations": [{"id": i + 1, "name": s} for i, s in enumerate(SITES)]})
        if len(parts) >= 3 and parts[:2] == ["api", "patients"] and parts[2] in recs:
            r = recs[parts[2]]
            if len(parts) == 3:
                return self._json({"patient": r})
            if parts[3] == "care_team":
                return self._json({"care_team": r["care_team"]})
            if parts[3] == "vital_signs":
                return self._json({"vital_signs": []})
            if parts[3] == "documents":
                from demo import synthetic

                path = synthetic.packet_path(r["practice_id"])
                docs = [{"id": f"{r['id']}-referral", "name": f"{r['practice_id']}-referral.pdf", "content_type": "application/pdf",
                         "data": base64.b64encode(path.read_bytes()).decode()}] if path and r["status"] == "pre_admission" else []
                return self._json({"documents": docs + [w["body"] for w in WRITES if w["path"] == p]})
        return self._json({"error": "not found"}, 404)

    def do_POST(self):
        n = int(self.headers.get("Content-Length") or 0)
        body = self.rfile.read(n)
        err = _verify(self, "POST", body)
        if err:
            return self._json({"error": err}, 401)
        p = urlparse(self.path).path
        data = json.loads(body or b"{}")
        with _lock:
            entry = {"t": time.time(), "path": p, "body": data}
            if p == "/api/patients":
                kid = f"K-{1001 + len(self.server.records)}"
                self.server.records[kid] = {"id": kid, "status": "pre_admission", **data.get("document", {}).get("data", {})}
                entry["created"] = kid
            WRITES.append(entry)
        return self._json({"ok": True, **({"id": entry["created"]} if "created" in entry else {})}, 201)


def ensure_running(port: int = 0):
    """Start the fake Kipu once, in this process, on a free local port."""
    global _server
    with _lock:
        if _server is None:
            srv = ThreadingHTTPServer(("127.0.0.1", port), _Handler)
            srv.records = _records()
            srv.url = f"http://127.0.0.1:{srv.server_address[1]}"
            threading.Thread(target=srv.serve_forever, daemon=True).start()
            _server = srv
    return _server
