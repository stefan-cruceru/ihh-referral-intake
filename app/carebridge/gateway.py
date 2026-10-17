"""Sign-in, Kipu and Teams routes for the local app, kept out of webapp.py's main handlers.

webapp.Handler calls allowed() first (is this request signed in?) and then handle() (is it one of
these routes?). Pages here are small and plain, in English and Spanish.
"""

import re
from html import escape
from urllib.parse import parse_qs, quote, urlparse

from . import auth, config, drafts, kipu, kipu_check, teams

# /mcp is not open: an agent calling it over HTTP signs in with a personal token (/api/me/token).
# The local stdio MCP server (Copilot in VS Code, Claude Desktop) runs as the Windows user instead.
# /send is the hospital upload page: no sign-in, it only takes a file and shows its own receipt.
OPEN = ("/static/", "/auth/", "/go/", "/api/state", "/send")

# Which permission (auth.PERMISSIONS) each changing route needs. Checked here for every request so a
# route cannot forget it. Any POST under /api/ that is not listed is refused (fail closed).
# /api/cards/<id>/act is checked in webapp, where the body says which action it is.
ROUTES = [
    ("POST", re.compile(r"^/api/key(/clear)?$"), "api_key"),
    ("POST", re.compile(r"^/api/settings$"), "settings"),
    ("POST", re.compile(r"^/api/(demo|clock)$"), "demo"),
    ("POST", re.compile(r"^/api/upload$"), "upload"),
    ("POST", re.compile(r"^/api/profiles/[^/]+/send$"), "upload"),
    ("POST", re.compile(r"^/api/cards/[^/]+/review$"), "review"),
    ("POST", re.compile(r"^/api/cards/[^/]+/kipu$"), "kipu_write"),
    ("POST", re.compile(r"^/api/cards/[^/]+/act$"), None),
    ("GET", re.compile(r"^/api/cards/[^/]+/teams-card$"), "teams_card"),
    ("POST", re.compile(r"^/api/kipu/settings$"), "kipu_settings"),
    ("POST", re.compile(r"^/api/kipu/sync$"), "kipu_sync"),
    ("POST", re.compile(r"^/api/kipu/find$"), "kipu_find"),
    ("POST", re.compile(r"^/api/notify/people$"), "people_edit"),
    ("POST", re.compile(r"^/api/notify/\d+/mark$"), "alert_mark"),
    ("POST", re.compile(r"^/api/(resources|handout|phi-check|staff/note|staff/explain)$"), "staff_tools"),
    ("POST", re.compile(r"^/api/me/token$"), "mcp_token"),
    ("POST", re.compile(r"^/api/access/people$"), "roles_edit"),
    ("POST", re.compile(r"^/mcp$"), None),  # each tool is checked in mcp.handle
]


def permission(method: str, path: str) -> tuple[bool, str | None]:
    """(listed, permission) for a request. Unlisted GETs are reads anyone signed in may do."""
    for m, rx, perm in ROUTES:
        if m == method and rx.match(path):
            return True, perm
    return False, None


def person(h) -> dict | None:
    return auth.session(h.headers.get("Cookie")) or auth.bearer_session(h.headers.get("Authorization"))


def allowed(h, path: str) -> bool:
    """Everything needs a signed-in person, except sign-in itself, static files and the local MCP
    endpoint. Sends the 302 or 401 itself and returns False when the request should stop."""
    if auth.mode() == "off" or path.startswith(OPEN):
        return True
    me = person(h)
    if not me:
        if path.startswith(("/api/", "/mcp")):
            h._json({"error": "sign_in", "sign_in": "/auth/signin"}, 401)
        else:
            h._send(302, b"", "text/plain", {"Location": f"/auth/signin?next={quote(h.path)}"})
        return False
    listed, perm = permission(h.command, path)
    if (h.command == "POST" and path.startswith("/api/") and not listed) or (perm and not auth.can(me, perm)):
        h._json({"error": "not_allowed", "role": me.get("role"), "needs": perm}, 403)
        return False
    return True


