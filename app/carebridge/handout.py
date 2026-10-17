"""A printable next-steps PDF for the client to take with them.

Large print, short words, one step per block, with boxes to tick as they follow through. Every
phone number, address and hour comes from the sourced resource list, looked up by ID here; only
the "why" and "first step" wording comes from the review. No client name or other identifier is
ever put in the file: there is a blank line for staff to write a first name by hand.
"""

from datetime import date

from fpdf import FPDF

from . import resources

T = {
    "title": ("Your next steps", "Sus próximos pasos"),
    "name": ("Name: ______________________", "Nombre: ____________________"),
    "made": ("Made on", "Hecho el"),
    "today": ("Today", "Hoy"),
    "step": ("Step", "Paso"),
    "do_first": ("What to do first", "Qué hacer primero"),
    "call": ("Call", "Llame al"),
    "go": ("Go to", "Vaya a"),
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
    "getting_there": ("Getting there", "Cómo llegar"),
    "bus": ("Ask staff for a bus pass or a ride. If you are 60 or older or have a disability, the bus may cost less (OC Bus reduced fare).",
            "Pida al personal un pase de autobús o transporte. Si tiene 60 años o más o una discapacidad, el autobús puede costar menos (tarifa reducida de OC Bus)."),
    "map": ("Ask staff to show you the way on a map, or call and ask: \"How do I get there by bus?\"",
            "Pida al personal que le muestre el camino en un mapa, o llame y pregunte: \"¿Cómo llego en autobús?\""),
    "bring": ("Bring with you", "Lleve con usted"),
    "bring_list": ("Any ID you have. Your Medi-Cal card if you have one. This paper. A phone if you have one.",
                   "Cualquier identificación que tenga. Su tarjeta de Medi-Cal si tiene una. Este papel. Un teléfono si tiene uno."),
    "safety": ("If you are in danger, call 911. If you feel like hurting yourself, call or text 988. It is free, any time.",
               "Si está en peligro, llame al 911. Si siente que quiere hacerse daño, llame o mande texto al 988. Es gratis, a cualquier hora."),
    "staff": ("Staff who helped me: ______________   Phone: ______________",
              "Personal que me ayudó: ______________   Teléfono: ______________"),
    "notes": ("My notes", "Mis notas"),
    "change": ("Call before you go. Hours and rules can change. Last checked:",
               "Llame antes de ir. Los horarios y las reglas pueden cambiar. Revisado:"),
}


def _t(key: str, lang: str) -> str:
    return T[key][1 if lang == "es" else 0]


def _safe(s: str | None) -> str:
    """The built-in PDF fonts are Latin-1, which covers English and Spanish."""
    s = (s or "").replace("–", "-").replace("—", "-").replace("’", "'").replace("“", '"').replace("”", '"')
    return s.encode("latin-1", "replace").decode("latin-1")


class _PDF(FPDF):
    def __init__(self, lang):
        super().__init__(format="Letter")
        self.lang = lang
        self.set_auto_page_break(True, margin=18)
        self.set_margins(18, 16, 18)

    def footer(self):
        self.set_y(-14)
        self.set_font("Helvetica", "", 10)
        self.cell(0, 6, _safe(f"{_t('title', self.lang)}  -  {self.page_no()}"), align="C")


