"""CRUD router for companies."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.deps import verify_api_key
from app.models import Company
from app.schemas import CompanyCreate, CompanyOut, CompanyUpdate

router = APIRouter(
    prefix="/api/v1/companies",
    tags=["companies"],
    dependencies=[Depends(verify_api_key)],
)


# ---------------------------------------------------------------------------
# LIST
# ---------------------------------------------------------------------------
@router.get("/", response_model=list[CompanyOut])
async def list_companies(
    skip: int = 0,
    limit: int = 100,
    db: AsyncSession = Depends(get_db),
) -> list[Company]:
    """Return all companies with pagination."""
    result = await db.execute(
        select(Company)
        .where(Company.is_active.is_(True))
        .offset(skip)
        .limit(limit)
        .order_by(Company.id)
    )
    return list(result.scalars().all())


# ---------------------------------------------------------------------------
# GET ONE
# ---------------------------------------------------------------------------
@router.get("/{company_id}", response_model=CompanyOut)
async def get_company(
    company_id: int,
    db: AsyncSession = Depends(get_db),
) -> Company:
    """Return a single company by ID."""
    result = await db.execute(select(Company).where(Company.id == company_id))
    company = result.scalar_one_or_none()
    if company is None:
        raise HTTPException(status_code=404, detail="Company not found.")
    return company


# ---------------------------------------------------------------------------
# CREATE
# ---------------------------------------------------------------------------
@router.post("/", response_model=CompanyOut, status_code=status.HTTP_201_CREATED)
async def create_company(
    payload: CompanyCreate,
    db: AsyncSession = Depends(get_db),
) -> Company:
    """Create a new company."""
    company = Company(**payload.model_dump())
    db.add(company)
    await db.flush()
    await db.refresh(company)
    return company


# ---------------------------------------------------------------------------
# UPDATE
# ---------------------------------------------------------------------------
@router.put("/{company_id}", response_model=CompanyOut)
async def update_company(
    company_id: int,
    payload: CompanyUpdate,
    db: AsyncSession = Depends(get_db),
) -> Company:
    """Update an existing company."""
    result = await db.execute(select(Company).where(Company.id == company_id))
    company = result.scalar_one_or_none()
    if company is None:
        raise HTTPException(status_code=404, detail="Company not found.")

    update_data = payload.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(company, field, value)

    await db.flush()
    await db.refresh(company)
    return company


# ---------------------------------------------------------------------------
# SOFT DELETE
# ---------------------------------------------------------------------------
@router.delete("/{company_id}", status_code=status.HTTP_204_NO_CONTENT, response_class=Response)
async def delete_company(
    company_id: int,
    db: AsyncSession = Depends(get_db),
) -> Response:
    """Soft-delete a company by setting is_active = False."""
    result = await db.execute(select(Company).where(Company.id == company_id))
    company = result.scalar_one_or_none()
    if company is None:
        raise HTTPException(status_code=404, detail="Company not found.")

    company.is_active = False
    await db.flush()
