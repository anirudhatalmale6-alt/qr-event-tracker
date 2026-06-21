"""Async IP geolocation service using the free ip-api.com endpoint.

Provides in-memory caching with configurable TTL to minimise external
lookups and stay within the free-tier rate limits (45 req/min).

Usage:
    geo = await get_geolocation("203.0.113.42")
    # geo == {"city": "Sydney", "region": "New South Wales", "country": "Australia"}
"""

from __future__ import annotations

import ipaddress
import logging
import time
from typing import Any

import httpx
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models import ScanEvent

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Module-level in-memory cache: {ip: (result_dict, timestamp)}
# ---------------------------------------------------------------------------
_cache: dict[str, tuple[dict[str, str], float]] = {}

# Default geo result returned for private/unreachable IPs.
_UNKNOWN_GEO: dict[str, str] = {
    "city": "Unknown",
    "region": "Unknown",
    "country": "Unknown",
}

# ip-api.com free endpoint (HTTP only -- HTTPS requires paid plan).
_IP_API_URL = "http://ip-api.com/json/{ip}"

# Timeout for outbound HTTP requests (seconds).
_REQUEST_TIMEOUT = 5.0


# ---------------------------------------------------------------------------
# Private-IP detection
# ---------------------------------------------------------------------------
def _is_private_ip(ip: str) -> bool:
    """Return True if *ip* is a private, loopback, or link-local address.

    Covers 127.x.x.x, 10.x.x.x, 192.168.x.x, 172.16-31.x.x, and IPv6
    equivalents (::1, fe80::, fc00::).
    """
    try:
        addr = ipaddress.ip_address(ip)
        return addr.is_private or addr.is_loopback or addr.is_link_local
    except ValueError:
        # Unparseable string -- treat as private to avoid leaking bad data.
        return True


# ---------------------------------------------------------------------------
# Cache helpers
# ---------------------------------------------------------------------------
def _get_cached(ip: str, ttl: int) -> dict[str, str] | None:
    """Return cached geo data if the entry exists and hasn't expired."""
    entry = _cache.get(ip)
    if entry is None:
        return None
    data, ts = entry
    if time.monotonic() - ts > ttl:
        del _cache[ip]
        return None
    return data


def _set_cached(ip: str, data: dict[str, str]) -> None:
    """Store geo data in the in-memory cache."""
    _cache[ip] = (data, time.monotonic())


def clear_cache() -> None:
    """Flush the entire geolocation cache (useful for testing)."""
    _cache.clear()


# ---------------------------------------------------------------------------
# Core lookup
# ---------------------------------------------------------------------------
async def get_geolocation(ip: str) -> dict[str, str]:
    """Resolve *ip* to ``{city, region, country}`` via ip-api.com.

    * Private / loopback addresses return ``_UNKNOWN_GEO`` immediately.
    * Results are cached in-memory for ``GEOLOCATION_CACHE_TTL`` seconds
      (default 24 h) to avoid redundant lookups.
    * On API failure the function returns ``_UNKNOWN_GEO`` rather than
      raising, so callers never need to handle geolocation errors.
    """
    if not ip or _is_private_ip(ip):
        return dict(_UNKNOWN_GEO)

    settings = get_settings()
    ttl: int = settings.GEOLOCATION_CACHE_TTL

    # Check cache first.
    cached = _get_cached(ip, ttl)
    if cached is not None:
        return dict(cached)  # return a copy to prevent mutation

    # Query ip-api.com.
    try:
        async with httpx.AsyncClient(timeout=_REQUEST_TIMEOUT) as client:
            resp = await client.get(_IP_API_URL.format(ip=ip))
            resp.raise_for_status()
            payload: dict[str, Any] = resp.json()

        if payload.get("status") == "success":
            geo = {
                "city": payload.get("city", "Unknown"),
                "region": payload.get("regionName", "Unknown"),
                "country": payload.get("country", "Unknown"),
            }
        else:
            # ip-api returns {"status": "fail", "message": "..."} for
            # reserved ranges or other issues.
            logger.warning(
                "ip-api returned failure for %s: %s",
                ip,
                payload.get("message", "unknown reason"),
            )
            geo = dict(_UNKNOWN_GEO)

    except httpx.HTTPStatusError as exc:
        logger.warning(
            "ip-api HTTP %s for %s: %s",
            exc.response.status_code,
            ip,
            exc.response.text[:200],
        )
        geo = dict(_UNKNOWN_GEO)

    except (httpx.RequestError, Exception) as exc:
        logger.warning("Geolocation lookup failed for %s: %s", ip, exc)
        geo = dict(_UNKNOWN_GEO)

    _set_cached(ip, geo)
    return dict(geo)


# ---------------------------------------------------------------------------
# Database helper
# ---------------------------------------------------------------------------
async def update_scan_event_geo(
    db: AsyncSession,
    scan_event_id: int,
    geo: dict[str, str],
) -> None:
    """Persist geolocation data on an existing ScanEvent row.

    Parameters
    ----------
    db:
        An active async SQLAlchemy session.
    scan_event_id:
        Primary key of the ScanEvent to update.
    geo:
        Dict with ``city``, ``region``, and ``country`` keys (as returned
        by :func:`get_geolocation`).
    """
    stmt = (
        update(ScanEvent)
        .where(ScanEvent.id == scan_event_id)
        .values(
            city=geo.get("city", "Unknown"),
            region=geo.get("region", "Unknown"),
            country=geo.get("country", "Unknown"),
        )
    )
    await db.execute(stmt)
    await db.flush()
