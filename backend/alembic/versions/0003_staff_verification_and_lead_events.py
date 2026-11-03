"""Staff verification of the sanctioned load, the lead audit trail and quote numbering.

Revision ID: 0003
Revises: 0002
Create Date: 2026-11-03
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

LEAD_STATUS = postgresql.ENUM(name="lead_status", create_type=False)


def upgrade() -> None:
    # A sanctioned load staff read from the DISCOM record when the bill didn't show it (§8).
    op.add_column("leads", sa.Column("verified_sanctioned_load_kw", sa.Numeric(5, 2)))
    op.add_column("leads", sa.Column("load_verified_by", sa.UUID(), nullable=True))
    op.add_column("leads", sa.Column("load_verified_at", sa.DateTime(timezone=True)))
    op.create_foreign_key(
        "fk_leads_load_verified_by_users", "leads", "users", ["load_verified_by"], ["id"]
    )
    op.create_check_constraint(
        "ck_leads_verified_load_range",
        "leads",
        "verified_sanctioned_load_kw IS NULL OR "
        "(verified_sanctioned_load_kw > 0 AND verified_sanctioned_load_kw <= 100)",
    )

    # Append-only audit of what staff (and the homeowner's acceptance) did to a lead.
    op.create_table(
        "lead_events",
        sa.Column("lead_id", sa.UUID(), sa.ForeignKey("leads.id"), nullable=False),
        sa.Column("kind", sa.Text(), nullable=False),
        sa.Column("from_status", LEAD_STATUS, nullable=True),
        sa.Column("to_status", LEAD_STATUS, nullable=True),
        sa.Column("actor_id", sa.UUID(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name="pk_lead_events"),
        sa.CheckConstraint(
            "kind IN ('verified','upgraded','closed','quote_sent','quote_accepted')",
            name="ck_lead_events_kind",
        ),
    )
    op.create_index("ix_lead_events_lead_id", "lead_events", ["lead_id"])

    # HF-Q-2026-000123: gap-tolerant, concurrency-safe numbering.
    op.execute("CREATE SEQUENCE quote_number_seq")


def downgrade() -> None:
    op.execute("DROP SEQUENCE quote_number_seq")
    op.drop_index("ix_lead_events_lead_id", table_name="lead_events")
    op.drop_table("lead_events")
    op.drop_constraint("ck_leads_verified_load_range", "leads", type_="check")
    op.drop_constraint("fk_leads_load_verified_by_users", "leads", type_="foreignkey")
    op.drop_column("leads", "load_verified_at")
    op.drop_column("leads", "load_verified_by")
    op.drop_column("leads", "verified_sanctioned_load_kw")