def _page(h, title: str, body: str, code: int = 200, extra: dict | None = None):
    html = f"""<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>{escape(title)}</title><link rel="stylesheet" href="/static/app.css"><script src="/static/display.js"></script>
<style>.gw{{max-width:560px;margin:3rem auto;padding:1.5rem;background:var(--panel);border:1px solid var(--line);border-radius:16px}}
.gw h1{{font-size:1.5rem;margin:0 0 .6rem}}.gw .who{{display:grid;gap:.5rem;margin:1rem 0}}
.gw button,.gw a.b{{font:inherit;font-weight:600;padding:.8rem 1rem;border-radius:10px;border:1px solid var(--line);background:var(--panel);cursor:pointer;text-align:left;color:inherit;text-decoration:none;display:block}}
.gw button.primary{{background:var(--brand);color:var(--brand-ink,#fff);border-color:var(--brand)}}.gw .m{{color:var(--muted);font-size:.92rem}}
.gw .teams,.gw a.b.teams{{background:#4b53bc;color:#fff;border-color:#4b53bc;text-align:center}}</style></head>
<body><main class="gw">{body}</main></body></html>"""
    h._send(code, html.encode("utf-8"), "text/html; charset=utf-8", extra)


def _sign_in_page(h, nxt: str, msg: str = ""):
    m = auth.mode()
    if m == "teams":
        try:
            return h._send(302, b"", "text/plain", {"Location": teams.sign_in_url(_redirect(h), nxt)})
        except RuntimeError as e:
            msg = str(e)
    people = "".join(
        f'<form method="post" action="/auth/practice"><input type="hidden" name="email" value="{escape(s["email"])}">'
        f'<input type="hidden" name="next" value="{escape(nxt)}"><button>{escape(s["name"])} '
        f'<span class="m">· {escape(s["role"])}</span></button></form>' for s in auth.staff())
    roles = "".join(f'<option value="{r}">{r}</option>' for r in auth.ROLES)
    _page(h, "Sign in", f"""<h1>Sign in · Iniciar sesión</h1>
<a class="b teams" href="/auth/microsoft?next={escape(quote(nxt))}">Sign in with Microsoft (Teams work account)<br>
<span style="font-weight:400">Entrar con Microsoft (cuenta de Teams del trabajo)</span></a>
<p class="m">At IHH this is the only way in. It isn't connected in this demo: click it to see how it works.<br>
En IHH esta es la única forma de entrar. No está conectada en esta demo: haga clic para ver cómo funciona.</p>
<h2 style="font-size:1.1rem;margin:1.4rem 0 .2rem">Practice sign-in · Inicio de práctica</h2>
<p class="m">These people are made up. Pick one to see the app with that role.<br>Estas personas son inventadas. Escoja una para ver la app con ese rol.</p>
{f'<p style="color:var(--red)">{escape(msg)}</p>' if msg else ''}
<div class="who">{people}</div>
<details><summary class="m" style="cursor:pointer">Add a practice person · Agregar una persona de práctica</summary>
<form method="post" action="/auth/practice/add" class="who">
<input type="hidden" name="next" value="{escape(nxt)}">
<label class="m">Name · Nombre<input name="name" required maxlength="60"></label>
<label class="m">Work email · Correo del trabajo<input name="email" type="email" required placeholder="name@ihh.example.org"></label>
<label class="m">Role · Rol<select name="role">{roles}</select></label>
<button class="primary">Add and sign in · Agregar y entrar</button>
<span class="m">Made-up people only. At IHH, accounts and roles come from Microsoft Entra.<br>Solo personas inventadas. En IHH, las cuentas y los roles vienen de Microsoft Entra.</span>
</form></details>""")


