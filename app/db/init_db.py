import asyncio

from app.db.base import Base
from app.models.client import Client  # noqa: F401
from app.models.kam import Kam  # noqa: F401
from app.models.monthly_report import MonthlyReport  # noqa: F401
from app.models.notification_log import NotificationLog  # noqa: F401
from app.db.session import engine
from app.models.visual import Visual  # noqa: F401


async def init_db() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


if __name__ == "__main__":
    asyncio.run(init_db())
