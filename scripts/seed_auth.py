import asyncio
import sys
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import selectinload

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.db.session import AsyncSessionLocal, engine
from app.models.client import Client
from app.models.user import User
from app.models.user_client import UserClient


PASSWORD = "SalesVisual2026"

USERS = [
    ("Aziza Hamrouni", "aziza.hamrouni@avocarbon.com", PASSWORD, "admin"),
    ("Franck Lagadec", "franck.lagadec@avocarbon.com", PASSWORD, "kam"),
    ("Youngjin PARK", "youngjin.park@avocarbon.com", PASSWORD, "kam"),
    ("Martin Zacny", "martin.zacny@avocarbon.com", PASSWORD, "kam"),
    ("Dean Hayward", "dean.hayward@avocarbon.com", PASSWORD, "kam"),
    ("Austin YUAN", "austin.yuan@avocarbon.com", PASSWORD, "kam"),
    ("Ren Tao", "tao.ren@avocarbon.com", PASSWORD, "kam"),
    ("Ramkumar Parthasarathi", "ramkumar.p@avocarbon.com", PASSWORD, "kam"),
]

ASSIGNMENTS = {
    "franck.lagadec@avocarbon.com": ["Sales NIDEC", "Sales Inteva", "Sales Valeo"],
    "youngjin.park@avocarbon.com": ["Sales DY"],
    "martin.zacny@avocarbon.com": ["Sales MAHLE", "Sales BOSCH"],
    "dean.hayward@avocarbon.com": ["Sales First Brand", "Sales B&D"],
    "austin.yuan@avocarbon.com": ["Sales JE"],
    "tao.ren@avocarbon.com": ["Sales JE"],
    "ramkumar.p@avocarbon.com": ["Sales Lucas"],
}


async def seed_auth():
    created_users = []
    updated_users = []
    created_assignments = []

    async with AsyncSessionLocal() as session:
        for name, email, password, role in USERS:
            result = await session.execute(select(User).where(User.email == email))
            user = result.scalar_one_or_none()
            if user is None:
                session.add(
                    User(
                        name=name,
                        email=email,
                        password=password,
                        role=role,
                        is_active=True,
                    )
                )
                created_users.append(email)
            else:
                changed = False
                for field, value in {
                    "name": name,
                    "password": password,
                    "role": role,
                    "is_active": True,
                }.items():
                    if getattr(user, field) != value:
                        setattr(user, field, value)
                        changed = True
                if changed:
                    updated_users.append(email)

        await session.flush()

        result = await session.execute(select(User).where(User.email.in_(ASSIGNMENTS.keys())))
        users_by_email = {user.email: user for user in result.scalars().all()}

        client_names = sorted({name for names in ASSIGNMENTS.values() for name in names})
        result = await session.execute(select(Client).where(Client.name.in_(client_names)))
        clients_by_name = {client.name: client for client in result.scalars().all()}
        missing_clients = sorted(set(client_names) - set(clients_by_name))
        if missing_clients:
            raise RuntimeError(f"Missing clients: {', '.join(missing_clients)}")

        for email, client_names_for_user in ASSIGNMENTS.items():
            user = users_by_email[email]
            for client_name in client_names_for_user:
                client = clients_by_name[client_name]
                result = await session.execute(
                    select(UserClient).where(
                        UserClient.user_id == user.id,
                        UserClient.client_id == client.id,
                    )
                )
                if result.scalar_one_or_none() is None:
                    session.add(UserClient(user_id=user.id, client_id=client.id))
                    created_assignments.append((email, client_name))

        await session.commit()

        result = await session.execute(
            select(User)
            .options(selectinload(User.user_clients).selectinload(UserClient.client))
            .order_by(User.role, User.name)
        )
        users = result.scalars().all()

    await engine.dispose()
    return created_users, updated_users, created_assignments, users


def print_results(created_users, updated_users, created_assignments, users):
    print("Created users:")
    if created_users:
        for email in created_users:
            print(f"  {email}")
    else:
        print("  (none)")

    print("Updated users:")
    if updated_users:
        for email in updated_users:
            print(f"  {email}")
    else:
        print("  (none)")

    print("Created user_clients:")
    if created_assignments:
        for email, client_name in created_assignments:
            print(f"  {email} -> {client_name}")
    else:
        print("  (none)")

    print("Seeded users and assignments:")
    for user in users:
        client_names = sorted(user_client.client.name for user_client in user.user_clients)
        clients_display = ", ".join(client_names) if client_names else "-"
        print(f"  {user.id} | {user.name} | {user.email} | {user.role} | {clients_display}")


async def main():
    created_users, updated_users, created_assignments, users = await seed_auth()
    print_results(created_users, updated_users, created_assignments, users)


if __name__ == "__main__":
    asyncio.run(main())
