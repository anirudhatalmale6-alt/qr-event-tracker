"""Public user registration endpoint for QR scan flow."""

from __future__ import annotations

from datetime import date
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
    gender: str | None = None
    date_of_birth: date | None = None
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
            gender=data.gender,
            date_of_birth=data.date_of_birth,
        )
        db.add(user)
        await db.flush()
    else:
        if data.gender and not user.gender:
            user.gender = data.gender
        if data.date_of_birth and not user.date_of_birth:
            user.date_of_birth = data.date_of_birth
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
