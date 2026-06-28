"""Analytics and reporting service for the QR Event Tracker.

Every public function accepts an async SQLAlchemy session and a
``ReportFilters`` object and returns a list of dicts (or a single
summary dict) ready for JSON serialisation.

The module also exposes:

* ``REPORT_REGISTRY`` -- a dict mapping report-type strings to their
  async handler functions, making it easy to dispatch from a single
  generic endpoint and to extend with new report types.
* ``to_csv()`` -- a helper that converts any list-of-dicts report
  output into a CSV string.

All database queries use SQLAlchemy async ``select`` with ``func``-based
aggregations so they are fully async-compatible.
"""

from __future__ import annotations

import csv
import io
import logging
from datetime import datetime
from typing import Any, Callable, Coroutine

from datetime import timedelta

from sqlalchemy import case, distinct, extract, func, literal_column, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings

_db_url = get_settings().DATABASE_URL
_is_sqlite = _db_url.startswith("sqlite")
_is_mysql = _db_url.startswith("mysql")

from app.models import (
    Campaign,
    Company,
    Gym,
    Location,
    QRCode,
    QRLocation,
    ScanEvent,
    ScanUser,
    User,
)
from app.schemas import ReportFilters

logger = logging.getLogger(__name__)

# Type alias for report handler functions.
ReportHandler = Callable[..., Coroutine[Any, Any, Any]]


# ---------------------------------------------------------------------------
# Filter helpers
# ---------------------------------------------------------------------------

def _apply_filters(stmt, filters: ReportFilters):
    """Append WHERE clauses shared across most reports.

    Assumes the statement already joins ScanEvent -> QRCode -> Campaign
    -> Company.  Returns the modified statement.
    """
    if filters.date_from is not None:
        stmt = stmt.where(ScanEvent.scanned_at >= filters.date_from)
    if filters.date_to is not None:
        end = filters.date_to
        if end.hour == 0 and end.minute == 0 and end.second == 0:
            end = end + timedelta(days=1)
        stmt = stmt.where(ScanEvent.scanned_at <= end)
    if filters.company_id is not None:
        stmt = stmt.where(Company.id == filters.company_id)
    if filters.campaign_id is not None:
        stmt = stmt.where(Campaign.id == filters.campaign_id)
    if filters.qr_code_id is not None:
        stmt = stmt.where(QRCode.id == filters.qr_code_id)
    if filters.gym_id is not None:
        stmt = stmt.where(QRCode.gym_id == filters.gym_id)
    if filters.city is not None:
        stmt = stmt.where(ScanEvent.city == filters.city)
    if filters.region is not None:
        stmt = stmt.where(ScanEvent.region == filters.region)
    if filters.country is not None:
        stmt = stmt.where(ScanEvent.country == filters.country)
    if filters.device_type is not None:
        stmt = stmt.where(ScanEvent.device_type == filters.device_type)
    if filters.browser is not None:
        stmt = stmt.where(ScanEvent.browser == filters.browser)
    if filters.os is not None:
        stmt = stmt.where(ScanEvent.os == filters.os)
    return stmt


# ===================================================================
# Report functions
# ===================================================================

async def scans_per_campaign(
    db: AsyncSession,
    filters: ReportFilters,
) -> list[dict[str, Any]]:
    """Total and unique scans grouped by campaign."""
    stmt = (
        select(
            Campaign.name.label("campaign_name"),
            Company.name.label("company_name"),
            func.count(ScanEvent.id).label("scan_count"),
            func.count(distinct(ScanEvent.ip_address)).label("unique_scans"),
        )
        .select_from(ScanEvent)
        .join(QRCode, ScanEvent.qr_code_id == QRCode.id)
        .join(Campaign, QRCode.campaign_id == Campaign.id)
        .join(Company, Campaign.company_id == Company.id)
        .group_by(Campaign.id, Campaign.name, Company.name)
        .order_by(func.count(ScanEvent.id).desc())
    )
    stmt = _apply_filters(stmt, filters)
    result = await db.execute(stmt)
    return [dict(row._mapping) for row in result.all()]


async def scans_per_company(
    db: AsyncSession,
    filters: ReportFilters,
) -> list[dict[str, Any]]:
    """Total scans and campaign count per company."""
    stmt = (
        select(
            Company.name.label("company_name"),
            func.count(ScanEvent.id).label("scan_count"),
            func.count(distinct(Campaign.id)).label("campaign_count"),
        )
        .select_from(ScanEvent)
        .join(QRCode, ScanEvent.qr_code_id == QRCode.id)
        .join(Campaign, QRCode.campaign_id == Campaign.id)
        .join(Company, Campaign.company_id == Company.id)
        .group_by(Company.id, Company.name)
        .order_by(func.count(ScanEvent.id).desc())
    )
    stmt = _apply_filters(stmt, filters)
    result = await db.execute(stmt)
    return [dict(row._mapping) for row in result.all()]


async def scans_by_geography(
    db: AsyncSession,
    filters: ReportFilters,
) -> list[dict[str, Any]]:
    """Scan counts grouped by country, region, and city."""
    stmt = (
        select(
            ScanEvent.country,
            ScanEvent.region,
            ScanEvent.city,
            func.count(ScanEvent.id).label("scan_count"),
        )
        .select_from(ScanEvent)
        .join(QRCode, ScanEvent.qr_code_id == QRCode.id)
        .join(Campaign, QRCode.campaign_id == Campaign.id)
        .join(Company, Campaign.company_id == Company.id)
        .group_by(ScanEvent.country, ScanEvent.region, ScanEvent.city)
        .order_by(func.count(ScanEvent.id).desc())
    )
    stmt = _apply_filters(stmt, filters)
    result = await db.execute(stmt)
    return [dict(row._mapping) for row in result.all()]


