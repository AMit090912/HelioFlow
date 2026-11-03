"""Quote PDF, rendered from the immutable snapshot on demand (§11), in en / hi / mr (Q-14).

Devanagari needs HarfBuzz shaping (uharfbuzz). In ReportLab only Platypus Paragraphs with
`shaping=1` shape correctly (the 2026-11-03 spike: canvas.drawString(shaping=True) still breaks
conjuncts), so every piece of words here is a Paragraph, including table cells and the labels
inside the drawn visuals. The canvas draws shapes only, plus bare Western digits on the payback
ruler (Latin needs no shaping).

One A4 page: a sunrise hero with the three numbers that matter, the options as cards, the money
split and payback drawn to scale, the working, the assumptions and what happens next. Every
figure comes from the snapshot; the visuals only redraw those numbers, they compute nothing new.
"""

import io
import math
from decimal import Decimal
from functools import cache
from pathlib import Path
from typing import Any, Literal
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics, ttfonts
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    Flowable,
    Image,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)
from reportlab.platypus import paragraph as rl_paragraph

from app.schemas.quotes import QuoteView
from app.services.notify import inr
from app.services.pdf.strings import ASSUMPTION_KEYS, NEXT_KEYS, STRINGS

FONTS = Path(__file__).resolve().parents[2] / "assets" / "fonts"
BRAND = Path(__file__).resolve().parents[2] / "assets" / "brand"
TEAL = colors.HexColor("#006863")
TEAL_SOFT = colors.HexColor("#E3EFED")
NIGHT = colors.HexColor("#012E2B")
GOLD = colors.HexColor("#E5B257")
GOLD_SOFT = colors.HexColor("#F6DFA8")
INK = colors.HexColor("#18211F")
INK_2 = colors.HexColor("#4F5D5A")
LINE = colors.HexColor("#DCE4E2")
SURFACE = colors.HexColor("#F2F6F5")
Locale = Literal["en", "hi", "mr"]


# ReportLab shapes with discretionary ligatures on (dlig=True), which turns Mukta's "st"/"ct"
# into decorative ligatures in ordinary text. Shape with standard ligatures and kerning only.
_SHAPING_FEATURES = {"kern": True, "liga": True, "dlig": False}
_rl_shape = ttfonts.shapeFragWord


# Needs uharfbuzz (a declared dependency): without it ReportLab's fallback has no `force`.
def _shape(word, features=None, force=False):
    return _rl_shape(word, features=features or _SHAPING_FEATURES, force=force)


ttfonts.shapeFragWord = _shape
rl_paragraph.shapeFragWord = _shape


@cache
def _fonts() -> None:
    pdfmetrics.registerFont(TTFont("Mukta", str(FONTS / "Mukta-Regular.ttf")))
    pdfmetrics.registerFont(TTFont("Mukta-SemiBold", str(FONTS / "Mukta-SemiBold.ttf")))


def _style(name: str, size: float, *, bold=False, color=INK, leading=None, **kw) -> ParagraphStyle:
    return ParagraphStyle(
        name,
        fontName="Mukta-SemiBold" if bold else "Mukta",
        fontSize=size,
        leading=leading or size * 1.55,  # Devanagari matras need the extra line height (§20)
        textColor=color,
        shaping=1,
        **kw,
    )


