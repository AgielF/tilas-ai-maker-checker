"""Procurement router — HTTP boundary.

Rules (docs/agents/BACKEND_AGENTS.md):
- Router delegates to service, never calls repository directly.
- Request/response validated by Pydantic schemas.
- Domain exceptions mapped to HTTP status codes here.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Request, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from timbang.modules.procurement.repository import (
    PriceQuoteRepository,
    ProcurementDocumentRepository,
    VendorRepository,
)
from timbang.modules.procurement.schemas import (
    DocumentDetail,
    DocumentListItem,
    ParsedBon,
    PriceQuoteCreate,
    PriceQuoteRead,
    PriceValidationResult,
    RecommendationResponse,
    VendorCreate,
    VendorRead,
)
from timbang.modules.procurement.service import ProcurementService
from timbang.shared.core.exceptions import (
    DomainError,
    NotFoundError,
    UpstreamError,
    ValidationError,
)
from timbang.shared.core.middleware import limiter
from timbang.shared.db.session import get_session

router = APIRouter(tags=["procurement"])


def _build_service(session: AsyncSession = Depends(get_session)) -> ProcurementService:
    return ProcurementService(
        vendor_repo=VendorRepository(session),
        quote_repo=PriceQuoteRepository(session),
        doc_repo=ProcurementDocumentRepository(session),
    )


def _map_exception(exc: DomainError) -> HTTPException:
    if isinstance(exc, NotFoundError):
        return HTTPException(status_code=404, detail=str(exc))
    if isinstance(exc, ValidationError):
        return HTTPException(status_code=400, detail=str(exc))
    if isinstance(exc, UpstreamError):
        return HTTPException(status_code=502, detail=str(exc))
    return HTTPException(status_code=400, detail=str(exc))


@router.get("/vendors", response_model=list[VendorRead])
@limiter.limit("120/minute")
async def list_vendors(
    request: Request,
    limit: int = 50,
    service: ProcurementService = Depends(_build_service),
) -> list[VendorRead]:
    """List all vendors."""
    return await service.list_vendors(limit=limit)


@router.post("/vendors", response_model=VendorRead, status_code=201)
@limiter.limit("30/minute")
async def register_vendor(
    request: Request,
    data: VendorCreate,
    service: ProcurementService = Depends(_build_service),
) -> VendorRead:
    """Register a new vendor."""
    try:
        return await service.register_vendor(data)
    except DomainError as exc:
        raise _map_exception(exc) from exc


@router.post("/vendors/{vendor_id}/quotes", response_model=PriceQuoteRead, status_code=201)
@limiter.limit("60/minute")
async def submit_quote(
    request: Request,
    vendor_id: uuid.UUID,
    data: PriceQuoteCreate,
    service: ProcurementService = Depends(_build_service),
) -> PriceQuoteRead:
    """Submit a price quote for a vendor."""
    try:
        return await service.submit_quote(vendor_id=vendor_id, data=data)
    except DomainError as exc:
        raise _map_exception(exc) from exc


@router.get("/items/{item_name}/validate", response_model=PriceValidationResult)
@limiter.limit("60/minute")
async def cross_validate_price(
    request: Request,
    item_name: str,
    service: ProcurementService = Depends(_build_service),
) -> PriceValidationResult:
    """Cross-validate prices for an item across all vendor quotes."""
    try:
        return await service.cross_validate_price(item_name=item_name)
    except DomainError as exc:
        raise _map_exception(exc) from exc


@router.post("/items/recommend-with-file", response_model=RecommendationResponse)
@limiter.limit("10/minute")
async def recommend_with_file(
    request: Request,
    item_name: str = Form(""),
    mode: str = Form("penawaran"),
    file: UploadFile = File(...),
    service: ProcurementService = Depends(_build_service),
) -> RecommendationResponse:
    """Upload PDF/Excel + mode → Maker Agent Langflow → Recommendation.

    mode: "penawaran" (vendor quote, compare vendor vs market) or
          "bon" (permintaan barang tanpa vendor, cari harga pasar saja).
    """
    try:
        return await service.get_recommendation_from_file(
            item_name=item_name, file=file, mode=mode
        )
    except DomainError as exc:
        raise _map_exception(exc) from exc


@router.get("/items/{item_name}/recommend", response_model=RecommendationResponse)
@limiter.limit("10/minute")
async def get_recommendation(
    request: Request,
    item_name: str,
    service: ProcurementService = Depends(_build_service),
) -> RecommendationResponse:
    """Get Maker Agent vendor recommendation for an item (Langflow integration)."""
    try:
        # Load quotes first so the service can include them in the Langflow prompt
        quotes = await service._load_quotes_for_item(item_name)
        return await service.get_recommendation(item_name=item_name, quotes=quotes or None)
    except DomainError as exc:
        raise _map_exception(exc) from exc


@router.post("/bons/parse", response_model=list[ParsedBon])
@limiter.limit("10/minute")
async def parse_bon_endpoint(
    request: Request,
    file: UploadFile = File(...),
    service: ProcurementService = Depends(_build_service),
) -> list[ParsedBon]:
    """Parse Bon Permintaan (Excel) → structured JSON."""
    try:
        return await service.parse_bon_from_file(file)
    except DomainError as exc:
        raise _map_exception(exc) from exc


@router.get("/documents", response_model=list[DocumentListItem])
@limiter.limit("30/minute")
async def list_documents(
    request: Request,
    doc_type: str | None = Query(None),
    division: str | None = Query(None),
    limit: int = Query(50, le=100),
    offset: int = Query(0, ge=0),
    service: ProcurementService = Depends(_build_service),
) -> list[DocumentListItem]:
    """List procurement documents with optional filters."""
    try:
        return await service.list_documents(
            doc_type=doc_type, division=division, limit=limit, offset=offset
        )
    except DomainError as exc:
        raise _map_exception(exc) from exc


@router.get("/documents/{doc_id}", response_model=DocumentDetail)
@limiter.limit("30/minute")
async def get_document(
    request: Request,
    doc_id: uuid.UUID,
    service: ProcurementService = Depends(_build_service),
) -> DocumentDetail:
    """Get detail of one procurement document."""
    try:
        return await service.get_document(doc_id)
    except DomainError as exc:
        raise _map_exception(exc) from exc
