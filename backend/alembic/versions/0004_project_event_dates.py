"""Installation date on the "installation scheduled" stage event (§12: optional date), and the
lead audit learns "converted" (advance recorded, project created).

Revision ID: 0004
Revises: 0003
Create Date: 2026-11-03
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0004"
down_revision: str | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


OLD_KINDS = "'verified','upgraded','closed','quote_sent','quote_accepted'"
NEW_KINDS = OLD_KINDS + ",'converted','link_regenerated','link_revoked'"


def upgrade() -> None:
    op.add_column("project_events", sa.Column("scheduled_for", sa.Date(), nullable=True))
    op.drop_constraint("ck_lead_events_kind", "lead_events", type_="check")
    op.create_check_constraint("ck_lead_events_kind", "lead_events", f"kind IN ({NEW_KINDS})")


def downgrade() -> None:
    op.drop_constraint("ck_lead_events_kind", "lead_events", type_="check")
    op.create_check_constraint("ck_lead_events_kind", "lead_events", f"kind IN ({OLD_KINDS})")
    op.drop_column("project_events", "scheduled_for")
