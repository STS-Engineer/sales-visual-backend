import os
import re
from datetime import datetime
from pathlib import Path
from urllib.parse import quote

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse, RedirectResponse

from app.core.auth import get_current_user, require_admin
from app.db.session import get_db_session
from app.models.client import Client
from app.models.monthly_report import MonthlyReport
from app.models.notification_log import NotificationLog
from app.models.user import User
from app.models.user_client import UserClient
from app.schemas.report import MarkDoneResponse, MonthlyReportResponse, ReportListItemResponse
from app.services.blob_service import delete_blob, upload_excel_to_blob
from app.services.email_service import send_kam_email

router = APIRouter(prefix="/reports", tags=["reports"])


def _report_item(report: MonthlyReport, client: Client) -> ReportListItemResponse:
    return ReportListItemResponse(
        id=report.id,
        client_name=client.name,
        person_name=client.person_name,
        power_bi_url=client.power_bi_url,
        power_bi_label=client.power_bi_label,
        statut=report.statut,
        end_date=report.end_date,
        report_year=report.report_year,
        report_month=report.report_month,
        fichier_filename=report.fichier_filename,
        fichier_url=report.fichier_url,
        notification_sent=report.notification_sent,
        kams=client.kams,
    )


def _safe_path_segment(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "_", value).strip("_") or "client"


def _filter_reports_for_user(query, current_user: User):
    if current_user.role == "admin":
        return query

    return query.where(
        MonthlyReport.client_id.in_(
            select(UserClient.client_id).where(UserClient.user_id == current_user.id)
        )
    )


@router.get("", response_model=list[ReportListItemResponse])
async def list_reports(
    year: int = Query(ge=2000, le=2100),
    month: int = Query(ge=1, le=12),
    session: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
):
    query = (
        select(MonthlyReport)
        .join(MonthlyReport.client)
        .options(
            selectinload(MonthlyReport.client).selectinload(Client.kams),
        )
        .where(
            MonthlyReport.report_year == year,
            MonthlyReport.report_month == month,
        )
        .order_by(Client.name)
    )
    query = _filter_reports_for_user(query, current_user)

    result = await session.execute(query)
    reports = result.scalars().all()
    return [_report_item(report, report.client) for report in reports]


@router.get("/history", response_model=list[ReportListItemResponse])
async def report_history(
    client_id: int | None = Query(default=None),
    year: int | None = Query(default=None, ge=2000, le=2100),
    session: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
):
    query = (
        select(MonthlyReport)
        .options(
            selectinload(MonthlyReport.client).selectinload(Client.kams),
        )
        .order_by(MonthlyReport.report_year.desc(), MonthlyReport.report_month.desc())
    )
    if client_id is not None:
        query = query.where(MonthlyReport.client_id == client_id)
    if year is not None:
        query = query.where(MonthlyReport.report_year == year)
    query = _filter_reports_for_user(query, current_user)

    result = await session.execute(query)
    reports = result.scalars().all()
    return [_report_item(report, report.client) for report in reports]


