"""
Two-part fix:

FIX 1 — Sync 2026 monthly_reports from Monday.com data.
  Fetch all Monday items, match by client name + year/month,
  update statut, end_date, fichier_url, notification_sent.

FIX 2 — Find ALL remaining unmatched visuals using LIKE matching.
  Use LOWER(visual.name) LIKE LOWER('%keyword%') to match clients.
  Show dry-run with counts, then insert after confirmation.
"""

import asyncio
import json
import sys
from pathlib import Path
from datetime import date, datetime
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import AsyncSessionLocal
from app.models.client import Client
from app.models.monthly_report import MonthlyReport
from app.models.visual import Visual
from app.core.monday_client import fetch_board_items, fetch_board_columns
from app.core.config import settings

# ─────────────────────────────────────────────
# CLIENT MATCHING — LIKE-based keywords
# ─────────────────────────────────────────────
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
    """Return the canonical client name if visual_name matches, else None."""
    name_lower = visual_name.lower().replace(" ", "")

    # Check skip list first
    for skip in SKIP_KEYWORDS:
        if skip.replace(" ", "") in name_lower:
            return None

    for keywords, client_name in CLIENT_MATCH_RULES:
        for kw in keywords:
            if kw.lower() in name_lower:
                return client_name
    return None


# ─────────────────────────────────────────────
# FIX 1: Sync 2026 from Monday
# ─────────────────────────────────────────────
async def fix_1_sync_2026(session: AsyncSession, dry_run: bool = True) -> None:
    print("=" * 60)
    print("FIX 1 — Sync 2026 monthly_reports from Monday.com")
    print("=" * 60)

    # Fetch all Monday items (raw)
    print("\nFetching Monday items...")
    try:
        board = await fetch_board_columns(settings.MONDAY_BOARD_ID)
        columns_by_id = {
            col["id"]: col for col in board.get("columns", [])
        }
        items = await fetch_board_items(settings.MONDAY_BOARD_ID)
    except Exception as e:
        print(f"  ERROR fetching Monday items: {e}")
        print("  Skipping FIX 1. The Monday API may be unavailable.")
        return

    print(f"  Fetched {len(items)} items from Monday board")
    print(f"  Columns: {[c['title'] for c in board.get('columns', [])]}")

    # Build client ID map (lowercase name → id)
    result = await session.execute(
        select(Client).where(Client.is_active.is_(True))
    )
    clients = result.scalars().all()
    client_by_name_lower = {c.name.lower(): c for c in clients}

    # Normalize Monday column keys
    def normalize_key(s: str) -> str:
        return "".join(c.lower() for c in s if c.isalnum())

    col_lookup = {}
    for col_id, col_meta in columns_by_id.items():
        key = normalize_key(col_meta.get("title", ""))
        col_lookup[key] = col_id
        col_lookup[normalize_key(col_id)] = col_id

    def get_text(item: dict, *names: str) -> str | None:
        for name in names:
            col_id = col_lookup.get(normalize_key(name))
            if col_id:
                for cv in item.get("column_values", []):
                    if cv.get("id") == col_id:
                        return cv.get("text") or cv.get("display_value") or None
        return None

    def get_value(item: dict, *names: str) -> Any:
        for name in names:
            col_id = col_lookup.get(normalize_key(name))
            if col_id:
                for cv in item.get("column_values", []):
                    if cv.get("id") == col_id:
                        val = cv.get("value")
                        if val:
                            try:
                                return json.loads(val)
                            except (json.JSONDecodeError, TypeError):
                                return val
                        return None
        return None

    def get_date(item: dict, *names: str) -> date | None:
        val = get_value(item, *names)
        if val and isinstance(val, dict):
            d = val.get("date")
            if d:
                try:
                    return datetime.strptime(d, "%Y-%m-%d").date()
                except ValueError:
                    pass
        # Fallback to text parsing
        text = get_text(item, *names)
        if text:
            try:
                parts = text.split("-")
                if len(parts) == 3:
                    return date(int(parts[0]), int(parts[1]), int(parts[2]))
            except (ValueError, IndexError):
                pass
        return None

    def get_url(item: dict, *names: str) -> str | None:
        val = get_value(item, *names)
        if val and isinstance(val, dict):
            if val.get("url"):
                return val["url"]
            if val.get("public_url"):
                return val["public_url"]
        text = get_text(item, *names)
        if text and text.startswith(("http://", "https://")):
            return text
        return None

    # Process each Monday item
    matched_items = []
    for item in items:
        item_name = item.get("name", "")
        client_name = match_client_name(item_name)

        # Find end_date
        end_date = get_date(item, "date", "end_date", "deadline", "date4")
        if end_date and end_date.year == 2026:
            matched_items.append((item, client_name, end_date))

    print(f"\n  Items with end_date in 2026: {len(matched_items)}")

    # Group by client for display
    from collections import Counter
    client_counts = Counter()
    for _, cn, _ in matched_items:
        client_counts[cn or "(unmatched)"] += 1

    print("\n  Breakdown by client:")
    for name, count in sorted(client_counts.items()):
        print(f"    {name}: {count}")

    print()

    # Now update monthly_reports
    updated_count = 0
    no_report_count = 0
    not_2026_count = 0

    for item, client_name, end_date in matched_items:
        if client_name is None:
            continue

        client = client_by_name_lower.get(client_name.lower())
        if client is None:
            continue

        year = end_date.year
        month = end_date.month

        # Find matching monthly_report
        result = await session.execute(
            select(MonthlyReport).where(
                MonthlyReport.client_id == client.id,
                MonthlyReport.report_year == year,
                MonthlyReport.report_month == month,
            )
        )
        report = result.scalar_one_or_none()

        if report is None:
            if not dry_run:
                # Create new report for this month
                session.add(MonthlyReport(
                    client_id=client.id,
                    report_year=year,
                    report_month=month,
                    statut="waiting" if item.get("name") else "waiting",
                    end_date=end_date,
                    notification_sent=False,
                ))
                no_report_count += 1
                print(f"  CREATED: {client.name} {year}-{month:02d}")
            else:
                no_report_count += 1
            continue

        if dry_run:
            old_status = report.statut
            print(f"  WOULD UPDATE: {client.name} {year}-{month:02d} (status: {old_status})")
        else:
            # Check Monday status
            monday_status = get_text(item, "status", "statut")
            if monday_status and monday_status.lower() in ("done", "completed"):
                report.statut = "done"

            report.end_date = end_date

            # Update fichier_url if available
            file_url = get_url(item, "file", "fichier", "fichier7")
            if file_url:
                report.fichier_url = file_url

            # For historical 2026 data that came from Monday, it was already notified
            report.notification_sent = True

            print(f"  UPDATED: {client.name} {year}-{month:02d} → statut={report.statut}")
            updated_count += 1

    if not dry_run:
        await session.commit()

    print(f"\n  FIX 1 Summary (dry_run={dry_run}):")
    print(f"    Updated: {updated_count}")
    print(f"    Would create new: {no_report_count}")
    print(f"    Total matched: {len(matched_items)}")