async def scans_by_device(
    db: AsyncSession,
    filters: ReportFilters,
) -> list[dict[str, Any]]:
    """Scan counts and percentages grouped by device type."""
    # Sub-query for total scans (with the same filters applied).
    total_sub = (
        select(func.count(ScanEvent.id).label("total"))
        .select_from(ScanEvent)
        .join(QRCode, ScanEvent.qr_code_id == QRCode.id)
        .join(Campaign, QRCode.campaign_id == Campaign.id)
        .join(Company, Campaign.company_id == Company.id)
    )
    total_sub = _apply_filters(total_sub, filters)
    total_result = await db.execute(total_sub)
    total: int = total_result.scalar() or 0

    stmt = (
        select(
            ScanEvent.device_type,
            func.count(ScanEvent.id).label("count"),
        )
        .select_from(ScanEvent)
        .join(QRCode, ScanEvent.qr_code_id == QRCode.id)
        .join(Campaign, QRCode.campaign_id == Campaign.id)
        .join(Company, Campaign.company_id == Company.id)
        .group_by(ScanEvent.device_type)
        .order_by(func.count(ScanEvent.id).desc())
    )
    stmt = _apply_filters(stmt, filters)
    result = await db.execute(stmt)

    rows: list[dict[str, Any]] = []
    for row in result.all():
        mapping = dict(row._mapping)
        mapping["percentage"] = (
            round(mapping["count"] / total * 100, 2) if total > 0 else 0.0
        )
        rows.append(mapping)
    return rows


async def scans_by_hour(
    db: AsyncSession,
    filters: ReportFilters,
) -> list[dict[str, Any]]:
    """Scan counts grouped by hour of day (0-23)."""
    if _is_sqlite:
        hour_col = func.strftime("%H", ScanEvent.scanned_at).label("hour")
    else:
        hour_col = extract("hour", ScanEvent.scanned_at).label("hour")
    stmt = (
        select(
            hour_col,
            func.count(ScanEvent.id).label("scan_count"),
        )
        .select_from(ScanEvent)
        .join(QRCode, ScanEvent.qr_code_id == QRCode.id)
        .join(Campaign, QRCode.campaign_id == Campaign.id)
        .join(Company, Campaign.company_id == Company.id)
        .group_by(hour_col)
        .order_by(hour_col)
    )
    stmt = _apply_filters(stmt, filters)
    result = await db.execute(stmt)
    return [dict(row._mapping) for row in result.all()]


async def scans_by_day_of_week(
    db: AsyncSession,
    filters: ReportFilters,
) -> list[dict[str, Any]]:
    """Scan counts grouped by day of week.

    Uses PostgreSQL ``EXTRACT(DOW ...)`` convention: 0=Sunday through
    6=Saturday.
    """
    if _is_sqlite:
        dow_col = func.strftime("%w", ScanEvent.scanned_at).label("day")
    elif _is_mysql:
        dow_col = (func.dayofweek(ScanEvent.scanned_at) - 1).label("day")
    else:
        dow_col = extract("dow", ScanEvent.scanned_at).label("day")
    stmt = (
        select(
            dow_col,
            func.count(ScanEvent.id).label("scan_count"),
        )
        .select_from(ScanEvent)
        .join(QRCode, ScanEvent.qr_code_id == QRCode.id)
        .join(Campaign, QRCode.campaign_id == Campaign.id)
        .join(Company, Campaign.company_id == Company.id)
        .group_by(dow_col)
        .order_by(dow_col)
    )
    stmt = _apply_filters(stmt, filters)
    result = await db.execute(stmt)
    return [dict(row._mapping) for row in result.all()]


async def top_campaigns(
    db: AsyncSession,
    filters: ReportFilters,
    limit: int = 10,
) -> list[dict[str, Any]]:
    """Top *limit* campaigns ranked by scan count."""
    stmt = (
        select(
            Campaign.name.label("campaign_name"),
            Company.name.label("company_name"),
            func.count(ScanEvent.id).label("scan_count"),
            func.count(distinct(ScanEvent.ip_address)).label("unique_scans"),
            Campaign.budget,
        )
        .select_from(ScanEvent)
        .join(QRCode, ScanEvent.qr_code_id == QRCode.id)
        .join(Campaign, QRCode.campaign_id == Campaign.id)
        .join(Company, Campaign.company_id == Company.id)
        .group_by(Campaign.id, Campaign.name, Company.name, Campaign.budget)
        .order_by(func.count(ScanEvent.id).desc())
        .limit(limit)
    )
    stmt = _apply_filters(stmt, filters)
    result = await db.execute(stmt)
    return [dict(row._mapping) for row in result.all()]


async def unique_vs_repeat(
    db: AsyncSession,
    filters: ReportFilters,
) -> list[dict[str, Any]]:
    """Total, unique, and repeat scan counts per QR code label."""
    unique_col = func.count(distinct(ScanEvent.ip_address)).label("unique_scans")
    total_col = func.count(ScanEvent.id).label("total_scans")

    stmt = (
        select(
            func.coalesce(QRCode.label, QRCode.code).label("qr_label"),
            total_col,
            unique_col,
        )
        .select_from(ScanEvent)
        .join(QRCode, ScanEvent.qr_code_id == QRCode.id)
        .join(Campaign, QRCode.campaign_id == Campaign.id)
        .join(Company, Campaign.company_id == Company.id)
        .group_by(QRCode.id, QRCode.label, QRCode.code)
        .order_by(total_col.desc())
    )
    stmt = _apply_filters(stmt, filters)
    result = await db.execute(stmt)

    rows: list[dict[str, Any]] = []
    for row in result.all():
        mapping = dict(row._mapping)
        mapping["repeat_scans"] = mapping["total_scans"] - mapping["unique_scans"]
        rows.append(mapping)
    return rows