STYLES = {
    "brand": _style("brand", 18, bold=True, color=TEAL),
    "meta": _style("meta", 9, color=INK_2, alignment=TA_RIGHT),
    "h1": _style("h1", 21, bold=True, leading=27),
    "lede": _style("lede", 9.5, color=INK_2),
    "h2": _style("h2", 11.5, bold=True, color=TEAL, leading=16),
    "body": _style("body", 9),
    "small": _style("small", 8, color=INK_2),
    "cell": _style("cell", 8.5, leading=12.5),
    "cell_strong": _style("cell_strong", 8.5, bold=True, leading=12.5),
    "hero_label": _style("hero_label", 9, color=GOLD_SOFT),
    "hero_value": _style("hero_value", 19, bold=True, color=colors.white, leading=27),
    "hero_note": _style("hero_note", 8, color=GOLD_SOFT),
    # Option cards: the focused card is night with white type, the others are light.
    "tag": _style("tag", 7.5, bold=True, color=NIGHT),
    "card_kw": _style("card_kw", 17, bold=True, color=TEAL, leading=22),
    "card_kw_on": _style("card_kw_on", 17, bold=True, color=colors.white, leading=22),
    "card_label": _style("card_label", 8, color=INK_2, leading=12),
    "card_label_on": _style("card_label_on", 8, color=GOLD_SOFT, leading=12),
    "card_value": _style("card_value", 9.5, bold=True, alignment=TA_RIGHT, leading=12.5),
    "card_value_on": _style(
        "card_value_on", 9.5, bold=True, color=colors.white, alignment=TA_RIGHT, leading=12.5
    ),
    "card_foot": _style("card_foot", 7.5, color=INK_2, leading=11),
    "card_foot_on": _style("card_foot_on", 7.5, color=GOLD_SOFT, leading=11),
    "bar_label": _style("bar_label", 8.5, bold=True),
    "bar_label_on": _style("bar_label_on", 8.5, bold=True, color=colors.white),
    "step_no": _style("step_no", 10, bold=True, color=NIGHT, alignment=TA_CENTER),
    "step": _style("step", 8, color=INK, alignment=TA_CENTER, leading=12),
    "note": _style("note", 7.8, color=INK_2, leading=11.5),
}


def P(text: str, style: str = "body") -> Paragraph:
    return Paragraph(escape(text), STYLES[style])


def _kw(value: str) -> str:
    return f"{value} kW"


def _payback(option: dict[str, Any], t: dict[str, str]) -> str:
    pb = option["payback"]
    if pb["status"] == "ok":
        return t["payback_years"].format(years=pb["years"])
    if pb["status"] == "immediate":
        return t["payback_immediate"]
    return t["not_available"]


def _payback_short(option: dict[str, Any], t: dict[str, str]) -> str:
    """For the narrow cards; the hero and the ruler carry the "about" and "estimate"."""
    pb = option["payback"]
    if pb["status"] == "ok":
        return t["years_short"].format(years=pb["years"])
    return _payback(option, t)


def _savings(option: dict[str, Any], t: dict[str, str]) -> str:
    amount = option["savings"]["annual_savings"]
    return inr(amount) if amount is not None else t["not_available"]


def _group(n: str | int) -> str:
    return inr(n).replace("₹", "")


def _focus(view: QuoteView) -> dict[str, Any]:
    """The accepted size, else the suggested one."""
    wanted = view.selected_kw
    for option in view.options:
        if wanted is not None and Decimal(option["kw"]) == wanted:
            return option
    return next(o for o in view.options if o["recommended"])


def _place(c, para: Paragraph, x: float, y_top: float, width: float) -> float:
    """Draw a Paragraph with its top at y_top; returns its height."""
    _, h = para.wrap(width, 1000)
    para.drawOn(c, x, y_top - h)
    return h


def _rays(c, cx: float, cy: float, inner: float, outer: float, count: int) -> None:
    """The logo's ray fan, upper half only."""
    for i in range(count):
        a = math.pi * (i + 0.5) / count
        c.line(
            cx + inner * math.cos(a),
            cy + inner * math.sin(a),
            cx + outer * math.cos(a),
            cy + outer * math.sin(a),
        )


class Hero(Flowable):
    """Night panel with a gold sun rising in the corner, and the quote's three numbers."""

    def __init__(self, cells: Table, width: float):
        super().__init__()
        self.cells, self.width = cells, width

    def wrap(self, aw, ah):
        _, h = self.cells.wrap(self.width, ah)
        self.height = h
        return self.width, h

    def draw(self):
        c, w, h = self.canv, self.width, self.height
        c.saveState()
        path = c.beginPath()
        path.roundRect(0, 0, w, h, 10)
        c.clipPath(path, stroke=0, fill=0)
        c.setFillColor(NIGHT)
        c.rect(0, 0, w, h, stroke=0, fill=1)
        cx, cy = w - 14 * mm, -4 * mm
        c.setStrokeColor(GOLD)
        c.setLineCap(1)
        c.setLineWidth(1.6)
        c.setStrokeAlpha(0.22)
        _rays(c, cx, cy, 20 * mm, 44 * mm, 11)
        c.setStrokeAlpha(1)
        c.setFillColor(GOLD)
        c.setFillAlpha(0.14)
        c.circle(cx, cy, 18 * mm, stroke=0, fill=1)
        c.setFillAlpha(1)
        c.circle(cx, cy, 14 * mm, stroke=0, fill=1)
        c.restoreState()
        self.cells.drawOn(c, 0, 0)


