"""Public user registration endpoint for QR scan flow."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, EmailStr
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import ScanEvent, ScanUser, User

router = APIRouter(prefix="/api/v1", tags=["register"])


class RegisterRequest(BaseModel):
    """Registration form data from the public page."""

    email: EmailStr
    name: str | None = None
    age_range: str | None = None
    gender: str | None = None
    city: str | None = None
    phone: str | None = None
    referral_source: str | None = None
    scan_id: int | None = None
    redirect_url: str | None = None


class RegisterResponse(BaseModel):
    user_id: int
    redirect_url: str


@router.post("/register", response_model=RegisterResponse)
async def register_user(
    data: RegisterRequest,
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Register a user (or find existing) and link to a scan event.

    This endpoint is PUBLIC -- no API key required.
    """
    # 1. Find or create user by email
    result = await db.execute(
        select(User).where(User.email == data.email)
    )
    user = result.scalar_one_or_none()

    if user is None:
        user = User(
            email=data.email,
            name=data.name,
            age_range=data.age_range,
            gender=data.gender,
            city=data.city,
            phone=data.phone,
            referral_source=data.referral_source,
        )
        db.add(user)
        await db.flush()
    else:
        # Update fields if they were empty before
        if data.name and not user.name:
            user.name = data.name
        if data.age_range and not user.age_range:
            user.age_range = data.age_range
        if data.gender and not user.gender:
            user.gender = data.gender
        if data.city and not user.city:
            user.city = data.city
        if data.phone and not user.phone:
            user.phone = data.phone
        if data.referral_source and not user.referral_source:
            user.referral_source = data.referral_source
        await db.flush()

    # 2. Link scan event to user (if scan_id provided)
    if data.scan_id:
        # Verify scan event exists
        scan_result = await db.execute(
            select(ScanEvent).where(ScanEvent.id == data.scan_id)
        )
        scan_event = scan_result.scalar_one_or_none()
        if scan_event:
            # Check if link already exists
            existing = await db.execute(
                select(ScanUser).where(
                    ScanUser.scan_event_id == data.scan_id,
                    ScanUser.user_id == user.id,
                )
            )
            if existing.scalar_one_or_none() is None:
                scan_user = ScanUser(
                    scan_event_id=data.scan_id,
                    user_id=user.id,
                )
                db.add(scan_user)
                await db.flush()

    # 3. Return user_id and redirect URL
    redirect = data.redirect_url or "/"
    return {"user_id": user.id, "redirect_url": redirect}