async def campaign_comparison(
    db: AsyncSession,
    campaign_ids: list[int],
) -> list[dict[str, Any]]:
    """Side-by-side comparison of the given campaigns.

    Note: this function takes an explicit list of campaign IDs rather
    than the standard ReportFilters object.
    """
    if not campaign_ids:
        return []

    stmt = (
        select(
            Campaign.id.label("campaign_id"),
            Campaign.name.label("campaign_name"),
            Company.name.label("company_name"),
            Campaign.budget,
            Campaign.start_date,
            Campaign.end_date,
            func.count(ScanEvent.id).label("scan_count"),
            func.count(distinct(ScanEvent.ip_address)).label("unique_scans"),
            func.count(distinct(QRCode.id)).label("qr_code_count"),
        )
        .select_from(ScanEvent)
        .join(QRCode, ScanEvent.qr_code_id == QRCode.id)
        .join(Campaign, QRCode.campaign_id == Campaign.id)
        .join(Company, Campaign.company_id == Company.id)
        .where(Campaign.id.in_(campaign_ids))
        .group_by(
            Campaign.id,
            Campaign.name,
            Company.name,
            Campaign.budget,
            Campaign.start_date,
            Campaign.end_date,
        )
        .order_by(func.count(ScanEvent.id).desc())
    )
    result = await db.execute(stmt)
    return [dict(row._mapping) for row in result.all()]


async def scans_per_location(
    db: AsyncSession,
    filters: ReportFilters,
) -> list[dict[str, Any]]:
    """Scan counts grouped by physical location (from the locations table)."""
    stmt = (
        select(
            Location.name.label("location_name"),
            Location.city,
            func.count(ScanEvent.id).label("scan_count"),
        )
        .select_from(ScanEvent)
        .join(QRCode, ScanEvent.qr_code_id == QRCode.id)
        .join(QRLocation, QRCode.id == QRLocation.qr_code_id)
        .join(Location, QRLocation.location_id == Location.id)
        .join(Campaign, QRCode.campaign_id == Campaign.id)
        .join(Company, Campaign.company_id == Company.id)
        .group_by(Location.id, Location.name, Location.city)
        .order_by(func.count(ScanEvent.id).desc())
    )
    stmt = _apply_filters(stmt, filters)
    result = await db.execute(stmt)
    return [dict(row._mapping) for row in result.all()]


async def user_demographics(
    db: AsyncSession,
    filters: ReportFilters,
) -> dict[str, list[dict[str, Any]]]:
    """Demographic breakdown of scanned users: gender and age groups.

    Joins through the ScanUser association to the User table to pull
    real user demographics.

    Returns a dict with two keys:
    - ``genders``: list of ``{gender, count}``
    - ``age_groups``: list of ``{age_group, count}``
    """
    # Gender breakdown.
    gender_stmt = (
        select(
            User.gender,
            func.count(distinct(User.id)).label("count"),
        )
        .select_from(User)
        .join(ScanUser, User.id == ScanUser.user_id)
        .join(ScanEvent, ScanUser.scan_event_id == ScanEvent.id)
        .join(QRCode, ScanEvent.qr_code_id == QRCode.id)
        .join(Campaign, QRCode.campaign_id == Campaign.id)
        .join(Company, Campaign.company_id == Company.id)
        .where(User.gender.isnot(None))
        .group_by(User.gender)
        .order_by(func.count(distinct(User.id)).desc())
    )
    gender_stmt = _apply_filters(gender_stmt, filters)
    gender_result = await db.execute(gender_stmt)
    genders = [dict(row._mapping) for row in gender_result.all()]

    # Age group breakdown (derived from date_of_birth).
    if _is_sqlite:
        age_expr = func.strftime("%Y", "now") - func.strftime("%Y", User.date_of_birth)
    elif _is_mysql:
        age_expr = func.year(func.curdate()) - func.year(User.date_of_birth)
    else:
        age_expr = extract("year", func.age(User.date_of_birth))

    age_group_col = case(
        (age_expr < 18, "< 18"),
        (age_expr.between(18, 24), "18-24"),
        (age_expr.between(25, 34), "25-34"),
        (age_expr.between(35, 44), "35-44"),
        (age_expr.between(45, 54), "45-54"),
        else_="55+",
    ).label("age_group")

    age_stmt = (
        select(
            age_group_col,
            func.count(distinct(User.id)).label("count"),
        )
        .select_from(User)
        .join(ScanUser, User.id == ScanUser.user_id)
        .join(ScanEvent, ScanUser.scan_event_id == ScanEvent.id)
        .join(QRCode, ScanEvent.qr_code_id == QRCode.id)
        .join(Campaign, QRCode.campaign_id == Campaign.id)
        .join(Company, Campaign.company_id == Company.id)
        .where(User.date_of_birth.isnot(None))
        .group_by(age_group_col)
        .order_by(func.count(distinct(User.id)).desc())
    )
    age_stmt = _apply_filters(age_stmt, filters)
    age_result = await db.execute(age_stmt)
    age_groups = [dict(row._mapping) for row in age_result.all()]

    return {"genders": genders, "age_groups": age_groups}


