"""Pydantic v2 schemas for the procurement module.

Separate request/response models enforce OWASP API3
(Broken Object Property Level Authorization).
"""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, field_validator

# ── Vendor ──────────────────────────────────────────────────────────────────


class VendorCreate(BaseModel):
    name: str
    contact_email: str | None = None
    phone: str | None = None
    address: str | None = None


class VendorRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    contact_email: str | None
    phone: str | None
    address: str | None
    is_active: bool
    created_at: datetime


# ── PriceQuote ───────────────────────────────────────────────────────────────


class PriceQuoteCreate(BaseModel):
    vendor_id: uuid.UUID
    item_name: str
    quantity: Decimal = Decimal("1")
    unit: str | None = None
    price: Decimal
    currency: str = "IDR"
    source_url: str | None = None
    valid_until: datetime | None = None
    notes: str | None = None


class PriceQuoteRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    vendor_id: uuid.UUID
    item_name: str
    quantity: Decimal
    unit: str | None
    price: Decimal
    currency: str
    source_url: str | None
    valid_until: datetime | None
    notes: str | None
    created_at: datetime


# ── Cross-validation ─────────────────────────────────────────────────────────


class PriceValidationResult(BaseModel):
    median: Decimal
    min: Decimal
    max: Decimal
    flagged_vendor_ids: list[uuid.UUID]
    spread_percent: Decimal


# ── Recommendation ───────────────────────────────────────────────────────────


class RecommendedItem(BaseModel):
    """Per-item analysis from the Langflow Maker Agent.

    Numeric fields are Optional[float] so that None (normalised from
    "Data tidak tersedia") is accepted by Pydantic without coercion errors.
    """

    model_config = ConfigDict(extra="ignore")

    nama_item: str = ""
    harga_vendor: float | None = None
    harga_pasar_rata: float | None = None
    selisih_persen: float | None = None
    status: str = ""
    rekomendasi: str = ""
    sumber: list[str] = []
    alasan: str = ""
    qty: int | None = None
    satuan: str = ""
    total_price_vendor: float | None = None


class Kesimpulan(BaseModel):
    """Kesimpulan block from the Langflow Maker Agent output."""

    total_penawaran: float | None = None
    total_pasar: float | None = None
    total_selisih_persen: float | None = None
    skor_vendor: float | None = None
    rekomendasi_vendor: str | None = None
    estimasi_penghematan: float | None = None
    ringkasan_alasan: str = ""
    # ── Deterministic math check fields ──
    total_penawaran_calculated: float | None = None
    math_discrepancy: float | None = None
    math_discrepancy_percent: float | None = None
    math_check_status: str = "OK"
    math_check_note: str = ""

    @field_validator(
        "total_penawaran",
        "total_pasar",
        "total_selisih_persen",
        "skor_vendor",
        "estimasi_penghematan",
        mode="before",
    )
    @classmethod
    def _coerce_numeric(cls, v: object) -> float | None:
        """Accept floats/ints as-is; convert numeric strings; null-out sentinels."""
        if v is None:
            return None
        if isinstance(v, (int, float)):
            return float(v)
        if isinstance(v, str):
            stripped = v.strip()
            if stripped in ("Data tidak tersedia", ""):
                return None
            try:
                return float(stripped.replace(",", "").replace("Rp", "").strip())
            except ValueError:
                return None
        return None


class RecommendationResponse(BaseModel):
    """Output of the Maker Agent recommendation flow (Langflow).

    New fields (from real Langflow output):
      vendor_name, items, kesimpulan, raw_text

    Legacy fields (kept for backward compat with existing tests):
      vendor_id, reason, estimated_saving, citations
    """

    # ── New Langflow fields ──
    model_config = ConfigDict(extra="ignore")

    vendor_name: str | None = None
    vendor_contact: str = ""
    vendor_address: str = ""
    items: list[RecommendedItem] = []
    kesimpulan: Kesimpulan | None = None
    raw_text: str | None = None  # populated when LLM output cannot be parsed

    # ── Legacy / fallback fields ──
    vendor_id: uuid.UUID | None = None
    reason: str = ""
    estimated_saving: Decimal = Decimal("0")
    citations: list[str] = []


# ── Bon Permintaan (Purchase Request) ──────────────────────────────────────────
# Aliases for backward compatibility with shared schemas

from timbang.shared.schemas.document import ExtractedItem as BonItem
from timbang.shared.schemas.document import ParsedDocument as ParsedBon


# ── Procurement Documents ───────────────────────────────────────────────────────


class DocumentListItem(BaseModel):
    """Lightweight document for list view."""

    model_config = ConfigDict(from_attributes=True, extra="ignore")

    id: uuid.UUID
    doc_type: str
    doc_number: str
    doc_date: str
    division: str
    vendor_reference: str
    amount: float | None
    currency: str
    item_count: int
    source_file: str
    created_at: datetime


class DocumentDetail(BaseModel):
    """Full document detail including items."""

    model_config = ConfigDict(from_attributes=True, extra="ignore")

    id: uuid.UUID
    doc_type: str
    doc_number: str
    doc_date: str
    division: str
    vendor_reference: str
    amount: float | None
    currency: str
    items: list[dict]
    raw_metadata: dict
    source_file: str
    created_at: datetime