# ─────────────────────────────────────────────
# FIX 2: Find all remaining unmatched visuals
# ─────────────────────────────────────────────
async def fix_2_find_remaining(session: AsyncSession, dry_run: bool = True) -> None:
    print()
    print("=" * 60)
    print("FIX 2 — Find ALL remaining unmatched visuals (LIKE-based)")
    print("=" * 60)

    # Build client ID map
    result = await session.execute(
        select(Client).where(Client.is_active.is_(True))
    )
    clients = result.scalars().all()
    client_by_name = {c.name: c for c in clients}

    # Get ALL visuals
    result = await session.execute(
        select(Visual).order_by(Visual.name)
    )
    all_visuals = result.scalars().all()
    print(f"\n  Total visuals in DB: {len(all_visuals)}")

    # Classify each visual
    matched_visuals = []  # (visual, client)
    unmatched = []
    skipped = []

    for v in all_visuals:
        name = v.name.strip()
        client_name = match_client_name(name)

        if client_name is None:
            skipped.append(v)
            continue

        client = client_by_name.get(client_name)
        if client is None:
            # Try case-insensitive
            for cn, c in client_by_name.items():
                if cn.lower() == client_name.lower():
                    client = c
                    break

        if client is None:
            unmatched.append((name, client_name))
            continue

        matched_visuals.append((v, client))

    print(f"  Matched to client: {len(matched_visuals)}")
    print(f"  Skipped (non-client): {len(skipped)}")
    if unmatched:
        print(f"  Unmatched (no client found): {len(unmatched)}")
        for name, cn in unmatched[:10]:
            print(f"    '{name}' → tried '{cn}' but not found")

    # Group by client
    from collections import Counter
    client_visual_counts = Counter()
    for _, c in matched_visuals:
        client_visual_counts[c.name] += 1

    print("\n  Visuals per client:")
    for name, count in sorted(client_visual_counts.items()):
        print(f"    {name}: {count}")

    # Now find which of these matched visuals are NOT in monthly_reports
    # for the same year+month
    missing_by_client = Counter()
    missing_details = []
    new_rows_to_insert = []

    for v, client in matched_visuals:
        # Derive year/month
        dt = v.end_date
        if dt is None:
            dt = v.created_at.date() if hasattr(v.created_at, 'date') else v.created_at
        if dt is None:
            continue

        year = dt.year
        month = dt.month

        # Skip 2026 (already handled)
        if year == 2026:
            continue

        # Check if (client_id, year, month) exists
        existing = await session.execute(
            select(MonthlyReport).where(
                MonthlyReport.client_id == client.id,
                MonthlyReport.report_year == year,
                MonthlyReport.report_month == month,
            )
        )
        if existing.scalar_one_or_none() is None:
            missing_by_client[client.name] += 1
            missing_details.append((v, client, year, month))
            if not dry_run:
                session.add(
                    MonthlyReport(
                        client_id=client.id,
                        report_year=year,
                        report_month=month,
                        statut="done" if v.status and v.status.lower() == "done" else "waiting",
                        end_date=v.end_date,
                        fichier_url=v.file_url,
                        notification_sent=True,
                        notification_sent_at=datetime.now() if v.status and v.status.lower() == "done" else None,
                    )
                )
                new_rows_to_insert.append((client.name, year, month))

    print(f"\n  Missing monthly_reports rows: {len(missing_details)}")
    print(f"\n  Breakdown by client:")
    for name, count in sorted(missing_by_client.items()):
        print(f"    {name}: {count} rows")

    if len(missing_details) > 0:
        print(f"\n  Sample details:")
        for v, client, year, month in missing_details[:10]:
            print(f"    {client.name} {year}-{month:02d} (from '{v.name}', status={v.status}, end={v.end_date})")

    print(f"\n  New rows to insert: {len(missing_details)}")
    print(f"  Skipped (non-client names): {len(skipped)}")

    if not dry_run and missing_details:
        print(f"\n  Inserting {len(new_rows_to_insert)} new rows...")
        await session.commit()
        print("  Done.")

    # Show which months become complete (10/10)
    print("\n  Projected monthly counts after insertion:")
    year_months = Counter()
    for _, _, year, month in missing_details:
        year_months[(year, month)] += 1

    # Check current counts for affected months
    for (year, month), add_count in sorted(year_months.items()):
        result = await session.execute(
            select(func.count(MonthlyReport.id)).where(
                MonthlyReport.report_year == year,
                MonthlyReport.report_month == month,
            )
        )
        current = result.scalar()
        new_total = current + add_count
        completeness = "✅ 10/10" if new_total >= 10 else f"⚠️ {new_total}/10"
        print(f"    {year}-{month:02d}: {current} → {new_total} ({completeness})")


# ─────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────
async def run():
    DRY_RUN = "--execute" not in sys.argv

    if DRY_RUN:
        print("🚧 DRY RUN MODE — no changes will be made")
        print('   Run with "--execute" flag to apply changes')
    else:
        print("⚠️  EXECUTE MODE — changes will be committed")
    print()

    async with AsyncSessionLocal() as session:
        # FIX 1: Sync 2026 from Monday
        await fix_1_sync_2026(session, dry_run=DRY_RUN)

        # FIX 2: Find remaining unmatched
        await fix_2_find_remaining(session, dry_run=DRY_RUN)

    print()
    print("Done.")


if __name__ == "__main__":
    asyncio.run(run())