async def campaign_roi(
    db: AsyncSession,
    filters: ReportFilters,
) -> list[dict[str, Any]]:
    """ROI metrics per campaign: budget, scan count, cost per scan."""
    stmt = (
        select(
            Campaign.name.label("campaign_name"),
            Campaign.budget,
            func.count(ScanEvent.id).label("scans"),
        )
        .select_from(ScanEvent)
        .join(QRCode, ScanEvent.qr_code_id == QRCode.id)
        .join(Campaign, QRCode.campaign_id == Campaign.id)
        .join(Company, Campaign.company_id == Company.id)
        .where(Campaign.budget.isnot(None))
        .where(Campaign.budget > 0)
        .group_by(Campaign.id, Campaign.name, Campaign.budget)
        .order_by(Campaign.name)
    )
    stmt = _apply_filters(stmt, filters)
    result = await db.execute(stmt)

    rows: list[dict[str, Any]] = []
    for row in result.all():
        mapping = dict(row._mapping)
        budget = float(mapping["budget"]) if mapping["budget"] else 0
        scans = mapping["scans"] or 0
        mapping["cost_per_scan"] = (
            round(budget / scans, 2) if scans > 0 else None
        )
        rows.append(mapping)
    return rows


async def trend_analysis(
    db: AsyncSession,
    filters: ReportFilters,
    interval: str = "day",
) -> list[dict[str, Any]]:
    """Scan counts over time with running cumulative totals.

    Parameters
    ----------
    interval:
        Grouping interval -- ``"day"``, ``"week"``, or ``"month"``.
    """
    valid_intervals = {"day", "week", "month"}
    if interval not in valid_intervals:
        interval = "day"

    if _is_sqlite:
        fmt_map = {"day": "%Y-%m-%d", "week": "%Y-%W", "month": "%Y-%m"}
        date_col = func.strftime(fmt_map[interval], ScanEvent.scanned_at).label("date")
    elif _is_mysql:
        fmt_map = {"day": "%Y-%m-%d", "week": "%x-%v", "month": "%Y-%m"}
        date_col = func.date_format(ScanEvent.scanned_at, fmt_map[interval]).label("date")
    else:
        date_col = func.date_trunc(interval, ScanEvent.scanned_at).label("date")

    stmt = (
        select(
            date_col,
            func.count(ScanEvent.id).label("scan_count"),
        )
        .select_from(ScanEvent)
        .join(QRCode, ScanEvent.qr_code_id == QRCode.id)
        .join(Campaign, QRCode.campaign_id == Campaign.id)
        .join(Company, Campaign.company_id == Company.id)
        .group_by(date_col)
        .order_by(date_col)
    )
    stmt = _apply_filters(stmt, filters)
    result = await db.execute(stmt)

    rows: list[dict[str, Any]] = []
    cumulative = 0
    for row in result.all():
        mapping = dict(row._mapping)
        cumulative += mapping["scan_count"]
        mapping["cumulative"] = cumulative
        # Convert datetime to ISO string for JSON serialisation safety.
        if isinstance(mapping["date"], datetime):
            mapping["date"] = mapping["date"].isoformat()
        rows.append(mapping)
    return rows


async def geographic_heatmap(
    db: AsyncSession,
    filters: ReportFilters,
) -> list[dict[str, Any]]:
    """Lat/lon data points for map-based heatmap visualisation.

    Joins through QRLocation -> Location to obtain coordinates, then
    groups by location to produce ``{lat, lon, count}`` rows.
    """
    stmt = (
        select(
            Location.latitude.label("lat"),
            Location.longitude.label("lon"),
            func.count(ScanEvent.id).label("count"),
        )
        .select_from(ScanEvent)
        .join(QRCode, ScanEvent.qr_code_id == QRCode.id)
        .join(QRLocation, QRCode.id == QRLocation.qr_code_id)
        .join(Location, QRLocation.location_id == Location.id)
        .join(Campaign, QRCode.campaign_id == Campaign.id)
        .join(Company, Campaign.company_id == Company.id)
        .where(Location.latitude.isnot(None))
        .where(Location.longitude.isnot(None))
        .group_by(Location.latitude, Location.longitude)
    )
    stmt = _apply_filters(stmt, filters)
    result = await db.execute(stmt)
    return [dict(row._mapping) for row in result.all()]


async def conversion_funnel(
    db: AsyncSession,
    filters: ReportFilters,
) -> dict[str, Any]:
    """High-level conversion funnel metrics.

    Returns total scans, unique visitors (distinct IPs), registered
    users who scanned, and the visitor-to-registration conversion rate.
    """
    # Total scans and unique IPs.
    scan_stmt = (
        select(
            func.count(ScanEvent.id).label("total_scans"),
            func.count(distinct(ScanEvent.ip_address)).label("unique_visitors"),
        )
        .select_from(ScanEvent)
        .join(QRCode, ScanEvent.qr_code_id == QRCode.id)
        .join(Campaign, QRCode.campaign_id == Campaign.id)
        .join(Company, Campaign.company_id == Company.id)
    )
    scan_stmt = _apply_filters(scan_stmt, filters)
    scan_result = await db.execute(scan_stmt)
    scan_row = scan_result.one()
    total_scans: int = scan_row.total_scans or 0
    unique_visitors: int = scan_row.unique_visitors or 0

    # Registered users who have at least one ScanUser link within the
    # filtered scan events.
    user_stmt = (
        select(func.count(distinct(ScanUser.user_id)).label("registered_users"))
        .select_from(ScanUser)
        .join(ScanEvent, ScanUser.scan_event_id == ScanEvent.id)
        .join(QRCode, ScanEvent.qr_code_id == QRCode.id)
        .join(Campaign, QRCode.campaign_id == Campaign.id)
        .join(Company, Campaign.company_id == Company.id)
    )
    user_stmt = _apply_filters(user_stmt, filters)
    user_result = await db.execute(user_stmt)
    registered_users: int = user_result.scalar() or 0

    conversion_rate = (
        round(registered_users / unique_visitors * 100, 2)
        if unique_visitors > 0
        else 0.0
    )

    return {
        "total_scans": total_scans,
        "unique_visitors": unique_visitors,
        "registered_users": registered_users,
        "conversion_rate": conversion_rate,
    }


