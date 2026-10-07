"""Tests for the recommend-with-file endpoint and service method."""

from __future__ import annotations

import io
from decimal import Decimal
from unittest.mock import AsyncMock, patch

import httpx
import pytest
from fastapi import UploadFile

from timbang.modules.procurement.repository import PriceQuoteRepository, VendorRepository, ProcurementDocumentRepository
from timbang.modules.procurement.service import ProcurementService
from timbang.shared.core.exceptions import UpstreamError, ValidationError


def _make_service(session) -> ProcurementService:
    return ProcurementService(
        vendor_repo=VendorRepository(session),
        quote_repo=PriceQuoteRepository(session),
        doc_repo=ProcurementDocumentRepository(session),
    )


def _make_upload_file(
    filename: str,
    content: bytes = b"dummy content",
    content_type: str = "application/pdf",
) -> UploadFile:
    """Helper: build a minimal UploadFile backed by BytesIO."""
    return UploadFile(
        filename=filename,
        file=io.BytesIO(content),
        size=len(content),
        headers={"content-type": content_type},
    )


# ── test 1: invalid extension → ValidationError ───────────────────────────────


@pytest.mark.asyncio
async def test_recommend_with_file_rejects_invalid_extension(session, monkeypatch):
    """Uploading a .exe file must raise ValidationError (400)."""
    monkeypatch.setattr(
        __import__("timbang.shared.core.config", fromlist=["get_settings"]).get_settings(),
        "langflow_maker_flow_id",
        "test-flow-id",
    )
    svc = _make_service(session)
    bad_file = _make_upload_file("malware.exe", b"\x4d\x5a", "application/octet-stream")

    with pytest.raises(ValidationError, match="Format file tidak didukung"):
        await svc.get_recommendation_from_file(item_name="Laptop", file=bad_file)


# ── test 2: oversized file → ValidationError ─────────────────────────────────


@pytest.mark.asyncio
async def test_recommend_with_file_rejects_oversized(session, monkeypatch):
    """Uploading a file > 10 MB must raise ValidationError."""
    monkeypatch.setattr(
        __import__("timbang.shared.core.config", fromlist=["get_settings"]).get_settings(),
        "langflow_maker_flow_id",
        "test-flow-id",
    )
    svc = _make_service(session)
    # 11 MB of zeros
    oversized_content = b"\x00" * (11 * 1024 * 1024)
    big_file = _make_upload_file("big.pdf", oversized_content, "application/pdf")

    with pytest.raises(ValidationError, match="File terlalu besar"):
        await svc.get_recommendation_from_file(item_name="Laptop", file=big_file)


# ── test 3: success path with mocked httpx ────────────────────────────────────


@pytest.mark.asyncio
async def test_recommend_with_file_success_mocked(session, monkeypatch):
    """Happy path: mocked Langflow upload + run → parses RecommendationResponse."""
    monkeypatch.setattr(
        __import__("timbang.shared.core.config", fromlist=["get_settings"]).get_settings(),
        "langflow_maker_flow_id",
        "test-flow-id",
    )

    # Mock upload response: returns file_path
    upload_response_body = {
        "flowId": "test-flow-id",
        "file_path": "test-flow-id/surat_penawaran.pdf",
    }
    # Mock run response: wraps recommendation JSON in Langflow envelope
    langflow_text = (
        '{"vendor_name": "PT Demo", '
        '"items": [{"nama_item": "Laptop", "harga_vendor": 12500000, '
        '"status": "WAJAR", "rekomendasi": "SETUJU", "alasan": "Harga sesuai pasar.", '
        '"sumber": []}]}'
    )
    run_response_body = {
        "outputs": [{"outputs": [{"results": {"message": {"text": langflow_text}}}]}]
    }

    svc = _make_service(session)
    pdf_file = _make_upload_file("surat_penawaran.pdf", b"%PDF-1.4 mock", "application/pdf")

    call_count = 0

    async def _mock_post(url, **kwargs):
        nonlocal call_count
        call_count += 1
        if "files/upload" in url:
            return httpx.Response(
                201,
                json=upload_response_body,
                request=httpx.Request("POST", url),
            )
        # run endpoint
        return httpx.Response(
            200,
            json=run_response_body,
            request=httpx.Request("POST", url),
        )

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock, side_effect=_mock_post):
        result = await svc.get_recommendation_from_file(item_name="Laptop", file=pdf_file)

    # Two calls: upload + run
    assert call_count == 2

    assert result.vendor_name == "PT Demo"
    assert len(result.items) == 1
    assert result.items[0].nama_item == "Laptop"
    assert result.items[0].harga_vendor == Decimal("12500000")
    assert result.items[0].rekomendasi == "SETUJU"


# ── test 4: Langflow upload failure → UpstreamError ──────────────────────────


@pytest.mark.asyncio
async def test_recommend_with_file_upload_failure(session, monkeypatch):
    """If Langflow upload returns non-2xx, service raises UpstreamError."""
    monkeypatch.setattr(
        __import__("timbang.shared.core.config", fromlist=["get_settings"]).get_settings(),
        "langflow_maker_flow_id",
        "test-flow-id",
    )
    svc = _make_service(session)
    pdf_file = _make_upload_file("doc.pdf", b"%PDF-1.4", "application/pdf")

    with patch(
        "httpx.AsyncClient.post",
        new_callable=AsyncMock,
        return_value=httpx.Response(
            503,
            text="Service Unavailable",
            request=httpx.Request("POST", "http://mock"),
        ),
    ):
        with pytest.raises(UpstreamError, match="file upload failed HTTP 503"):
            await svc.get_recommendation_from_file(item_name="Laptop", file=pdf_file)
