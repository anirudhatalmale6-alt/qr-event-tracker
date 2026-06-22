"""CRUD router for Gym management."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.database import get_db
from app.models import Gym
from app.schemas import GymCreate, GymOut, GymUpdate

settings = get_settings()

router = APIRouter(prefix="/api/v1/gyms", tags=["gyms"])


def _require_api_key(request: Request) -> None:
    key = request.headers.get("X-API-Key", "")
    if key != settings.API_KEY:
        raise HTTPException(status_code=403, detail="Invalid API key")


@router.get("", response_model=list[GymOut])
async def list_gyms(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    _require_api_key(request)
    result = await db.execute(
        select(Gym).where(Gym.is_active.is_(True)).order_by(Gym.name)
    )
    return result.scalars().all()


@router.get("/{gym_id}", response_model=GymOut)
async def get_gym(
    gym_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    _require_api_key(request)
    result = await db.execute(select(Gym).where(Gym.id == gym_id))
    gym = result.scalar_one_or_none()
    if gym is None:
        raise HTTPException(status_code=404, detail="Gym not found")
    return gym


@router.post("", response_model=GymOut, status_code=201)
async def create_gym(
    data: GymCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    _require_api_key(request)
    gym = Gym(**data.model_dump())
    db.add(gym)
    await db.flush()
    return gym


@router.put("/{gym_id}", response_model=GymOut)
async def update_gym(
    gym_id: int,
    data: GymUpdate,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    _require_api_key(request)
    result = await db.execute(select(Gym).where(Gym.id == gym_id))
    gym = result.scalar_one_or_none()
    if gym is None:
        raise HTTPException(status_code=404, detail="Gym not found")
    for key, value in data.model_dump(exclude_unset=True).items():
        setattr(gym, key, value)
    await db.flush()
    return gym


@router.delete("/{gym_id}", response_class=Response, status_code=204)
async def delete_gym(
    gym_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> Response:
    _require_api_key(request)
    result = await db.execute(select(Gym).where(Gym.id == gym_id))
    gym = result.scalar_one_or_none()
    if gym is None:
        raise HTTPException(status_code=404, detail="Gym not found")
    gym.is_active = False
    await db.flush()
    return Response(status_code=204)
