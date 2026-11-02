"""One stored file per (lead, sha256): a double-submitted upload maps to a single reading.

Revision ID: 0002
Revises: 0001
Create Date: 2026-11-03
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_index("ix_bill_files_lead_sha", table_name="bill_files")
    op.create_index("uq_bill_files_lead_sha", "bill_files", ["lead_id", "sha256"], unique=True)
    # When the current AI read started (a re-upload after an outage starts a new one), so the
    # stale sweep measures the right thing.
    op.add_column(
        "bill_readings",
        sa.Column("processing_started_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("bill_readings", "processing_started_at")
    op.drop_index("uq_bill_files_lead_sha", table_name="bill_files")
    op.create_index("ix_bill_files_lead_sha", "bill_files", ["lead_id", "sha256"], unique=False)
