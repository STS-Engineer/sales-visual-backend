from datetime import date, datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class MonthlyReport(Base):
    __tablename__ = "monthly_reports"
    __table_args__ = (
        UniqueConstraint(
            "client_id",
            "report_year",
            "report_month",
            name="uq_monthly_reports_client_period",
        ),
        CheckConstraint(
            "report_month >= 1 AND report_month <= 12",
            name="ck_monthly_reports_report_month",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    client_id: Mapped[int] = mapped_column(
        ForeignKey("clients.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    monday_item_id: Mapped[str | None] = mapped_column(String, nullable=True)
    report_year: Mapped[int] = mapped_column(Integer, nullable=False)
    report_month: Mapped[int] = mapped_column(Integer, nullable=False)
    statut: Mapped[str] = mapped_column(String, default="waiting", nullable=False)
    end_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    fichier_filename: Mapped[str | None] = mapped_column(String, nullable=True)
    fichier_path: Mapped[str | None] = mapped_column(String, nullable=True)
    fichier_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    marked_done_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    notification_sent: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    notification_sent_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    client = relationship("Client", back_populates="reports")
    notification_logs = relationship(
        "NotificationLog",
        back_populates="report",
        cascade="all, delete-orphan",
    )
