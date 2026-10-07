"""Tests for ProcurementService business logic."""

from __future__ import annotations

from decimal import Decimal
from unittest.mock import AsyncMock, patch

import httpx
import pytest

from timbang.modules.procurement.repository import PriceQuoteRepository, VendorRepository, ProcurementDocumentRepository
from timbang.modules.procurement.schemas import PriceQuoteCreate, VendorCreate
from timbang.modules.procurement.service import ProcurementService
from timbang.shared.core.exceptions import UpstreamError, ValidationError


def _make_service(session) -> ProcurementService:
    return ProcurementService(
        vendor_repo=VendorRepository(session),
        quote_repo=PriceQuoteRepository(session),
        doc_repo=ProcurementDocumentRepository(session),
    )


# ── register_vendor ───────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_register_vendor_happy(session):
    """Register a new vendor — should return VendorRead with correct data."""
    svc = _make_service(session)
    result = await svc.register_vendor(VendorCreate(name="PT Maju Jaya"))
    assert result.name == "PT Maju Jaya"
    assert result.is_active is True
    assert result.id is not None


@pytest.mark.asyncio
async def test_register_vendor_duplicate_raises(session):
    """Registering a vendor with the same name should raise ValidationError."""
    svc = _make_service(session)
    await svc.register_vendor(VendorCreate(name="PT Sama"))
    with pytest.raises(ValidationError, match="already exists"):
        await svc.register_vendor(VendorCreate(name="PT Sama"))


# ── cross_validate_price ──────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_cross_validate_price_flags_outlier(session, seed_vendors_and_quotes):
    """Vendor with price 20_000_000 (outlier ~93% above median ~10_100_000) is flagged."""
    svc = _make_service(session)
    result = await svc.cross_validate_price("laptop")
    assert result.median > 0
    assert len(result.flagged_vendor_ids) >= 1
    # The outlier price is 20_000_000 — spread must be large
    assert result.spread_percent > Decimal("30")


@pytest.mark.asyncio
async def test_cross_validate_price_requires_min_quotes(session):
    """cross_validate_price with < 2 quotes raises ValidationError."""
    svc = _make_service(session)
    with pytest.raises(ValidationError, match="at least 2 quotes"):
        await svc.cross_validate_price("item_that_does_not_exist")


@pytest.mark.asyncio
async def test_cross_validate_price_no_outlier(session):
    """When prices are close, no vendor is flagged."""
    svc = _make_service(session)
    vendor1 = await svc.register_vendor(VendorCreate(name="V-Close-A"))
    vendor2 = await svc.register_vendor(VendorCreate(name="V-Close-B"))

    quote_repo = PriceQuoteRepository(session)
    await quote_repo.create(
        PriceQuoteCreate(vendor_id=vendor1.id, item_name="printer", price=Decimal("1000000"))
    )
    await quote_repo.create(
        PriceQuoteCreate(vendor_id=vendor2.id, item_name="printer", price=Decimal("1020000"))
    )

    result = await svc.cross_validate_price("printer")
    assert len(result.flagged_vendor_ids) == 0
    assert result.spread_percent < Decimal("5")


# ── get_recommendation (mock Langflow) ────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_recommendation_mock_9router(session, seed_vendors_and_quotes, monkeypatch):
    """get_recommendation calls Langflow and parses the JSON response."""
    monkeypatch.setattr(
        __import__("timbang.shared.core.config", fromlist=["get_settings"]).get_settings(),
        "langflow_maker_flow_id",
        "test-flow-id",
    )
    langflow_text = (
        '{"vendor_name": "Vendor 1", '
        '"items": [{"nama_item": "laptop", "harga_vendor": 9000000, '
        '"status": "WAJAR", "rekomendasi": "SETUJU", "alasan": "ok", "sumber": []}]}'
    )
    mock_response_body = {
        "outputs": [{"outputs": [{"results": {"message": {"text": langflow_text}}}]}]
    }

    svc = _make_service(session)

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = httpx.Response(
            status_code=200,
            json=mock_response_body,
            request=httpx.Request("POST", "http://mock"),
        )
        result = await svc.get_recommendation("laptop")

    assert result.vendor_name == "Vendor 1"
    assert len(result.items) == 1
    assert result.items[0].nama_item == "laptop"


@pytest.mark.asyncio
async def test_get_recommendation_upstream_error(session, seed_vendors_and_quotes, monkeypatch):
    """get_recommendation raises UpstreamError when Langflow returns non-200."""
    monkeypatch.setattr(
        __import__("timbang.shared.core.config", fromlist=["get_settings"]).get_settings(),
        "langflow_maker_flow_id",
        "test-flow-id",
    )
    svc = _make_service(session)

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = httpx.Response(
            status_code=503,
            text="Service Unavailable",
            request=httpx.Request("POST", "http://mock"),
        )
        with pytest.raises(UpstreamError, match="HTTP 503"):
            await svc.get_recommendation("laptop")
