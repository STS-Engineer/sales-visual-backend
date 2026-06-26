import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from fastapi import APIRouter, Depends

from app.core.auth import require_admin
from app.db.session import get_db_session
from app.models.client import Client
from app.models.monthly_report import MonthlyReport
from app.models.user import User
from app.services.email_service import notification_subject, send_kam_notification

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/test", tags=["test"])


@router.post("/email/{client_id}")
async def test_email(
    client_id: int,
    session: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(require_admin),
):
    try:
        client_result = await session.execute(
            select(Client)
            .options(selectinload(Client.kams))
            .where(Client.id == client_id)
        )
        client = client_result.scalar_one_or_none()
        if client is None:
            return {
                "success": False,
                "error": "Client not found",
                "mailtrap_test": True,
            }

        report_result = await session.execute(
            select(MonthlyReport)
            .where(MonthlyReport.client_id == client.id)
            .order_by(
                MonthlyReport.report_year.desc(),
                MonthlyReport.report_month.desc(),
                MonthlyReport.id.desc(),
            )
            .limit(1)
        )
        report = report_result.scalar_one_or_none()
        if report is None:
            return {
                "success": False,
                "error": "No reports found for client",
                "mailtrap_test": True,
            }

        result = await send_kam_notification(report, client)
        return result
    except Exception as exc:
        logger.exception("Mailtrap test email failed")
        return {
            "success": False,
            "recipient": None,
            "subject": None,
            "mailtrap_test": True,
            "error": str(exc),
        }