def _microsoft_page(h, nxt: str):
    """How the Microsoft sign-in works at IHH. Shown until IT registers the app; after that the
    button goes straight to IHH's Microsoft sign-in (teams.sign_in_url)."""
    roles = "".join(f"<li><code>{escape(k)}</code> → {escape(v)}</li>" for k, v in auth.ENTRA_ROLES.items())
    _page(h, "Sign in with Microsoft", f"""<h1>Sign in with Microsoft · Entrar con Microsoft</h1>
<p class="m">Not connected in this demo. This is what happens at IHH once IT registers the app.<br>
No está conectado en esta demo. Esto pasa en IHH cuando TI registre la app.</p>
<ol>
<li>You click <b>Sign in with Microsoft</b>. Care Bridge sends you to IHH's own Microsoft sign-in page
(<code>login.microsoftonline.com</code>, IHH's tenant). Care Bridge never sees your password.</li>
<li>You sign in with the same work account you use for Teams, with IHH's usual multi-factor check.</li>
<li>Microsoft sends you back with a one-time code. Care Bridge trades it with Microsoft, over a secure
connection, for an ID token with your name, email and your <b>Care Bridge roles</b> (standard OAuth 2.0
with PKCE and OpenID Connect).</li>
<li>Care Bridge checks the token was made for this app, for IHH's tenant and for this sign-in, then
signs you in with those roles. The server checks every action against them.</li>
</ol>
<p><b>Roles come from Microsoft Entra.</b> IT assigns these app roles to people or groups:</p>
<ul>{roles}</ul>
<p class="m">No role, no entry. Only the clinical role can deny a referral.</p>
<p><b>What IT does once:</b> register Care Bridge in Microsoft Entra, add the four app roles, assign
people or groups, then put the tenant ID and client ID in Settings (or <code>CAREBRIDGE_TEAMS_TENANT</code>
and <code>CAREBRIDGE_TEAMS_CLIENT_ID</code>). From then on this button is the only way in, and practice
sign-in turns off.</p>
<p class="m">TI registra Care Bridge en Microsoft Entra, agrega los cuatro roles, los asigna a personas o
grupos y pone los ID del inquilino y del cliente en Ajustes. Desde entonces este botón es la única
forma de entrar y el inicio de práctica se apaga.</p>
<a class="b" href="/auth/signin?next={escape(quote(nxt))}">← Back to sign-in · Volver</a>""")


def _redirect(h) -> str:
    return f"http://{h.headers.get('Host', '127.0.0.1')}/auth/callback"


def _form(h) -> dict:
    return {k: v[0] for k, v in parse_qs(h._body().decode()).items()}


