from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from fastapi import APIRouter, Depends, HTTPException

from app.core.auth import get_current_user, require_admin
from app.db.session import get_db_session
from app.models.client import Client
from app.models.user import User
from app.models.user_client import UserClient
from app.schemas.client import ClientResponse, ClientUpdate, ClientWithReportsResponse

router = APIRouter(prefix="/clients", tags=["clients"])


@router.get("", response_model=list[ClientResponse])
async def list_clients(
    session: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
):
    query = (
        select(Client)
        .options(selectinload(Client.kams))
        .where(Client.is_active.is_(True))
        .order_by(Client.name)
    )
    if current_user.role != "admin":
        query = query.where(
            Client.id.in_(
                select(UserClient.client_id).where(UserClient.user_id == current_user.id)
            )
        )

    result = await session.execute(query)
    return result.scalars().all()


@router.get("/{client_id}", response_model=ClientWithReportsResponse)
async def get_client(
    client_id: int,
    session: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
):
    result = await session.execute(
        select(Client)
        .options(selectinload(Client.kams), selectinload(Client.reports))
        .where(Client.id == client_id)
    )
    client = result.scalar_one_or_none()
    if client is None:
        raise HTTPException(status_code=404, detail="Client not found")
    return client


@router.patch("/{client_id}", response_model=ClientResponse)
async def update_client(
    client_id: int,
    payload: ClientUpdate,
    session: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(require_admin),
):
    client = await session.get(Client, client_id)
    if client is None:
        raise HTTPException(status_code=404, detail="Client not found")

    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(client, field, value)

    await session.commit()
    await session.refresh(client)
    return client
