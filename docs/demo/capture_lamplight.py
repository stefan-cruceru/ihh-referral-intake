"""Record the real local Lamplight practice workflow with Sam's film artwork.

--inspect: sign in as the existing made-up Avery lead and take local visual QA
screenshots. --quick: rehearse all interactions without timeline waits. With no
flag, record the full 120-second film. All mutations require verified practice
authentication and the supplied synthetic demonstration IDs.

The first clean frame is detected from a discarded pre-roll marker; use the
reported video_offset when compositing to remove startup/loading frames.
"""
from __future__ import annotations

import argparse
from contextlib import contextmanager
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import re
import threading
import time
from urllib.parse import urlparse
from urllib.request import urlopen

import imageio_ffmpeg
import numpy as np
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent
VIEWPORT = {"width": 1600, "height": 760}
SYNTHETIC = {"DEMO-101": "S06", "DEMO-102": "S01", "DEMO-103": "S09"}
INIT = """try {
localStorage.setItem('cb_onboarded','1');
localStorage.setItem('cb_scope','all');
localStorage.setItem('cb-display',JSON.stringify({theme:'light',colors:'standard',easy:'off'}));
} catch(e) {}"""

CURSOR = r"""(() => {
if(document.querySelector('#film-cursor'))return;
const style=document.createElement('style');style.textContent=`
#film-cursor{position:fixed;left:800px;top:700px;width:25px;height:25px;border:2px solid #E39235;border-radius:50%;pointer-events:none;z-index:99999;box-shadow:0 0 0 4px #FFF8F073;transform:translate(-50%,-50%);transition:width .15s,height .15s}
#film-cursor:after{content:'';position:absolute;inset:8px;background:#3B2B22;border-radius:50%}
#film-callout{position:fixed;left:53px;top:194px;width:410px;padding:26px 28px;border-left:4px solid #E39235;background:#FFF8F0F5;color:#3B2B22;z-index:40;border-radius:0 17px 17px 0;box-shadow:0 18px 55px #3B2B221A;animation:film-in .4s both;font-family:'Public Sans',sans-serif}
#film-callout small{color:#705744;font-size:13px;font-weight:500;display:block;margin-bottom:14px}
#film-callout h2{font-size:29px;font-weight:620;letter-spacing:-1px;line-height:1.16;margin:0 0 13px;color:#3B2B22}
#film-callout p{font-size:19px;line-height:1.36;color:#A0461F;margin:0}
#film-callout.quote h2{font-size:25px;letter-spacing:-.5px;line-height:1.23}
#film-callout.quote p{font-size:17px}
@keyframes film-in{from{opacity:0;transform:translateX(-16px)}to{opacity:1;transform:translateX(0)}}
`;document.head.append(style);
const cur=document.createElement('div');cur.id='film-cursor';document.body.append(cur);
document.addEventListener('mousemove',e=>{cur.style.left=e.clientX+'px';cur.style.top=e.clientY+'px'});
document.addEventListener('mousedown',()=>{cur.style.width='37px';cur.style.height='37px'});
document.addEventListener('mouseup',()=>{cur.style.width='25px';cur.style.height='25px'});
})();"""


class ArtworkHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, artwork_dir, assets_dir, repo_dir, **kwargs):
        self.artwork_dir, self.assets_dir, self.repo_dir = artwork_dir, assets_dir, repo_dir
        super().__init__(*args, **kwargs)

    def asset_path(self, request_path):
        path = urlparse(request_path).path.lstrip("/")
        name = Path(path).name
        if ".." in Path(path).parts:
            return None
        if name in {"lamplight-opening.html", "lamplight-closing.html"}:
            return self.artwork_dir / name
        if "/stock-footage/" in "/" + path and name in {
                "coordinator-computer-pexels-6997946.mp4", "team-computers-pexels-8048240.mp4"}:
            return self.assets_dir / name
        if path.endswith(("campaign/logo/lamplight-logo.svg", "campaign/logo/lamplight-logo-1024.png")):
            return self.repo_dir / "campaign/logo" / name
        if name in {"lamplight-public-sans-variable.ttf", "PublicSans-Variable.ttf"}:
            return self.repo_dir / "app/carebridge/web/fonts/PublicSans-Variable.ttf"
        return None

    def do_GET(self):
        if not self.asset_path(self.path):
            self.send_error(404)
            return
        super().do_GET()

    def translate_path(self, path):
        return str(self.asset_path(path))

    def log_message(self, *_args):
        pass


