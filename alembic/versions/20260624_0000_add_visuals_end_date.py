"""add visuals end_date

Revision ID: 20260624_0000
Revises:
Create Date: 2026-06-24
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "20260624_0000"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("visuals", sa.Column("end_date", sa.Date(), nullable=True))


def downgrade() -> None:
    op.drop_column("visuals", "end_date")
