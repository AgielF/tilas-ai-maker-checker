"""SQLAlchemy 2.0 models for the procurement module."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Numeric, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from timbang.shared.db.base import Base


class Vendor(Base):
    """Represents a vendor/supplier in the procurement context."""

    __tablename__ = "vendors"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(255), nullable=False, unique=True, index=True)
    contact_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    address: Mapped[str | None] = mapped_column(String(500), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    quotes: Mapped[list[PriceQuote]] = relationship(back_populates="vendor")


class PriceQuote(Base):
    """Price quotation from a vendor for a specific item."""

    __tablename__ = "price_quotes"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    vendor_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("vendors.id", ondelete="CASCADE"), nullable=False, index=True
    )
    item_name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    quantity: Mapped[float] = mapped_column(Numeric(14, 4), nullable=False, default=1)
    unit: Mapped[str | None] = mapped_column(String(50), nullable=True)
    price: Mapped[float] = mapped_column(Numeric(14, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(10), nullable=False, default="IDR")
    source_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    valid_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    notes: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    vendor: Mapped[Vendor] = relationship(back_populates="quotes")


class ProcurementDocument(Base):
    """Archive for Bon Permintaan and other procurement documents."""

    __tablename__ = "procurement_documents"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    doc_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    doc_number: Mapped[str] = mapped_column(String(100), default="", index=True)
    doc_date: Mapped[str] = mapped_column(String(20), default="")
    division: Mapped[str] = mapped_column(String(50), default="")
    vendor_reference: Mapped[str] = mapped_column(String(64), default="", index=True)
    amount: Mapped[float | None] = mapped_column(Numeric(14, 2), nullable=True)
    currency: Mapped[str] = mapped_column(String(10), nullable=False, default="IDR")
    items_json: Mapped[dict] = mapped_column(JSON, default=dict)
    raw_metadata: Mapped[dict] = mapped_column(JSON, default=dict)
    source_file: Mapped[str] = mapped_column(String(255), default="")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