class MoneyAtAGlance(Flowable):
    """The price split to scale (subsidy in gold, the homeowner's share in teal) and, when there
    is one, the payback point on a ruler of years. Both redraw snapshot numbers only."""

    BAR = 9 * mm
    RULER = 12 * mm

    def __init__(self, focus: dict[str, Any], t: dict[str, str], width: float):
        super().__init__()
        self.focus, self.t, self.width = focus, t, width
        pb = focus["payback"]
        self.years = Decimal(pb["years"]) if pb["status"] == "ok" and pb["years"] else None

    def wrap(self, aw, ah):
        self.height = self.BAR + (2 * mm + self.RULER if self.years is not None else 0)
        return self.width, self.height

    def draw(self):
        c, w, t, f = self.canv, self.width, self.t, self.focus
        gross = Decimal(f["gross"])
        subsidy = Decimal(f["subsidy"]["amount"])
        net = Decimal(f["net"])
        top = self.height

        # 1 · The price, split into who pays what.
        y = top - self.BAR
        share = float(subsidy / gross) if gross > 0 else 0.0
        split = w * share
        c.saveState()
        path = c.beginPath()
        path.roundRect(0, y, w, self.BAR, self.BAR / 2)
        c.clipPath(path, stroke=0, fill=0)
        c.setFillColor(GOLD)
        c.rect(0, y, split, self.BAR, stroke=0, fill=1)
        c.setFillColor(TEAL)
        c.rect(split, y, w - split, self.BAR, stroke=0, fill=1)
        c.restoreState()
        pad = 3 * mm
        if subsidy > 0:
            label = P(t["g_subsidy"].format(amount=inr(subsidy)), "bar_label")
            lw, lh = label.wrap(w, self.BAR)
            if lw and split > 46 * mm:
                label.drawOn(c, pad, y + (self.BAR - lh) / 2 + 0.6)
        you_style = ParagraphStyle("you_r", parent=STYLES["bar_label_on"], alignment=TA_RIGHT)
        you = Paragraph(escape(t["g_you"].format(amount=inr(net))), you_style)
        _, yh = you.wrap(w - split - 2 * pad, self.BAR)
        you.drawOn(c, split + pad, y + (self.BAR - yh) / 2 + 0.6)

        if self.years is None:
            return

        # 2 · Payback on a ruler of years, the point marked by a small sun.
        span = max(10, math.ceil(self.years) + 2)
        line_y = 5.5 * mm
        label_w = 74 * mm
        x0, x1 = label_w + 4 * mm, w - 6 * mm
        step = (x1 - x0) / span
        _place(c, P(t["g_payback"].format(years=self.years), "note"), 0, line_y + 3 * mm, label_w)
        c.setLineCap(1)
        c.setStrokeColor(TEAL_SOFT)
        c.setLineWidth(6)
        c.line(x0, line_y, x1, line_y)
        mark = x0 + step * float(self.years)
        c.setStrokeColor(TEAL)
        c.line(x0, line_y, mark, line_y)
        c.setFont("Mukta", 7)
        c.setFillColor(INK_2)
        for year in range(0, span + 1):
            x = x0 + step * year
            if year % 5 == 0 or year == span:
                c.drawCentredString(x, line_y - 4.2 * mm, str(year))
        c.setFillColor(GOLD)
        c.setStrokeColor(GOLD)
        c.setLineWidth(1)
        _rays(c, mark, line_y + 1.5, 3.6 * mm, 5.4 * mm, 7)
        c.circle(mark, line_y, 2.8 * mm, stroke=0, fill=1)
        c.setFillColor(colors.white)
        c.circle(mark, line_y, 1 * mm, stroke=0, fill=1)


