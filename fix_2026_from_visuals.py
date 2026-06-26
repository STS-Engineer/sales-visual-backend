"""
Fix 2026 monthly_reports using the visuals table (which already has
parsed end_dates and statuses from Monday).

The issue: months 1-5 in 2026 have only 6 clients (missing 4 clients).
The visuals table has "Done" status for all 10 clients for each month.

Steps:
1. For each visual row with end_date in 2026:
   - Match to client using LIKE-based name matching
   - Derive year/month from end_date (fallback created_at)
   - Find or create monthly_report for (client_id, year, month)
   - Update: statut, end_date, notification_sent, fichier_url
2. Skip non-client visual names (All Visual, Others Customers)
3. Skip duplicates

Shows dry-run first, then executes.
"""

import asyncio, sys
from pathlib import Path
from datetime import date, datetime
sys.path.insert(0, str(Path(__file__).resolve().parent))

from sqlalchemy import select, func
from app.db.session import AsyncSessionLocal
from app.models.client import Client
from app.models.monthly_report import MonthlyReport
from app.models.visual import Visual

# Match rules (same as fix_2026_and_remaining.py)
CLIENT_MATCH_RULES = [
    (["nidec"], "Sales NIDEC"),
    (["inteva"], "Sales Inteva"),
    (["mahle"], "Sales MAHLE"),
    (["valeo"], "Sales Valeo"),
    (["bosch"], "Sales BOSCH"),
    (["lucas"], "Sales Lucas"),
    (["first", "fb"], "Sales First Brand"),
    (["je"], "Sales JE"),
    (["dy"], "Sales DY"),
    (["b&d", "b%d"], "Sales B&D"),
]
SKIP_KEYWORDS = ["all visual", "allvisual", "other customers", "othercustomers"]


def match_client_name(visual_name: str) -> str | None:
    name_lower = visual_name.lower().replace(" ", "")
    for skip in SKIP_KEYWORDS:
        if skip.replace(" ", "") in name_lower:
            return None
    for keywords, client_name in CLIENT_MATCH_RULES:
        for kw in keywords:
            if kw.lower() in name_lower:
                return client_name
    return None


async def run():
    DRY_RUN = "--execute" not in sys.argv

    async with AsyncSessionLocal() as session:
        # Build client name→id map
        result = await session.execute(
            select(Client).where(Client.is_active.is_(True))
        )
        clients = result.scalars().all()
        client_map = {}
        for c in clients:
            client_map[c.name.lower()] = c
            client_map[c.name.replace(" ", "").lower()] = c

        print(f"Loaded {len(clients)} clients")

        # Get all visuals with end_date in 2026
        start = date(2026, 1, 1)
        end = date(2026, 12, 31)

        result = await session.execute(
            select(Visual)
            .where(Visual.end_date.between(start, end))
            .order_by(Visual.end_date, Visual.name)
        )
        visuals = result.scalars().all()
        print(f"Visuals with end_date in 2026: {len(visuals)}")

        # Process each visual
        created_count = 0
        updated_count = 0
        skipped_non_client = 0
        skipped_no_match = 0

        for v in visuals:
            client_name = match_client_name(v.name.strip())
            if client_name is None:
                skipped_non_client += 1
                continue

            # Find client
            client = client_map.get(client_name.lower())
            if client is None:
                client = client_map.get(client_name.replace(" ", "").lower())
            if client is None:
                skipped_no_match += 1
                continue

            year = v.end_date.year
            month = v.end_date.month

            # Check if report exists
            result = await session.execute(
                select(MonthlyReport).where(
                    MonthlyReport.client_id == client.id,
                    MonthlyReport.report_year == year,
                    MonthlyReport.report_month == month,
                )
            )
            report = result.scalar_one_or_none()

            if report is None:
                if DRY_RUN:
                    print(f"  WOULD CREATE: {client.name} {year}-{month:02d} (from '{v.name}', end={v.end_date}, status={v.status})")
                else:
                    session.add(MonthlyReport(
                        client_id=client.id,
                        report_year=year,
                        report_month=month,
                        statut="done" if v.status and v.status.lower() == "done" else "waiting",
                        end_date=v.end_date,
                        fichier_url=v.file_url,
                        notification_sent=True,
                        notification_sent_at=datetime.now() if v.status and v.status.lower() == "done" else None,
                    ))
                    created_count += 1
                continue

            # Update existing
            old_status = report.statut
            if DRY_RUN:
                if report.statut != "done" or report.end_date != v.end_date:
                    print(f"  WOULD UPDATE: {client.name} {year}-{month:02d} (status: {old_status} → done)")
            else:
                if v.status and v.status.lower() == "done":
                    report.statut = "done"
                report.end_date = v.end_date
                if v.file_url:
                    report.fichier_url = v.file_url
                report.notification_sent = True
                updated_count += 1

        if not DRY_RUN:
            await session.commit()

        print(f"\nSummary (dry_run={DRY_RUN}):")
        print(f"  Created: {created_count}")
        print(f"  Updated: {updated_count}")
        print(f"  Skipped (non-client): {skipped_non_client}")
        print(f"  Skipped (no match): {skipped_no_match}")

        # Show monthly counts for 2026
        print(f"\n2026 monthly counts:")
        for m in range(1, 13):
            result = await session.execute(
                select(func.count(MonthlyReport.id)).where(
                    MonthlyReport.report_year == 2026,
                    MonthlyReport.report_month == m,
                )
            )
            cnt = result.scalar()
            statuses = []
            if cnt > 0:
                result = await session.execute(
                    select(MonthlyReport.statut).where(
                        MonthlyReport.report_year == 2026,
                        MonthlyReport.report_month == m,
                    )
                )
                statuses = [r[0] for r in result.all()]
            print(f"  2026-{m:02d}: {cnt} rows — {statuses}")

    print("\nDone.")


if __name__ == "__main__":
    asyncio.run(run())