def handle(h, method: str) -> bool:
    """Serve one of the sign-in, Kipu or Teams routes. Returns False if the path is not ours."""
    u = urlparse(h.path)
    p, q = u.path, {k: v[0] for k, v in parse_qs(u.query).items()}
    # ---- sign-in ----
    if p == "/auth/signin":
        _sign_in_page(h, q.get("next", "/"))
        return True
    if p == "/auth/microsoft":
        nxt = q.get("next", "/")
        if auth.microsoft_configured():
            try:
                h._send(302, b"", "text/plain", {"Location": teams.sign_in_url(_redirect(h), nxt)})
                return True
            except RuntimeError:
                pass
        _microsoft_page(h, nxt)
        return True
    if p == "/auth/practice/add" and method == "POST":
        f = _form(h)
        try:
            who = auth.add_practice_person(f.get("name", ""), f.get("email", ""), f.get("role", ""))
        except (ValueError, PermissionError) as e:
            _sign_in_page(h, f.get("next", "/"), str(e))
            return True
        token = auth.start_session(who, "practice")
        h._send(302, b"", "text/plain", {"Location": f.get("next") or "/", "Set-Cookie": auth.set_cookie(token)})
        return True
    if p == "/auth/practice" and method == "POST":
        f = _form(h)
        who = auth.lookup(f.get("email", "")) if auth.mode() == "practice" else None
        if not who:
            _sign_in_page(h, f.get("next", "/"), "Pick someone on the list.")
            return True
        token = auth.start_session(who, "practice")
        h._send(302, b"", "text/plain", {"Location": f.get("next") or "/", "Set-Cookie": auth.set_cookie(token)})
        return True
    if p == "/auth/callback":
        try:
            who, nxt = teams.finish_sign_in(q.get("code", ""), q.get("state", ""), _redirect(h))
        except Exception as e:
            _page(h, "Sign-in problem", f"<h1>Sign-in problem</h1><p>{escape(str(e))}</p><a class='b' href='/auth/signin'>Try again</a>", 403)
            return True
        token = auth.start_session(who, "teams")
        h._send(302, b"", "text/plain", {"Location": nxt or "/", "Set-Cookie": auth.set_cookie(token)})
        return True
    if p == "/auth/signout":
        auth.end_session(h.headers.get("Cookie"))
        h._send(302, b"", "text/plain", {"Location": "/auth/signin", "Set-Cookie": auth.clear_cookie()})
        return True
    if p == "/api/me":
        me = person(h)
        out = {"auth": auth.mode()}
        if me:
            out.update({k: me.get(k) for k in ("email", "name", "role", "via")})
            out["roles"] = sorted(auth.roles_of(me))
            # What this person may do, so the screen can hide buttons it would refuse anyway.
            out["can"] = sorted(k for k in auth.PERMISSIONS if auth.can(me, k))
        h._json(out, 200 if me else 401)
        return True
    if p == "/api/access":
        # Everything the Access page shows: roles, what each may do (the same table the server
        # enforces), the Entra mapping, the people, and whether this person may change roles.
        me = person(h)
        h._json({"mode": auth.mode(), "microsoft": auth.microsoft_configured(), "roles": list(auth.ROLES),
                 "entra": auth.ENTRA_ROLES, "permissions": {k: list(v) for k, v in auth.PERMISSIONS.items()},
                 "people": [{k: s.get(k) for k in ("email", "name", "role")} for s in auth.staff()],
                 "me": {k: me.get(k) for k in ("email", "name", "role", "via")} if me else None,
                 "can_edit": auth.can(me, "roles_edit") and auth.mode() == "practice"})
        return True
    if p == "/api/access/people" and method == "POST":
        b = h._jbody()
        try:
            if b.get("add"):
                who = auth.add_practice_person(b.get("name", ""), b.get("email", ""), b.get("role", ""))
            else:
                who = auth.set_role(b.get("email", ""), b.get("role", ""))
        except PermissionError as e:
            h._json({"error": str(e)}, 409)
            return True
        except ValueError as e:
            h._json({"error": str(e)}, 400)
            return True
        h._json({"ok": True, "person": who})
        return True
    if p == "/api/me/token" and method == "POST":
        # A token for an agent to call /mcp as this person, with this person's roles. Same lifetime
        # as a sign-in; making a new one does not end the old ones.
        me = person(h)
        who = {k: me.get(k) for k in ("email", "name", "role", "roles")}
        token = auth.start_session(who, "token")
        h._json({"token": token, "hours": auth.SESSION_HOURS,
                 "use": "Authorization: Bearer <token> on POST /mcp. Treat it like a password."})
        return True
    # ---- Teams card links ----
    if p.startswith("/go/"):
        _go(h, method, p[len("/go/"):])
        return True
    parts = p.strip("/").split("/")
    if parts[:2] == ["api", "cards"] and len(parts) == 4 and parts[3] == "teams-card":
        _teams_card(h, parts[2], q)
        return True
    # ---- Kipu ----
    if p.startswith("/api/kipu/") or (parts[:2] == ["api", "cards"] and len(parts) == 4 and parts[3] == "kipu"):
        try:
            _kipu(h, method, p, parts)
        except kipu.KipuOff as e:
            h._json({"error": str(e), "mode": "off"}, 409)
        except kipu.KipuError as e:
            h._json({"error": str(e)}, 502)
        return True
    return False


