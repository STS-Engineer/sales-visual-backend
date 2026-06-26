from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from fastapi import APIRouter, Depends

from app.core.auth import require_admin
from app.db.session import get_db_session
from app.models.user import User
from app.models.client import Client
from app.models.monthly_report import MonthlyReport
from app.schemas.report import InitMonthRequest, InitMonthResponse

router = APIRouter(prefix="/admin", tags=["admin"])
reports_router = APIRouter(prefix="/reports", tags=["admin"])


@router.post("/init-month", response_model=InitMonthResponse)
@reports_router.post("/init", response_model=InitMonthResponse)
async def init_month(
    payload: InitMonthRequest,
    session: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(require_admin),
):
    result = await session.execute(
        select(Client)
        .where(Client.is_active.is_(True))
        .order_by(Client.name)
    )
    clients = result.scalars().all()

    created = 0
    skipped = 0

    for client in clients:
        existing = await session.execute(
            select(MonthlyReport).where(
                MonthlyReport.client_id == client.id,
                MonthlyReport.report_year == payload.year,
                MonthlyReport.report_month == payload.month,
            )
        )
        if existing.scalar_one_or_none() is not None:
            skipped += 1
            continue

        session.add(
            MonthlyReport(
                client_id=client.id,
                report_year=payload.year,
                report_month=payload.month,
                statut="waiting",
                notification_sent=False,
            )
        )
        created += 1

    await session.commit()
    return InitMonthResponse(created=created, skipped=skipped)
