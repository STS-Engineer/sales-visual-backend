import asyncio
import sys
from pathlib import Path

from sqlalchemy import delete, select
from sqlalchemy.orm import selectinload

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.db.session import AsyncSessionLocal, engine
from app.models.client import Client
from app.models.kam import Kam


REMOVALS = [
    ("Sales MAHLE", "Antoine Irthum", "antoine.irthum@avocarbon.com"),
    ("Sales BOSCH", "Lionel Clodong", "lionel.clodong@avocarbon.com"),
    ("Sales DY", "Ren Tao", "tao.ren@avocarbon.com"),
]

ADDITIONS = [
    ("Sales MAHLE", "Martin Zacny", "martin.zacny@avocarbon.com"),
    ("Sales BOSCH", "Martin Zacny", "martin.zacny@avocarbon.com"),
]


async def get_client_map(session):
    client_names = {client_name for client_name, _, _ in REMOVALS + ADDITIONS}
    result = await session.execute(
        select(Client).where(Client.name.in_(client_names))
    )
    clients = {client.name: client for client in result.scalars().all()}
    missing = sorted(client_names - set(clients))
    if missing:
        raise RuntimeError(f"Missing clients: {', '.join(missing)}")
    return clients


async def apply_updates():
    deleted_rows = []
    added_rows = []

    async with AsyncSessionLocal() as session:
        clients = await get_client_map(session)

        for client_name, kam_name, kam_email in REMOVALS:
            client = clients[client_name]
            result = await session.execute(
                select(Kam).where(
                    Kam.client_id == client.id,
                    Kam.name == kam_name,
                    Kam.email == kam_email,
                )
            )
            rows = result.scalars().all()
            for row in rows:
                deleted_rows.append(
                    {
                        "client": client_name,
                        "name": row.name,
                        "email": row.email,
                    }
                )

            await session.execute(
                delete(Kam).where(
                    Kam.client_id == client.id,
                    Kam.name == kam_name,
                    Kam.email == kam_email,
                )
            )

        for client_name, kam_name, kam_email in ADDITIONS:
            client = clients[client_name]
            result = await session.execute(
                select(Kam).where(
                    Kam.client_id == client.id,
                    Kam.name == kam_name,
                    Kam.email == kam_email,
                )
            )
            existing = result.scalar_one_or_none()
            if existing is None:
                session.add(
                    Kam(
                        client_id=client.id,
                        name=kam_name,
                        email=kam_email,
                    )
                )
                added_rows.append(
                    {
                        "client": client_name,
                        "name": kam_name,
                        "email": kam_email,
                    }
                )

        await session.commit()

        result = await session.execute(
            select(Client)
            .options(selectinload(Client.kams))
            .order_by(Client.id)
        )
        clients_with_kams = result.scalars().all()

        final_rows = []
        for client in clients_with_kams:
            for kam in sorted(client.kams, key=lambda item: item.id):
                final_rows.append(
                    {
                        "client": client.name,
                        "name": kam.name,
                        "email": kam.email,
                    }
                )

    await engine.dispose()
    return deleted_rows, added_rows, final_rows


def print_rows(title, rows):
    print(title)
    if not rows:
        print("  (none)")
        return

    for row in rows:
        print(f"  {row['client']} | {row['name']} | {row['email']}")


async def main():
    deleted_rows, added_rows, final_rows = await apply_updates()

    print_rows("Deleted rows:", deleted_rows)
    print_rows("Added rows:", added_rows)
    print_rows("Final kams table:", final_rows)
    print(f"Total count: {len(final_rows)}")


if __name__ == "__main__":
    asyncio.run(main())
