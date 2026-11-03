"""Quote PDF in en/hi/mr, rendered from the snapshot (§11, Q-14)."""

import io
from datetime import date, timedelta
from decimal import Decimal

import pytest
from pypdf import PdfReader
from sqlalchemy import select

from app.models import PriceRule
from tests.integration.test_bills_api import CSRF, sign_in
from tests.integration.test_quotes_api import (  # noqa: F401  (fixtures)
    OWNER,
    ai,
    lead,
    send,
    verify,
)


def text_of(pdf: bytes) -> str:
    return "".join(page.extract_text() for page in PdfReader(io.BytesIO(pdf)).pages)


@pytest.mark.parametrize("lang", ["en", "hi", "mr"])
def test_pdf_renders_in_each_language(client, lead, lang):  # noqa: F811
    verify(client, lead)
    quote = send(client, lead).json()
    res = client.get(f"/api/quotes/{quote['id']}/pdf?lang={lang}")
    assert res.status_code == 200
    assert res.headers["content-type"] == "application/pdf"
    assert quote["number"] in res.headers["content-disposition"]
    assert res.content.startswith(b"%PDF")
    text = text_of(res.content)
    assert quote["number"] in text and "1,02,000" in text


def test_pdf_defaults_to_homeowner_language(client, lead):  # noqa: F811
    sign_in(client, OWNER)
    client.patch("/api/auth/me", headers=CSRF, json={"preferred_locale": "hi"})
    sign_in(client, "quote-desk@example.com")
    verify(client, lead)
    quote = send(client, lead).json()
    sign_in(client, OWNER)
    res = client.get(f"/api/quotes/{quote['id']}/pdf")
    assert res.status_code == 200 and b"%PDF" in res.content[:8]
    assert client.get(f"/api/quotes/{quote['id']}/pdf?lang=fr").status_code == 422


def test_pdf_uses_snapshot_after_rule_change(client, lead, db_session):  # noqa: F811
    verify(client, lead)
    quote = send(client, lead).json()
    rule = db_session.execute(select(PriceRule)).scalars().one()
    rule.effective_to = date.today() - timedelta(days=1)
    db_session.flush()
    db_session.add(
        PriceRule(
            min_kw=Decimal("1"),
            max_kw=Decimal("10"),
            price_per_kw=Decimal("70000"),
            gst_inclusive=True,
            effective_from=date.today(),
        )
    )
    db_session.flush()
    text = text_of(client.get(f"/api/quotes/{quote['id']}/pdf?lang=en").content)
    assert "1,80,000" in text and "2,10,000" not in text


def test_foreign_pdf_is_404(client, lead):  # noqa: F811
    from tests.integration.test_leads_api import signup

    verify(client, lead)
    quote_id = send(client, lead).json()["id"]
    signup(client, "pdf-stranger@example.com")
    assert client.get(f"/api/quotes/{quote_id}/pdf").status_code == 404


def test_pdf_assumptions_use_the_quotes_own_usable_share(client, lead):  # noqa: F811
    verify(client, lead)
    override = {"field": "usable_generation_pct", "value": "0.8", "reason": "Shaded in winter"}
    quote = send(client, lead, [override]).json()
    text = text_of(client.get(f"/api/quotes/{quote['id']}/pdf?lang=en").content)
    assert "About 80% of the electricity" in text and "90%" not in text


def test_pdf_carries_the_logo(client, lead):  # noqa: F811
    verify(client, lead)
    quote = send(client, lead).json()
    pdf = PdfReader(io.BytesIO(client.get(f"/api/quotes/{quote['id']}/pdf?lang=hi").content))
    assert len(pdf.pages[0].images) >= 1  # the HelioFlow mark
