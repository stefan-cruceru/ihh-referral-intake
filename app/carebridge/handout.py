"""A printable next-steps PDF for the client to take with them.

One or two pages, large print, short words. Up to four numbered steps, each with what to do first,
the phone, place and hours, boxes to tick, and a notes box where staff write by hand (a name to ask
for, an appointment time, a bus line). Two looks: `color` and `bw` (black and white, for any
printer or copier).

Every phone number, address and hour comes from the sourced resource list, looked up by ID here;
only the "why" and "first step" wording comes from the review. No client name or other
identifier is ever put in the file: there is a blank line for staff to write a first name by hand.
"""

from datetime import date

from fpdf import FPDF

from . import resources

MAX_STEPS = 4  # keeps it to two pages

T = {
    "title": ("Your next steps", "Sus próximos pasos"),
    "name": ("Name", "Nombre"),
    "made": ("Made on", "Hecho el"),
    "today": ("Today", "Hoy"),
    "step": ("Step", "Paso"),
    "do_first": ("First", "Primero"),
    "call": ("Call", "Llame al"),
    "where": ("Where", "Dónde"),
    "hours": ("Open", "Horario"),
    "online": ("Online", "En internet"),
    "know": ("Good to know", "Bueno saber"),
    # When there is no first step from a review: what the sourced list says about how to get in.
    "first_phone": ("Call them.", "Llámeles."),
    "first_walk-in": ("Go in person. Call first to check the hours.", "Vaya en persona. Llame antes para confirmar el horario."),
    "first_appointment": ("Call to make an appointment.", "Llame para hacer una cita."),
    "first_online": ("Apply online. Ask staff to help.", "Haga la solicitud en internet. Pida ayuda al personal."),
    "first_referral-only": ("Ask staff to make the referral.", "Pida al personal que haga el referido."),
    "first_mixed": ("Call them, or ask staff to help.", "Llámeles, o pida ayuda al personal."),
    "referral": ("You need a referral first. Ask staff to help.", "Primero necesita un referido. Pida ayuda al personal."),
    "no_address": ("Ask staff where to go.", "Pregunte al personal adónde ir."),
    "called": ("I called", "Llamé"),
    "went": ("I went", "Fui"),
    "done": ("Done", "Listo"),
    "notes": ("Notes from staff", "Notas del personal"),
    "getting_there": ("Getting there", "Cómo llegar"),
    "bus": ("Ask staff for a bus pass or a ride. If you are 60 or older or have a disability, the bus may cost less (OC Bus reduced fare).",
            "Pida al personal un pase de autobús o transporte. Si tiene 60 años o más o una discapacidad, el autobús puede costar menos (tarifa reducida de OC Bus)."),
    "map": ("Or call the place and ask: \"How do I get there by bus?\"",
            "O llame al lugar y pregunte: \"¿Cómo llego en autobús?\""),
    "bring": ("Bring with you", "Lleve con usted"),
    "bring_list": ("Any ID you have. Your Medi-Cal card if you have one. This paper. A phone if you have one.",
                   "Cualquier identificación que tenga. Su tarjeta de Medi-Cal si tiene una. Este papel. Un teléfono si tiene uno."),
    "safety": ("In danger? Call 911.   Feel like hurting yourself? Call or text 988. Free, any time.",
               "¿En peligro? Llame al 911.   ¿Quiere hacerse daño? Llame o mande texto al 988. Gratis, a toda hora."),
    "staff": ("Staff who helped me", "Personal que me ayudó"),
    "phone": ("Phone", "Teléfono"),
    "change": ("Call before you go. Hours and rules can change. Checked:",
               "Llame antes de ir. Los horarios y las reglas pueden cambiar. Revisado:"),
    "more": ("More help on page 2", "Más ayuda en la página 2"),
}

# (fill, ink) colors per look. Color: a calm teal with a warm orange for step numbers.
LOOKS = {
    "color": {"brand": (23, 105, 115), "brand_soft": (226, 240, 241), "accent": (233, 120, 40),
              "alert": (253, 236, 200), "alert_ink": (122, 72, 0), "ink": (29, 42, 51), "muted": (90, 102, 112),
              "line": (190, 205, 208), "notes": (247, 250, 250), "head_ink": (255, 255, 255)},
    "bw": {"brand": (0, 0, 0), "brand_soft": (255, 255, 255), "accent": (0, 0, 0),
           "alert": (255, 255, 255), "alert_ink": (0, 0, 0), "ink": (0, 0, 0), "muted": (60, 60, 60),
           "line": (110, 110, 110), "notes": (255, 255, 255), "head_ink": (0, 0, 0)},
}


def _t(key: str, lang: str) -> str:
    return T[key][1 if lang == "es" else 0]


def _safe(s: str | None) -> str:
    """The built-in PDF fonts are Latin-1, which covers English and Spanish."""
    s = (s or "").replace("–", "-").replace("—", "-").replace("’", "'").replace("“", '"').replace("”", '"')
    return s.encode("latin-1", "replace").decode("latin-1")


