"""Tests for the Langflow Maker Agent integration in ProcurementService.

All Langflow HTTP calls are mocked — no real Langflow instance required.
Uses httpx.AsyncClient.post monkeypatching (unittest.mock) to intercept
calls at the service layer.
"""

from __future__ import annotations

import json
from decimal import Decimal
from unittest.mock import AsyncMock, patch

import httpx
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from timbang.main import create_app
from timbang.modules.procurement.repository import PriceQuoteRepository, VendorRepository, ProcurementDocumentRepository
from timbang.modules.procurement.schemas import PriceQuoteCreate, VendorCreate
from timbang.modules.procurement.service import (
    ProcurementService,
    _extract_chat_text,
    _try_parse_json,
)
from timbang.shared.core.config import get_settings
from timbang.shared.core.exceptions import UpstreamError
from timbang.shared.db.base import Base
from timbang.shared.db.session import get_session

_TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"
_FLOW_ID = "37f9fa1a-008a-49c3-b6fc-451a1ae5bb87"

# ── Helpers ───────────────────────────────────────────────────────────────────


def _langflow_response(text: str) -> dict:
    """Build a Langflow-shaped response dict with chat text."""
    return {"outputs": [{"outputs": [{"results": {"message": {"text": text}}}]}]}


def _make_langflow_items_json(vendor_name: str = "PT Sinar Elektronik") -> str:
    """Return a realistic Langflow Maker output JSON string."""
    return json.dumps(
        {
            "vendor_name": vendor_name,
            "items": [
                {
                    "nama_item": "Laptop Asus VivoBook 14",
                    "harga_vendor": 9750000,
                    "harga_pasar_rata": 9100000,
                    "selisih_persen": 7.14,
                    "status": "PERHATIAN",
                    "rekomendasi": "NEGOSIASI",
                    "sumber": ["https://tokopedia.com/a", "https://shopee.co.id/b"],
                    "alasan": "Harga penawaran 7.14% di atas harga rata-rata pasar",
                }
            ],
        }
    )


# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest_asyncio.fixture
async def lf_engine():
    engine = create_async_engine(_TEST_DATABASE_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest_asyncio.fixture
async def lf_session(lf_engine):
    factory = async_sessionmaker(lf_engine, expire_on_commit=False, class_=AsyncSession)
    async with factory() as s:
        yield s


@pytest_asyncio.fixture
async def lf_client(lf_engine):
    factory = async_sessionmaker(lf_engine, expire_on_commit=False, class_=AsyncSession)

    async def override_get_session():
        async with factory() as s:
            yield s

    app = create_app()
    app.dependency_overrides[get_session] = override_get_session
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()


def _make_service(session) -> ProcurementService:
    return ProcurementService(
        vendor_repo=VendorRepository(session),
        quote_repo=PriceQuoteRepository(session),
        doc_repo=ProcurementDocumentRepository(session),
    )


async def _seed_quotes(session, item_name: str = "Laptop Asus VivoBook 14") -> list[str]:
    """Seed 3 vendors + quotes for item_name. Returns vendor IDs as strings."""
    vendor_repo = VendorRepository(session)
    quote_repo = PriceQuoteRepository(session)
    vendor_ids = []
    for i, price in enumerate([9_750_000, 9_100_000, 9_300_000], start=1):
        vendor = await vendor_repo.create(VendorCreate(name=f"LF Vendor {i}"))
        await quote_repo.create(
            PriceQuoteCreate(vendor_id=vendor.id, item_name=item_name, price=Decimal(str(price)))
        )
        vendor_ids.append(str(vendor.id))
    return vendor_ids


# ── Unit tests: helper functions ─────────────────────────────────────────────


def test_extract_chat_text_canonical():
    """Canonical Langflow path is extracted correctly."""
    data = _langflow_response("Hello from Langflow")
    assert _extract_chat_text(data) == "Hello from Langflow"


def test_extract_chat_text_fallback():
    """Falls back to any 'text' key in the tree."""
    data = {"nested": {"deep": {"text": "Found it"}}}
    assert _extract_chat_text(data) == "Found it"


def test_try_parse_json_plain():
    """Plain JSON string is parsed correctly."""
    result = _try_parse_json('{"vendor_name": "PT X", "items": []}')
    assert result is not None
    assert result["vendor_name"] == "PT X"


def test_try_parse_json_markdown_fence():
    """JSON wrapped in markdown code fence is stripped and parsed."""
    text = '```json\n{"vendor_name": "PT X", "items": []}\n```'
    result = _try_parse_json(text)
    assert result is not None
    assert result["vendor_name"] == "PT X"


def test_try_parse_json_returns_none_on_freetext():
    """Free-text (non-JSON) returns None."""
    result = _try_parse_json("Saya merekomendasikan PT Sinar karena harga terbaik.")
    assert result is None


# ── 1. test_get_recommendation_success ───────────────────────────────────────


@pytest.mark.asyncio
async def test_get_recommendation_success(lf_session, monkeypatch):
    """Langflow returns valid structured JSON → RecommendationResponse fully populated."""
    monkeypatch.setattr(get_settings(), "langflow_maker_flow_id", _FLOW_ID)

    await _seed_quotes(lf_session)
    svc = _make_service(lf_session)

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = httpx.Response(
            status_code=200,
            json=_langflow_response(_make_langflow_items_json()),
            request=httpx.Request("POST", "http://mock"),
        )
        result = await svc.get_recommendation("Laptop Asus VivoBook 14")

    assert result.vendor_name == "PT Sinar Elektronik"
    assert len(result.items) == 1
    item = result.items[0]
    assert item.nama_item == "Laptop Asus VivoBook 14"
    assert item.harga_vendor == Decimal("9750000")
    assert item.rekomendasi == "NEGOSIASI"
    assert item.status == "PERHATIAN"
    assert len(item.sumber) == 2
    assert result.raw_text is None  # structured parse succeeded — no raw_text


# ── 2. test_get_recommendation_json_wrapped_in_markdown ──────────────────────


@pytest.mark.asyncio
async def test_get_recommendation_json_wrapped_in_markdown(lf_session, monkeypatch):
    """Output text wrapped in ```json ... ``` fences is still parsed correctly."""
    monkeypatch.setattr(get_settings(), "langflow_maker_flow_id", _FLOW_ID)

    await _seed_quotes(lf_session)
    svc = _make_service(lf_session)

    markdown_text = f"```json\n{_make_langflow_items_json('PT Markdown')}\n```"

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = httpx.Response(
            status_code=200,
            json=_langflow_response(markdown_text),
            request=httpx.Request("POST", "http://mock"),
        )
        result = await svc.get_recommendation("Laptop Asus VivoBook 14")

    assert result.vendor_name == "PT Markdown"
    assert len(result.items) == 1
    assert result.raw_text is None


# ── 3. test_get_recommendation_langflow_timeout ───────────────────────────────


@pytest.mark.asyncio
async def test_get_recommendation_langflow_timeout(lf_session, monkeypatch):
    """Timeout from Langflow → service raises UpstreamError."""
    monkeypatch.setattr(get_settings(), "langflow_maker_flow_id", _FLOW_ID)

    await _seed_quotes(lf_session)
    svc = _make_service(lf_session)

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.side_effect = httpx.TimeoutException("connection timed out")
        with pytest.raises(UpstreamError, match="timed out"):
            await svc.get_recommendation("Laptop Asus VivoBook 14")


@pytest.mark.asyncio
async def test_get_recommendation_langflow_timeout_via_router(lf_client, lf_engine, monkeypatch):
    """Timeout propagates to router → 502 response."""
    monkeypatch.setattr(get_settings(), "langflow_maker_flow_id", _FLOW_ID)

    factory = async_sessionmaker(lf_engine, expire_on_commit=False, class_=AsyncSession)
    async with factory() as s:
        await _seed_quotes(s, "TOR Item")

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.side_effect = httpx.TimeoutException("timed out")
        r = await lf_client.get("/api/v1/procurement/items/TOR Item/recommend")

    assert r.status_code == 502
    assert "timed out" in r.json()["detail"]


# ── 4. test_get_recommendation_langflow_500 ───────────────────────────────────


@pytest.mark.asyncio
async def test_get_recommendation_langflow_500(lf_session, monkeypatch):
    """Langflow returns HTTP 500 → service raises UpstreamError."""
    monkeypatch.setattr(get_settings(), "langflow_maker_flow_id", _FLOW_ID)

    await _seed_quotes(lf_session)
    svc = _make_service(lf_session)

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = httpx.Response(
            status_code=500,
            text="Internal Server Error",
            request=httpx.Request("POST", "http://mock"),
        )
        with pytest.raises(UpstreamError, match="HTTP 500"):
            await svc.get_recommendation("Laptop Asus VivoBook 14")


@pytest.mark.asyncio
async def test_get_recommendation_langflow_500_via_router(lf_client, lf_engine, monkeypatch):
    """Langflow 500 → router returns 502."""
    monkeypatch.setattr(get_settings(), "langflow_maker_flow_id", _FLOW_ID)

    factory = async_sessionmaker(lf_engine, expire_on_commit=False, class_=AsyncSession)
    async with factory() as s:
        await _seed_quotes(s, "ERR Item")

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = httpx.Response(
            status_code=500,
            text="Internal Server Error",
            request=httpx.Request("POST", "http://mock"),
        )
        r = await lf_client.get("/api/v1/procurement/items/ERR Item/recommend")

    assert r.status_code == 502


# ── 5. test_get_recommendation_missing_flow_id ────────────────────────────────


@pytest.mark.asyncio
async def test_get_recommendation_missing_flow_id(lf_session, monkeypatch):
    """Empty LANGFLOW_MAKER_FLOW_ID → UpstreamError immediately, no HTTP call made."""
    monkeypatch.setattr(get_settings(), "langflow_maker_flow_id", "")

    await _seed_quotes(lf_session)
    svc = _make_service(lf_session)

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        with pytest.raises(UpstreamError, match="LANGFLOW_MAKER_FLOW_ID"):
            await svc.get_recommendation("Laptop Asus VivoBook 14")
        mock_post.assert_not_called()


@pytest.mark.asyncio
async def test_get_recommendation_missing_flow_id_via_router(lf_client, monkeypatch):
    """Empty flow ID → router returns 502 with informative message."""
    monkeypatch.setattr(get_settings(), "langflow_maker_flow_id", "")

    r = await lf_client.get("/api/v1/procurement/items/AnyItem/recommend")
    assert r.status_code == 502
    assert "LANGFLOW_MAKER_FLOW_ID" in r.json()["detail"]
