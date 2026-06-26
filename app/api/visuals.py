from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from fastapi import APIRouter, Depends, HTTPException, Query

from app.db.session import get_db_session
from app.models.visual import Visual
from app.schemas.visual import VisualResponse

router = APIRouter(prefix="/visuals", tags=["visuals"])


@router.get("", response_model=list[VisualResponse])
async def list_visuals(
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    session: AsyncSession = Depends(get_db_session),
):
    result = await session.execute(
        select(Visual)
        .order_by(Visual.id)
        .limit(limit)
        .offset(offset)
    )
    return result.scalars().all()


@router.get("/search", response_model=list[VisualResponse])
async def search_visuals(
    q: str = Query(min_length=1),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    session: AsyncSession = Depends(get_db_session),
):
    pattern = f"%{q}%"
    result = await session.execute(
        select(Visual)
        .where(
            or_(
                Visual.name.ilike(pattern),
                Visual.status.ilike(pattern),
                Visual.kam.ilike(pattern),
                Visual.vp_sales.ilike(pattern),
                Visual.monday_item_id.ilike(pattern),
            )
        )
        .order_by(Visual.id)
        .limit(limit)
        .offset(offset)
    )
    return result.scalars().all()


@router.get("/status/{status}", response_model=list[VisualResponse])
async def get_visuals_by_status(
    status: str,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    session: AsyncSession = Depends(get_db_session),
):
    result = await session.execute(
        select(Visual)
        .where(Visual.status.ilike(status))
        .order_by(Visual.id)
        .limit(limit)
        .offset(offset)
    )
    return result.scalars().all()


@router.get("/{visual_id}", response_model=VisualResponse)
async def get_visual(
    visual_id: int,
    session: AsyncSession = Depends(get_db_session),
):
    visual = await session.get(Visual, visual_id)
    if visual is None:
        raise HTTPException(status_code=404, detail="Visual not found")
    return visual