@contextmanager
def artwork_server(url: str, artwork_dir: Path, assets_dir: Path, repo_dir: Path):
    parsed = urlparse(url)
    if parsed.hostname != "127.0.0.1" or not parsed.port:
        raise ValueError("Artwork server must be on 127.0.0.1 with an explicit port.")
    try:
        with urlopen(url + "/lamplight-opening.html", timeout=1) as response:
            existing = b"Lamplight" in response.read(2000)
    except Exception:
        existing = False
    if existing:
        yield
        return
    handler = partial(ArtworkHandler, artwork_dir=artwork_dir, assets_dir=assets_dir, repo_dir=repo_dir)
    server = ThreadingHTTPServer(("127.0.0.1", parsed.port), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=3)


def check_response(response, label):
    if not response.ok:
        raise RuntimeError(f"{label} returned HTTP {response.status}")
    return response.json()


def sign_in(browser, base):
    context = browser.new_context(viewport=VIEWPORT)
    runtime = check_response(context.request.get(base + "/api/state"), "runtime mode")
    if runtime.get("production") is not False:
        raise RuntimeError("Refusing to capture unless production is explicitly false.")
    context.add_init_script(INIT)
    page = context.new_page()
    context.new_cdp_session(page).send("Emulation.setDefaultBackgroundColorOverride",
                                       {"color": {"r": 255, "g": 248, "b": 240, "a": 1}})
    page.goto(base + "/auth/signin?lang=en", wait_until="networkidle")
    if "Practice sign-in" not in page.locator("body").inner_text():
        raise RuntimeError("Refusing to record: the local practice sign-in is not available.")
    page.get_by_role("button", name=re.compile(r"^Avery \(lead\)")).click()
    page.wait_for_url(base + "/", wait_until="networkidle")
    me = check_response(context.request.get(base + "/api/me"), "practice identity")
    if me.get("auth") != "practice" or me.get("via") != "practice" or me.get("role") != "lead":
        raise RuntimeError("Refusing to record outside the supplied Avery practice lead account.")
    return context, page, me


def practice_admin_state(browser, base):
    """A separate invented IT account; Avery keeps the lead role throughout."""
    context = browser.new_context(viewport=VIEWPORT)
    context.add_init_script(INIT)
    page = context.new_page()
    page.goto(base + "/auth/signin?lang=en", wait_until="networkidle")
    if "Practice sign-in" not in page.locator("body").inner_text():
        raise RuntimeError("Refusing to create an IT fixture outside practice sign-in.")
    existing = page.get_by_role("button", name=re.compile(r"^Demo IT \(fictional\)"))
    if existing.count():
        existing.click()
    else:
        page.get_by_text("Add a practice person", exact=True).click()
        form = page.locator('form[action="/auth/practice/add"]')
        form.locator('[name="name"]').fill("Demo IT (fictional)")
        form.locator('[name="email"]').fill("demo.it@ihh.example.org")
        form.locator('[name="role"]').select_option("admin")
        form.get_by_role("button", name="Add and sign in", exact=True).click()
    page.wait_for_url(base + "/", wait_until="networkidle")
    me = check_response(context.request.get(base + "/api/me"), "practice IT identity")
    assert me.get("auth") == "practice" and me.get("via") == "practice" and me.get("role") == "admin", me
    assert me.get("email") == "demo.it@ihh.example.org", me
    state = context.storage_state()
    context.close()
    return state


def seed_practice(context, base):
    queue = check_response(context.request.get(base + "/api/queue"), "existing queue")
    if any(not card.get("practice") for card in queue.get("cards", [])):
        raise RuntimeError("Refusing to reset a queue containing non-practice referrals.")
    check_response(context.request.post(base + "/api/settings", data={"lang": "en"}), "English preference")
    check_response(context.request.post(base + "/api/demo", data={"speed": 600}), "practice seed")
    deadline = time.monotonic() + 8
    while time.monotonic() < deadline:
        queue = check_response(context.request.get(base + "/api/queue"), "practice queue")
        if queue["pending"] == 0 and len(queue["cards"]) == 5:
            break
        time.sleep(.15)
    check_response(context.request.post(base + "/api/clock", data={"speed": 0}), "pause practice clock")
    cards = {c["id"]: c for c in queue.get("cards", [])}
    for cid, packet in SYNTHETIC.items():
        if cid not in cards or not cards[cid].get("practice") or not cards[cid].get("synthetic"):
            raise RuntimeError(f"Expected synthetic practice referral {cid} is missing.")
        if cards[cid].get("packet_id") != packet:
            raise RuntimeError(f"Synthetic referral {cid} does not have the supplied {packet} packet.")