# ===================================================================
# Gym / Advertiser reports
# ===================================================================


async def leads_generated(
    db: AsyncSession,
    filters: ReportFilters,
) -> list[dict[str, Any]]:
    """Count of new user registrations grouped by campaign, with date filter.

    A 'lead' = a user who registered via QR scan (exists in scan_users).
    """
    stmt = (
        select(
            Campaign.name.label("campaign_name"),
            Company.name.label("company_name"),
            func.count(distinct(User.id)).label("leads"),
        )
        .select_from(User)
        .join(ScanUser, User.id == ScanUser.user_id)
        .join(ScanEvent, ScanUser.scan_event_id == ScanEvent.id)
        .join(QRCode, ScanEvent.qr_code_id == QRCode.id)
        .join(Campaign, QRCode.campaign_id == Campaign.id)
        .join(Company, Campaign.company_id == Company.id)
        .group_by(Campaign.id, Campaign.name, Company.name)
        .order_by(func.count(distinct(User.id)).desc())
    )
    stmt = _apply_filters(stmt, filters)
    result = await db.execute(stmt)
    return [dict(row._mapping) for row in result.all()]


async def scans_by_gym(
    db: AsyncSession,
    filters: ReportFilters,
) -> list[dict[str, Any]]:
    """Scan counts grouped by gym, with classification and ATV."""
    stmt = (
        select(
            Gym.name.label("gym_name"),
            Gym.classification,
            Gym.atv,
            Gym.discipline,
            func.count(ScanEvent.id).label("scan_count"),
            func.count(distinct(ScanEvent.ip_address)).label("unique_scans"),
        )
        .select_from(ScanEvent)
        .join(QRCode, ScanEvent.qr_code_id == QRCode.id)
        .join(Gym, QRCode.gym_id == Gym.id)
        .join(Campaign, QRCode.campaign_id == Campaign.id)
        .join(Company, Campaign.company_id == Company.id)
        .group_by(Gym.id, Gym.name, Gym.classification, Gym.atv, Gym.discipline)
        .order_by(func.count(ScanEvent.id).desc())
    )
    stmt = _apply_filters(stmt, filters)
    result = await db.execute(stmt)
    return [dict(row._mapping) for row in result.all()]


async def qr_to_lead_conversion(
    db: AsyncSession,
    filters: ReportFilters,
) -> list[dict[str, Any]]:
    """Per campaign: total scans, unique scans, registered users, conversion rate."""
    # Total and unique scans per campaign
    scan_stmt = (
        select(
            Campaign.id.label("campaign_id"),
            Campaign.name.label("campaign_name"),
            Company.name.label("company_name"),
            func.count(ScanEvent.id).label("total_scans"),
            func.count(distinct(ScanEvent.ip_address)).label("unique_scans"),
        )
        .select_from(ScanEvent)
        .join(QRCode, ScanEvent.qr_code_id == QRCode.id)
        .join(Campaign, QRCode.campaign_id == Campaign.id)
        .join(Company, Campaign.company_id == Company.id)
        .group_by(Campaign.id, Campaign.name, Company.name)
    )
    scan_stmt = _apply_filters(scan_stmt, filters)
    scan_result = await db.execute(scan_stmt)
    scan_rows = {row.campaign_id: dict(row._mapping) for row in scan_result.all()}

    # Registered users per campaign
    user_stmt = (
        select(
            Campaign.id.label("campaign_id"),
            func.count(distinct(User.id)).label("registered_users"),
        )
        .select_from(User)
        .join(ScanUser, User.id == ScanUser.user_id)
        .join(ScanEvent, ScanUser.scan_event_id == ScanEvent.id)
        .join(QRCode, ScanEvent.qr_code_id == QRCode.id)
        .join(Campaign, QRCode.campaign_id == Campaign.id)
        .join(Company, Campaign.company_id == Company.id)
        .group_by(Campaign.id)
    )
    user_stmt = _apply_filters(user_stmt, filters)
    user_result = await db.execute(user_stmt)
    user_map = {row.campaign_id: row.registered_users for row in user_result.all()}

    rows: list[dict[str, Any]] = []
    for cid, data in scan_rows.items():
        registered = user_map.get(cid, 0)
        unique = data["unique_scans"] or 0
        data["registered_users"] = registered
        data["conversion_rate"] = (
            round(registered / unique * 100, 2) if unique > 0 else 0.0
        )
        del data["campaign_id"]
        rows.append(data)

    rows.sort(key=lambda r: r["conversion_rate"], reverse=True)
    return rows


async def discipline_product_affinity(
    db: AsyncSession,
    filters: ReportFilters,
) -> list[dict[str, Any]]:
    """Cross-reference: which campaign categories (disciplines) generate
    the most scans for which advertiser campaigns."""
    stmt = (
        select(
            Campaign.category.label("category"),
            Company.name.label("company_name"),
            Campaign.name.label("campaign_name"),
            func.count(ScanEvent.id).label("scan_count"),
        )
        .select_from(ScanEvent)
        .join(QRCode, ScanEvent.qr_code_id == QRCode.id)
        .join(Campaign, QRCode.campaign_id == Campaign.id)
        .join(Company, Campaign.company_id == Company.id)
        .where(Campaign.category.isnot(None))
        .group_by(Campaign.category, Company.name, Campaign.name)
        .order_by(func.count(ScanEvent.id).desc())
    )
    stmt = _apply_filters(stmt, filters)
    result = await db.execute(stmt)
    return [dict(row._mapping) for row in result.all()]


