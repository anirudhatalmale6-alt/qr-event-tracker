"""CRUD router for campaigns."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.deps import verify_api_key
from app.models import Campaign
from app.schemas import CampaignCreate, CampaignOut, CampaignUpdate

router = APIRouter(
    prefix="/api/v1/campaigns",
    tags=["campaigns"],
    dependencies=[Depends(verify_api_key)],
)


# ---------------------------------------------------------------------------
# LIST
# ---------------------------------------------------------------------------
@router.get("/", response_model=list[CampaignOut])
async def list_campaigns(
    skip: int = 0,
    limit: int = 100,
    company_id: int | None = None,
    is_active: bool | None = None,
    db: AsyncSession = Depends(get_db),
) -> list[Campaign]:
    """Return campaigns with optional company_id and is_active filters."""
    stmt = select(Campaign).order_by(Campaign.id)

    if company_id is not None:
        stmt = stmt.where(Campaign.company_id == company_id)
    if is_active is not None:
        stmt = stmt.where(Campaign.is_active.is_(is_active))

    stmt = stmt.offset(skip).limit(limit)
    result = await db.execute(stmt)
    return list(result.scalars().all())


# ---------------------------------------------------------------------------
# GET ONE
# ---------------------------------------------------------------------------
@router.get("/{campaign_id}", response_model=CampaignOut)
async def get_campaign(
    campaign_id: int,
    db: AsyncSession = Depends(get_db),
) -> Campaign:
    """Return a single campaign by ID."""
    result = await db.execute(select(Campaign).where(Campaign.id == campaign_id))
    campaign = result.scalar_one_or_none()
    if campaign is None:
        raise HTTPException(status_code=404, detail="Campaign not found.")
    return campaign


# ---------------------------------------------------------------------------
# CREATE
# ---------------------------------------------------------------------------
@router.post("/", response_model=CampaignOut, status_code=status.HTTP_201_CREATED)
async def create_campaign(
    payload: CampaignCreate,
    db: AsyncSession = Depends(get_db),
) -> Campaign:
    """Create a new campaign."""
    campaign = Campaign(**payload.model_dump())
    db.add(campaign)
    await db.flush()
    await db.refresh(campaign)
    return campaign


# ---------------------------------------------------------------------------
# UPDATE
# ---------------------------------------------------------------------------
@router.put("/{campaign_id}", response_model=CampaignOut)
async def update_campaign(
    campaign_id: int,
    payload: CampaignUpdate,
    db: AsyncSession = Depends(get_db),
) -> Campaign:
    """Update an existing campaign."""
    result = await db.execute(select(Campaign).where(Campaign.id == campaign_id))
    campaign = result.scalar_one_or_none()
    if campaign is None:
        raise HTTPException(status_code=404, detail="Campaign not found.")

    update_data = payload.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(campaign, field, value)

    await db.flush()
    await db.refresh(campaign)
    return campaign


# ---------------------------------------------------------------------------
# SOFT DELETE
# ---------------------------------------------------------------------------
@router.delete("/{campaign_id}", status_code=status.HTTP_204_NO_CONTENT, response_class=Response)
async def delete_campaign(
    campaign_id: int,
    db: AsyncSession = Depends(get_db),
) -> Response:
    """Soft-delete a campaign by setting is_active = False."""
    result = await db.execute(select(Campaign).where(Campaign.id == campaign_id))
    campaign = result.scalar_one_or_none()
    if campaign is None:
        raise HTTPException(status_code=404, detail="Campaign not found.")

    campaign.is_active = False
    await db.flush()