def visual_qa(browser, state, base, scratch):
    destination = scratch / "lamplight-browser-qa"
    destination.mkdir(exist_ok=True)
    contexts, checks, external = [], {}, []
    variants = {"light": {}, "dark": {"theme": "dark"},
                "colorblind": {"colors": "cvd"}, "easy": {"easy": "on"}}
    try:
        for name, changes in variants.items():
            display = {"theme": "light", "colors": "standard", "easy": "off", **changes}
            context = browser.new_context(viewport=VIEWPORT, storage_state=state)
            contexts.append(context)
            context.add_init_script(INIT + "\nlocalStorage.setItem('cb-display'," + json.dumps(json.dumps(display)) + ");")
            page = context.new_page()
            page.on("request", lambda request: external.append(urlparse(request.url).netloc)
                    if request.url.startswith(("http://", "https://")) and urlparse(request.url).netloc != urlparse(base).netloc else None)
            page.goto(base + "/", wait_until="networkidle")
            page.evaluate("async()=>{await document.fonts.ready}")
            page.locator(".brand .name").wait_for()
            computed = page.evaluate("""()=>({font:getComputedStyle(document.body).fontFamily,
              publicSansLoaded:document.fonts.check('16px "Public Sans"'),
              background:getComputedStyle(document.body).backgroundColor,
              theme:document.documentElement.dataset.theme,colors:document.documentElement.dataset.colors,
              easy:document.documentElement.dataset.easy,logo:document.querySelector('.logo img')?.naturalWidth})""")
            if name == "light":
                assert computed["background"] == "rgb(255, 248, 240)", computed
            assert "Public Sans" in computed["font"] and computed["publicSansLoaded"] and computed["logo"] > 0, computed
            page.screenshot(path=str(destination / f"{name}.png"))
            page.evaluate("window.scrollTo(0,340)")
            page.wait_for_timeout(120)
            page.screenshot(path=str(destination / f"{name}-queue.png"))
            checks[name] = computed
        logo = contexts[0].request.get(base + "/static/lamplight-logo.svg")
        font = contexts[0].request.get(base + "/static/fonts/PublicSans-Variable.ttf")
        assert logo.status == 200 and "<svg" in logo.text()
        assert font.status == 200 and len(font.body()) > 100000
        assert not external, f"Unexpected external origins: {sorted(set(external))}"
        result = {"modes": checks, "logo_status": logo.status, "font_status": font.status,
                  "external_requests": len(external)}
        (destination / "checks.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
        print("Browser QA: Public Sans loaded; local SVG/font HTTP200; cream background; 4 display modes; no external requests.", flush=True)
    finally:
        for context in contexts:
            context.close()


def first_clean_frame(path):
    """Find the first clean encoded frame after the discarded magenta pre-roll."""
    frames = imageio_ffmpeg.read_frames(str(path), pix_fmt="rgb24", output_params=["-vf", "fps=25", "-t", "30"])
    metadata = next(frames)
    width, height = metadata["size"]
    marked = False
    try:
        for index, frame in enumerate(frames):
            image = np.frombuffer(frame, dtype=np.uint8).reshape(height, width, 3)
            corner = image[3:15, 3:15]
            magenta = np.mean((corner[:, :, 0] > 175) & (corner[:, :, 1] < 100) & (corner[:, :, 2] > 150)) > .6
            if magenta:
                marked = True
            elif marked:
                return round(index / 25, 3)
    finally:
        frames.close()
    raise RuntimeError("Could not detect the discarded recording pre-roll marker.")


def record(browser, state, admin_state, args):
    recordings = args.scratch / "lamplight-recordings"
    recordings.mkdir(exist_ok=True)
    context = browser.new_context(viewport=VIEWPORT, storage_state=state,
                                  record_video_dir=str(recordings), record_video_size=VIEWPORT)
    context.add_init_script(INIT)
    context.add_init_script("if(location.origin===" + json.dumps(args.base) +
                            "){localStorage.removeItem('cb_onboarded')}")
    page = context.new_page()
    context.new_cdp_session(page).send("Emulation.setDefaultBackgroundColorOverride",
                                       {"color": {"r": 255, "g": 248, "b": 240, "a": 1}})
    page.set_default_timeout(8000)
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.goto(args.film + "/lamplight-opening.html", wait_until="networkidle")
    page.wait_for_function("document.querySelector('video').readyState >= 2")
    page.evaluate("async()=>{await document.fonts.ready;await window.seekScene(0);let d=document.createElement('div');d.id='capture-preroll';d.style='position:fixed;left:0;top:0;width:20px;height:20px;z-index:999999;background:#ff00ff';document.body.append(d)}")
    page.wait_for_timeout(700)
    t0 = time.monotonic()
    page.evaluate("async()=>{document.getElementById('capture-preroll').remove();document.getAnimations().forEach(a=>a.play());await document.querySelector('video').play()}")
    events = []

    def mark(text):
        elapsed = round(time.monotonic() - t0, 3)
        events.append({"time": elapsed, "event": text})
        print(f"{elapsed:6.2f} {text}", flush=True)

    def at(second):
        if args.quick:
            return
        delay = second - (time.monotonic() - t0)
        if delay > 0:
            page.wait_for_timeout(delay * 1000)
        elif delay < -.8:
            mark(f"late for {second:g}s by {-delay:.2f}s")

    def callout(en, es, quote=False, note="Demo note / Nota de la demo"):
        page.evaluate("""([en,es,quote,note])=>{document.querySelector('#film-callout')?.remove();
        let d=document.createElement('aside');d.id='film-callout';if(quote)d.className='quote';
        let small=document.createElement('small');small.textContent=note;
        let h=document.createElement('h2');h.innerHTML=en;
        let p=document.createElement('p');p.innerHTML=es;p.lang='es';d.append(small,h,p);document.body.append(d)}""", [en, es, quote, note])

    def clear():
        page.evaluate("document.querySelector('#film-callout')?.remove()")

    def focus(locator):
        locator.first.scroll_into_view_if_needed()
        page.wait_for_timeout(100)
        box = locator.first.bounding_box()
        if box:
            page.mouse.move(box["x"] + min(box["width"] / 2, 210),
                            box["y"] + min(box["height"] / 2, 60), steps=18)

    def click(locator):
        focus(locator)
        locator.first.click()
        page.wait_for_timeout(190)

    def panel(heading):
        return page.locator("#detail-body .panel").filter(has=page.get_by_role("heading", name=heading, exact=True)).first

    def smooth_to(locator, offset=30):
        locator.first.evaluate("""(el,off)=>{let d=document.querySelector('#detail-body');
        d.scrollTo({top:el.getBoundingClientRect().top-d.getBoundingClientRect().top+d.scrollTop-off,behavior:'smooth'})}""", offset)
        page.wait_for_timeout(520)

    def open_card(cid):
        if cid not in SYNTHETIC:
            raise ValueError("Only the supplied synthetic demo IDs may be recorded.")
        clear()
        if page.locator("#detail").is_visible():
            click(page.locator("#d-close"))
        click(page.locator(f'.card[data-id="{cid}"]'))
        page.locator("#detail .gates").wait_for()
        page.wait_for_timeout(220)

    def language(lang):
        clear()
        if page.locator("#detail").is_visible():
            click(page.locator("#d-close"))
        page.evaluate("window.scrollTo({top:0,behavior:'smooth'})")
        page.wait_for_timeout(280)
        click(page.locator(f'.lang [data-lang="{lang}"]'))
        page.wait_for_function("lang=>document.documentElement.lang===lang", arg=lang)

    mark("opening")
    at(13)
    page.goto(args.base + "/", wait_until="domcontentloaded")
    page.evaluate(CURSOR)
    page.locator("#onboard:not(.hidden)").wait_for()
    page.locator("#ob-title").wait_for()
    mark("four-step welcome: lamp and staff promise")
    at(15); click(page.locator("#ob-next")); mark("welcome role selection")
    at(16); click(page.locator("#ob-next")); mark("welcome human decision and AI limits")
    at(18); click(page.locator("#ob-next")); mark("welcome practice invitation")
    at(19); click(page.locator("#ob-skip"))
    page.locator("#onboard").wait_for(state="hidden")
    page.locator(".card").first.wait_for()
    queue = check_response(context.request.get(args.base + "/api/queue"), "retained practice queue")
    assert queue["pending"] == 0 and queue["speed"] == 0 and len(queue["cards"]) == 5
    mark("practice queue; welcome skipped without reset")
    at(20); page.mouse.move(340, 560, steps=30); page.evaluate("window.scrollTo({top:310,behavior:'smooth'})")
    at(22); callout("Fictional patients.<br>A working workflow.", "Pacientes ficticios.<br>Un flujo de trabajo en acción.")
    at(26); clear(); page.mouse.move(550, 390, steps=20)
    at(30); open_card("DEMO-101"); callout("Check the chart.<br>Keep the conflict.", "Revise el expediente.<br>Muestre la contradicción."); mark("S06 self-care evidence")
    at(35); target = page.locator("#detail-body .flag").filter(has_text="MOB-1").first; smooth_to(target, 140)
    at(38); click(target.locator('[data-page="11"]')); page.locator("#viewer-img").wait_for()
    callout('“She cannot walk, transfer, bathe, dress or toilet without hands-on help.”', "Necesita ayuda física para caminar, trasladarse, bañarse, vestirse e ir al baño.", quote=True, note="S06 · Page 11 / Página 11")
    mark("source page11 exact quote")
    at(40); page.locator("#viewer-img").evaluate("el=>{el.style.transition='transform 1.2s';el.style.transform='scale(1.16)';el.style.transformOrigin='50% 42%'}")
    at(44); click(page.locator("#viewer-close")); callout("A rule. A page.<br>The original words.", "Una regla. Una página.<br>Las palabras originales.")
    at(46); smooth_to(panel("The form and the chart don't match"), 70); clear(); mark("conflict stays visible")
    at(50); smooth_to(panel("Papers the hospital should send"), 38)
    at(54); smooth_to(panel("How the app checked its own work"), 38)
    at(57); smooth_to(page.locator(".drafts-tabs"), 50); click(page.locator('[data-draft="clinical"]'))
    at(60); open_card("DEMO-103"); callout("One list of missing items.", "Una lista de lo que falta."); smooth_to(panel("Papers the hospital should send"), 30); mark("S09 missing records")
    at(65); smooth_to(page.locator(".drafts-tabs"), 40); click(page.locator('[data-draft="missing_items"]'))
    at(69); click(page.locator('[data-draft="chase_nudge"]')); callout("Draft. Review. Send.", "Borrador. Revisión. Envío.")
    at(73); click(page.locator('[data-draft="missing_items"]')); clear()
    at(76); page.locator("#detail-body").evaluate("d=>d.scrollTo({top:0,behavior:'smooth'})"); mark("same S09 card English")
    at(79); smooth_to(page.locator(".drafts-tabs"), 40); click(page.locator('[data-draft="chase_nudge"]'))
    at(82); language("es"); open_card("DEMO-103"); mark("same S09 card Spanish")
    at(84); smooth_to(panel("En pocas palabras"), 40)
    at(86); smooth_to(page.locator(".drafts-tabs"), 40); click(page.locator('[data-draft="chase_nudge"]')); callout("Same referral.<br>Spanish follow-up.", "El mismo referido.<br>Seguimiento en español.")
    at(90); language("en")
    at(92); open_card("DEMO-102"); smooth_to(page.locator('[data-act="hospital_replied"]'), 120); mark("staff resolve questions and decide")
    callout("People resolve questions.<br>People decide.", "Las personas aclaran las dudas.<br>Las personas deciden.")
    at(94.5); click(page.locator('[data-act="hospital_replied"]'))
    at(95.5); click(page.locator('[data-act="intake_cleared"]'))
    at(96.5); click(page.locator('[data-act="accepted"]')); mark("accepted by Avery practice lead")
    accepted = check_response(context.request.get(args.base + "/api/cards/DEMO-102"), "practice acceptance")
    assert accepted["card"]["status"] == "accepted"
    assert any(a["what"] == "accepted" and "Avery" in a["who"] for a in accepted["audit"])
    at(98); smooth_to(page.locator(".drafts-tabs"), 38); click(page.locator('[data-draft="handoffs"]')); clear()
    at(100.5); smooth_to(page.get_by_role("heading", name=re.compile(r"^For the census sheet")), 30)
    at(103)
    admin_cookies = [cookie for cookie in admin_state["cookies"] if cookie["name"] == "cb_session"]
    assert len(admin_cookies) == 1
    context.add_cookies(admin_cookies)
    page.goto(args.base + "/static/audit.html", wait_until="domcontentloaded")
    page.locator("#rows tr").first.wait_for()
    page.locator("#case").fill("DEMO-102")
    page.locator("#kind").select_option("decision")
    with page.expect_response(lambda response: response.url.startswith(args.base + "/api/audit-log?")
                              and "case=DEMO-102" in response.url) as filtered:
        page.locator("#go").click()
    assert filtered.value.ok
    decision = page.locator("#rows tr").filter(has_text="accepted").filter(has_text="Avery").last
    decision.wait_for()
    decision.scroll_into_view_if_needed()
    focus(decision.locator("td").nth(3))
    me = check_response(context.request.get(args.base + "/api/me"), "audit viewer identity")
    assert me.get("role") == "admin" and me.get("email") == "demo.it@ihh.example.org"
    mark("separate fictional admin audit: who, what, when")
    at(107); page.goto(args.film + "/lamplight-closing.html", wait_until="networkidle"); page.locator("video").evaluate("v=>v.play()"); mark("closing")
    at(120.25)
    stem = "lamplight-smoke" if args.quick else "lamplight"
    page.screenshot(path=str(args.scratch / f"{stem}-closing.png"))
    video = page.video
    context.close()
    temporary = Path(video.path())
    raw = args.output
    if raw.exists():
        raise FileExistsError(f"Preserving existing recording: {raw}")
    temporary.replace(raw)
    offset = first_clean_frame(raw)
    result = {"raw": raw.name, "video_offset": offset, "duration": 120 if not args.quick else None,
              "practice_only": True, "cases": SYNTHETIC, "viewport": VIEWPORT,
              "roles": {"decision": "Avery (lead)", "audit": "Demo IT (fictional)"},
              "events": events, "page_errors": errors}
    (args.scratch / f"{stem}-capture.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    if errors:
        raise RuntimeError(f"Browser had {len(errors)} JavaScript errors; inspect capture metadata.")
    print(f"RAW {raw}\nVIDEO OFFSET {offset:.3f}", flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--app-url", "--base", dest="base", default="http://127.0.0.1:18780")
    parser.add_argument("--film", default="http://127.0.0.1:18781")
    parser.add_argument("--scratch", type=Path, required=True)
    parser.add_argument("--artwork-dir", type=Path, default=ROOT)
    parser.add_argument("--assets-dir", type=Path, required=True,
                        help="Directory containing the two licensed stock MP4 files.")
    repo_default = ROOT.parent.parent
    parser.add_argument("--repo-dir", type=Path, default=repo_default)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--quick", action="store_true")
    parser.add_argument("--inspect", action="store_true")
    parser.add_argument("--skip-visual-qa", action="store_true")
    args = parser.parse_args()
    args.base, args.film = args.base.rstrip("/"), args.film.rstrip("/")
    if urlparse(args.base).hostname != "127.0.0.1":
        parser.error("Only the local practice server on 127.0.0.1 is allowed.")
    args.scratch.mkdir(parents=True, exist_ok=True)
    args.output = args.output or args.scratch / ("lamplight-smoke.webm" if args.quick else "lamplight-raw.webm")
    if not args.inspect and args.output.exists():
        parser.error(f"Preserving existing recording; choose another --output: {args.output}")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with artwork_server(args.film, args.artwork_dir, args.assets_dir, args.repo_dir), sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True, args=["--autoplay-policy=no-user-gesture-required"])
        setup, page, me = sign_in(browser, args.base)
        if not args.inspect:
            seed_practice(setup, args.base)
            page.reload(wait_until="networkidle")
        state = setup.storage_state()
        setup.close()
        if not args.skip_visual_qa:
            visual_qa(browser, state, args.base, args.scratch)
        if not args.inspect:
            admin_state = practice_admin_state(browser, args.base)
            record(browser, state, admin_state, args)
        browser.close()


if __name__ == "__main__":
    main()
