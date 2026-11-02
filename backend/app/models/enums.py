from enum import StrEnum


class UserRole(StrEnum):
    homeowner = "homeowner"
    sales = "sales"
    admin = "admin"


class Locale(StrEnum):
    en = "en"
    hi = "hi"
    mr = "mr"


class Ownership(StrEnum):
    owner = "owner"
    tenant = "tenant"


class PropertyType(StrEnum):
    home = "home"
    business = "business"


class RoofType(StrEnum):
    rcc_flat = "rcc_flat"
    metal_sheet = "metal_sheet"
    tiled = "tiled"
    other = "other"


class LeadStatus(StrEnum):
    draft = "draft"
    bill_processing = "bill_processing"
    bill_review = "bill_review"
    qualified = "qualified"
    survey_pending = "survey_pending"
    call_pending = "call_pending"
    surveyed = "surveyed"
    quoted = "quoted"
    accepted = "accepted"
    converted = "converted"
    closed_lost = "closed_lost"


class LeadScore(StrEnum):
    high = "high"
    low = "low"


class NextAction(StrEnum):
    survey_visit = "survey_visit"
    call = "call"


class RoofVerifiedVia(StrEnum):
    survey = "survey"
    call = "call"


class BillKind(StrEnum):
    image = "image"
    pdf = "pdf"


class ReadingStatus(StrEnum):
    processing = "processing"
    needs_reupload = "needs_reupload"
    needs_review = "needs_review"
    confirmed = "confirmed"
    failed_manual = "failed_manual"


class ReadingSource(StrEnum):
    pdf_text = "pdf_text"
    vision = "vision"
    manual = "manual"


class SubsidySegment(StrEnum):
    residential = "residential"


class QuoteStatus(StrEnum):
    sent = "sent"
    accepted = "accepted"
    superseded = "superseded"


class ProjectStage(StrEnum):
    advance_received = "advance_received"
    installation_scheduled = "installation_scheduled"
    installation_completed = "installation_completed"
    net_metering_completed = "net_metering_completed"
    subsidy_applied = "subsidy_applied"
    subsidy_credited = "subsidy_credited"


class NotificationType(StrEnum):
    quote_sent = "quote_sent"
    stage_changed = "stage_changed"
    status_link = "status_link"


class NotificationChannel(StrEnum):
    whatsapp = "whatsapp"
    sms = "sms"
