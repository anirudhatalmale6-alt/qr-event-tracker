"""Analytics and reporting endpoints with CSV export."""

from __future__ import annotations

import csv
import io
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.deps import verify_api_key
from app.schemas import ReportFilters
from app.services.reports import REPORT_REGISTRY, run_report

router = APIRouter(
    prefix="/api/v1",
    tags=["reports"],
    dependencies=[Depends(verify_api_key)],
)

_VALID_REPORT_TYPES = list(REPORT_REGISTRY.keys())


# ---------------------------------------------------------------------------
# Helper: build ReportFilters from query params
# ---------------------------------------------------------------------------

def _build_filters(
    date_from: datetime | None = Query(None),
    date_to: datetime | None = Query(None),
    company_id: int | None = Query(None),
    campaign_id: int | None = Query(None),
    qr_code_id: int | None = Query(None),
    city: str | None = Query(None),
    region: str | None = Query(None),
    country: str | None = Query(None),
    device_type: str | None = Query(None),
    browser: str | None = Query(None),
    os: str | None = Query(None),
) -> ReportFilters:
    return ReportFilters(
        date_from=date_from,
        date_to=date_to,
        company_id=company_id,
        campaign_id=campaign_id,
        qr_code_id=qr_code_id,
        city=city,
        region=region,
        country=country,
        device_type=device_type,
        browser=browser,
        os=os,
    )


# ---------------------------------------------------------------------------
# GET /api/v1/reports/{report_type}
# ---------------------------------------------------------------------------

@router.get("/reports/{report_type}")
async def get_report(
    report_type: str,
    filters: ReportFilters = Depends(_build_filters),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Run a named report and return JSON results.

    Valid report_type values:
    - scans-per-campaign
    - scans-per-company
    - scans-by-geography
    - scans-by-device
    - scans-by-hour
    - scans-by-day-of-week
    - top-campaigns
    - unique-vs-repeat
    - campaign-comparison
    - scans-per-location
    - user-demographics
    - campaign-roi
    - trend-analysis
    - geographic-heatmap
    - conversion-funnel
    """
    if report_type not in REPORT_REGISTRY:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown report type: {report_type}. "
                   f"Valid types: {_VALID_REPORT_TYPES}",
        )

    try:
        data = await run_report(db, report_type, filters)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    if isinstance(data, dict):
        return {
            "report_type": report_type,
            "filters": filters.model_dump(exclude_none=True),
            "data": data,
        }

    return {
        "report_type": report_type,
        "filters": filters.model_dump(exclude_none=True),
        "count": len(data),
        "data": _serialise(data),
    }


# ---------------------------------------------------------------------------
# GET /api/v1/export/{report_type}?format=csv
# ---------------------------------------------------------------------------

@router.get("/export/{report_type}")
async def export_report(
    report_type: str,
    format: str = Query("csv", pattern="^csv$"),
    filters: ReportFilters = Depends(_build_filters),
    db: AsyncSession = Depends(get_db),
) -> StreamingResponse:
    """Export a report as CSV (streamed)."""
    if report_type not in REPORT_REGISTRY:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown report type: {report_type}. "
                   f"Valid types: {_VALID_REPORT_TYPES}",
        )

    try:
        data = await run_report(db, report_type, filters)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    if isinstance(data, dict):
        data = [data]
    else:
        data = _serialise(data)

    # Build CSV in-memory
    buf = io.StringIO()
    if data:
        writer = csv.DictWriter(buf, fieldnames=list(data[0].keys()))
        writer.writeheader()
        writer.writerows(data)
    buf.seek(0)

    filename = f"{report_type}.csv"

    return StreamingResponse(
        iter([buf.getvalue()]),
        media_type="text/csv",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
        },
    )


# ---------------------------------------------------------------------------
# Helper: ensure all values are JSON-serialisable
# ---------------------------------------------------------------------------

def _serialise(rows: list[dict]) -> list[dict]:
    """Convert datetime / date / Decimal values to strings for JSON."""
    clean: list[dict] = []
    for row in rows:
        out = {}
        for k, v in row.items():
            if isinstance(v, datetime):
                out[k] = v.isoformat()
            elif hasattr(v, "isoformat"):  # date objects
                out[k] = v.isoformat()
            elif v is not None and not isinstance(v, (str, int, float, bool)):
                out[k] = str(v)
            else:
                out[k] = v
        clean.append(out)
    return clean
