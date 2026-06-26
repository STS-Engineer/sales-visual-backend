"""Check how many visuals have end_date in 2026."""
import asyncio, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))

from sqlalchemy import select, func
from app.db.session import AsyncSessionLocal
from app.models.visual import Visual
from app.models.monthly_report import MonthlyReport

async def run():
    async with AsyncSessionLocal() as session:
        # Visuals with end_date in 2026
        result = await session.execute(
            select(func.count(), func.min(Visual.end_date), func.max(Visual.end_date))
            .where(Visual.end_date >= '2026-01-01', Visual.end_date <= '2026-12-31')
        )
        cnt, mn, mx = result.one()
        print(f'Visuals with end_date in 2026: {cnt} (range: {mn} to {mx})')

        if cnt > 0:
            result = await session.execute(
                select(Visual).where(
                    Visual.end_date >= '2026-01-01', 
                    Visual.end_date <= '2026-12-31'
                ).order_by(Visual.name)
            )
            for v in result.scalars().all():
                print(f'  id={v.id}, name={v.name!r}, end={v.end_date}, status={v.status!r}')

        # Check 2026 monthly_reports
        result = await session.execute(
            select(func.count(MonthlyReport.id)).where(
                MonthlyReport.report_year == 2026
            )
        )
        total_2026 = result.scalar()
        print(f'\nTotal monthly_reports in 2026: {total_2026}')

        # Show 2026 reports with their statuses
        result = await session.execute(
            select(MonthlyReport).where(
                MonthlyReport.report_year == 2026
            ).order_by(MonthlyReport.report_month, MonthlyReport.client_id)
        )
        for r in result.scalars().all():
            print(f'  month={r.report_month}, client_id={r.client_id}, statut={r.statut}, end_date={r.end_date}')

asyncio.run(run())