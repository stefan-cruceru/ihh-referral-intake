"""Kipu connector: the referral team's steps in IHH's own record system.

The intake director's steps today (docs/workflow-and-timing.md): check Kipu for an existing chart,
create one if needed, file the referral documents into it, then review. This module does the Kipu
side of those steps, and pulls census data so the board can show who is where.

Modes (setting `kipu_mode`, or CAREBRIDGE_KIPU_MODE):
  mock  default. A fake Kipu inside this app (kipu_mock.py), loaded with the invented practice
        patients. Never leaves the computer.
  off   Nothing talks to Kipu.
  live  IHH's real Kipu. Only after IHH IT signs off and a BAA covers this use. Needs the three
        credentials Kipu issues (KIPU_ACCESS_ID, KIPU_SECRET_KEY, KIPU_APP_ID).

Writes (create a chart, file documents, add an intake note) also need `kipu_write` turned on, and
each one is started by a signed-in person. Nothing writes on its own.

What we know about Kipu's API comes from public client libraries, not Kipu's own docs: requests are
signed with HMAC ("APIAuth"), the app_id goes in the query string, and the paths below are the ones
those clients call. Anything marked UNCONFIRMED must be checked against Kipu's documentation before
a pilot.
"""

import base64
import email.utils
import hashlib
import hmac
import json
import os
import urllib.error
import urllib.parse
import urllib.request

from . import config

DEFAULT_BASE = "https://api.kipuapi.com"
VERSION = 3

PATHS = {
    "census": "/api/patients/census",
    "latest": "/api/patients/latest",
    "admissions": "/api/patients/admissions",
    "patient": "/api/patients/{id}",
    "care_team": "/api/patients/{id}/care_team",
    "vital_signs": "/api/patients/{id}/vital_signs",
    "create_patient": "/api/patients",
    "create_evaluation": "/api/patients/{id}/patient_evaluations",
    "locations": "/api/locations",
    # UNCONFIRMED: no public client shows how to attach a document to an existing chart.
    "documents": "/api/patients/{id}/documents",
}


class KipuError(RuntimeError):
    pass


class KipuOff(KipuError):
    pass


def mode() -> str:
    m = os.environ.get("CAREBRIDGE_KIPU_MODE") or config.load_settings().get("kipu_mode") or "mock"
    return m if m in ("off", "mock", "live") else "mock"


def write_enabled() -> bool:
    return bool(os.environ.get("CAREBRIDGE_KIPU_WRITE") or config.load_settings().get("kipu_write"))


def credentials() -> tuple[str | None, str | None, str | None]:
    """Live credentials: environment first, then Windows Credential Manager. Never in a file in git."""
    def get(name):
        v = os.environ.get(name)
        if v:
            return v
        try:
            import keyring

            return keyring.get_password(config.SERVICE, name)
        except Exception:
            return None

    return get("KIPU_ACCESS_ID"), get("KIPU_SECRET_KEY"), get("KIPU_APP_ID")


def sign(secret: str, method: str, uri: str, date: str, content_type: str = "", content_md5: str = "") -> str:
    """APIAuth signature as the public Kipu clients build it (v3: HMAC-SHA1, base64)."""
    canonical = f",,{uri},{date}" if method == "GET" else f"{content_type},{content_md5},{uri},{date}"
    return base64.b64encode(hmac.new(secret.encode(), canonical.encode(), hashlib.sha1).digest()).decode()


