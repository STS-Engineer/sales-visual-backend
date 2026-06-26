"""Check 2026 data with proper date casting for PostgreSQL."""
import asyncio, sys
from pathlib import Path
from datetime import date
sys.path.insert(0, str(Path(__file__).resolve().parent))

from sqlalchemy import select, func, cast, Date
from app.db.session import AsyncSessionLocal
from app.models.visual import Visual
from app.models.monthly_report import MonthlyReport

async def run():
    async with AsyncSessionLocal() as session:
        # Convert strings to proper date objects
        start = date(2026, 1, 1)
        end = date(2026, 12, 31)
        
        result = await session.execute(
            select(func.count(), func.min(Visual.end_date), func.max(Visual.end_date))
            .where(Visual.end_date.between(start, end))
        )
        cnt, mn, mx = result.one()
        print(f'Visuals with end_date in 2026: {cnt} (range: {mn} to {mx})')

        if cnt and cnt > 0:
            result = await session.execute(
                select(Visual).where(Visual.end_date.between(start, end)).order_by(Visual.name)
            )
            for v in result.scalars().all():
                print(f'  id={v.id}, name={v.name!r}, end={v.end_date}, status={v.status!r}')
        
        # 2026 monthly_reports
        result = await session.execute(
            select(MonthlyReport).where(MonthlyReport.report_year == 2026).order_by(MonthlyReport.report_month, MonthlyReport.client_id)
        )
        reports = result.scalars().all()
        print(f'\n2026 monthly_reports: {len(reports)} rows')
        for r in reports:
            print(f'  client_id={r.client_id}, month={r.report_month}, statut={r.statut}, end_date={r.end_date}')

asyncio.run(run())