def build(items: list[dict], plan_today: str = "", lang: str = "en", danger: bool = False) -> bytes:
    """items: [{resource_id, why, first_step, watch_out}] in the order to do them."""
    by_id = {r["id"]: r for r in resources.catalog()}
    pdf = _PDF(lang)
    pdf.add_page()
    w = pdf.w - pdf.l_margin - pdf.r_margin

    def text(s, size=14, style="", h=None, gap=1.5):
        pdf.set_font("Helvetica", style, size)
        pdf.multi_cell(w, h or size * 0.5, _safe(s), align="L", new_x="LMARGIN", new_y="NEXT")
        pdf.ln(gap)

    def box(label):
        x, y = pdf.get_x(), pdf.get_y()
        pdf.rect(x, y + 1, 6, 6)
        pdf.set_xy(x + 8, y)
        pdf.set_font("Helvetica", "", 14)
        pdf.cell(42, 8, _safe(label))

    text(_t("title", lang), 28, "B", h=12, gap=2)
    text(f"{_t('name', lang)}      {_t('made', lang)} {date.today():%m/%d/%Y}", 13)

    pdf.set_draw_color(0)
    pdf.set_line_width(0.8)
    y0 = pdf.get_y()
    pdf.set_x(pdf.l_margin + 3)
    pdf.set_font("Helvetica", "B" if danger else "", 14)
    pdf.multi_cell(w - 6, 7, _safe(_t("safety", lang)), new_x="LMARGIN", new_y="NEXT")
    pdf.rect(pdf.l_margin, y0 - 2, w, pdf.get_y() - y0 + 4)
    pdf.ln(5)
    pdf.set_line_width(0.3)

    if plan_today:
        text(_t("today", lang), 18, "B", h=9)
        text(plan_today, 14, h=7, gap=4)

    n = 0
    for it in items:
        r = by_id.get(it.get("resource_id"))
        if not r:
            continue  # only sourced resources are ever printed
        n += 1
        if pdf.get_y() > pdf.h - 90:
            pdf.add_page()
        pdf.set_fill_color(235, 235, 235)
        pdf.set_font("Helvetica", "B", 18)
        pdf.multi_cell(w, 9, _safe(f" {_t('step', lang)} {n}.  {r['name']}"), fill=True, align="L", new_x="LMARGIN", new_y="NEXT")
        pdf.ln(2)
        if it.get("why"):
            text(it["why"], 14, h=7)
        first = it.get("first_step")
        if not first and f"first_{r.get('how_to_access')}" in T:
            first = _t(f"first_{r['how_to_access']}", lang)
        if first:
            text(f"{_t('do_first', lang)}: {first}", 14, "B", h=7)
        if r.get("phone"):
            text(f"{_t('call', lang)}: {r['phone']}", 16, "B", h=8)
        survivor = {"survivors", "domestic-violence", "confidential-location"} & set(r.get("tags", []))
        place = "" if survivor else (r.get("address") or "")
        if place and r.get("city") and r["city"].lower() not in place.lower():
            place += f", {r['city']}"
        if r.get("how_to_access") == "referral-only" or r.get("referral_required"):
            text(_t("referral", lang), 14, h=7)
        if place:
            text(f"{_t('where', lang)}: {place}", 14, h=7)
        elif r.get("how_to_access") in ("walk-in", "appointment", "mixed"):
            text(_t("no_address", lang), 14, h=7)
        if r.get("hours"):
            text(f"{_t('hours', lang)}: {r['hours']}", 13, h=6.5)
        if r.get("website") and r.get("how_to_access") in ("online", "mixed"):
            text(f"{_t('online', lang)}: {r['website']}", 12, h=6)
        if it.get("watch_out"):
            text(f"{_t('know', lang)}: {it['watch_out']}", 13, h=6.5)
        text(f"{_t('change', lang)} {r.get('verified_date') or '?'}", 10, h=5)
        pdf.ln(1)
        box(_t("called", lang))
        box(_t("went", lang))
        box(_t("done", lang))
        pdf.ln(14)

    if pdf.get_y() > pdf.h - 80:
        pdf.add_page()
    text(_t("getting_there", lang), 18, "B", h=9)
    text(_t("bus", lang), 14, h=7)
    text(_t("map", lang), 14, h=7, gap=4)
    text(_t("bring", lang), 18, "B", h=9)
    text(_t("bring_list", lang), 14, h=7, gap=4)
    text(_t("staff", lang), 13, h=7, gap=4)
    text(_t("notes", lang), 18, "B", h=9)
    for _ in range(5):
        y = pdf.get_y() + 9
        pdf.line(pdf.l_margin, y, pdf.l_margin + w, y)
        pdf.set_y(y)
    return bytes(pdf.output())
