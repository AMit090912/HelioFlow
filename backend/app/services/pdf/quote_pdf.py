"""Quote PDF, rendered from the immutable snapshot on demand (§11), in en / hi / mr (Q-14).

Devanagari needs HarfBuzz shaping (uharfbuzz). In ReportLab only Platypus Paragraphs with
`shaping=1` shape correctly (the 2026-11-03 spike: canvas.drawString(shaping=True) still breaks
conjuncts), so every piece of text here is a Paragraph, including table cells.
"""

import io
from decimal import Decimal
from functools import cache
from pathlib import Path
from typing import Any, Literal
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics, ttfonts
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Image, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
from reportlab.platypus import paragraph as rl_paragraph

from app.schemas.quotes import QuoteView
from app.services.notify import inr
from app.services.pdf.strings import ASSUMPTION_KEYS, STRINGS

FONTS = Path(__file__).resolve().parents[2] / "assets" / "fonts"
BRAND = Path(__file__).resolve().parents[2] / "assets" / "brand"
TEAL = colors.HexColor("#006863")
NIGHT = colors.HexColor("#012E2B")
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
    "h1": _style("h1", 20, bold=True),
    "h2": _style("h2", 13, bold=True, leading=20),
    "body": _style("body", 9.5),
    "small": _style("small", 8.5, color=INK_2),
    "cell": _style("cell", 9),
    "cell_head": _style("cell_head", 8.5, bold=True, color=colors.white),
    "cell_strong": _style("cell_strong", 9, bold=True),
    "hero_label": _style("hero_label", 9, color=GOLD_SOFT),
    "hero_value": _style("hero_value", 20, bold=True, color=colors.white, leading=28),
    "hero_note": _style("hero_note", 8, color=GOLD_SOFT),
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


def render_quote_pdf(view: QuoteView, locale: Locale) -> bytes:
    _fonts()
    t = STRINGS[locale]
    focus = _focus(view)
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=18 * mm,
        rightMargin=18 * mm,
        topMargin=12 * mm,
        bottomMargin=12 * mm,
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
        TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (0, 0), 0)])
    )
    story += [header, Spacer(1, 1 * mm), P(t["title"], "h1"), Spacer(1, 3 * mm)]

    # The quote in three numbers: size → cost after subsidy → payback (estimate) (§20).
    hero = Table(
        [
            [P(t["size"], "hero_label"), P(t["net"], "hero_label"), P(t["payback"], "hero_label")],
            [
                P(_kw(focus["kw"]), "hero_value"),
                P(inr(focus["net"]), "hero_value"),
                P(_payback(focus, t), "hero_value"),
            ],
            [P("", "hero_note"), P("", "hero_note"), P(t["estimate"], "hero_note")],
        ],
        colWidths=[width / 3] * 3,
    )
    hero.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), NIGHT),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 10),
                ("TOPPADDING", (0, 0), (-1, 0), 10),
                ("BOTTOMPADDING", (0, -1), (-1, -1), 10),
            ]
        )
    )
    story += [hero, Spacer(1, 4 * mm), P(t["options"], "h2"), Spacer(1, 2 * mm)]

    rows = [
        [
            P(t[k], "cell_head")
            for k in (
                "col_size",
                "col_price",
                "col_subsidy",
                "col_net",
                "col_savings",
                "col_payback",
            )
        ]
    ]
    for option in view.options:
        tag = ""
        if view.selected_kw is not None and Decimal(option["kw"]) == view.selected_kw:
            tag = f" · {t['selected']}"
        elif option["recommended"]:
            tag = f" · {t['recommended']}"
        strong = "cell_strong" if option is focus else "cell"
        rows.append(
            [
                P(_kw(option["kw"]) + tag, strong),
                P(inr(option["gross"]), strong),
                P(inr(option["subsidy"]["amount"]), strong),
                P(inr(option["net"]), strong),
                P(_savings(option, t), strong),
                P(_payback(option, t), strong),
            ]
        )
    table = Table(rows, colWidths=[width * w for w in (0.2, 0.15, 0.14, 0.17, 0.18, 0.16)])
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), TEAL),
                ("LINEBELOW", (0, 1), (-1, -1), 0.5, LINE),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ]
        )
    )
    story += [table, Spacer(1, 4 * mm)]

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
    breakdown = Table(
        [[P(k, "cell"), P(v, "cell_strong")] for k, v in lines],
        colWidths=[width * 0.65, width * 0.35],
    )
    breakdown.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), SURFACE),
                ("LINEBELOW", (0, 0), (-1, -2), 0.5, LINE),
                ("TOPPADDING", (0, 0), (-1, -1), 2),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
            ]
        )
    )
    story += [
        P(t["breakdown"].format(kw=_kw(focus["kw"])), "h2"),
        Spacer(1, 2 * mm),
        breakdown,
        Spacer(1, 4 * mm),
        P(t["assumptions"], "h2"),
        Spacer(1, 1 * mm),
    ]
    # The usable share is the one this quote used (it may be a sales override), never a fixed 90%.
    story += [P("• " + t[k].format(pct=format(pct, "f")), "body") for k in ASSUMPTION_KEYS]
    rule = view.subsidy_rule
    if rule:
        story += [
            Spacer(1, 2 * mm),
            P(
                t["subsidy_rule"].format(
                    scheme=rule["scheme_code"],
                    start=rule["effective_from"],
                    note=rule["source_note"],
                ),
                "small",
            ),
        ]
    story += [
        Spacer(1, 5 * mm),
        P(t["disclaimer"], "h2"),
        Spacer(1, 2 * mm),
        P(t["footer"], "small"),
    ]

    doc.build(story)
    return buffer.getvalue()
