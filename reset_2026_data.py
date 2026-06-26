"""
Reset script — delete and reinitialize monthly reports for 2026.

Operations:
1. DELETE monthly_reports WHERE report_year = 2026 AND report_month = 6
2. POST /reports/init for 2026/6  (recreates 10 waiting rows)
3. POST /reports/init for 2026/7  (creates 10 waiting rows)

Only affects year 2026. All years <= 2025 are untouched.
"""

import asyncio
import sys
from pathlib import Path

# Add the backend root to sys.path so app imports work
sys.path.insert(0, str(Path(__file__).resolve().parent))

from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import engine, AsyncSessionLocal
from app.models.client import Client
from app.models.monthly_report import MonthlyReport


async def run():
    print("=" * 60)
    print("STEP 1 — Show current row counts for 2026")
    print("=" * 60)

    async with AsyncSessionLocal() as session:
        for month in [6, 7]:
            result = await session.execute(
                select(MonthlyReport).where(
                    MonthlyReport.report_year == 2026,
                    MonthlyReport.report_month == month,
                )
            )
            rows = result.scalars().all()
            print(f"  monthly_reports WHERE year=2026 AND month={month}: {len(rows)} rows")
            for r in rows:
                print(f"    id={r.id}, client_id={r.client_id}, statut={r.statut}, "
                      f"end_date={r.end_date}, notification_sent={r.notification_sent}")

    print()
    print("=" * 60)
    print("STEP 2 — DELETE monthly_reports WHERE year=2026 AND month=6")
    print("=" * 60)

    async with AsyncSessionLocal() as session:
        result = await session.execute(
            delete(MonthlyReport).where(
                MonthlyReport.report_year == 2026,
                MonthlyReport.report_month == 6,
            )
        )
        print(f"  Deleted {result.rowcount} rows")
        await session.commit()

    print()
    print("=" * 60)
    print("STEP 3 — Verify deletion")
    print("=" * 60)

    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(MonthlyReport).where(
                MonthlyReport.report_year == 2026,
                MonthlyReport.report_month == 6,
            )
        )
        remaining = result.scalars().all()
        print(f"  Remaining rows for 2026/6: {len(remaining)}")

    print()
    print("=" * 60)
    print("STEP 4 — Init month 2026/6 (recreate clean rows)")
    print("=" * 60)

    async with AsyncSessionLocal() as session:
        # Get all active clients
        clients_result = await session.execute(
            select(Client).where(Client.is_active.is_(True)).order_by(Client.name)
        )
        clients = clients_result.scalars().all()
        print(f"  Active clients found: {len(clients)}")

        created = 0
        skipped = 0
        for client in clients:
            existing = await session.execute(
                select(MonthlyReport).where(
                    MonthlyReport.client_id == client.id,
                    MonthlyReport.report_year == 2026,
                    MonthlyReport.report_month == 6,
                )
            )
            if existing.scalar_one_or_none() is not None:
                skipped += 1
                continue

            session.add(
                MonthlyReport(
                    client_id=client.id,
                    report_year=2026,
                    report_month=6,
                    statut="waiting",
                    notification_sent=False,
                )
            )
            created += 1
            print(f"    Created report for client_id={client.id} ({client.name})")

        await session.commit()
        print(f"  Created: {created}, Skipped: {skipped}")

    print()
    print("=" * 60)
    print("STEP 5 — Init month 2026/7")
    print("=" * 60)

    async with AsyncSessionLocal() as session:
        clients_result = await session.execute(
            select(Client).where(Client.is_active.is_(True)).order_by(Client.name)
        )
        clients = clients_result.scalars().all()
        print(f"  Active clients found: {len(clients)}")

        created = 0
        skipped = 0
        for client in clients:
            existing = await session.execute(
                select(MonthlyReport).where(
                    MonthlyReport.client_id == client.id,
                    MonthlyReport.report_year == 2026,
                    MonthlyReport.report_month == 7,
                )
            )
            if existing.scalar_one_or_none() is not None:
                skipped += 1
                print(f"    Skipped client_id={client.id} ({client.name}) — already exists")
                continue

            session.add(
                MonthlyReport(
                    client_id=client.id,
                    report_year=2026,
                    report_month=7,
                    statut="waiting",
                    notification_sent=False,
                )
            )
            created += 1
            print(f"    Created report for client_id={client.id} ({client.name})")

        await session.commit()
        print(f"  Created: {created}, Skipped: {skipped}")

    print()
    print("=" * 60)
    print("STEP 6 — Final verification: row counts per month in 2026")
    print("=" * 60)

    async with AsyncSessionLocal() as session:
        for month in range(1, 13):
            result = await session.execute(
                select(MonthlyReport).where(
                    MonthlyReport.report_year == 2026,
                    MonthlyReport.report_month == month,
                )
            )
            rows = result.scalars().all()
            statuses = [r.statut for r in rows]
            print(f"  2026/{month:02d}: {len(rows)} rows — statuses: {statuses}")

    print()
    print("=" * 60)
    print("STEP 7 — Verify all months <= 2025 are untouched")
    print("=" * 60)

    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(MonthlyReport).where(MonthlyReport.report_year <= 2025)
        )
        old_rows = result.scalars().all()
        print(f"  Total rows with year <= 2025: {len(old_rows)} (should be > 0)")

    print()
    print("Done. Only 2026 data was modified.")


if __name__ == "__main__":
    asyncio.run(run())