class Client:
    def __init__(self, base_url: str, access_id: str, secret: str, app_id: str, timeout: float = 20):
        self.base = base_url.rstrip("/")
        self.access_id, self.secret, self.app_id = access_id, secret, app_id
        self.timeout = timeout

    def _request(self, method: str, path: str, params: dict | None = None, body: dict | None = None):
        params = {**(params or {}), "app_id": self.app_id}
        uri = f"{path}?{urllib.parse.urlencode(params)}"
        date = email.utils.formatdate(usegmt=True)
        data = json.dumps(body).encode() if body is not None else None
        headers = {"Accept": f"application/vnd.kipusystems+json; version={VERSION}", "Date": date}
        ctype = md5 = ""
        if data is not None:
            ctype = "application/json"
            md5 = base64.b64encode(hashlib.md5(data).digest()).decode()
            headers.update({"Content-Type": ctype, "Content-MD5": md5})
        headers["Authorization"] = f"APIAuth {self.access_id}:{sign(self.secret, method, uri, date, ctype, md5)}"
        req = urllib.request.Request(self.base + uri, data=data, method=method, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as r:
                raw = r.read()
        except urllib.error.HTTPError as e:
            raise KipuError(f"Kipu said {e.code} for {method} {path}") from e
        except urllib.error.URLError as e:
            raise KipuError(f"Could not reach Kipu at {self.base}") from e
        return json.loads(raw or b"{}")

    def get(self, name: str, pid: str | None = None, **params):
        return self._request("GET", PATHS[name].format(id=pid), params)

    def post(self, name: str, body: dict, pid: str | None = None):
        if not write_enabled():
            raise KipuError("Writing to Kipu is turned off (kipu_write).")
        return self._request("POST", PATHS[name].format(id=pid), body=body)


def client() -> Client:
    m = mode()
    if m == "off":
        raise KipuOff("Kipu is turned off. Pick practice (mock) or live in Settings.")
    if m == "mock":
        from . import kipu_mock

        srv = kipu_mock.ensure_running()
        return Client(srv.url, kipu_mock.ACCESS_ID, kipu_mock.SECRET, kipu_mock.APP_ID)
    access_id, secret, app_id = credentials()
    if not (access_id and secret and app_id):
        raise KipuError("Live Kipu needs KIPU_ACCESS_ID, KIPU_SECRET_KEY and KIPU_APP_ID.")
    # A live Kipu address comes from IT's environment only; the settings page may only point at a local mock.
    saved = config.load_settings().get("kipu_base_url") or ""
    local = (urllib.parse.urlparse(saved).hostname or "") in ("127.0.0.1", "localhost")
    base = os.environ.get("KIPU_BASE_URL") or (saved if local else "") or DEFAULT_BASE
    return Client(base, access_id, secret, app_id)


# ---- the referral team's steps --------------------------------------------------------------

def _rows(resp, key="patients"):
    if isinstance(resp, list):
        return resp
    return resp.get(key) or resp.get("data") or []


def census() -> dict:
    """Who is in care now, by site. Used for the board's bed picture. Names are not returned to the UI."""
    c = client()
    patients = _rows(c.get("census"))
    by_site: dict[str, int] = {}
    for p in patients:
        site = p.get("location_name") or p.get("location") or "unknown"
        by_site[site] = by_site.get(site, 0) + 1
    return {"mode": mode(), "total": len(patients), "by_site": by_site}


def pending_referrals() -> list[dict]:
    """Pre-admission records in Kipu (newest first). Each becomes a card on the board, keyed by the
    Kipu id. UNCONFIRMED: which Kipu status IHH uses for a referral that is not yet admitted."""
    c = client()
    rows = _rows(c.get("latest", phase="pre_admission"))
    return [r for r in rows if (r.get("status") or r.get("phase") or "pre_admission") in ("pre_admission", "pending", "referral")]


def fetch_packet(kipu_id: str) -> tuple[bytes, str] | None:
    """The referral PDF attached to a pre-admission record. UNCONFIRMED endpoint (see PATHS)."""
    for d in _rows(client().get("documents", kipu_id), "documents"):
        if d.get("content_type") == "application/pdf" and d.get("data"):
            return base64.b64decode(d["data"]), d.get("name") or f"{kipu_id}.pdf"
    return None


def find_existing(first: str, last: str, dob: str) -> list[dict]:
    """The returning-client check. Run only when a person clicks it; a person confirms any match.
    Matches need first name, last name and date of birth together (two identifiers, as IHH asked)."""
    c = client()
    rows = _rows(c.get("census")) + _rows(c.get("latest"))
    want = (first.strip().lower(), last.strip().lower(), dob.strip())
    seen, out = set(), []
    for r in rows:
        key = ((r.get("first_name") or "").lower(), (r.get("last_name") or "").lower(), r.get("dob") or "")
        if key == want and r.get("id") not in seen:
            seen.add(r.get("id"))
            out.append({"id": r.get("id"), "mr_number": r.get("mr_number"), "location": r.get("location_name")})
    return out


def create_chart(fields: dict, who: str) -> dict:
    """Create a chart from the Kipu fields the review drafted (drafts.handoffs). A person starts it."""
    c = client()
    body = {"document": {"recipient_id": c.app_id, "data": {**fields, "created_by_care_bridge_for": who}}}
    return c.post("create_patient", body)


def file_documents(kipu_id: str, filename: str, pdf: bytes, who: str) -> dict:
    """File the referral packet into the chart. UNCONFIRMED endpoint (see PATHS)."""
    c = client()
    body = {"document": {"recipient_id": c.app_id, "filed_by": who,
                         "attachments_attributes": [{"name": filename, "content_type": "application/pdf",
                                                     "data": base64.b64encode(pdf).decode()}]}}
    return c.post("documents", body, pid=kipu_id)


def add_intake_note(kipu_id: str, report: dict, decision: str, who: str) -> dict:
    """An intake note in the chart: the route, gates, rule IDs and pages. No quotes, no free text
    about the patient beyond what the review already holds; a person checks it before it is sent."""
    rec = report["recommendation"]
    note = {
        "evaluation_name": "Recuperative care intake review",
        "decision": decision, "decided_by": who,
        "suggested_route": rec["code"],
        "gates": {g: v["status"] for g, v in report["gates"].items()},
        "not_met": [r["rule_id"] for r in report["rules"] if r["status"] == "not_met"],
        "missing_documents": [d["doc_id"] for d in report["checklist"] if d["status"] == "missing"],
        "source": "IHH Care Bridge (AI-assisted review; a person decided)",
    }
    return client().post("create_evaluation", {"patient_evaluation": note}, pid=kipu_id)