async def fitness_trends_by_city(
    db: AsyncSession,
    filters: ReportFilters,
) -> list[dict[str, Any]]:
    """Top campaign categories (disciplines) by city, showing scan counts."""
    stmt = (
        select(
            ScanEvent.city.label("city"),
            Campaign.category.label("category"),
            func.count(ScanEvent.id).label("scan_count"),
        )
        .select_from(ScanEvent)
        .join(QRCode, ScanEvent.qr_code_id == QRCode.id)
        .join(Campaign, QRCode.campaign_id == Campaign.id)
        .join(Company, Campaign.company_id == Company.id)
        .where(Campaign.category.isnot(None))
        .where(ScanEvent.city.isnot(None))
        .group_by(ScanEvent.city, Campaign.category)
        .order_by(func.count(ScanEvent.id).desc())
    )
    stmt = _apply_filters(stmt, filters)
    result = await db.execute(stmt)
    return [dict(row._mapping) for row in result.all()]


async def gender_distribution(
    db: AsyncSession,
    filters: ReportFilters,
) -> list[dict[str, Any]]:
    """Scan counts grouped by user gender, with campaign/company filter."""
    stmt = (
        select(
            User.gender.label("gender"),
            func.count(ScanEvent.id).label("scan_count"),
        )
        .select_from(User)
        .join(ScanUser, User.id == ScanUser.user_id)
        .join(ScanEvent, ScanUser.scan_event_id == ScanEvent.id)
        .join(QRCode, ScanEvent.qr_code_id == QRCode.id)
        .join(Campaign, QRCode.campaign_id == Campaign.id)
        .join(Company, Campaign.company_id == Company.id)
        .where(User.gender.isnot(None))
        .group_by(User.gender)
        .order_by(func.count(ScanEvent.id).desc())
    )
    stmt = _apply_filters(stmt, filters)
    result = await db.execute(stmt)
    return [dict(row._mapping) for row in result.all()]


async def age_distribution(
    db: AsyncSession,
    filters: ReportFilters,
) -> list[dict[str, Any]]:
    """Scan counts grouped by age group (derived from date_of_birth)."""
    if _is_sqlite:
        age_expr = func.strftime("%Y", "now") - func.strftime("%Y", User.date_of_birth)
    elif _is_mysql:
        age_expr = func.year(func.curdate()) - func.year(User.date_of_birth)
    else:
        age_expr = extract("year", func.age(User.date_of_birth))

    age_group_col = case(
        (age_expr < 18, "< 18"),
        (age_expr.between(18, 24), "18-24"),
        (age_expr.between(25, 34), "25-34"),
        (age_expr.between(35, 44), "35-44"),
        (age_expr.between(45, 54), "45-54"),
        else_="55+",
    ).label("age_range")

    stmt = (
        select(
            age_group_col,
            func.count(ScanEvent.id).label("scan_count"),
        )
        .select_from(User)
        .join(ScanUser, User.id == ScanUser.user_id)
        .join(ScanEvent, ScanUser.scan_event_id == ScanEvent.id)
        .join(QRCode, ScanEvent.qr_code_id == QRCode.id)
        .join(Campaign, QRCode.campaign_id == Campaign.id)
        .join(Company, Campaign.company_id == Company.id)
        .where(User.date_of_birth.isnot(None))
        .group_by(age_group_col)
        .order_by(func.count(ScanEvent.id).desc())
    )
    stmt = _apply_filters(stmt, filters)
    result = await db.execute(stmt)
    return [dict(row._mapping) for row in result.all()]


async def events_by_interest(
    db: AsyncSession,
    filters: ReportFilters,
) -> list[dict[str, Any]]:
    """Campaigns with category='evento' ranked by scan count."""
    stmt = (
        select(
            Campaign.name.label("campaign_name"),
            Company.name.label("company_name"),
            func.count(ScanEvent.id).label("scan_count"),
            func.count(distinct(ScanEvent.ip_address)).label("unique_scans"),
        )
        .select_from(ScanEvent)
        .join(QRCode, ScanEvent.qr_code_id == QRCode.id)
        .join(Campaign, QRCode.campaign_id == Campaign.id)
        .join(Company, Campaign.company_id == Company.id)
        .where(Campaign.category == "evento")
        .group_by(Campaign.id, Campaign.name, Company.name)
        .order_by(func.count(ScanEvent.id).desc())
    )
    stmt = _apply_filters(stmt, filters)
    result = await db.execute(stmt)
    return [dict(row._mapping) for row in result.all()]


async def top_disciplines(
    db: AsyncSession,
    filters: ReportFilters,
) -> list[dict[str, Any]]:
    """Campaigns grouped by category, ranked by scan count.

    Only discipline categories -- excludes 'evento' and 'promocion'.
    """
    stmt = (
        select(
            Campaign.category.label("category"),
            func.count(ScanEvent.id).label("scan_count"),
            func.count(distinct(ScanEvent.ip_address)).label("unique_scans"),
            func.count(distinct(Campaign.id)).label("campaign_count"),
        )
        .select_from(ScanEvent)
        .join(QRCode, ScanEvent.qr_code_id == QRCode.id)
        .join(Campaign, QRCode.campaign_id == Campaign.id)
        .join(Company, Campaign.company_id == Company.id)
        .where(Campaign.category.isnot(None))
        .where(Campaign.category.notin_(["evento", "promocion"]))
        .group_by(Campaign.category)
        .order_by(func.count(ScanEvent.id).desc())
    )
    stmt = _apply_filters(stmt, filters)
    result = await db.execute(stmt)
    return [dict(row._mapping) for row in result.all()]


