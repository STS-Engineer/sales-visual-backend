from datetime import datetime

from sqlalchemy import Boolean, DateTime, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Client(Base):
    __tablename__ = "clients"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    power_bi_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    power_bi_label: Mapped[str | None] = mapped_column(String, nullable=True)
    vp_sales_name: Mapped[str | None] = mapped_column(String, nullable=True)
    person_name: Mapped[str] = mapped_column(String, default="AH", nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
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

    reports = relationship(
        "MonthlyReport",
        back_populates="client",
        cascade="all, delete-orphan",
    )
    kams = relationship(
        "Kam",
        back_populates="client",
        cascade="all, delete-orphan",
    )
    documents = relationship(
        "ClientDocument",
        back_populates="client",
        cascade="all, delete-orphan",
    )
