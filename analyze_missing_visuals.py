"""
Analyze visuals whose names were NOT matched to any client
during the initial migration to monthly_reports.

Shows: name → count → sample end_dates
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import AsyncSessionLocal
from app.models.client import Client
from app.models.visual import Visual


async def run():
    async with AsyncSessionLocal() as session:
        # Get all client names (normalized for comparison)
        result = await session.execute(
            select(Client).where(Client.is_active.is_(True)).order_by(Client.name)
        )
        clients = result.scalars().all()
        client_names_normalized = {
            c.name.replace(" ", "").lower(): c.name for c in clients
        }
        print("Client names in DB:")
        for c in clients:
            print(f"  '{c.name}' → normalized: '{c.name.replace(' ', '').lower()}'")
        print()

        # Get all distinct visual names with counts
        result = await session.execute(
            select(Visual.name, func.count(Visual.id))
            .group_by(Visual.name)
            .order_by(Visual.name)
        )
        all_visual_names = result.all()

        print(f"Total distinct visual names: {len(all_visual_names)}")
        print()

        unmatched = []
        for name, count in all_visual_names:
            norm = name.replace(" ", "").lower()
            matched = False
            for client_norm, client_orig in client_names_normalized.items():
                if norm == client_norm:
                    matched = True
                    break
            if not matched:
                unmatched.append((name, count))

        print(f"UNMATCHED visual names ({len(unmatched)}):")
        print("-" * 70)
        for name, count in sorted(unmatched, key=lambda x: -x[1]):
            # Get sample end_dates
            result = await session.execute(
                select(Visual.end_date)
                .where(Visual.name == name)
                .limit(3)
            )
            dates = [str(r[0]) if r[0] else "None" for r in result.all()]
            print(f"  '{name}': {count} rows — sample end_dates: {dates}")

        print()
        print("MATCHED visual names:")
        print("-" * 70)
        matched_names = [n for n in all_visual_names if n not in unmatched]
        for name, count in sorted(matched_names, key=lambda x: -x[1]):
            print(f"  '{name}': {count} rows")

    print()
    print("Done.")


if __name__ == "__main__":
    asyncio.run(run())