"""create client documents table

Revision ID: 20260626_0004
Revises: 20260625_0003
Create Date: 2026-06-26
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "20260626_0004"
down_revision: str | None = "20260625_0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "client_documents",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("client_id", sa.Integer(), nullable=False),
        sa.Column("filename", sa.String(), nullable=False),
        sa.Column("blob_name", sa.String(), nullable=True),
        sa.Column("file_url", sa.Text(), nullable=True),
        sa.Column("file_size", sa.Integer(), nullable=True),
        sa.Column("uploaded_by", sa.String(), nullable=True),
        sa.Column(
            "uploaded_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("description", sa.String(), nullable=True),
        sa.ForeignKeyConstraint(["client_id"], ["clients.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_client_documents_id", "client_documents", ["id"])
    op.create_index(
        "ix_client_documents_client_id",
        "client_documents",
        ["client_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_client_documents_client_id", table_name="client_documents")
    op.drop_index("ix_client_documents_id", table_name="client_documents")
    op.drop_table("client_documents")
