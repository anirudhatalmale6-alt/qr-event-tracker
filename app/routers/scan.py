"""Public scan endpoint -- records the event and redirects."""

from __future__ import annotations

import re
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, Response
from fastapi.responses import RedirectResponse
from slowapi import Limiter
from slowapi.util import get_remote_address
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.database import get_db
from app.models import QRCode, ScanEvent

router = APIRouter(tags=["scan"])
_settings = get_settings()
limiter = Limiter(key_func=get_remote_address)


# ---------------------------------------------------------------------------
# Lightweight UA parser (no external dependencies)
# ---------------------------------------------------------------------------

_MOBILE_RE = re.compile(
    r"(iPhone|iPod|Android.*Mobile|webOS|BlackBerry|Opera Mini|IEMobile|Windows Phone)",
    re.I,
)
_TABLET_RE = re.compile(r"(iPad|Android(?!.*Mobile)|Tablet|Kindle|Silk)", re.I)


def _parse_device_type(ua: str) -> str:
    if _TABLET_RE.search(ua):
        return "tablet"
    if _MOBILE_RE.search(ua):
        return "mobile"
    return "desktop"


def _parse_browser(ua: str) -> str:
    # Order matters: check specific browsers before generic engines
    patterns: list[tuple[str, re.Pattern[str]]] = [
        ("Edge", re.compile(r"Edg(?:e|A|iOS)?/", re.I)),
        ("Opera", re.compile(r"(?:OPR|Opera)/", re.I)),
        ("Samsung Internet", re.compile(r"SamsungBrowser/", re.I)),
        ("UCBrowser", re.compile(r"UCBrowser/", re.I)),
        ("Firefox", re.compile(r"Firefox/", re.I)),
        ("Chrome", re.compile(r"Chrome/", re.I)),
        ("Safari", re.compile(r"Safari/", re.I)),
    ]
    for name, pat in patterns:
        if pat.search(ua):
            return name
    return "Other"


def _parse_os(ua: str) -> str:
    patterns: list[tuple[str, re.Pattern[str]]] = [
        ("iOS", re.compile(r"(iPhone|iPad|iPod)", re.I)),
        ("Android", re.compile(r"Android", re.I)),
        ("Windows", re.compile(r"Windows NT", re.I)),
        ("macOS", re.compile(r"Macintosh", re.I)),
        ("Linux", re.compile(r"Linux", re.I)),
        ("Chrome OS", re.compile(r"CrOS", re.I)),
    ]
    for name, pat in patterns:
        if pat.search(ua):
            return name
    return "Other"


# ---------------------------------------------------------------------------
# Background geolocation task
# ---------------------------------------------------------------------------

async def _do_geolocation(scan_event_id: int, ip_address: str | None) -> None:
    """Look up geo data for the IP and update the scan_event row.

    This runs as a FastAPI BackgroundTask so the redirect is not blocked.
    """
    if not ip_address or ip_address in ("127.0.0.1", "::1"):
        return

    from app.database import async_session
    from app.services.geolocation import get_geolocation, update_scan_event_geo

    geo = await get_geolocation(ip_address)
    async with async_session() as session:
        await update_scan_event_geo(session, scan_event_id, geo)
        await session.commit()


# ---------------------------------------------------------------------------
# GET /scan/{code}
# ---------------------------------------------------------------------------

@router.get("/scan/{code}", response_class=RedirectResponse)
async def scan(
    code: str,
    request: Request,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
) -> RedirectResponse:
    """Record the scan event and 302-redirect to the target URL."""

    # 1. Look up QR code ------------------------------------------------
    result = await db.execute(
        select(QRCode).where(QRCode.code == code, QRCode.is_active.is_(True))
    )
    qr = result.scalar_one_or_none()
    if qr is None:
        raise HTTPException(status_code=404, detail="QR code not found or inactive.")

    # 2. Session cookie -------------------------------------------------
    session_id = request.cookies.get("qr_session")
    if not session_id:
        session_id = str(uuid.uuid4())

    # 3. Parse User-Agent -----------------------------------------------
    ua = request.headers.get("user-agent", "")
    device_type = _parse_device_type(ua)
    browser = _parse_browser(ua)
    os_name = _parse_os(ua)

    # 4. Determine IP address -------------------------------------------
    ip_address = request.headers.get("x-forwarded-for", "")
    if ip_address:
        ip_address = ip_address.split(",")[0].strip()
    else:
        ip_address = request.client.host if request.client else None

    # 5. Create scan event record ---------------------------------------
    scan_event = ScanEvent(
        qr_code_id=qr.id,
        ip_address=ip_address,
        user_agent=ua,
        device_type=device_type,
        browser=browser,
        os=os_name,
        referrer=request.headers.get("referer"),
        session_id=session_id,
        scanned_at=datetime.now(timezone.utc),
    )
    db.add(scan_event)
    await db.flush()  # get the id without committing (commit in get_db)

    # 6. Schedule geolocation in background -----------------------------
    background_tasks.add_task(_do_geolocation, scan_event.id, ip_address)

    # 7. Redirect -------------------------------------------------------
    redirect = RedirectResponse(url=qr.redirect_url, status_code=302)
    redirect.set_cookie(
        key="qr_session",
        value=session_id,
        max_age=60 * 60 * 24 * 365,  # 1 year
        httponly=True,
        samesite="lax",
    )
    return redirect
