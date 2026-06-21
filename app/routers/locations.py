"""CRUD router for locations and QR-location assignments."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.deps import verify_api_key
from app.models import Location, QRLocation
from app.schemas import LocationCreate, LocationOut, LocationUpdate

router = APIRouter(
    prefix="/api/v1/locations",
    tags=["locations"],
    dependencies=[Depends(verify_api_key)],
)


# ===================================================================
# Location CRUD
# ===================================================================

@router.get("/", response_model=list[LocationOut])
async def list_locations(
    skip: int = 0,
    limit: int = 100,
    db: AsyncSession = Depends(get_db),
) -> list[Location]:
    """Return all locations with pagination."""
    result = await db.execute(
        select(Location).offset(skip).limit(limit).order_by(Location.id)
    )
    return list(result.scalars().all())


@router.get("/{location_id}", response_model=LocationOut)
async def get_location(
    location_id: int,
    db: AsyncSession = Depends(get_db),
) -> Location:
    """Return a single location by ID."""
    result = await db.execute(select(Location).where(Location.id == location_id))
    loc = result.scalar_one_or_none()
    if loc is None:
        raise HTTPException(status_code=404, detail="Location not found.")
    return loc


@router.post("/", response_model=LocationOut, status_code=status.HTTP_201_CREATED)
async def create_location(
    payload: LocationCreate,
    db: AsyncSession = Depends(get_db),
) -> Location:
    """Create a new location."""
    loc = Location(**payload.model_dump())
    db.add(loc)
    await db.flush()
    await db.refresh(loc)
    return loc


@router.put("/{location_id}", response_model=LocationOut)
async def update_location(
    location_id: int,
    payload: LocationUpdate,
    db: AsyncSession = Depends(get_db),
) -> Location:
    """Update an existing location."""
    result = await db.execute(select(Location).where(Location.id == location_id))
    loc = result.scalar_one_or_none()
    if loc is None:
        raise HTTPException(status_code=404, detail="Location not found.")

    update_data = payload.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(loc, field, value)

    await db.flush()
    await db.refresh(loc)
    return loc


@router.delete("/{location_id}", status_code=status.HTTP_204_NO_CONTENT, response_class=Response)
async def delete_location(
    location_id: int,
    db: AsyncSession = Depends(get_db),
) -> Response:
    """Delete a location."""
    result = await db.execute(select(Location).where(Location.id == location_id))
    loc = result.scalar_one_or_none()
    if loc is None:
        raise HTTPException(status_code=404, detail="Location not found.")

    await db.delete(loc)
    await db.flush()


# ===================================================================
# QR-Location assignments
# ===================================================================

@router.post(
    "/{location_id}/qr-codes/{qr_code_id}",
    status_code=status.HTTP_201_CREATED,
)
async def assign_qr_to_location(
    location_id: int,
    qr_code_id: int,
    db: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    """Assign a QR code to a location."""
    # Check for existing assignment
    result = await db.execute(
        select(QRLocation).where(
            and_(
                QRLocation.qr_code_id == qr_code_id,
                QRLocation.location_id == location_id,
            )
        )
    )
    existing = result.scalar_one_or_none()
    if existing is not None:
        raise HTTPException(
            status_code=409, detail="QR code already assigned to this location."
        )

    assignment = QRLocation(qr_code_id=qr_code_id, location_id=location_id)
    db.add(assignment)
    await db.flush()
    return {"detail": "QR code assigned to location."}


@router.delete(
    "/{location_id}/qr-codes/{qr_code_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
)
async def remove_qr_from_location(
    location_id: int,
    qr_code_id: int,
    db: AsyncSession = Depends(get_db),
) -> Response:
    """Remove a QR code from a location."""
    result = await db.execute(
        select(QRLocation).where(
            and_(
                QRLocation.qr_code_id == qr_code_id,
                QRLocation.location_id == location_id,
            )
        )
    )
    assignment = result.scalar_one_or_none()
    if assignment is None:
        raise HTTPException(
            status_code=404,
            detail="QR code is not assigned to this location.",
        )

    await db.delete(assignment)
    await db.flush()