class NextSteps(Flowable):
    """Numbered sun discs joined by a gold thread, the step under each (a real sequence)."""

    def __init__(self, steps: list[str], width: float):
        super().__init__()
        self.steps, self.width = steps, width
        self.col = width / len(steps)
        self.paras = [P(s, "step") for s in steps]

    def wrap(self, aw, ah):
        text_h = max(p.wrap(self.col - 4 * mm, ah)[1] for p in self.paras)
        self.height = 10 * mm + text_h
        return self.width, self.height

    def draw(self):
        c, col = self.canv, self.col
        disc_y = self.height - 4 * mm
        c.setStrokeColor(GOLD)
        c.setLineWidth(1.4)
        c.setDash(1.5, 3)
        c.line(col / 2, disc_y, self.width - col / 2, disc_y)
        c.setDash()
        for i, para in enumerate(self.paras):
            cx = col * i + col / 2
            c.setFillColor(GOLD_SOFT if i else GOLD)
            c.circle(cx, disc_y, 4 * mm, stroke=0, fill=1)
            number = P(str(i + 1), "step_no")
            _, nh = number.wrap(8 * mm, 8 * mm)
            number.drawOn(c, cx - 4 * mm, disc_y - nh / 2 + 0.8)
            _place(c, para, cx - (col - 4 * mm) / 2, disc_y - 6 * mm, col - 4 * mm)


def _brand() -> Table:
    """The HelioFlow mark beside the wordmark, as on the website."""
    mark = Image(str(BRAND / "helio-mark.png"), width=11 * mm, height=11 * mm)
    lockup = Table([[mark, P("HelioFlow", "brand")]], colWidths=[13 * mm, None])
    lockup.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 0),
            ]
        )
    )
    lockup.hAlign = "LEFT"
    return lockup


def _card(option: dict[str, Any], view: QuoteView, focus: dict[str, Any], t, width) -> Table:
    on = option is focus
    sfx = "_on" if on else ""
    tag = ""
    if view.selected_kw is not None and Decimal(option["kw"]) == view.selected_kw:
        tag = t["selected"]
    elif option["recommended"]:
        tag = t["recommended"]
    corner: Any = ""
    if tag:
        # Sized to its words (unshaped width, plus slack for Devanagari) so the pill hugs them.
        pill_w = pdfmetrics.stringWidth(tag, "Mukta-SemiBold", 7.5) * 1.1 + 14
        corner = Table([[P(tag, "tag")]], colWidths=[pill_w])
        corner.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, -1), GOLD if on else GOLD_SOFT),
                    ("ROUNDEDCORNERS", [6, 6, 6, 6]),
                    ("TOPPADDING", (0, 0), (-1, -1), 1),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 2.5),
                    ("LEFTPADDING", (0, 0), (-1, -1), 6),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                ]
            )
        )
        corner.hAlign = "RIGHT"
    rows: list[list[Any]] = [
        [P(_kw(option["kw"]), f"card_kw{sfx}"), corner],
        [P(t["col_net"], f"card_label{sfx}"), P(inr(option["net"]), f"card_value{sfx}")],
        [P(t["card_savings"], f"card_label{sfx}"), P(_savings(option, t), f"card_value{sfx}")],
        [P(t["col_payback"], f"card_label{sfx}"), P(_payback_short(option, t), f"card_value{sfx}")],
        [
            P(
                f"{t['col_price']} {inr(option['gross'])} · "
                f"{t['col_subsidy']} − {inr(option['subsidy']['amount'])}",
                f"card_foot{sfx}",
            ),
            "",
        ],
    ]
    card = Table(rows, colWidths=[width * 0.58, width * 0.42])  # padding sits inside these
    card.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), NIGHT if on else SURFACE),
                ("ROUNDEDCORNERS", [8, 8, 8, 8]),
                ("SPAN", (0, -1), (-1, -1)),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                ("LEFTPADDING", (0, 0), (0, -1), 9),
                ("RIGHTPADDING", (-1, 0), (-1, -1), 9),
                ("TOPPADDING", (0, 0), (-1, -1), 1.5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 1.5),
                ("TOPPADDING", (0, 0), (-1, 0), 7),
                ("BOTTOMPADDING", (0, 0), (-1, 0), 3),
                ("LINEBELOW", (0, 1), (-1, -3), 0.4, colors.HexColor("#1F4A46") if on else LINE),
                ("TOPPADDING", (0, -1), (-1, -1), 4),
                ("BOTTOMPADDING", (0, -1), (-1, -1), 7),
            ]
        )
    )
    return card


