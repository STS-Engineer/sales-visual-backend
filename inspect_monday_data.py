"""Inspect Monday.com data format for date and status columns."""
import asyncio, json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))

from app.core.monday_client import fetch_sample_board_items, fetch_board_columns
from app.core.config import settings

async def run():
    board = await fetch_board_columns(settings.MONDAY_BOARD_ID)
    print("Columns:")
    for c in board.get("columns", []):
        print(f"  {c['id']}: {c['title']} ({c['type']})")
    
    items = await fetch_sample_board_items(settings.MONDAY_BOARD_ID)
    print(f"\nSample items: {len(items)}")
    for item in items[:3]:
        print(f"\nItem: {item.get('name')}")
        for cv in item.get("column_values", []):
            cid = cv.get("id", "")
            if "date" in cid.lower() or "status" in cid.lower() or cid in ("date", "date4", "status", "status_1"):
                val = cv.get("value")
                if val and len(val) > 200:
                    val = val[:200] + "..."
                print(f"  {cid}: text={cv.get('text')}, value={val}")

asyncio.run(run())