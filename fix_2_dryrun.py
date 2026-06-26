"""
FIX 2 — DRY RUN ONLY

Find ALL remaining unmatched visuals for 2023-2025 using
case-insensitive LIKE-based name matching.

Shows:
- total new rows to insert
- breakdown by year/month/client
- which months would go from incomplete to 10/10

Does NOT insert anything.
"""

import asyncio, sys
from pathlib import Path
from datetime import date
from collections import Counter, defaultdict
sys.path.insert(0, str(Path(__file__).resolve().parent))

from sqlalchemy import select, func
from app.db.session import AsyncSessionLocal
from app.models.client import Client
from app.models.monthly_report import MonthlyReport
from app.models.visual import Visual

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
    async with AsyncSessionLocal() as session:
        # Build client map
        result = await session.execute(
            select(Client).where(Client.is_active.is_(True))
        )
        clients = result.scalars().all()
        client_map = {}
        for c in clients:
            client_map[c.name.lower()] = c
            client_map[c.name.replace(" ", "").lower()] = c

        print(f"Loaded {len(clients)} clients\n")

        # Get ALL visuals
        result = await session.execute(
            select(Visual).order_by(Visual.name)
        )
        all_visuals = result.scalars().all()
        print(f"Total visuals in DB: {len(all_visuals)}\n")

        # Classify and find missing
        missing = []  # (client, year, month, visual_name, status, end_date)
        matched_count = 0
        skipped_count = 0

        for v in all_visuals:
            client_name = match_client_name(v.name.strip())
            if client_name is None:
                skipped_count += 1
                continue

            client = client_map.get(client_name.lower())
            if client is None:
                client = client_map.get(client_name.replace(" ", "").lower())
            if client is None:
                skipped_count += 1
                continue

            matched_count += 1

            # Derive year/month
            dt = v.end_date
            if dt is None:
                dt = v.created_at.date() if hasattr(v.created_at, 'date') else v.created_at
            if dt is None:
                continue

            year = dt.year
            month = dt.month

            # Skip 2026 (already fixed)
            if year == 2026:
                continue

            # Check if (client_id, year, month) exists
            result = await session.execute(
                select(MonthlyReport).where(
                    MonthlyReport.client_id == client.id,
                    MonthlyReport.report_year == year,
                    MonthlyReport.report_month == month,
                )
            )
            if result.scalar_one_or_none() is None:
                missing.append((client, year, month, v.name, v.status, v.end_date))

        print(f"Matched to client: {matched_count}")
        print(f"Skipped (non-client): {skipped_count}")
        print(f"\n{'='*60}")
        print(f"TOTAL NEW ROWS TO INSERT: {len(missing)}")
        print(f"{'='*60}\n")

        if not missing:
            print("No missing rows found. All visuals are already in monthly_reports.")
            return

        # Breakdown by year/month
        ym_counts = Counter()
        ym_clients = defaultdict(list)
        for client, year, month, vname, status, ed in missing:
            ym_counts[(year, month)] += 1
            ym_clients[(year, month)].append((client.name, vname, status, ed))

        print("BREAKDOWN BY YEAR/MONTH:")
        print("-" * 60)
        for (year, month), count in sorted(ym_counts.items()):
            print(f"\n  {year}-{month:02d}: {count} new rows")
            for cname, vname, status, ed in sorted(ym_clients[(year, month)]):
                print(f"    {cname:20s} ← '{vname}' (status={status}, end={ed})")

        # Current vs projected counts
        print(f"\n{'='*60}")
        print("MONTH COMPLETENESS: CURRENT → PROJECTED")
        print(f"{'='*60}")
        for (year, month), add_count in sorted(ym_counts.items()):
            result = await session.execute(
                select(func.count(MonthlyReport.id)).where(
                    MonthlyReport.report_year == year,
                    MonthlyReport.report_month == month,
                )
            )
            current = result.scalar()
            new_total = current + add_count
            completeness = "✅ 10/10" if new_total >= 10 else f"⚠️ {new_total}/10"
            print(f"  {year}-{month:02d}: {current} → {new_total} ({completeness})")

        # Summary by client
        print(f"\n{'='*60}")
        print("SUMMARY BY CLIENT:")
        print(f"{'='*60}")
        client_totals = Counter()
        for client, year, month, vname, status, ed in missing:
            client_totals[client.name] += 1
        for cname, count in sorted(client_totals.items()):
            print(f"  {cname:20s}: {count} new rows")

    print("\nDry run complete. No data was modified.")


if __name__ == "__main__":
    asyncio.run(run())