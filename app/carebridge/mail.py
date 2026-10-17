"""Email intake: a referral email saved as .eml becomes one packet, the same shape as a fax.

The body becomes typed page(s) at the front and each attachment (PDF, TIFF, PNG, JPEG) follows, so the
reviewer, the page viewer and the 2-hour clock treat an email exactly like a fax. Nothing is fetched from a
mail server: staff (or the mail client's rule) save the message into the inbox folder.
"""

import io
import textwrap
from email import policy
from email.parser import BytesParser
from email.utils import parsedate_to_datetime

from PIL import Image, ImageDraw, ImageFont

from . import guard

ATTACH_KINDS = {"pdf", "tiff", "png", "jpeg"}
BODY_PAGES_MAX = 5
PAGE_W, PAGE_H, MARGIN = 1275, 1650, 90  # US letter at 150 dpi
FONT_PX = 26


def _font():
    for name in ("DejaVuSans.ttf", "arial.ttf", "Arial.ttf"):
        try:
            return ImageFont.truetype(name, FONT_PX)
        except OSError:
            continue
    return ImageFont.load_default(size=FONT_PX)


def text_pages(header: str, body: str) -> list[Image.Image]:
    """Draw the email as plain letter-size pages, so it reads like any other faxed page."""
    font = _font()
    line_h = int(FONT_PX * 1.45)
    per_page = (PAGE_H - 2 * MARGIN) // line_h
    lines = []
    for para in (header + "\n\n" + body).splitlines():
        lines += textwrap.wrap(para, 80, replace_whitespace=False) or [""]
    pages = []
    for start in range(0, max(len(lines), 1), per_page):
        if len(pages) == BODY_PAGES_MAX:
            break
        img = Image.new("L", (PAGE_W, PAGE_H), 255)
        d = ImageDraw.Draw(img)
        for i, line in enumerate(lines[start:start + per_page]):
            d.text((MARGIN, MARGIN + i * line_h), line, fill=0, font=font)
        pages.append(img)
    return pages


def _to_pdf_pages(dest, data: bytes, kind: str):
    import pypdfium2 as pdfium

    if kind == "pdf":
        src = pdfium.PdfDocument(data)
        try:
            dest.import_pages(src)
        finally:
            src.close()
        return
    img = Image.open(io.BytesIO(data))
    frames = []
    i = 0
    while True:
        frames.append(img.convert("L").copy())
        i += 1
        try:
            img.seek(i)  # multi-page TIFF
        except EOFError:
            break
    _add_images(dest, frames)


def _add_images(dest, images: list[Image.Image]):
    import pypdfium2 as pdfium

    buf = io.BytesIO()
    images[0].save(buf, "PDF", save_all=True, append_images=images[1:], resolution=150)
    src = pdfium.PdfDocument(buf.getvalue())
    try:
        dest.import_pages(src)
    finally:
        src.close()


def packet_from_eml(raw: bytes) -> dict:
    """{'pdf': bytes|None, 'subject', 'sender', 'sent_at': float|None, 'attachments': [...], 'skipped': [...],
    'body_set_aside': bool}. Attachments the guard blocks are dropped and listed in skipped."""
    import pypdfium2 as pdfium

    msg = BytesParser(policy=policy.default).parsebytes(raw)
    subject = str(msg.get("Subject") or "")
    sender = str(msg.get("From") or "")
    try:
        sent_at = parsedate_to_datetime(str(msg.get("Date"))).timestamp() if msg.get("Date") else None
    except (TypeError, ValueError):
        sent_at = None

    body_part = msg.get_body(preferencelist=("plain",))
    body = body_part.get_content() if body_part else ""
    # Text that gives orders to an AI never becomes a page: a person reads the email in their mail client.
    body_set_aside = bool(guard.scan_text(body) or guard.scan_text(subject))

    attachments, skipped = [], []
    for part in msg.iter_attachments():
        name = part.get_filename() or "attachment"
        data = part.get_payload(decode=True) or b""
        kind = guard.kind_of(data)
        if kind not in ATTACH_KINDS:
            skipped.append({"name": name, "reason": "not_a_fax_file"})
            continue
        threat = guard.scan_file(data, name)
        if threat["verdict"] == guard.BLOCK:
            skipped.append({"name": name, "reason": "security_block"})
            continue
        attachments.append((name, kind, data))

    dest = pdfium.PdfDocument.new()
    try:
        if body.strip() and not body_set_aside:
            header = f"EMAIL\nSubject: {subject}"
            _add_images(dest, text_pages(header, body.strip()))
        for name, kind, data in attachments:
            try:
                _to_pdf_pages(dest, data, kind)
            except Exception:
                skipped.append({"name": name, "reason": "unreadable"})
        pdf = None
        if len(dest):
            buf = io.BytesIO()
            dest.save(buf)
            pdf = buf.getvalue()
    finally:
        dest.close()
    return {"pdf": pdf, "subject": subject, "sender": sender, "sent_at": sent_at,
            "attachments": [a[0] for a in attachments], "skipped": skipped, "body_set_aside": body_set_aside}


REASON = {"not_a_fax_file": "not a PDF or image", "security_block": "blocked by the security check",
          "unreadable": "could not be read"}


def summary_lines(got: dict) -> list[str]:
    """What staff should know about the email itself, shown above the review (Copilot and the command line)."""
    out = [f"**Email:** {got['subject'] or '(no subject)'}, from {got['sender'] or 'unknown'}. "
           f"Attachments used: {', '.join(got['attachments']) or 'none'}."]
    if got["body_set_aside"]:
        out.append("> **SECURITY HOLD:** the email text gives orders to the AI. It was not used. A person reads the "
                   "email in the mail program.")
    out += [f"- Not used: {s['name']} ({REASON.get(s['reason'], s['reason'])})" for s in got["skipped"]]
    return out
