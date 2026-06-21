"""SQLAlchemy ORM models for the QR Event Tracker."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Numeric,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


# ---------------------------------------------------------------------------
# Companies
# ---------------------------------------------------------------------------
class Company(Base):
    __tablename__ = "companies"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    contact_email: Mapped[str | None] = mapped_column(String(255))
    contact_phone: Mapped[str | None] = mapped_column(String(50))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")

    # relationships
    campaigns: Mapped[list[Campaign]] = relationship(
        back_populates="company", cascade="all, delete-orphan", lazy="selectin"
    )


# ---------------------------------------------------------------------------
# Campaigns
# ---------------------------------------------------------------------------
class Campaign(Base):
    __tablename__ = "campaigns"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    company_id: Mapped[int] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    start_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    end_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    target_audience: Mapped[str | None] = mapped_column(String(255))
    budget: Mapped[float | None] = mapped_column(Numeric(12, 2))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # relationships
    company: Mapped[Company] = relationship(back_populates="campaigns")
    qr_codes: Mapped[list[QRCode]] = relationship(
        back_populates="campaign", cascade="all, delete-orphan", lazy="selectin"
    )

    __table_args__ = (
        Index("ix_campaigns_company_id", "company_id"),
    )


# ---------------------------------------------------------------------------
# QR Codes
# ---------------------------------------------------------------------------
class QRCode(Base):
    __tablename__ = "qr_codes"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    campaign_id: Mapped[int] = mapped_column(
        ForeignKey("campaigns.id", ondelete="CASCADE"), nullable=False
    )
    code: Mapped[str] = mapped_column(
        String(36), unique=True, nullable=False, default=lambda: str(uuid.uuid4())
    )
    label: Mapped[str | None] = mapped_column(String(255))
    redirect_url: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")

    # relationships
    campaign: Mapped[Campaign] = relationship(back_populates="qr_codes")
    scan_events: Mapped[list[ScanEvent]] = relationship(
        back_populates="qr_code", cascade="all, delete-orphan", lazy="selectin"
    )
    qr_locations: Mapped[list[QRLocation]] = relationship(
        back_populates="qr_code", cascade="all, delete-orphan", lazy="selectin"
    )

    __table_args__ = (
        Index("ix_qr_codes_code", "code"),
    )


# ---------------------------------------------------------------------------
# Scan Events
# ---------------------------------------------------------------------------
class ScanEvent(Base):
    __tablename__ = "scan_events"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    qr_code_id: Mapped[int] = mapped_column(
        ForeignKey("qr_codes.id", ondelete="CASCADE"), nullable=False
    )
    scanned_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    ip_address: Mapped[str | None] = mapped_column(String(45))
    user_agent: Mapped[str | None] = mapped_column(Text)
    device_type: Mapped[str | None] = mapped_column(String(50))
    browser: Mapped[str | None] = mapped_column(String(100))
    os: Mapped[str | None] = mapped_column(String(100))
    city: Mapped[str | None] = mapped_column(String(100))
    region: Mapped[str | None] = mapped_column(String(100))
    country: Mapped[str | None] = mapped_column(String(100))
    referrer: Mapped[str | None] = mapped_column(Text)
    session_id: Mapped[str | None] = mapped_column(String(255))

    # relationships
    qr_code: Mapped[QRCode] = relationship(back_populates="scan_events")
    scan_users: Mapped[list[ScanUser]] = relationship(
        back_populates="scan_event", cascade="all, delete-orphan", lazy="selectin"
    )

    __table_args__ = (
        Index("ix_scan_events_scanned_at", "scanned_at"),
        Index("ix_scan_events_qr_code_id", "qr_code_id"),
    )


# ---------------------------------------------------------------------------
# Users
# ---------------------------------------------------------------------------
class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    name: Mapped[str | None] = mapped_column(String(255))
    age_range: Mapped[str | None] = mapped_column(String(20))
    city: Mapped[str | None] = mapped_column(String(100))
    phone: Mapped[str | None] = mapped_column(String(50))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # relationships
    scan_users: Mapped[list[ScanUser]] = relationship(
        back_populates="user", cascade="all, delete-orphan", lazy="selectin"
    )


# ---------------------------------------------------------------------------
# Scan ↔ User association (composite PK)
# ---------------------------------------------------------------------------
class ScanUser(Base):
    __tablename__ = "scan_users"

    scan_event_id: Mapped[int] = mapped_column(
        ForeignKey("scan_events.id", ondelete="CASCADE"), primary_key=True
    )
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )

    # relationships
    scan_event: Mapped[ScanEvent] = relationship(back_populates="scan_users")
    user: Mapped[User] = relationship(back_populates="scan_users")


# ---------------------------------------------------------------------------
# Locations
# ---------------------------------------------------------------------------
class Location(Base):
    __tablename__ = "locations"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    address: Mapped[str | None] = mapped_column(Text)
    city: Mapped[str | None] = mapped_column(String(100))
    region: Mapped[str | None] = mapped_column(String(100))
    country: Mapped[str | None] = mapped_column(String(100))
    latitude: Mapped[float | None] = mapped_column(Float)
    longitude: Mapped[float | None] = mapped_column(Float)

    # relationships
    qr_locations: Mapped[list[QRLocation]] = relationship(
        back_populates="location", cascade="all, delete-orphan", lazy="selectin"
    )


# ---------------------------------------------------------------------------
# QR Code ↔ Location association (composite PK)
# ---------------------------------------------------------------------------
class QRLocation(Base):
    __tablename__ = "qr_locations"

    qr_code_id: Mapped[int] = mapped_column(
        ForeignKey("qr_codes.id", ondelete="CASCADE"), primary_key=True
    )
    location_id: Mapped[int] = mapped_column(
        ForeignKey("locations.id", ondelete="CASCADE"), primary_key=True
    )
    placed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    removed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # relationships
    qr_code: Mapped[QRCode] = relationship(back_populates="qr_locations")
    location: Mapped[Location] = relationship(back_populates="qr_locations")