@router.get("/{report_id}/download")
async def download_report_file(
    report_id: int,
    session: AsyncSession = Depends(get_db_session),
):
    report = await session.get(MonthlyReport, report_id)
    if report is None or not report.fichier_path:
        raise HTTPException(status_code=404, detail="File not found")

    if report.fichier_url and report.fichier_url.startswith("https://"):
        return RedirectResponse(url=report.fichier_url)

    file_path = Path(report.fichier_path)
    if not file_path.exists() or not file_path.is_file():
        raise HTTPException(status_code=404, detail="File not found")

    filename = (report.fichier_filename or file_path.name).replace('"', "")
    return FileResponse(
        path=file_path,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        filename=filename,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/{report_id}/mark-done", response_model=MarkDoneResponse)
async def mark_report_done(
    report_id: int,
    session: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(require_admin),
):
    result = await session.execute(
        select(MonthlyReport)
        .options(
            selectinload(MonthlyReport.client).selectinload(Client.kams),
        )
        .where(MonthlyReport.id == report_id)
    )
    report = result.scalar_one_or_none()
    if report is None:
        raise HTTPException(status_code=404, detail="Report not found")

    now = datetime.now()
    report.statut = "done"
    report.end_date = now.date()
    report.marked_done_at = now

    attempted = len(report.client.kams)
    sent = 0
    failed = 0
    for kam in report.client.kams:
        success, error_msg, _response = await send_kam_email(report, report.client, kam)
        if success:
            sent += 1
        else:
            failed += 1
        session.add(
            NotificationLog(
                report_id=report.id,
                sent_to=kam.email,
                sent_at=now,
                success=success,
                error_msg=error_msg,
            )
        )

    if not report.client.kams:
        failed += 1
        session.add(
            NotificationLog(
                report_id=report.id,
                sent_to="",
                sent_at=now,
                success=False,
                error_msg="No KAMs configured for client",
            )
        )

    if sent > 0:
        report.notification_sent = True
        report.notification_sent_at = now

    await session.commit()
    await session.refresh(report)
    return MarkDoneResponse(
        report_id=report.id,
        notifications={
            "attempted": attempted,
            "sent": sent,
            "failed": failed,
        },
    )


@router.post("/{report_id}/upload-file", response_model=MonthlyReportResponse)
async def upload_report_file(
    
    report_id: int,
    file: UploadFile = File(),
    session: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(require_admin),
):
    result = await session.execute(
        select(MonthlyReport)
        .options(selectinload(MonthlyReport.client))
        .where(MonthlyReport.id == report_id)
    )
    report = result.scalar_one_or_none()
    if report is None:
        raise HTTPException(status_code=404, detail="Report not found")

    filename = Path(file.filename or "report.xlsx").name
    if not filename.lower().endswith((".xlsx", ".xls")):
        raise HTTPException(status_code=400, detail="Only Excel files are accepted")
    
    # DEBUG AZURE
    import os
    print("=== UPLOAD CALLED ===")
    print(f"AZURE_CONNECTION_STRING set: {bool(os.getenv('AZURE_CONNECTION_STRING'))}")
    print(f"AZURE_BLOB_CONTAINER: {os.getenv('AZURE_BLOB_CONTAINER')}")

    file_content = await file.read()

    if os.getenv("AZURE_CONNECTION_STRING"):
        if report.fichier_path and (report.fichier_url or "").startswith("/uploads/"):
            old_file_path = Path(report.fichier_path)
            if old_file_path.exists() and old_file_path.is_file():
                old_file_path.unlink()
        elif report.fichier_path:
            delete_blob(report.fichier_path)

        blob_result = upload_excel_to_blob(
            file_content=file_content,
            client_name=report.client.name,
            year=report.report_year,
            month=report.report_month,
            filename=filename,
        )

        report.fichier_filename = filename
        report.fichier_path = blob_result["blob_name"]
        report.fichier_url = blob_result["sas_url"]
    else:
        upload_dir = (
            Path("uploads")
            / _safe_path_segment(report.client.name)
            / f"{report.report_year}-{report.report_month:02d}"
        )
        upload_dir.mkdir(parents=True, exist_ok=True)
        destination = upload_dir / filename

        if report.fichier_path:
            old_file_path = Path(report.fichier_path)
            if old_file_path.exists() and old_file_path.is_file():
                old_file_path.unlink()

        destination.write_bytes(file_content)

        report.fichier_filename = filename
        report.fichier_path = str(destination)
        report.fichier_url = (
            "/uploads/"
            f"{quote(_safe_path_segment(report.client.name))}/"
            f"{report.report_year}-{report.report_month:02d}/"
            f"{quote(filename)}"
        )

    await session.commit()
    await session.refresh(report)
    return report
