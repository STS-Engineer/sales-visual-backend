"""
Migrate visuals rows that were skipped during initial import
because their names didn't match any client name exactly.

Name mapping for visual names → client names:
  "B&D"              → "Sales B&D"
  "Sales FB"         → "Sales First Brand"
  "Sales Fist Brand" → "Sales First Brand"
  "DY"               → "Sales DY"

Non-client names (skipped):
  "All Visual", "All visual", "Others Customers", "Other Customers"

Case variants already handled by normalization (Sales Bosch → Sales BOSCH,
Sales Mahle → Sales MAHLE, Sales Nidec → Sales NIDEC, Sales Je → Sales JE,
Sales Dy → Sales DY, Sales VALEO → Sales Valeo, "Sales  B&D" → Sales B&D).

For each matched visual row:
  - Look up the mapped client_id
  - Derive report_year/report_month from end_date (fallback to created_at)
  - Insert into monthly_reports if (client_id, year, month) does not exist
  - Skip 2026 rows (already cleaned)
  - Skip duplicates silently

After migration, show counts per month for 2023-2025.
"""

import asyncio
import sys
from pathlib import Path
from datetime import date

sys.path.insert(0, str(Path(__file__).resolve().parent))

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import AsyncSessionLocal
from app.models.client import Client
from app.models.monthly_report import MonthlyReport
from app.models.visual import Visual

# Visual name → target client name (for names that don't match by normalization)
NAME_MAP = {
    "B&D": "Sales B&D",
    "Sales FB": "Sales First Brand",
    "Sales Fist Brand": "Sales First Brand",
    "DY": "Sales DY",
}

# Names that are NOT clients — skip these
SKIP_NAMES = {"All Visual", "All visual", "Others Customers", "Other Customers"}

# Case variants that normalise to a client name but with different casing
# e.g. "Sales Bosch" → normalize to "salesbosch" → matches "Sales BOSCH"
# These were already handled, but some months may be missing.


async def run():
    async with AsyncSessionLocal() as session:
        # Build client lookup: normalized name → client_id
        result = await session.execute(
            select(Client).where(Client.is_active.is_(True))
        )
        clients = result.scalars().all()
        client_by_norm = {c.name.replace(" ", "").lower(): c for c in clients}

        print(f"Loaded {len(clients)} active clients")

        # Also build a fallback: try to find clients by normalized visual name
        # e.g. "Sales Bosch" → norm "salesbosch" → matches norm "salesbosch" → "Sales BOSCH"
        # We'll do direct lookup in the loop.

        # Get all visual rows, ordered by name
        result = await session.execute(
            select(Visual).order_by(Visual.name)
        )
        visuals = result.scalars().all()
        print(f"Total visuals rows: {len(visuals)}")

        inserted = 0
        skipped_no_client = 0
        skipped_skip_name = 0
        skipped_2026 = 0
        skipped_dup = 0
        already_existed = 0

        for v in visuals:
            name = v.name.strip()

            # Skip non-client names
            if name in SKIP_NAMES:
                skipped_skip_name += 1
                continue

            # Resolve target client name
            target_name = NAME_MAP.get(name, name)

            # Find client: first by exact, then by normalized
            client = None
            norm = target_name.replace(" ", "").lower()
            client = client_by_norm.get(norm)

            if client is None:
                # Try finding by case-insensitive comparison
                for c in clients:
                    if c.name.replace(" ", "").lower() == norm:
                        client = c
                        break

            if client is None:
                skipped_no_client += 1
                if skipped_no_client <= 5:
                    print(f"  SKIP (no client): '{name}' → target '{target_name}'")
                continue

            # Derive year/month from end_date, fallback to created_at
            dt = v.end_date
            if dt is None:
                dt = v.created_at.date() if hasattr(v.created_at, 'date') else v.created_at

            if dt is None:
                skipped_no_client += 1
                continue

            if hasattr(dt, 'year'):
                year = dt.year
                month = dt.month
            else:
                # datetime object
                year = dt.year
                month = dt.month

            # Skip 2026 (already cleaned)
            if year == 2026:
                skipped_2026 += 1
                continue

            # Check if (client_id, year, month) already exists
            existing = await session.execute(
                select(MonthlyReport).where(
                    MonthlyReport.client_id == client.id,
                    MonthlyReport.report_year == year,
                    MonthlyReport.report_month == month,
                )
            )
            if existing.scalar_one_or_none() is not None:
                already_existed += 1
                continue

            # Also check if there's already a row for this visual's exact month
            # from any source
            session.add(
                MonthlyReport(
                    client_id=client.id,
                    report_year=year,
                    report_month=month,
                    statut="waiting",
                    notification_sent=False,
                )
            )
            inserted += 1
            print(f"  INSERTED: client_id={client.id} ({client.name}), year={year}, month={month:02d} — from visual '{name}'")

        await session.commit()

        print()
        print("=" * 60)
        print("MIGRATION SUMMARY")
        print("=" * 60)
        print(f"  Inserted:          {inserted}")
        print(f"  Already existed:   {already_existed}")
        print(f"  Skipped (no client): {skipped_no_client}")
        print(f"  Skipped (skip name): {skipped_skip_name}")
        print(f"  Skipped (2026):      {skipped_2026}")

        print()
        print("=" * 60)
        print("MONTHLY COUNTS FOR 2023-2025")
        print("=" * 60)
        for year in [2023, 2024, 2025]:
            for month in range(1, 13):
                result = await session.execute(
                    select(MonthlyReport).where(
                        MonthlyReport.report_year == year,
                        MonthlyReport.report_month == month,
                    )
                )
                rows = result.scalars().all()
                statuses = [r.statut for r in rows]
                done_count = statuses.count("done")
                waiting_count = statuses.count("waiting")
                print(f"  {year}-{month:02d}: {len(rows)} rows (done={done_count}, waiting={waiting_count})")

    print()
    print("Done.")


if __name__ == "__main__":
    asyncio.run(run())