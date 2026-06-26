"""create client report tables

Revision ID: 20260624_0001
Revises: 20260624_0000
Create Date: 2026-06-24
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "20260624_0001"
down_revision: str | None = "20260624_0000"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "clients",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("power_bi_url", sa.Text(), nullable=True),
        sa.Column("power_bi_label", sa.String(), nullable=True),
        sa.Column("kam_name", sa.String(), nullable=True),
        sa.Column("kam_email", sa.String(), nullable=True),
        sa.Column("vp_sales_name", sa.String(), nullable=True),
        sa.Column("person_name", sa.String(), nullable=False, server_default="AH"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("name", name="uq_clients_name"),
    )
    op.create_index("ix_clients_id", "clients", ["id"])

    op.create_table(
        "monthly_reports",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("client_id", sa.Integer(), nullable=False),
        sa.Column("monday_item_id", sa.String(), nullable=True),
        sa.Column("report_year", sa.Integer(), nullable=False),
        sa.Column("report_month", sa.Integer(), nullable=False),
        sa.Column("statut", sa.String(), nullable=False, server_default="waiting"),
        sa.Column("end_date", sa.Date(), nullable=True),
        sa.Column("fichier_filename", sa.String(), nullable=True),
        sa.Column("fichier_path", sa.String(), nullable=True),
        sa.Column("fichier_url", sa.Text(), nullable=True),
        sa.Column("marked_done_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("notification_sent", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("notification_sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("report_month >= 1 AND report_month <= 12", name="ck_monthly_reports_report_month"),
        sa.ForeignKeyConstraint(["client_id"], ["clients.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("client_id", "report_year", "report_month", name="uq_monthly_reports_client_period"),
    )
    op.create_index("ix_monthly_reports_id", "monthly_reports", ["id"])
    op.create_index("ix_monthly_reports_client_id", "monthly_reports", ["client_id"])

    op.create_table(
        "notification_logs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("report_id", sa.Integer(), nullable=False),
        sa.Column("sent_to", sa.String(), nullable=False),
        sa.Column("sent_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("success", sa.Boolean(), nullable=False),
        sa.Column("error_msg", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["report_id"], ["monthly_reports.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_notification_logs_id", "notification_logs", ["id"])
    op.create_index("ix_notification_logs_report_id", "notification_logs", ["report_id"])


def downgrade() -> None:
    op.drop_index("ix_notification_logs_report_id", table_name="notification_logs")
    op.drop_index("ix_notification_logs_id", table_name="notification_logs")
    op.drop_table("notification_logs")

    op.drop_index("ix_monthly_reports_client_id", table_name="monthly_reports")
    op.drop_index("ix_monthly_reports_id", table_name="monthly_reports")
    op.drop_table("monthly_reports")

    op.drop_index("ix_clients_id", table_name="clients")
    op.drop_table("clients")