def _go(h, method: str, token: str):
    from . import webapp

    data = auth.read_link_token(token)
    if not data:
        return _page(h, "Link expired", "<h1>This link has expired / Este enlace venció</h1><a class='b' href='/'>Open Care Bridge</a>", 410)
    me = person(h)
    if not me or (auth.mode() != "off" and me["email"].lower() != data["e"]):
        return _page(h, "Not your link", f"<h1>This link is for someone else</h1><p class='m'>It was sent to {escape(data['e'])}. "
                     f"Sign in as that person, or open the referral from the board.</p><a class='b' href='/auth/signout'>Switch person</a>", 403)
    card = webapp.TRACK.cards.get(data["c"])
    if not card:
        return _page(h, "Not found", "<h1>That referral is not on the board right now.</h1><a class='b' href='/'>Open the board</a>", 404)
    if data["a"] == "open":
        return h._send(302, b"", "text/plain", {"Location": "/"})
    label = {"denied": "Say no (clinical)", "accepted": "Say yes", "clinical_pickup": "I have it"}.get(data["a"], data["a"])
    if method == "GET":
        return _page(h, "Confirm", f"""<h1>{escape(card['case_no'])}: {escape(label)}?</h1>
<p class="m">Signed in as {escape(me['name'])} ({escape(me['role'])}).</p>
<form method="post"><label class="m">Why? / ¿Por qué?<input name="reason" style="width:100%" required></label>
<button class="primary" style="margin-top:.8rem">{escape(label)}</button></form>""")
    if not auth.can(me, data["a"]):
        return _page(h, "Not allowed", "<h1>Only the clinical reviewer can say no.</h1>", 403)
    if not auth.use_link_token(token):
        return _page(h, "Already used", "<h1>This link was already used.</h1><a class='b' href='/'>Open the board</a>", 409)
    reason = _form(h).get("reason", "")
    try:
        webapp.TRACK.act(card["id"], data["a"], me["name"], f"{reason} (from Teams link)", role=auth.act_role(me))
    except ValueError as e:
        return _page(h, "Not done", f"<h1>{escape(str(e))}</h1>", 400)
    _page(h, "Done", f"<h1>Done: {escape(label)}</h1><p class='m'>Saved in the log under {escape(me['name'])}.</p><a class='b' href='/'>Open the board</a>")


def _teams_card(h, cid: str, q: dict):
    from . import webapp

    if cid not in webapp.TRACK.cards:
        return h._json({"error": "not found"}, 404)
    rep = webapp.card_report(cid)
    if not rep:
        return h._json({"error": "No review yet."}, 400)
    to = auth.lookup(q.get("to", "")) or next((s for s in auth.staff() if s["role"] == "clinical"), None)
    if not to:
        return h._json({"error": "No clinical reviewer on the staff list."}, 400)
    base = f"http://{h.headers.get('Host', '127.0.0.1')}"
    h._json({"to": to, "card": teams.review_card(webapp.TRACK.view(cid), rep, to, base, q.get("lang", "en")),
             "note": "Draft. Paste into a Teams chat with this person (or let a Power Automate flow post it). Nothing was sent."})


