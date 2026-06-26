import json
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.monday_client import fetch_board_columns, fetch_board_items
from app.models.visual import Visual


def _normalize_key(value: str) -> str:
    return "".join(char.lower() for char in value if char.isalnum())


def _column_text(column_value: dict[str, Any] | None) -> str | None:
    if not column_value:
        return None
    return column_value.get("display_value") or column_value.get("text") or None


def _column_raw_value(column_value: dict[str, Any] | None) -> Any:
    if not column_value:
        return None

    value = column_value.get("value")
    if not value:
        return None

    try:
        return json.loads(value)
    except (TypeError, json.JSONDecodeError):
        return value


def _extract_url(column_value: dict[str, Any] | None) -> str | None:
    raw_value = _column_raw_value(column_value)

    if isinstance(raw_value, dict):
        if raw_value.get("url"):
            return raw_value["url"]
        if raw_value.get("public_url"):
            return raw_value["public_url"]

        files = raw_value.get("files")
        if isinstance(files, list):
            for file_data in files:
                if not isinstance(file_data, dict):
                    continue
                if file_data.get("url"):
                    return file_data["url"]
                if file_data.get("public_url"):
                    return file_data["public_url"]
                if file_data.get("asset_id"):
                    return str(file_data["asset_id"])

    text = _column_text(column_value)
    if text and text.startswith(("http://", "https://")):
        return text

    if raw_value is not None:
        return json.dumps(raw_value) if not isinstance(raw_value, str) else raw_value

    return text


def _column_lookup(
    item: dict[str, Any],
    columns_by_id: dict[str, dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    lookup: dict[str, dict[str, Any]] = {}

    for column_value in item.get("column_values", []):
        column_id = column_value.get("id")
        column_meta = columns_by_id.get(column_id, {})
        title = column_meta.get("title") or column_id or ""
        if column_id:
            lookup[_normalize_key(column_id)] = column_value
        lookup[_normalize_key(title)] = column_value

    return lookup


def _get_column(
    columns: dict[str, dict[str, Any]],
    *keys: str,
) -> dict[str, Any] | None:
    for key in keys:
        column = columns.get(_normalize_key(key))
        if column:
            return column
    return None


async def sync_monday_visuals(session: AsyncSession) -> dict[str, int]:
    board = await fetch_board_columns(settings.MONDAY_BOARD_ID)
    columns_by_id = {
        column["id"]: column
        for column in board.get("columns", [])
    }

    items = await fetch_board_items(settings.MONDAY_BOARD_ID)
    processed = 0
    created = 0
    updated = 0

    for item in items:
        processed += 1
        columns = _column_lookup(item, columns_by_id)

        visual_data = {
            "monday_item_id": item.get("id"),
            "name": item.get("name") or "",
            "status": _column_text(_get_column(columns, "status", "statut")),
            "power_bi_url": _extract_url(
                _get_column(columns, "powerbivisual", "lien_internet1")
            ),
            "file_url": _extract_url(_get_column(columns, "file", "fichier", "fichier7")),
            "kam": _column_text(_get_column(columns, "kam", "personnes")),
            "vp_sales": _column_text(_get_column(columns, "vpsales", "people__1")),
        }

        result = await session.execute(
            select(Visual).where(
                Visual.monday_item_id == visual_data["monday_item_id"]
            )
        )
        visual = result.scalar_one_or_none()

        if visual is None:
            session.add(Visual(**visual_data))
            created += 1
            continue

        for key, value in visual_data.items():
            setattr(visual, key, value)
        updated += 1

    await session.commit()

    return {
        "processed": processed,
        "created": created,
        "updated": updated,
    }