class _PDF(FPDF):
    def __init__(self, lang: str, look: dict):
        super().__init__(format="Letter")
        self.lang, self.look = lang, look
        self.set_auto_page_break(True, margin=16)
        self.set_margins(14, 12, 14)

    def footer(self):
        self.set_y(-12)
        self.set_font("Helvetica", "", 9)
        self.set_text_color(*self.look["muted"])
        self.cell(0, 5, _safe(f"{_t('title', self.lang)}  ·  {self.page_no()}/{{nb}}"), align="C")


def build(items: list[dict], plan_today: str = "", lang: str = "en", danger: bool = False, style: str = "color") -> bytes:
    """items: [{resource_id, why, first_step, watch_out}] in the order to do them. style: color | bw."""
    look = LOOKS.get(style, LOOKS["color"])
    bw = style == "bw"
    by_id = {r["id"]: r for r in resources.catalog()}
    steps = [(it, by_id[it["resource_id"]]) for it in items if it.get("resource_id") in by_id][:MAX_STEPS]

    pdf = _PDF(lang, look)
    pdf.alias_nb_pages()
    pdf.add_page()
    L, W = pdf.l_margin, pdf.w - pdf.l_margin - pdf.r_margin

    def ink(key="ink"):
        pdf.set_text_color(*look[key])

    def text(s, size=12, style_="", h=None, color="ink", x=None, w=None):
        pdf.set_font("Helvetica", style_, size)
        ink(color)
        if x is not None:
            pdf.set_x(x)
        pdf.multi_cell(w or W - ((x or L) - L), h or size * 0.47, _safe(s), align="L", new_x="LMARGIN", new_y="NEXT")

    # ---- header band ------------------------------------------------------------------------
    top = pdf.get_y()
    if bw:
        pdf.set_draw_color(0)
        pdf.set_line_width(1.2)
        pdf.line(L, top + 22, L + W, top + 22)
    else:
        pdf.set_fill_color(*look["brand"])
        pdf.rect(0, 0, pdf.w, top + 22, style="F")
    pdf.set_xy(L, top + 3)
    pdf.set_font("Helvetica", "B", 26)
    ink("head_ink")
    pdf.cell(W * 0.62, 14, _safe(_t("title", lang)))
    pdf.set_font("Helvetica", "", 11)
    pdf.cell(W * 0.38, 14, _safe(f"{_t('made', lang)} {date.today():%m/%d/%Y}"), align="R")
    pdf.set_y(top + 27)

    # Name and staff lines (written by hand; nothing identifying is printed).
    pdf.set_draw_color(*look["line"])
    pdf.set_line_width(0.3)
    y = pdf.get_y()
    pdf.set_font("Helvetica", "", 11)
    ink("muted")
    for x, label, width in ((L, _t("name", lang), 62), (L + 70, _t("staff", lang), 62), (L + 140, _t("phone", lang), W - 140)):
        pdf.set_xy(x, y)
        pdf.cell(width, 5, _safe(label))
        pdf.line(x, y + 11, x + width - 4, y + 11)
    pdf.set_y(y + 14)

    # ---- safety strip --------------------------------------------------------------------------
    y = pdf.get_y()
    pdf.set_font("Helvetica", "B", 12)
    msg = _safe(_t("safety", lang))
    hgt = pdf.multi_cell(W - 6, 6, msg, dry_run=True, output="HEIGHT") + 6
    pdf.set_fill_color(*look["alert"])
    pdf.set_draw_color(*(look["alert_ink"] if not bw else (0, 0, 0)))
    pdf.set_line_width(0.8 if (bw or danger) else 0.3)
    pdf.rect(L, y, W, hgt, style="DF")
    pdf.set_xy(L + 3, y + 3)
    ink("alert_ink")
    pdf.multi_cell(W - 6, 6, msg, align="L")
    pdf.set_y(y + hgt + 4)
    pdf.set_line_width(0.3)

    if plan_today:
        text(_t("today", lang), 14, "B", h=7, color="brand" if not bw else "ink")
        text(plan_today, 12, h=6)
        pdf.ln(2)

    # ---- steps ------------------------------------------------------------------------------
    for n, (it, r) in enumerate(steps, 1):
        if pdf.get_y() > pdf.h - 92:
            pdf.add_page()
        _step(pdf, n, it, r, lang, look, bw, text, L, W)

    # ---- getting there and what to bring ------------------------------------------------------
    if pdf.get_y() > pdf.h - 46:  # needs about 30 mm above the footer
        pdf.add_page()
    y = pdf.get_y()
    col = (W - 6) / 2
    for i, (head, body) in enumerate(((_t("getting_there", lang), _t("bus", lang) + " " + _t("map", lang)),
                                      (_t("bring", lang), _t("bring_list", lang)))):
        x = L + i * (col + 6)
        pdf.set_xy(x, y)
        pdf.set_font("Helvetica", "B", 13)
        ink("brand" if not bw else "ink")
        pdf.cell(col, 7, _safe(head), new_x="LEFT", new_y="NEXT")
        pdf.set_font("Helvetica", "", 11)
        ink()
        pdf.set_x(x)
        pdf.multi_cell(col, 5.4, _safe(body), align="L")
    return bytes(pdf.output())