async def advertiser_performance(
    db: AsyncSession,
    filters: ReportFilters,
) -> list[dict[str, Any]]:
    """Per company: total QR scans, leads generated, conversion rate,
    top performing campaign."""
    # Scans per company
    scan_stmt = (
        select(
            Company.id.label("company_id"),
            Company.name.label("company_name"),
            func.count(ScanEvent.id).label("total_scans"),
            func.count(distinct(ScanEvent.ip_address)).label("unique_scans"),
        )
        .select_from(ScanEvent)
        .join(QRCode, ScanEvent.qr_code_id == QRCode.id)
        .join(Campaign, QRCode.campaign_id == Campaign.id)
        .join(Company, Campaign.company_id == Company.id)
        .group_by(Company.id, Company.name)
    )
    scan_stmt = _apply_filters(scan_stmt, filters)
    scan_result = await db.execute(scan_stmt)
    company_data: dict[int, dict[str, Any]] = {}
    for row in scan_result.all():
        company_data[row.company_id] = dict(row._mapping)

    # Leads per company
    lead_stmt = (
        select(
            Company.id.label("company_id"),
            func.count(distinct(User.id)).label("leads"),
        )
        .select_from(User)
        .join(ScanUser, User.id == ScanUser.user_id)
        .join(ScanEvent, ScanUser.scan_event_id == ScanEvent.id)
        .join(QRCode, ScanEvent.qr_code_id == QRCode.id)
        .join(Campaign, QRCode.campaign_id == Campaign.id)
        .join(Company, Campaign.company_id == Company.id)
        .group_by(Company.id)
    )
    lead_stmt = _apply_filters(lead_stmt, filters)
    lead_result = await db.execute(lead_stmt)
    lead_map = {row.company_id: row.leads for row in lead_result.all()}

    # Top campaign per company (by scan count)
    top_stmt = (
        select(
            Company.id.label("company_id"),
            Campaign.name.label("top_campaign"),
            func.count(ScanEvent.id).label("camp_scans"),
        )
        .select_from(ScanEvent)
        .join(QRCode, ScanEvent.qr_code_id == QRCode.id)
        .join(Campaign, QRCode.campaign_id == Campaign.id)
        .join(Company, Campaign.company_id == Company.id)
        .group_by(Company.id, Campaign.id, Campaign.name)
        .order_by(func.count(ScanEvent.id).desc())
    )
    top_stmt = _apply_filters(top_stmt, filters)
    top_result = await db.execute(top_stmt)
    top_map: dict[int, str] = {}
    for row in top_result.all():
        if row.company_id not in top_map:
            top_map[row.company_id] = row.top_campaign

    rows: list[dict[str, Any]] = []
    for cid, data in company_data.items():
        leads = lead_map.get(cid, 0)
        unique = data.get("unique_scans", 0) or 0
        data["leads"] = leads
        data["conversion_rate"] = (
            round(leads / unique * 100, 2) if unique > 0 else 0.0
        )
        data["top_campaign"] = top_map.get(cid, "-")
        del data["company_id"]
        rows.append(data)

    rows.sort(key=lambda r: r["total_scans"], reverse=True)
    return rows


async def economic_profile(
    db: AsyncSession,
    filters: ReportFilters,
) -> list[dict[str, Any]]:
    """Cross-reference gym classification with user demographics to
    determine economic profiles of scanners.

    A+ gyms = high purchasing power, C gyms = low purchasing power.
    """
    stmt = (
        select(
            Gym.classification,
            Gym.atv,
            User.gender,
            func.count(distinct(User.id)).label("user_count"),
            func.count(ScanEvent.id).label("scan_count"),
        )
        .select_from(User)
        .join(ScanUser, User.id == ScanUser.user_id)
        .join(ScanEvent, ScanUser.scan_event_id == ScanEvent.id)
        .join(QRCode, ScanEvent.qr_code_id == QRCode.id)
        .join(Gym, QRCode.gym_id == Gym.id)
        .join(Campaign, QRCode.campaign_id == Campaign.id)
        .join(Company, Campaign.company_id == Company.id)
        .where(Gym.classification.isnot(None))
        .group_by(Gym.classification, Gym.atv, User.gender)
        .order_by(Gym.classification, func.count(distinct(User.id)).desc())
    )
    stmt = _apply_filters(stmt, filters)
    result = await db.execute(stmt)
    return [dict(row._mapping) for row in result.all()]


async def scans_by_classification(
    db: AsyncSession,
    filters: ReportFilters,
) -> list[dict[str, Any]]:
    """Scan counts grouped by gym classification tier."""
    stmt = (
        select(
            Gym.classification,
            func.count(ScanEvent.id).label("scan_count"),
            func.count(distinct(ScanEvent.ip_address)).label("unique_scans"),
            func.count(distinct(Gym.id)).label("gym_count"),
        )
        .select_from(ScanEvent)
        .join(QRCode, ScanEvent.qr_code_id == QRCode.id)
        .join(Gym, QRCode.gym_id == Gym.id)
        .join(Campaign, QRCode.campaign_id == Campaign.id)
        .join(Company, Campaign.company_id == Company.id)
        .where(Gym.classification.isnot(None))
        .group_by(Gym.classification)
        .order_by(Gym.classification)
    )
    stmt = _apply_filters(stmt, filters)
    result = await db.execute(stmt)
    return [dict(row._mapping) for row in result.all()]


async def scans_by_atv(
    db: AsyncSession,
    filters: ReportFilters,
) -> list[dict[str, Any]]:
    """Scan counts grouped by gym average ticket value range."""
    stmt = (
        select(
            Gym.atv,
            func.count(ScanEvent.id).label("scan_count"),
            func.count(distinct(ScanEvent.ip_address)).label("unique_scans"),
            func.count(distinct(Gym.id)).label("gym_count"),
        )
        .select_from(ScanEvent)
        .join(QRCode, ScanEvent.qr_code_id == QRCode.id)
        .join(Gym, QRCode.gym_id == Gym.id)
        .join(Campaign, QRCode.campaign_id == Campaign.id)
        .join(Company, Campaign.company_id == Company.id)
        .where(Gym.atv.isnot(None))
        .group_by(Gym.atv)
        .order_by(func.count(ScanEvent.id).desc())
    )
    stmt = _apply_filters(stmt, filters)
    result = await db.execute(stmt)
    return [dict(row._mapping) for row in result.all()]


