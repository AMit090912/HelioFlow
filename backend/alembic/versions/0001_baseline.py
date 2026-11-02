"""baseline

Revision ID: 0001
Revises: 
Create Date: 2026-11-02 22:15:38.760348
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = '0001'
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


ENUM_TYPES = [
    "user_role", "locale", "ownership", "property_type", "roof_type", "lead_status",
    "lead_score", "next_action", "roof_verified_via", "subsidy_segment", "bill_kind",
    "quote_status", "reading_status", "reading_source", "project_stage",
    "notification_type", "notification_channel",
]

# Overlapping effective dates for the same rule scope are rejected by the database (§3.5, §3.6).
PRICE_RULES_NO_OVERLAP = """
ALTER TABLE price_rules ADD CONSTRAINT ex_price_rules_no_overlap EXCLUDE USING gist (
    numrange(min_kw, max_kw, '[]') WITH &&,
    daterange(effective_from, coalesce(effective_to, 'infinity'::date), '[]') WITH &&
)
"""

SUBSIDY_RULES_NO_OVERLAP = """
ALTER TABLE subsidy_rules ADD CONSTRAINT ex_subsidy_rules_no_overlap EXCLUDE USING gist (
    scheme_code WITH =,
    segment WITH =,
    daterange(effective_from, coalesce(effective_to, 'infinity'::date), '[]') WITH &&
)
"""

# Quote snapshot and identity are immutable; lifecycle fields change once, via allowed
# transitions only (§3.8). Holds even if application code is wrong or SQL is run by hand.
QUOTES_GUARD = """
CREATE OR REPLACE FUNCTION quotes_guard() RETURNS trigger AS $$
BEGIN
    IF NEW.number IS DISTINCT FROM OLD.number
       OR NEW.lead_id IS DISTINCT FROM OLD.lead_id
       OR NEW.priced_on IS DISTINCT FROM OLD.priced_on
       OR NEW.snapshot IS DISTINCT FROM OLD.snapshot
       OR NEW.calc_version IS DISTINCT FROM OLD.calc_version
       OR NEW.created_by IS DISTINCT FROM OLD.created_by
       OR NEW.sent_at IS DISTINCT FROM OLD.sent_at
       OR NEW.created_at IS DISTINCT FROM OLD.created_at
       OR NEW.id IS DISTINCT FROM OLD.id THEN
        RAISE EXCEPTION 'QUOTE_IMMUTABLE';
    END IF;

    IF (OLD.selected_kw IS NOT NULL AND NEW.selected_kw IS DISTINCT FROM OLD.selected_kw)
       OR (OLD.accepted_at IS NOT NULL AND NEW.accepted_at IS DISTINCT FROM OLD.accepted_at)
       OR (OLD.accepted_by IS NOT NULL AND NEW.accepted_by IS DISTINCT FROM OLD.accepted_by)
       OR (OLD.superseded_at IS NOT NULL AND NEW.superseded_at IS DISTINCT FROM OLD.superseded_at)
       OR (OLD.superseded_by_quote_id IS NOT NULL
           AND NEW.superseded_by_quote_id IS DISTINCT FROM OLD.superseded_by_quote_id) THEN
        RAISE EXCEPTION 'QUOTE_FIELD_ALREADY_SET';
    END IF;

    IF NEW.status IS DISTINCT FROM OLD.status THEN
        IF OLD.status = 'sent' AND NEW.status = 'accepted' THEN
            IF NEW.accepted_at IS NULL OR NEW.selected_kw IS NULL THEN
                RAISE EXCEPTION 'QUOTE_INVALID_TRANSITION';
            END IF;
        ELSIF OLD.status = 'sent' AND NEW.status = 'superseded' THEN
            IF NEW.superseded_at IS NULL THEN
                RAISE EXCEPTION 'QUOTE_INVALID_TRANSITION';
            END IF;
        ELSE
            RAISE EXCEPTION 'QUOTE_INVALID_TRANSITION';
        END IF;
    END IF;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER quotes_guard BEFORE UPDATE ON quotes
    FOR EACH ROW EXECUTE FUNCTION quotes_guard();
