from sqlalchemy.ext.asyncio import AsyncSession

from fastapi import APIRouter, Depends, HTTPException

from app.core.config import settings
from app.core.monday_client import (
    fetch_board_columns,
    fetch_board_items,
    fetch_first_board_item,
    fetch_sample_board_items,
)
from app.db.session import get_db_session
from app.services.monday_sync import sync_monday_visuals

router = APIRouter(prefix="/monday", tags=["monday"])


def format_sample_item(item, columns_by_id):
    return {
        "id": item.get("id"),
        "name": item.get("name"),
        "group": (item.get("group") or {}).get("title"),
        "columns": [
            {
                "id": column_value.get("id"),
                "title": columns_by_id.get(column_value.get("id"), {}).get("title"),
                "type": column_value.get("type"),
                "text": column_value.get("text"),
                "value": column_value.get("value"),
                "display_value": column_value.get("display_value"),
            }
            for column_value in item.get("column_values", [])
        ],
    }


@router.get("/items")
async def get_monday_items():
    items = await fetch_board_items(settings.MONDAY_BOARD_ID)
    return {"count": len(items), "items": items}


@router.get("/columns")
async def get_monday_columns():
    return await fetch_board_columns(settings.MONDAY_BOARD_ID)


@router.get("/sample-item")
async def get_monday_sample_item():
    item = await fetch_first_board_item(settings.MONDAY_BOARD_ID)
    if item is None:
        raise HTTPException(status_code=404, detail="No Monday items found")

    board = await fetch_board_columns(settings.MONDAY_BOARD_ID)
    columns_by_id = {
        column["id"]: column
        for column in board.get("columns", [])
    }

    return format_sample_item(item, columns_by_id)


@router.get("/sample-items")
async def get_monday_sample_items():
    items = await fetch_sample_board_items(settings.MONDAY_BOARD_ID)

    board = await fetch_board_columns(settings.MONDAY_BOARD_ID)
    columns_by_id = {
        column["id"]: column
        for column in board.get("columns", [])
    }

    return {
        "count": len(items),
        "items": [
            format_sample_item(item, columns_by_id)
            for item in items
        ],
    }


@router.post("/sync")
async def sync_monday_board(session: AsyncSession = Depends(get_db_session)):
    return await sync_monday_visuals(session)