async def scans_by_gym_discipline(
    db: AsyncSession,
    filters: ReportFilters,
) -> list[dict[str, Any]]:
    """Scan counts grouped by gym discipline type."""
    stmt = (
        select(
            Gym.discipline,
            func.count(ScanEvent.id).label("scan_count"),
            func.count(distinct(ScanEvent.ip_address)).label("unique_scans"),
            func.count(distinct(Gym.id)).label("gym_count"),
        )
        .select_from(ScanEvent)
        .join(QRCode, ScanEvent.qr_code_id == QRCode.id)
        .join(Gym, QRCode.gym_id == Gym.id)
        .join(Campaign, QRCode.campaign_id == Campaign.id)
        .join(Company, Campaign.company_id == Company.id)
        .where(Gym.discipline.isnot(None))
        .group_by(Gym.discipline)
        .order_by(func.count(ScanEvent.id).desc())
    )
    stmt = _apply_filters(stmt, filters)
    result = await db.execute(stmt)
    return [dict(row._mapping) for row in result.all()]


# ===================================================================
# CSV export helper
# ===================================================================

def to_csv(data: list[dict[str, Any]] | dict[str, Any]) -> str:
    """Convert report output to a CSV-formatted string.

    Accepts either:
    - A list of dicts (typical tabular report).
    - A single dict (e.g. ``conversion_funnel``), which is wrapped in a
      single-row list.

    Returns a UTF-8 CSV string with a header row.
    """
    if isinstance(data, dict):
        data = [data]

    if not data:
        return ""

    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=data[0].keys())
    writer.writeheader()
    writer.writerows(data)
    return output.getvalue()


# ===================================================================
# Report registry -- extensible mapping of type names to handlers.
# ===================================================================

REPORT_REGISTRY: dict[str, ReportHandler] = {
    "scans_per_campaign": scans_per_campaign,
    "scans_per_company": scans_per_company,
    "scans_by_geography": scans_by_geography,
    "scans_by_device": scans_by_device,
    "scans_by_hour": scans_by_hour,
    "scans_by_day_of_week": scans_by_day_of_week,
    "top_campaigns": top_campaigns,
    "unique_vs_repeat": unique_vs_repeat,
    "campaign_comparison": campaign_comparison,
    "scans_per_location": scans_per_location,
    "user_demographics": user_demographics,
    "campaign_roi": campaign_roi,
    "trend_analysis": trend_analysis,
    "geographic_heatmap": geographic_heatmap,
    "conversion_funnel": conversion_funnel,
    # Gym / Advertiser reports
    "leads_generated": leads_generated,
    "scans_by_gym": scans_by_gym,
    "qr_to_lead_conversion": qr_to_lead_conversion,
    "discipline_product_affinity": discipline_product_affinity,
    "fitness_trends_by_city": fitness_trends_by_city,
    "gender_distribution": gender_distribution,
    "age_distribution": age_distribution,
    "events_by_interest": events_by_interest,
    "top_disciplines": top_disciplines,
    "advertiser_performance": advertiser_performance,
    "economic_profile": economic_profile,
    "scans_by_classification": scans_by_classification,
    "scans_by_atv": scans_by_atv,
    "scans_by_gym_discipline": scans_by_gym_discipline,
}

# Also register with hyphenated keys for backward compatibility
# with existing API consumers.
REPORT_REGISTRY.update({
    "scans-per-campaign": scans_per_campaign,
    "scans-per-company": scans_per_company,
    "scans-by-geography": scans_by_geography,
    "scans-by-device": scans_by_device,
    "scans-by-hour": scans_by_hour,
    "scans-by-day-of-week": scans_by_day_of_week,
    "top-campaigns": top_campaigns,
    "unique-vs-repeat": unique_vs_repeat,
    "campaign-comparison": campaign_comparison,
    "scans-per-location": scans_per_location,
    "user-demographics": user_demographics,
    "campaign-roi": campaign_roi,
    "trend-analysis": trend_analysis,
    "geographic-heatmap": geographic_heatmap,
    "conversion-funnel": conversion_funnel,
    # Gym / Advertiser reports (hyphenated)
    "leads-generated": leads_generated,
    "scans-by-gym": scans_by_gym,
    "qr-to-lead-conversion": qr_to_lead_conversion,
    "discipline-product-affinity": discipline_product_affinity,
    "fitness-trends-by-city": fitness_trends_by_city,
    "gender-distribution": gender_distribution,
    "age-distribution": age_distribution,
    "events-by-interest": events_by_interest,
    "top-disciplines": top_disciplines,
    "advertiser-performance": advertiser_performance,
    "economic-profile": economic_profile,
    "scans-by-classification": scans_by_classification,
    "scans-by-atv": scans_by_atv,
    "scans-by-gym-discipline": scans_by_gym_discipline,
})


async def run_report(
    db: AsyncSession,
    report_type: str,
    filters: ReportFilters,
) -> list[dict[str, Any]] | dict[str, Any]:
    """Look up and execute the named report.

    Raises ``ValueError`` if *report_type* is not in the registry.
    """
    handler = REPORT_REGISTRY.get(report_type)
    if handler is None:
        raise ValueError(
            f"Unknown report type: {report_type!r}.  "
            f"Available: {sorted(set(REPORT_REGISTRY.keys()))}"
        )
    return await handler(db, filters)
