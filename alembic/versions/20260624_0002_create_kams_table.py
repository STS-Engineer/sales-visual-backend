"""create kams table

Revision ID: 20260624_0002
Revises: 20260624_0001
Create Date: 2026-06-24
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "20260624_0002"
down_revision: str | None = "20260624_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

KAM_ROWS = [
    ("Sales NIDEC", "Franck Lagadec", "franck.lagadec@avocarbon.com"),
    ("Sales Inteva", "Franck Lagadec", "franck.lagadec@avocarbon.com"),
    ("Sales DY", "Youngjin PARK", "youngjin.park@avocarbon.com"),
    ("Sales DY", "Ren Tao", "tao.ren@avocarbon.com"),
    ("Sales MAHLE", "Antoine Irthum", "antoine.irthum@avocarbon.com"),
    ("Sales Valeo", "Franck Lagadec", "franck.lagadec@avocarbon.com"),
    ("Sales First Brand", "Dean Hayward", "dean.hayward@avocarbon.com"),
    ("Sales JE", "Austin YUAN", "austin.yuan@avocarbon.com"),
    ("Sales JE", "Ren Tao", "tao.ren@avocarbon.com"),
    ("Sales BOSCH", "Lionel Clodong", "lionel.clodong@avocarbon.com"),
    ("Sales Lucas", "Ramkumar Parthasarathi", "ramkumar.p@avocarbon.com"),
    ("Sales B&D", "Dean Hayward", "dean.hayward@avocarbon.com"),
]


def upgrade() -> None:
    op.create_table(
        "kams",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("client_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("email", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["client_id"], ["clients.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_kams_id", "kams", ["id"])
    op.create_index("ix_kams_client_id", "kams", ["client_id"])

    connection = op.get_bind()
    for client_name, kam_name, email in KAM_ROWS:
        connection.execute(
            sa.text(
                """
                INSERT INTO kams (client_id, name, email)
                SELECT id, :kam_name, :email
                FROM clients
                WHERE name = :client_name
                """
            ),
            {
                "client_name": client_name,
                "kam_name": kam_name,
                "email": email,
            },
        )

    op.drop_column("clients", "kam_email")
    op.drop_column("clients", "kam_name")


def downgrade() -> None:
    op.add_column("clients", sa.Column("kam_name", sa.String(), nullable=True))
    op.add_column("clients", sa.Column("kam_email", sa.String(), nullable=True))

    connection = op.get_bind()
    connection.execute(
        sa.text(
            """
            UPDATE clients
            SET kam_name = first_kam.name,
                kam_email = first_kam.email
            FROM (
                SELECT DISTINCT ON (client_id) client_id, name, email
                FROM kams
                ORDER BY client_id, id
            ) AS first_kam
            WHERE clients.id = first_kam.client_id
            """
        )
    )

    op.drop_index("ix_kams_client_id", table_name="kams")
    op.drop_index("ix_kams_id", table_name="kams")
    op.drop_table("kams")