"""


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS citext")
    op.execute("CREATE EXTENSION IF NOT EXISTS btree_gist")

    op.create_table('users',
    sa.Column('role', sa.Enum('homeowner', 'sales', 'admin', name='user_role'), nullable=False),
    sa.Column('full_name', sa.Text(), nullable=False),
    sa.Column('email', postgresql.CITEXT(), nullable=True),
    sa.Column('phone', sa.Text(), nullable=True),
    sa.Column('password_hash', sa.Text(), nullable=False),
    sa.Column('preferred_locale', sa.Enum('en', 'hi', 'mr', name='locale'), server_default='en', nullable=False),
    sa.Column('is_active', sa.Boolean(), server_default='true', nullable=False),
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint("phone IS NULL OR phone ~ '^[6-9][0-9]{9}$'", name=op.f('ck_users_phone_format')),
    sa.CheckConstraint('email IS NOT NULL OR phone IS NOT NULL', name=op.f('ck_users_email_or_phone')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_users')),
    sa.UniqueConstraint('email', name=op.f('uq_users_email')),
    sa.UniqueConstraint('phone', name=op.f('uq_users_phone'))
    )
    op.create_table('leads',
    sa.Column('code', sa.Text(), nullable=False),
    sa.Column('homeowner_id', sa.UUID(), nullable=False),
    sa.Column('ownership', sa.Enum('owner', 'tenant', name='ownership'), nullable=False),
    sa.Column('property_type', sa.Enum('home', 'business', name='property_type'), nullable=False),
    sa.Column('roof_type', sa.Enum('rcc_flat', 'metal_sheet', 'tiled', 'other', name='roof_type'), nullable=False),
    sa.Column('roof_area_sqft', sa.Numeric(precision=8, scale=2), nullable=False),
    sa.Column('declared_monthly_bill', sa.Numeric(precision=12, scale=2), nullable=False),
    sa.Column('pincode', sa.CHAR(length=6), nullable=False),
    sa.Column('address', sa.Text(), nullable=True),
    sa.Column('consent_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('consent_version', sa.Text(), nullable=False),
    sa.Column('status', sa.Enum('draft', 'bill_processing', 'bill_review', 'qualified', 'survey_pending', 'call_pending', 'surveyed', 'quoted', 'accepted', 'converted', 'closed_lost', name='lead_status'), server_default='draft', nullable=False),
    sa.Column('score', sa.Enum('high', 'low', name='lead_score'), nullable=True),
    sa.Column('score_reasons', postgresql.JSONB(astext_type=sa.Text()), server_default='[]', nullable=False),
    sa.Column('recommended_kw', sa.Numeric(precision=5, scale=2), nullable=True),
    sa.Column('sizing_detail', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    sa.Column('next_action', sa.Enum('survey_visit', 'call', name='next_action'), nullable=True),
    sa.Column('verified_roof_area_sqft', sa.Numeric(precision=8, scale=2), nullable=True),
    sa.Column('roof_verified_via', sa.Enum('survey', 'call', name='roof_verified_via'), nullable=True),
    sa.Column('roof_verified_by', sa.UUID(), nullable=True),
    sa.Column('roof_verified_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('survey_notes', sa.Text(), nullable=True),
    sa.Column('surveyed_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('surveyed_by', sa.UUID(), nullable=True),
    sa.Column('current_bill_reading_id', sa.UUID(), nullable=True),
    sa.Column('seed_note', sa.Text(), nullable=True),
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint("pincode ~ '^[1-9][0-9]{5}$'", name=op.f('ck_leads_pincode_format')),
    sa.CheckConstraint('declared_monthly_bill > 0', name=op.f('ck_leads_bill_positive')),
    sa.CheckConstraint('roof_area_sqft > 0', name=op.f('ck_leads_roof_area_positive')),
    sa.CheckConstraint('verified_roof_area_sqft IS NULL OR verified_roof_area_sqft > 0', name=op.f('ck_leads_verified_roof_positive')),
    sa.ForeignKeyConstraint(['homeowner_id'], ['users.id'], name=op.f('fk_leads_homeowner_id_users')),
    sa.ForeignKeyConstraint(['roof_verified_by'], ['users.id'], name=op.f('fk_leads_roof_verified_by_users')),
    sa.ForeignKeyConstraint(['surveyed_by'], ['users.id'], name=op.f('fk_leads_surveyed_by_users')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_leads')),
    sa.UniqueConstraint('code', name=op.f('uq_leads_code'))
    )
    op.create_index(op.f('ix_leads_homeowner_id'), 'leads', ['homeowner_id'], unique=False)
    op.create_index('ix_leads_inbox', 'leads', ['status', 'score', sa.literal_column('created_at DESC')], unique=False)
    op.create_table('price_rules',
    sa.Column('min_kw', sa.Numeric(precision=5, scale=2), nullable=False),
    sa.Column('max_kw', sa.Numeric(precision=5, scale=2), nullable=False),
    sa.Column('price_per_kw', sa.Numeric(precision=12, scale=2), nullable=False),
    sa.Column('gst_inclusive', sa.Boolean(), nullable=False),
    sa.Column('effective_from', sa.Date(), nullable=False),
    sa.Column('effective_to', sa.Date(), nullable=True),
    sa.Column('note', sa.Text(), nullable=True),
    sa.Column('created_by', sa.UUID(), nullable=True),
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint('effective_to IS NULL OR effective_to >= effective_from', name=op.f('ck_price_rules_date_order')),
    sa.CheckConstraint('min_kw > 0 AND min_kw <= max_kw', name=op.f('ck_price_rules_kw_range')),
    sa.CheckConstraint('price_per_kw > 0', name=op.f('ck_price_rules_price_positive')),
    sa.ForeignKeyConstraint(['created_by'], ['users.id'], name=op.f('fk_price_rules_created_by_users')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_price_rules'))
    )
    op.create_table('settings',
    sa.Column('key', sa.Text(), nullable=False),
    sa.Column('value', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('updated_by', sa.UUID(), nullable=True),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['updated_by'], ['users.id'], name=op.f('fk_settings_updated_by_users')),
    sa.PrimaryKeyConstraint('key', name=op.f('pk_settings'))
    )
    op.create_table('subsidy_rules',
    sa.Column('scheme_code', sa.Text(), nullable=False),
    sa.Column('segment', sa.Enum('residential', name='subsidy_segment'), nullable=False),
    sa.Column('slabs', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('cap_amount', sa.Numeric(precision=12, scale=2), nullable=False),
    sa.Column('effective_from', sa.Date(), nullable=False),
    sa.Column('effective_to', sa.Date(), nullable=True),
    sa.Column('source_note', sa.Text(), nullable=False),
    sa.Column('created_by', sa.UUID(), nullable=True),
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint('cap_amount >= 0', name=op.f('ck_subsidy_rules_cap_non_negative')),
    sa.CheckConstraint('effective_to IS NULL OR effective_to >= effective_from', name=op.f('ck_subsidy_rules_date_order')),
    sa.ForeignKeyConstraint(['created_by'], ['users.id'], name=op.f('fk_subsidy_rules_created_by_users')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_subsidy_rules'))
    )
    op.create_table('bill_files',
    sa.Column('lead_id', sa.UUID(), nullable=False),
    sa.Column('kind', sa.Enum('image', 'pdf', name='bill_kind'), nullable=False),
    sa.Column('mime', sa.Text(), nullable=False),
    sa.Column('size_bytes', sa.Integer(), nullable=False),
    sa.Column('sha256', sa.CHAR(length=64), nullable=False),
    sa.Column('page_count', sa.Integer(), nullable=True),
    sa.Column('content', sa.LargeBinary(), nullable=False),
    sa.Column('preview_png', sa.LargeBinary(), nullable=True),
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['lead_id'], ['leads.id'], name=op.f('fk_bill_files_lead_id_leads')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_bill_files'))
    )
    op.create_index('ix_bill_files_lead_sha', 'bill_files', ['lead_id', 'sha256'], unique=False)
    op.create_table('quotes',
    sa.Column('number', sa.Text(), nullable=False),
    sa.Column('lead_id', sa.UUID(), nullable=False),
    sa.Column('priced_on', sa.Date(), nullable=False),
    sa.Column('snapshot', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('calc_version', sa.Text(), nullable=False),
    sa.Column('created_by', sa.UUID(), nullable=False),
    sa.Column('sent_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('status', sa.Enum('sent', 'accepted', 'superseded', name='quote_status'), server_default='sent', nullable=False),
    sa.Column('selected_kw', sa.Numeric(precision=5, scale=2), nullable=True),
    sa.Column('accepted_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('accepted_by', sa.UUID(), nullable=True),
    sa.Column('superseded_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('superseded_by_quote_id', sa.UUID(), nullable=True),
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint("(status = 'accepted') = (accepted_at IS NOT NULL AND accepted_by IS NOT NULL AND selected_kw IS NOT NULL)", name=op.f('ck_quotes_accepted_fields_match_status')),
    sa.CheckConstraint("(status = 'superseded') = (superseded_at IS NOT NULL)", name=op.f('ck_quotes_superseded_fields_match_status')),
    sa.ForeignKeyConstraint(['accepted_by'], ['users.id'], name=op.f('fk_quotes_accepted_by_users')),
    sa.ForeignKeyConstraint(['created_by'], ['users.id'], name=op.f('fk_quotes_created_by_users')),
    sa.ForeignKeyConstraint(['lead_id'], ['leads.id'], name=op.f('fk_quotes_lead_id_leads')),
    sa.ForeignKeyConstraint(['superseded_by_quote_id'], ['quotes.id'], name=op.f('fk_quotes_superseded_by_quote_id_quotes')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_quotes')),
    sa.UniqueConstraint('number', name=op.f('uq_quotes_number'))
    )
    op.create_index(op.f('ix_quotes_lead_id'), 'quotes', ['lead_id'], unique=False)
    op.create_index('uq_quotes_one_open_per_lead', 'quotes', ['lead_id'], unique=True, postgresql_where=sa.text("status = 'sent'"))
    op.create_table('bill_readings',
    sa.Column('lead_id', sa.UUID(), nullable=False),
    sa.Column('bill_file_id', sa.UUID(), nullable=False),
    sa.Column('status', sa.Enum('processing', 'needs_reupload', 'needs_review', 'confirmed', 'failed_manual', name='reading_status'), server_default='processing', nullable=False),
    sa.Column('quality', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    sa.Column('source_path', sa.Enum('pdf_text', 'vision', 'manual', name='reading_source'), nullable=True),
    sa.Column('attempts', postgresql.JSONB(astext_type=sa.Text()), server_default='[]', nullable=False),
    sa.Column('provider', sa.Text(), nullable=True),
    sa.Column('model', sa.Text(), nullable=True),
    sa.Column('prompt_version', sa.Text(), nullable=True),
    sa.Column('ai_values', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    sa.Column('validation_flags', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    sa.Column('consumer_number', sa.Text(), nullable=True),
    sa.Column('tariff_category', sa.Text(), nullable=True),
    sa.Column('sanctioned_load_kw', sa.Numeric(precision=6, scale=2), nullable=True),
    sa.Column('monthly_units', postgresql.ARRAY(sa.Integer()), nullable=True),
    sa.Column('avg_monthly_units', sa.Numeric(precision=8, scale=2), nullable=True),
    sa.Column('bill_amount', sa.Numeric(precision=12, scale=2), nullable=True),
    sa.Column('fixed_charge_monthly', sa.Numeric(precision=10, scale=2), nullable=True),
    sa.Column('edited_fields', postgresql.ARRAY(sa.Text()), nullable=True),
    sa.Column('confirmed_by', sa.UUID(), nullable=True),
    sa.Column('confirmed_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['bill_file_id'], ['bill_files.id'], name=op.f('fk_bill_readings_bill_file_id_bill_files')),
    sa.ForeignKeyConstraint(['confirmed_by'], ['users.id'], name=op.f('fk_bill_readings_confirmed_by_users')),
    sa.ForeignKeyConstraint(['lead_id'], ['leads.id'], name=op.f('fk_bill_readings_lead_id_leads')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_bill_readings')),
    sa.UniqueConstraint('bill_file_id', name=op.f('uq_bill_readings_bill_file_id'))
    )
    op.create_index(op.f('ix_bill_readings_lead_id'), 'bill_readings', ['lead_id'], unique=False)
    op.create_table('projects',
    sa.Column('lead_id', sa.UUID(), nullable=False),
    sa.Column('quote_id', sa.UUID(), nullable=False),
    sa.Column('stage', sa.Enum('advance_received', 'installation_scheduled', 'installation_completed', 'net_metering_completed', 'subsidy_applied', 'subsidy_credited', name='project_stage'), server_default='advance_received', nullable=False),
    sa.Column('stage_changed_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('advance_amount', sa.Numeric(precision=12, scale=2), nullable=False),
    sa.Column('advance_reference', sa.Text(), nullable=False),
    sa.Column('status_token_hash', sa.CHAR(length=64), nullable=True),
    sa.Column('status_token_created_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('status_token_revoked_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['lead_id'], ['leads.id'], name=op.f('fk_projects_lead_id_leads')),
    sa.ForeignKeyConstraint(['quote_id'], ['quotes.id'], name=op.f('fk_projects_quote_id_quotes')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_projects')),
    sa.UniqueConstraint('lead_id', name=op.f('uq_projects_lead_id')),
    sa.UniqueConstraint('status_token_hash', name=op.f('uq_projects_status_token_hash'))
    )
    op.create_index('ix_projects_stage', 'projects', ['stage', 'stage_changed_at'], unique=False)
    op.create_table('notifications',
    sa.Column('lead_id', sa.UUID(), nullable=False),
    sa.Column('project_id', sa.UUID(), nullable=True),
    sa.Column('type', sa.Enum('quote_sent', 'stage_changed', 'status_link', name='notification_type'), nullable=False),
    sa.Column('channel', sa.Enum('whatsapp', 'sms', name='notification_channel'), nullable=False),
    sa.Column('locale', postgresql.ENUM('en', 'hi', 'mr', name='locale', create_type=False), nullable=False),
    sa.Column('recipient_masked', sa.Text(), nullable=False),
    sa.Column('message', sa.Text(), nullable=False),
    sa.Column('delivery_status', sa.Text(), server_default='simulated', nullable=False),
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint("delivery_status = 'simulated'", name=op.f('ck_notifications_simulated_only')),
    sa.ForeignKeyConstraint(['lead_id'], ['leads.id'], name=op.f('fk_notifications_lead_id_leads')),
    sa.ForeignKeyConstraint(['project_id'], ['projects.id'], name=op.f('fk_notifications_project_id_projects')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_notifications'))
    )
    op.create_index(op.f('ix_notifications_lead_id'), 'notifications', ['lead_id'], unique=False)
    op.create_table('project_events',
    sa.Column('project_id', sa.UUID(), nullable=False),
    sa.Column('from_stage', postgresql.ENUM(name='project_stage', create_type=False), nullable=True),
    sa.Column('to_stage', postgresql.ENUM(name='project_stage', create_type=False), nullable=False),
    sa.Column('actor_id', sa.UUID(), nullable=True),
    sa.Column('note', sa.Text(), nullable=True),
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['actor_id'], ['users.id'], name=op.f('fk_project_events_actor_id_users')),
    sa.ForeignKeyConstraint(['project_id'], ['projects.id'], name=op.f('fk_project_events_project_id_projects')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_project_events'))
    )
    op.create_index(op.f('ix_project_events_project_id'), 'project_events', ['project_id'], unique=False)

    # leads ↔ bill_readings reference each other, so this FK is added last.
    op.create_foreign_key(
        'fk_leads_current_bill_reading', 'leads', 'bill_readings',
        ['current_bill_reading_id'], ['id'],
    )
    op.execute(PRICE_RULES_NO_OVERLAP)
    op.execute(SUBSIDY_RULES_NO_OVERLAP)
    op.execute(QUOTES_GUARD)


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS quotes_guard ON quotes")
    op.execute("DROP FUNCTION IF EXISTS quotes_guard()")
    op.drop_constraint('fk_leads_current_bill_reading', 'leads', type_='foreignkey')
    op.drop_index(op.f('ix_project_events_project_id'), table_name='project_events')
    op.drop_table('project_events')
    op.drop_index(op.f('ix_notifications_lead_id'), table_name='notifications')
    op.drop_table('notifications')
    op.drop_index('ix_projects_stage', table_name='projects')
    op.drop_table('projects')
    op.drop_index(op.f('ix_bill_readings_lead_id'), table_name='bill_readings')
    op.drop_table('bill_readings')
    op.drop_index('uq_quotes_one_open_per_lead', table_name='quotes', postgresql_where=sa.text("status = 'sent'"))
    op.drop_index(op.f('ix_quotes_lead_id'), table_name='quotes')
    op.drop_table('quotes')
    op.drop_index('ix_bill_files_lead_sha', table_name='bill_files')
    op.drop_table('bill_files')
    op.drop_table('subsidy_rules')
    op.drop_table('settings')
    op.drop_table('price_rules')
    op.drop_index('ix_leads_inbox', table_name='leads')
    op.drop_index(op.f('ix_leads_homeowner_id'), table_name='leads')
    op.drop_table('leads')
    op.drop_table('users')
    for name in ENUM_TYPES:
        op.execute(f"DROP TYPE IF EXISTS {name}")
