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


STAGE_NAMES = {
    "en": {
        "advance_received": "Advance received",
        "installation_scheduled": "Installation scheduled",
        "installation_completed": "Installation completed",
        "net_metering_completed": "Net metering completed",
        "subsidy_applied": "Subsidy application submitted",
        "subsidy_credited": "Subsidy credited",
    },
    "hi": {
        "advance_received": "अग्रिम राशि मिली",
        "installation_scheduled": "इंस्टॉलेशन तय हुआ",
        "installation_completed": "इंस्टॉलेशन पूरा हुआ",
        "net_metering_completed": "नेट मीटरिंग पूरी हुई",
        "subsidy_applied": "सब्सिडी आवेदन जमा हुआ",
        "subsidy_credited": "सब्सिडी खाते में आई",
    },
    "mr": {
        "advance_received": "आगाऊ रक्कम मिळाली",
        "installation_scheduled": "इन्स्टॉलेशन ठरले",
        "installation_completed": "इन्स्टॉलेशन पूर्ण झाले",
        "net_metering_completed": "नेट मीटरिंग पूर्ण झाले",
        "subsidy_applied": "अनुदान अर्ज सादर केला",
        "subsidy_credited": "अनुदान खात्यात जमा झाले",
    },
}

PROJECT_CREATED = {
    "en": "HelioFlow: we've received your advance for {code}. "
    "Follow your installation here: {link}",
    "hi": "HelioFlow: {code} के लिए आपकी अग्रिम राशि मिल गई है। अपने इंस्टॉलेशन की स्थिति यहाँ देखें: {link}",
    "mr": "HelioFlow: {code} साठी तुमची आगाऊ रक्कम मिळाली. तुमच्या इन्स्टॉलेशनची स्थिती इथे पाहा: {link}",
}

STAGE_CHANGED = {
    "en": 'HelioFlow: {code} has moved to "{stage}".',
    "hi": 'HelioFlow: {code} अब "{stage}" चरण पर है।',
    "mr": 'HelioFlow: {code} आता "{stage}" टप्प्यावर आहे.',
}

INSTALL_DATE = {
    "en": " Installation date: {date}.",
    "hi": " इंस्टॉलेशन की तारीख: {date}।",
    "mr": " इन्स्टॉलेशनची तारीख: {date}.",
}


def _outbox(db: Session, lead: Lead, project_id, kind: NotificationType, message: str) -> None:
    owner = db.get(User, lead.homeowner_id)
    channel, recipient = mask_recipient(owner)
    db.add(
        Notification(
            lead_id=lead.id,
            project_id=project_id,
            type=kind,
            channel=channel,
            locale=owner.preferred_locale,
            recipient_masked=recipient,
            message=message,
        )
    )


def project_created(db: Session, lead: Lead, project_id, frontend_origin: str) -> None:
    """The status link goes out with the project. The outbox is a table every staff member can
    read, so the stored text never contains the live token (decision D-1): staff copy the link
    once from the project panel."""
    locale = db.get(User, lead.homeowner_id).preferred_locale.value
    link = f"{frontend_origin.rstrip('/')}/{locale}/s/••••"
    message = PROJECT_CREATED[locale].format(code=lead.code, link=link)
    _outbox(db, lead, project_id, NotificationType.status_link, message)


def stage_changed(db: Session, lead: Lead, project_id, stage: str, scheduled_for=None) -> None:
    locale = db.get(User, lead.homeowner_id).preferred_locale.value
    message = STAGE_CHANGED[locale].format(code=lead.code, stage=STAGE_NAMES[locale][stage])
    if scheduled_for is not None:
        message += INSTALL_DATE[locale].format(date=scheduled_for.strftime("%d-%m-%Y"))
    _outbox(db, lead, project_id, NotificationType.stage_changed, message)
