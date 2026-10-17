"""One language at a time: no page shows English and Spanish side by side, a switch flips between
them, and the choice (the cb_lang cookie) carries from page to page, including sign-in."""

import http.cookiejar
import os
import re
import sys
import tempfile
import threading
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path

APP = Path(__file__).resolve().parents[1]
WEB = APP / "carebridge" / "web"
sys.path.insert(0, str(APP))
_tmp = tempfile.mkdtemp()
os.environ["CAREBRIDGE_DB"] = os.path.join(_tmp, "test.db")  # never touch the real log
os.environ["LOCALAPPDATA"] = _tmp
os.environ["CAREBRIDGE_KIPU_MODE"] = "mock"
os.environ["CAREBRIDGE_AUTH"] = "practice"

from carebridge import gateway  # noqa: E402

# Words that only show up in one of the two languages on these pages.
SPANISH = re.compile(r"Iniciar sesión|Entrar con|Agregar|Escoja|Nombre|Correo|inventadas|Volver|enlace|¿Por qué")
ENGLISH = re.compile(r"\bSign in\b|Add a practice|Pick one|Work email|made up|Back to sign-in|This link")


def _serve():
    from carebridge import webapp

    srv = ThreadingHTTPServer(("127.0.0.1", 0), webapp.Handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return f"http://127.0.0.1:{srv.server_address[1]}"


def _body(main: str) -> str:
    """The page text people read, without the switch link (which names the other language)."""
    return re.sub(r'<div class="langs">.*?</div>', "", main.split("<body>", 1)[1], flags=re.S)


def test_sign_in_pages_show_one_language_and_switch():
    base = _serve()
    jar = http.cookiejar.CookieJar()
    web = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))

    en = web.open(base + "/auth/signin").read().decode()
    assert '<html lang="en"' in en and ENGLISH.search(_body(en)) and not SPANISH.search(_body(en))
    assert ">Español</a>" in en and "lang=es" in en

    es = web.open(base + "/auth/signin?next=/&lang=es").read().decode()
    assert '<html lang="es"' in es and SPANISH.search(_body(es)) and not ENGLISH.search(_body(es))
    assert ">English</a>" in es and "next=/" in es
    # The switch is remembered: the next page opens in Spanish with no ?lang.
    assert any(c.name == "cb_lang" and c.value == "es" for c in jar)
    how = web.open(base + "/auth/microsoft").read().decode()
    assert '<html lang="es"' in how and "login.microsoftonline.com" in how and not ENGLISH.search(_body(how))


def test_link_pages_follow_the_cookie():
    base = _serve()
    req = urllib.request.Request(base + "/go/not-a-real-token", headers={"Cookie": "cb_lang=es"})
    try:
        urllib.request.urlopen(req)
        raise AssertionError("an unknown link should not work")
    except urllib.error.HTTPError as e:
        page = e.read().decode()
    assert "Este enlace venció." in page and "expired" not in _body(page)


def test_browser_translation_is_off_on_every_page():
    # The app has its own switch. Chrome's auto-translate would turn the Spanish screens back
    # into (different) English and make the switch look broken.
    for page in sorted(WEB.glob("*.html")):
        src = page.read_text(encoding="utf-8")
        assert 'translate="no"' in src and 'content="notranslate"' in src, page.name
    gw = (APP / "carebridge" / "gateway.py").read_text(encoding="utf-8")
    assert 'translate="no"' in gw and 'content="notranslate"' in gw


def test_every_word_on_these_pages_has_both_languages():
    for key, pair in gateway.W.items():
        assert len(pair) == 2 and all(pair), key


def test_app_pages_share_one_language_choice():
    # Every page with its own language switch saves it the same way, so the next page opens in it.
    for name in ("kipu.html", "profiles.html", "access.html", "send.html"):
        src = (WEB / name).read_text(encoding="utf-8")
        assert "cbLang?.set(" in src and "cbLang?.get()" in src, name
    app = (WEB / "app.js").read_text(encoding="utf-8")
    assert "cbLang?.set(" in app and "cbLang?.get()" in app
    assert "Bienvenido" not in app