def _step(pdf, n, it, r, lang, look, bw, text, L, W):
    """One step: number, name, what to do first, phone/place/hours, tick boxes, notes box."""
    top = pdf.get_y()
    inner = L + 15
    iw = W - 18
    # number badge
    if bw:
        pdf.set_draw_color(0)
        pdf.set_line_width(0.8)
        pdf.ellipse(L + 1, top + 1, 10, 10, style="D")
        pdf.set_text_color(0)
    else:
        pdf.set_fill_color(*look["accent"])
        pdf.ellipse(L + 1, top + 1, 10, 10, style="F")
        pdf.set_text_color(255, 255, 255)
    pdf.set_line_width(0.3)
    pdf.set_font("Helvetica", "B", 14)
    pdf.set_xy(L + 1, top + 1)
    pdf.cell(10, 10, str(n), align="C")

    pdf.set_xy(inner, top + 1.5)
    text(r["name"], 15, "B", h=7, x=inner, w=iw)
    if it.get("why"):
        text(it["why"], 11, h=5.4, color="muted", x=inner, w=iw)
    first = it.get("first_step")
    if not first and f"first_{r.get('how_to_access')}" in T:
        first = _t(f"first_{r['how_to_access']}", lang)
    if first:
        text(f"{_t('do_first', lang)}: {first}", 12.5, "B", h=6.2, x=inner, w=iw)

    rows = []
    if r.get("phone"):
        rows.append((_t("call", lang), r["phone"], True))
    survivor = {"survivors", "domestic-violence", "confidential-location"} & set(r.get("tags", []))
    place = "" if survivor else (r.get("address") or "")
    if place and r.get("city") and r["city"].lower() not in place.lower():
        place += f", {r['city']}"
    if place:
        rows.append((_t("where", lang), place, False))
    elif r.get("how_to_access") in ("walk-in", "appointment", "mixed"):
        rows.append((_t("where", lang), _t("no_address", lang), False))
    if r.get("hours"):
        rows.append((_t("hours", lang), r["hours"], False))
    if r.get("website") and r.get("how_to_access") in ("online", "mixed"):
        rows.append((_t("online", lang), r["website"], False))
    for label, value, big in rows:
        pdf.set_x(inner)
        pdf.set_font("Helvetica", "B", 11)
        pdf.set_text_color(*look["muted"])
        pdf.cell(25, 6, _safe(label))
        pdf.set_font("Helvetica", "B" if big else "", 13 if big else 11)
        pdf.set_text_color(*look["ink"])
        pdf.multi_cell(iw - 25, 6, _safe(value), align="L", new_x="LMARGIN", new_y="NEXT")
    if r.get("how_to_access") == "referral-only" or r.get("referral_required"):
        text(_t("referral", lang), 11, "B", h=5.6, x=inner, w=iw)
    if it.get("watch_out"):
        text(f"{_t('know', lang)}: {it['watch_out']}", 11, h=5.4, x=inner, w=iw)

    # tick boxes
    y = pdf.get_y() + 1.5
    pdf.set_draw_color(*(look["brand"] if not bw else (0, 0, 0)))
    pdf.set_line_width(0.5)
    for i, key in enumerate(("called", "went", "done")):
        x = inner + i * 38
        pdf.rect(x, y, 5.5, 5.5)
        pdf.set_xy(x + 7.5, y - 0.5)
        pdf.set_font("Helvetica", "", 12)
        pdf.set_text_color(*look["ink"])
        pdf.cell(28, 6.5, _safe(_t(key, lang)))

    # notes box for staff to write in by hand
    y += 9
    pdf.set_fill_color(*look["notes"])
    pdf.set_draw_color(*look["line"])
    pdf.set_line_width(0.3)
    pdf.rect(inner, y, iw, 20, style="DF" if not bw else "D")
    pdf.set_xy(inner + 2, y + 1.5)
    pdf.set_font("Helvetica", "B", 9.5)
    pdf.set_text_color(*look["muted"])
    pdf.cell(50, 4, _safe(_t("notes", lang)))
    pdf.set_font("Helvetica", "", 8)
    pdf.set_xy(inner + 52, y + 1.5)
    pdf.cell(iw - 54, 4, _safe(f"{_t('change', lang)} {r.get('verified_date') or '?'}"), align="R")
    for k in (1, 2):
        ly = y + 5 + k * 6.5
        pdf.line(inner + 3, ly, inner + iw - 3, ly)
    bottom = y + 20

    # left accent bar ties the step together
    if not bw:
        pdf.set_fill_color(*look["brand_soft"])
        pdf.rect(L + 5, top + 12, 1.4, max(0, bottom - top - 12), style="F")
    else:
        pdf.set_draw_color(0)
        pdf.line(L + 6, top + 12, L + 6, bottom)
    pdf.set_y(bottom + 4)