def _section(title: str) -> list[Any]:
    return [P(title, "h2"), Spacer(1, 1.5 * mm)]


def render_quote_pdf(view: QuoteView, locale: Locale) -> bytes:
    _fonts()
    t = STRINGS[locale]
    focus = _focus(view)
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=16 * mm,
        rightMargin=16 * mm,
        topMargin=10 * mm,
        bottomMargin=9 * mm,
        title=f"HelioFlow {view.number}",
        author="HelioFlow",
    )
    width = doc.width - 12  # the frame keeps 6 pt padding on each side
    story: list[Any] = []

    header = Table(
        [
            [
                _brand(),
                [
                    P(t["quote_no"].format(number=view.number), "meta"),
                    P(t["dated"].format(date=view.priced_on.strftime("%d-%m-%Y")), "meta"),
                    P(t["lead"].format(code=view.lead_code), "meta"),
                ],
            ]
        ],
        colWidths=[width * 0.5, width * 0.5],
    )
    header.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (0, 0), 0),
                ("RIGHTPADDING", (-1, 0), (-1, 0), 0),
            ]
        )
    )
    story += [header, P(t["title"], "h1"), P(t["lede"], "lede"), Spacer(1, 3 * mm)]

    # The quote in three numbers: size → cost after subsidy → payback (estimate) (§20).
    cells = Table(
        [
            [
                P(t["size"], "hero_label"),
                P(t["net"], "hero_label"),
                P(t["payback"], "hero_label"),
                "",
            ],
            [
                P(_kw(focus["kw"]), "hero_value"),
                P(inr(focus["net"]), "hero_value"),
                P(_payback(focus, t), "hero_value"),
                "",
            ],
            [
                P(t["yearly"].format(amount=_savings(focus, t)), "hero_note"),
                P(t["after"].format(amount=inr(focus["subsidy"]["amount"])), "hero_note"),
                P(t["estimate"], "hero_note"),
                "",
            ],
        ],
        # The last fifth is left to the sun.
        colWidths=[width * 0.22, width * 0.27, width * 0.33, width * 0.18],
    )
    cells.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 12),
                ("TOPPADDING", (0, 0), (-1, -1), 0),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
                ("TOPPADDING", (0, 0), (-1, 0), 11),
                ("BOTTOMPADDING", (0, -1), (-1, -1), 12),
            ]
        )
    )
    story += [Hero(cells, width), Spacer(1, 3.5 * mm)]

    # The options as cards; the accepted (else suggested) one stands out.
    gap = 4 * mm
    n = len(view.options)
    card_w = (width - gap * (n - 1)) / n
    cards = Table(
        [[_card(o, view, focus, t, card_w) for o in view.options]],
        colWidths=[card_w + (gap if i < n - 1 else 0) for i in range(n)],
    )
    cards.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-2, -1), gap),
                ("TOPPADDING", (0, 0), (-1, -1), 0),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
            ]
        )
    )
    story += [*_section(t["options"]), cards, Spacer(1, 3.5 * mm)]

    story += [
        *_section(t["glance"].format(kw=_kw(focus["kw"]))),
        Spacer(1, 1 * mm),
        MoneyAtAGlance(focus, t, width),
        Spacer(1, 3.5 * mm),
    ]

    # The working (left) beside what it assumes (right).
    sv = focus["savings"]
    source = {"bill": "src_bill", "default": "src_default", "override": "src_override"}[
        sv["fixed_charge_source"]
    ]
    pct = (Decimal(sv["usable_generation_pct"]) * 100).normalize()
    rate = sv["savings_rate"]
    lines = [
        (t["b_price"], inr(focus["gross"])),
        (t["b_subsidy"], f"− {inr(focus['subsidy']['amount'])}"),
        (t["b_net"], inr(focus["net"])),
        (t["b_generation"], t["units_year"].format(units=_group(sv["annual_generation"]))),
        (
            t["b_usable"].format(pct=format(pct, "f")),
            t["units_year"].format(units=_group(Decimal(sv["usable_generation"]))),
        ),
        (
            t["b_rate"],
            t["per_unit"].format(rate=f"₹{Decimal(rate).quantize(Decimal('0.01'))}")
            if rate
            else t["not_available"],
        ),
        (t["b_fixed"].format(source=t[source]), inr(sv["fixed_charge"])),
        (t["b_savings"], _savings(focus, t)),
    ]
    left_w = width * 0.56
    right_w = width - left_w - 6 * mm
    breakdown = Table(
        [[P(k, "cell"), P(v, "cell_strong")] for k, v in lines],
        colWidths=[left_w * 0.66, left_w * 0.34],
    )
    breakdown.setStyle(
        TableStyle(
            [
                ("LINEBELOW", (0, 0), (-1, -2), 0.5, LINE),
                ("LINEABOVE", (0, -1), (-1, -1), 1, TEAL),
                ("BACKGROUND", (0, -1), (-1, -1), TEAL_SOFT),
                ("BACKGROUND", (0, 2), (-1, 2), SURFACE),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("LEFTPADDING", (0, 0), (0, -1), 0),
                ("LEFTPADDING", (0, -1), (0, -1), 4),
                ("TOPPADDING", (0, 0), (-1, -1), 1.5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 2.5),
            ]
        )
    )
    # The usable share is the one this quote used (it may be a sales override), never a fixed 90%.
    notes: list[Any] = [
        P("• " + t[k].format(pct=format(pct, "f")), "note") for k in ASSUMPTION_KEYS
    ]
    rule = view.subsidy_rule
    if rule:
        notes += [
            Spacer(1, 1.5 * mm),
            P(
                t["subsidy_rule"].format(
                    scheme=rule["scheme_code"],
                    start=rule["effective_from"],
                    note=rule["source_note"],
                ),
                "small",
            ),
        ]
    working = Table(
        [
            [
                [*_section(t["breakdown"].format(kw=_kw(focus["kw"]))), breakdown],
                [*_section(t["assumptions"]), *notes],
            ]
        ],
        colWidths=[left_w + 6 * mm, right_w],
    )
    working.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (0, 0), 6 * mm),
                ("RIGHTPADDING", (1, 0), (1, 0), 0),
                ("TOPPADDING", (0, 0), (-1, -1), 0),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
            ]
        )
    )
    story += [working, Spacer(1, 3.5 * mm)]

    story += [*_section(t["next"]), Spacer(1, 1 * mm)]
    story += [NextSteps([t[k] for k in NEXT_KEYS], width), Spacer(1, 3.5 * mm)]

    # The caveat, set apart with the brand's gold rule.
    caveat = Table([[[P(t["disclaimer"], "cell_strong"), P(t["footer"], "small")]]])
    caveat.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#FDF6E6")),
                ("LINEBEFORE", (0, 0), (0, -1), 3, GOLD),
                ("LEFTPADDING", (0, 0), (-1, -1), 10),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ]
        )
    )
    story += [caveat]

    doc.build(story, onFirstPage=_page_edge)
    return buffer.getvalue()


def _page_edge(c, doc) -> None:
    """A thin teal-and-gold band along the top edge of the page."""
    w, h = A4
    c.saveState()
    c.setFillColor(TEAL)
    c.rect(0, h - 3 * mm, w, 3 * mm, stroke=0, fill=1)
    c.setFillColor(GOLD)
    c.rect(0, h - 4 * mm, w, 1 * mm, stroke=0, fill=1)
    c.restoreState()