def _kipu(h, method: str, p: str, parts: list[str]):
    from . import webapp

    me = person(h) or {"name": "", "role": ""}
    if p == "/api/kipu/checks" and method == "GET":
        # The background readiness checks (kipu_check.py). Reading them never writes to Kipu.
        return h._json(kipu_check.summary(webapp.TRACK))
    if p == "/api/kipu/status" and method == "GET":
        out = {"mode": kipu.mode(), "write": kipu.write_enabled()}
        if kipu.mode() != "off":
            out["census"] = kipu.census()
            out["pending"] = len(kipu.pending_referrals())
        return h._json(out)
    if p == "/api/kipu/settings" and method == "POST":
        b = h._jbody()
        keep = {k: b[k] for k in ("kipu_mode", "kipu_write", "kipu_base_url") if k in b}
        return h._json(config.save_settings(keep))
    if p == "/api/kipu/writes" and method == "GET":
        if kipu.mode() != "mock":
            return h._json({"writes": [], "note": "Only practice Kipu keeps a list of writes."})
        from . import kipu_mock

        return h._json({"writes": [{"t": w["t"], "path": w["path"], "created": w.get("created"),
                                    "what": list((w["body"].get("document") or w["body"].get("patient_evaluation") or {}).keys())}
                                   for w in kipu_mock.WRITES]})
    if p == "/api/kipu/sync" and method == "POST":
        return h._json(sync(me))
    if p == "/api/kipu/find" and method == "POST":
        b = h._jbody()
        matches = kipu.find_existing(b.get("first", ""), b.get("last", ""), b.get("dob", ""))
        webapp.TRACK.log(b.get("case"), me["name"] or "staff", "Kipu returning-client check", f"{len(matches)} match(es)")
        return h._json({"matches": matches, "note": "A person confirms a match. Two identifiers must agree."})
    if parts[:2] == ["api", "cards"] and method == "POST":
        cid = parts[2]
        card = webapp.TRACK.cards.get(cid)
        if not card:
            return h._json({"error": "not found"}, 404)
        b = h._jbody()
        step = b.get("step")
        rep = webapp.card_report(cid)
        if step == "create_chart":
            if card.get("kipu_id"):
                return h._json({"error": f"This referral already has a Kipu chart ({card['kipu_id']})."}, 409)
            fields = dict(drafts.handoffs(webapp.TRACK.view(cid), rep, "en")["kipu_fields"])
            res = kipu.create_chart(fields, me["name"])
            card["kipu_id"] = res.get("id") or card.get("kipu_id")
        elif step == "file_documents":
            if not card.get("kipu_id") or cid not in webapp.PACKETS:
                return h._json({"error": "Needs a Kipu chart and a packet first."}, 400)
            data, name = webapp.PACKETS[cid]
            res = kipu.file_documents(card["kipu_id"], name, data, me["name"])
        elif step == "intake_note":
            if not card.get("kipu_id") or not rep or not card.get("decision"):
                return h._json({"error": "Needs a Kipu chart, a review and a decision first."}, 400)
            res = kipu.add_intake_note(card["kipu_id"], rep, card["decision"], me["name"])
        else:
            return h._json({"error": "unknown step"}, 400)
        webapp.TRACK.log(cid, me["name"] or "staff", f"Kipu: {step}", f"chart {card.get('kipu_id')}")
        return h._json({"ok": True, "kipu_id": card.get("kipu_id"), "result": res})
    h._json({"error": "not found"}, 404)


def sync(me: dict | None = None) -> dict:
    """Pull pre-admission referrals from Kipu onto the board (data in, one place). Each becomes a
    card keyed by its Kipu id, with its packet attached; practice patients get their practice review."""
    from . import webapp

    added = []
    for r in kipu.pending_referrals():
        cid = f"KIPU-{r['id']}"
        if cid in webapp.TRACK.cards:
            continue
        card = webapp.TRACK.add({"id": cid, "case_no": cid, "channel": "kipu", "hospital": r.get("referral_source") or "unknown",
                                 "kipu_id": r["id"], "practice": kipu.mode() == "mock",
                                 "synthetic": bool(r.get("practice_id"))})
        got = kipu.fetch_packet(r["id"])
        if got:
            webapp.PACKETS[cid] = got
        if r.get("practice_id"):
            card["packet_id"] = r["practice_id"]
            webapp.PACKETS.pop(cid, None)
            webapp._on_land(card)
        elif got and config.get_api_key():
            webapp.start_review(cid)
        added.append(cid)
    webapp.TRACK.log(None, (me or {}).get("name") or "system", "Kipu sync", f"{len(added)} new referral(s)")
    return {"added": added, "mode": kipu.mode()}
