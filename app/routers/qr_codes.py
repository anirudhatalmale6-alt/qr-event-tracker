"""CRUD router for QR codes + QR image generation."""

from __future__ import annotations

import io
import uuid

from fastapi import APIRouter, Depends, HTTPException, Response, status
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.deps import verify_api_key
from app.models import QRCode
from app.schemas import QRCodeCreate, QRCodeOut, QRCodeUpdate

router = APIRouter(
    prefix="/api/v1/qr-codes",
    tags=["qr-codes"],
    dependencies=[Depends(verify_api_key)],
)

# Separate router for /api/v1/qr/generate (different prefix)
generate_router = APIRouter(
    prefix="/api/v1/qr",
    tags=["qr-codes"],
    dependencies=[Depends(verify_api_key)],
)


# ---------------------------------------------------------------------------
# LIST
# ---------------------------------------------------------------------------
@router.get("/", response_model=list[QRCodeOut])
async def list_qr_codes(
    skip: int = 0,
    limit: int = 100,
    campaign_id: int | None = None,
    db: AsyncSession = Depends(get_db),
) -> list[QRCode]:
    """Return QR codes with optional campaign_id filter."""
    stmt = select(QRCode).order_by(QRCode.id)

    if campaign_id is not None:
        stmt = stmt.where(QRCode.campaign_id == campaign_id)

    stmt = stmt.offset(skip).limit(limit)
    result = await db.execute(stmt)
    return list(result.scalars().all())


# ---------------------------------------------------------------------------
# GET ONE
# ---------------------------------------------------------------------------
@router.get("/{qr_code_id}", response_model=QRCodeOut)
async def get_qr_code(
    qr_code_id: int,
    db: AsyncSession = Depends(get_db),
) -> QRCode:
    """Return a single QR code by ID."""
    result = await db.execute(select(QRCode).where(QRCode.id == qr_code_id))
    qr = result.scalar_one_or_none()
    if qr is None:
        raise HTTPException(status_code=404, detail="QR code not found.")
    return qr


# ---------------------------------------------------------------------------
# CREATE
# ---------------------------------------------------------------------------
@router.post("/", response_model=QRCodeOut, status_code=status.HTTP_201_CREATED)
async def create_qr_code(
    payload: QRCodeCreate,
    db: AsyncSession = Depends(get_db),
) -> QRCode:
    """Create a new QR code.  A UUID code is auto-generated."""
    qr = QRCode(
        **payload.model_dump(),
        code=str(uuid.uuid4()),
    )
    db.add(qr)
    await db.flush()
    await db.refresh(qr)
    return qr


# ---------------------------------------------------------------------------
# UPDATE
# ---------------------------------------------------------------------------
@router.put("/{qr_code_id}", response_model=QRCodeOut)
async def update_qr_code(
    qr_code_id: int,
    payload: QRCodeUpdate,
    db: AsyncSession = Depends(get_db),
) -> QRCode:
    """Update an existing QR code."""
    result = await db.execute(select(QRCode).where(QRCode.id == qr_code_id))
    qr = result.scalar_one_or_none()
    if qr is None:
        raise HTTPException(status_code=404, detail="QR code not found.")

    update_data = payload.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(qr, field, value)

    await db.flush()
    await db.refresh(qr)
    return qr


# ---------------------------------------------------------------------------
# SOFT DELETE
# ---------------------------------------------------------------------------
@router.delete("/{qr_code_id}", status_code=status.HTTP_204_NO_CONTENT, response_class=Response)
async def delete_qr_code(
    qr_code_id: int,
    db: AsyncSession = Depends(get_db),
) -> Response:
    """Soft-delete a QR code by setting is_active = False."""
    result = await db.execute(select(QRCode).where(QRCode.id == qr_code_id))
    qr = result.scalar_one_or_none()
    if qr is None:
        raise HTTPException(status_code=404, detail="QR code not found.")

    qr.is_active = False
    await db.flush()


# ---------------------------------------------------------------------------
# GENERATE QR PNG
# ---------------------------------------------------------------------------
@generate_router.get("/generate/{qr_code_id}")
async def generate_qr_image(
    qr_code_id: int,
    db: AsyncSession = Depends(get_db),
) -> StreamingResponse:
    """Generate a QR-code PNG image for the given qr_code_id.

    The QR code encodes the public scan URL:
        https://yourdomain.com/scan/{code}

    Requires the ``qrcode`` and ``Pillow`` packages::

        pip install qrcode[pil]
    """
    result = await db.execute(select(QRCode).where(QRCode.id == qr_code_id))
    qr = result.scalar_one_or_none()
    if qr is None:
        raise HTTPException(status_code=404, detail="QR code not found.")

    from app.config import get_settings
    from app.services.qr_generator import generate_qr_image

    settings = get_settings()
    base_url = getattr(settings, "BASE_URL", "http://localhost:8000")
    scan_url = f"{base_url}/scan/{qr.code}"

    png_bytes = generate_qr_image(scan_url, label=qr.label)
    buf = io.BytesIO(png_bytes)

    return StreamingResponse(
        buf,
        media_type="image/png",
        headers={
            "Content-Disposition": f'inline; filename="qr_{qr.code}.png"',
        },
    )
