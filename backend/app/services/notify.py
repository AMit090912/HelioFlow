"""Simulated WhatsApp/SMS outbox (§13). Nothing leaves the server: rows are written with
`delivery_status = 'simulated'` in the homeowner's language, with a masked recipient."""

from decimal import Decimal

from sqlalchemy.orm import Session

from app.models import Lead, Notification, Quote, User
from app.models.enums import NotificationChannel, NotificationType

QUOTE_SENT = {
    "en": "HelioFlow: your solar quote {number} is ready. Suggested system {kw} kW, "
    "cost after subsidy {net}. Open My solar to see it.",
    "hi": "HelioFlow: आपका सोलर कोटेशन {number} तैयार है। सुझाया गया सिस्टम {kw} kW, "
    "सब्सिडी के बाद लागत {net}। इसे देखने के लिए 'मेरा सोलर' खोलें।",
    "mr": "HelioFlow: तुमचे सोलर कोटेशन {number} तयार आहे. सुचवलेला सिस्टम {kw} kW, "
    "अनुदानानंतर खर्च {net}. पाहण्यासाठी 'माझे सोलर' उघडा.",
}


def inr(amount: Decimal | str) -> str:
    """₹1,02,000: Indian digit grouping, Western digits, whole rupees (A-27)."""
    value = int(Decimal(str(amount)).quantize(Decimal("1")))
    sign, digits = ("-" if value < 0 else ""), str(abs(value))
    if len(digits) > 3:
        head, tail = digits[:-3], digits[-3:]
        groups = []
        while len(head) > 2:
            groups.insert(0, head[-2:])
            head = head[:-2]
        if head:
            groups.insert(0, head)
        digits = ",".join([*groups, tail])
    return f"{sign}₹{digits}"


def mask_recipient(user: User) -> tuple[NotificationChannel, str]:
    if user.phone:
        return NotificationChannel.whatsapp, f"+91 ••••• •{user.phone[-4:]}"
    local, _, domain = (user.email or "").partition("@")
    return NotificationChannel.sms, f"{local[:1]}•••@{domain}"


def quote_sent(db: Session, lead: Lead, quote: Quote) -> Notification:
    owner = db.get(User, lead.homeowner_id)
    locale = owner.preferred_locale.value
    recommended = next(o for o in quote.snapshot["options"] if o["recommended"])
    channel, recipient = mask_recipient(owner)
    note = Notification(
        lead_id=lead.id,
        type=NotificationType.quote_sent,
        channel=channel,
        locale=owner.preferred_locale,
        recipient_masked=recipient,
        message=QUOTE_SENT[locale].format(
            number=quote.number, kw=recommended["kw"], net=inr(recommended["net"])
        ),
    )
    db.add(note)
    return note
