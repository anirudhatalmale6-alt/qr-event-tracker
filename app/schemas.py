"""Pydantic schemas for request validation and response serialisation."""

from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field


# ===================================================================
# Company
# ===================================================================
class CompanyCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    contact_email: str | None = None
    contact_phone: str | None = None
    is_active: bool = True


class CompanyUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=255)
    contact_email: str | None = None
    contact_phone: str | None = None
    is_active: bool | None = None


class CompanyOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    contact_email: str | None = None
    contact_phone: str | None = None
    created_at: datetime
    is_active: bool


# ===================================================================
# Campaign
# ===================================================================
class CampaignCreate(BaseModel):
    company_id: int
    name: str = Field(..., min_length=1, max_length=255)
    description: str | None = None
    start_date: datetime | None = None
    end_date: datetime | None = None
    target_audience: str | None = None
    budget: float | None = None
    category: str | None = None
    is_active: bool = True


class CampaignUpdate(BaseModel):
    company_id: int | None = None
    name: str | None = Field(None, min_length=1, max_length=255)
    description: str | None = None
    start_date: datetime | None = None
    end_date: datetime | None = None
    target_audience: str | None = None
    budget: float | None = None
    category: str | None = None
    is_active: bool | None = None


class CampaignOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    company_id: int
    name: str
    description: str | None = None
    start_date: datetime | None = None
    end_date: datetime | None = None
    target_audience: str | None = None
    budget: float | None = None
    category: str | None = None
    is_active: bool
    created_at: datetime


# ===================================================================
# Gym
# ===================================================================
class GymCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    atv: str | None = None
    discipline: str | None = None
    classification: str | None = None
    address: str | None = None
    city: str | None = None
    region: str | None = None
    country: str | None = None
    is_active: bool = True


class GymUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=255)
    atv: str | None = None
    discipline: str | None = None
    classification: str | None = None
    address: str | None = None
    city: str | None = None
    region: str | None = None
    country: str | None = None
    is_active: bool | None = None


class GymOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    atv: str | None = None
    discipline: str | None = None
    classification: str | None = None
    address: str | None = None
    city: str | None = None
    region: str | None = None
    country: str | None = None
    is_active: bool
    created_at: datetime


# ===================================================================
# QR Code
# ===================================================================
class QRCodeCreate(BaseModel):
    campaign_id: int
    gym_id: int | None = None
    label: str | None = None
    redirect_url: str | None = None
    is_active: bool = True


class QRCodeUpdate(BaseModel):
    campaign_id: int | None = None
    gym_id: int | None = None
    label: str | None = None
    redirect_url: str | None = None
    is_active: bool | None = None


class QRCodeOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    campaign_id: int
    gym_id: int | None = None
    code: str
    label: str | None = None
    redirect_url: str | None = None
    created_at: datetime
    is_active: bool


# ===================================================================
# Location
# ===================================================================
class LocationCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    address: str | None = None
    city: str | None = None
    region: str | None = None
    country: str | None = None
    latitude: float | None = None
    longitude: float | None = None


class LocationUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=255)
    address: str | None = None
    city: str | None = None
    region: str | None = None
    country: str | None = None
    latitude: float | None = None
    longitude: float | None = None


class LocationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    address: str | None = None
    city: str | None = None
    region: str | None = None
    country: str | None = None
    latitude: float | None = None
    longitude: float | None = None


# ===================================================================
# User
# ===================================================================
class UserCreate(BaseModel):
    email: EmailStr
    gender: str | None = None
    date_of_birth: date | None = None


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: str
    gender: str | None = None
    date_of_birth: date | None = None
    created_at: datetime


# ===================================================================
# Scan Event
# ===================================================================
class ScanEventOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    qr_code_id: int
    scanned_at: datetime
    ip_address: str | None = None
    user_agent: str | None = None
    device_type: str | None = None
    browser: str | None = None
    os: str | None = None
    city: str | None = None
    region: str | None = None
    country: str | None = None
    referrer: str | None = None
    session_id: str | None = None


# ===================================================================
# Report Filters
# ===================================================================
class ReportFilters(BaseModel):
    """Query parameters accepted by analytics / reporting endpoints."""

    date_from: datetime | None = None
    date_to: datetime | None = None
    company_id: int | None = None
    campaign_id: int | None = None
    qr_code_id: int | None = None
    gym_id: int | None = None
    city: str | None = None
    region: str | None = None
    country: str | None = None
    device_type: str | None = None
    browser: str | None = None
    os: str | None = None
