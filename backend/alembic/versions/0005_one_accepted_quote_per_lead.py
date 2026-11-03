"""At most one accepted quote per lead, enforced by the database (the staff inbox joins it).

Revision ID: 0005
Revises: 0004
Create Date: 2026-11-03
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0005"
down_revision: str | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_index(
        "uq_quotes_one_accepted_per_lead",
        "quotes",
        ["lead_id"],
        unique=True,
        postgresql_where=sa.text("status = 'accepted'"),
    )


def downgrade() -> None:
    op.drop_index("uq_quotes_one_accepted_per_lead", table_name="quotes")
