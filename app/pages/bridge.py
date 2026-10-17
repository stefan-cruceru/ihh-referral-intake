"""Runs the real Lamplight web server inside the browser (Pyodide), for the GitHub Pages demo.

sw.js hands each request here. It goes through the same Handler the exe uses, with no socket:
the request is written into a byte buffer and the reply is read back out. Practice mode only:
there is no API key in a browser, so no packet ever leaves the page.
"""

import io
import os
import sys
import time
import types

os.environ.setdefault("LOCALAPPDATA", "/home/pyodide/appdata")
os.environ.setdefault("CAREBRIDGE_AUTH", "practice")


class _Missing(Exception):
    pass


# The Anthropic SDK is never called without a key; llm.py only needs the names to exist.
_anthropic = types.ModuleType("anthropic")
_anthropic.__getattr__ = lambda name: _Missing
sys.modules.setdefault("anthropic", _anthropic)

from carebridge import hospital, notify, webapp  # noqa: E402

_last_sync = 0.0


def _sync() -> None:
    """What the exe's background loop does every 10 seconds, run on the next request instead."""
    global _last_sync
    if time.time() - _last_sync < 10:
        return
    _last_sync = time.time()
    try:
        notify.sync(webapp.TRACK)
        hospital.sync(webapp.TRACK)
    except Exception:
        import traceback

        traceback.print_exc()


def handle(method: str, path: str, headers: dict, body: bytes) -> tuple:
    """One HTTP request in, (status, [(header, value)], body bytes) out."""
    _sync()
    headers = headers.to_py() if hasattr(headers, "to_py") else headers
    body = bytes(body.to_py() if hasattr(body, "to_py") else body)
    head = [f"{method} {path} HTTP/1.1", "Host: 127.0.0.1"]
    head += [f"{k}: {v}" for k, v in headers.items() if k.lower() not in ("host", "origin", "content-length")]
    head.append(f"Content-Length: {len(body)}")
    h = webapp.Handler.__new__(webapp.Handler)
    h.rfile = io.BytesIO(("\r\n".join(head) + "\r\n\r\n").encode("latin-1") + body)
    h.wfile = io.BytesIO()
    h.client_address = ("127.0.0.1", 0)
    h.server = None
    h.request = None
    h.close_connection = True
    h.handle_one_request()
    raw = h.wfile.getvalue()
    top, _, out = raw.partition(b"\r\n\r\n")
    lines = top.decode("latin-1").split("\r\n")
    status = int(lines[0].split(" ")[1])
    hdrs = [tuple(x.split(": ", 1)) for x in lines[1:] if ": " in x]
    try:
        from pyodide.ffi import to_js

        return to_js([status, [list(x) for x in hdrs], out])
    except ImportError:  # plain Python, for the tests
        return status, hdrs, out
