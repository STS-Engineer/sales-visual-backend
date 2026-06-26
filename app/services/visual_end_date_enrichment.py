import argparse
import asyncio
import json
from datetime import date
from typing import Any

from sqlalchemy import func, select

from app.core.config import settings
from app.core.monday_client import fetch_board_items
from app.db.session import AsyncSessionLocal
from app.models.visual import Visual

PREFERRED_DATE_COLUMN_IDS = ["date1", "date__1", "date4__1"]


def _parse_monday_date(column_value: dict[str, Any]) -> date | None:
    raw_value = column_value.get("value")
    if raw_value:
        try:
            parsed = json.loads(raw_value)
        except json.JSONDecodeError:
            parsed = None

        if isinstance(parsed, dict) and parsed.get("date"):
            return date.fromisoformat(parsed["date"])

    text = column_value.get("text")
    if text:
        try:
            return date.fromisoformat(text[:10])
        except ValueError:
            return None

    return None


def extract_end_date(item: dict[str, Any]) -> tuple[date | None, dict[str, Any] | None]:
    column_values = item.get("column_values", [])
    by_id = {
        column_value.get("id"): column_value
        for column_value in column_values
    }

    for column_id in PREFERRED_DATE_COLUMN_IDS:
        column_value = by_id.get(column_id)
        if not column_value:
            continue
        parsed = _parse_monday_date(column_value)
        if parsed:
            return parsed, column_value

    for column_value in column_values:
        if column_value.get("type") != "date":
            continue
        parsed = _parse_monday_date(column_value)
        if parsed:
            return parsed, column_value

    return None, None


async def sample_monday_end_dates(limit: int = 10) -> None:
    items = await fetch_board_items(settings.MONDAY_BOARD_ID)
    item_ids = [item["id"] for item in items[:limit]]

    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(Visual).where(Visual.monday_item_id.in_(item_ids))
        )
        visuals_by_item_id = {
            visual.monday_item_id: visual
            for visual in result.scalars().all()
        }

    print("MONDAY_END_DATE_SAMPLE")
    for item in items[:limit]:
        end_date, raw_column = extract_end_date(item)
        visual = visuals_by_item_id.get(item["id"])
        print(
            json.dumps(
                {
                    "monday_item_id": item.get("id"),
                    "name": item.get("name"),
                    "raw_end_date_value": raw_column.get("value") if raw_column else None,
                    "parsed_end_date": end_date.isoformat() if end_date else None,
                    "visual_created_at": visual.created_at.isoformat() if visual else None,
                },
                ensure_ascii=False,
            )
        )


async def update_visual_end_dates() -> dict[str, int]:
    items = await fetch_board_items(settings.MONDAY_BOARD_ID)
    dates_by_item_id = {
        item["id"]: end_date
        for item in items
        for end_date, _raw_column in [extract_end_date(item)]
        if end_date is not None
    }

    async with AsyncSessionLocal() as session:
        result = await session.execute(select(Visual))
        visuals = result.scalars().all()

        matched = 0
        updated = 0
        missing_monday_date = 0

        for visual in visuals:
            end_date = dates_by_item_id.get(visual.monday_item_id)
            if end_date is None:
                missing_monday_date += 1
                continue

            matched += 1
            if visual.end_date != end_date:
                visual.end_date = end_date
                updated += 1

        await session.commit()

        populated = await session.scalar(
            select(func.count()).select_from(Visual).where(Visual.end_date.is_not(None))
        )
        null_count = await session.scalar(
            select(func.count()).select_from(Visual).where(Visual.end_date.is_(None))
        )

    return {
        "monday_items": len(items),
        "monday_items_with_end_date": len(dates_by_item_id),
        "matched_visuals": matched,
        "updated_visuals": updated,
        "missing_monday_date": missing_monday_date,
        "visuals_end_date_populated": populated or 0,
        "visuals_end_date_null": null_count or 0,
    }


async def main(apply: bool) -> None:
    await sample_monday_end_dates()
    if apply:
        result = await update_visual_end_dates()
        print("VISUAL_END_DATE_UPDATE")
        for key, value in result.items():
            print(f"{key}={value}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    asyncio.run(main(apply=args.apply))
