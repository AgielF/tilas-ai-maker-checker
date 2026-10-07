"""Parser Agent router."""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, File, Query, Request, UploadFile
from slowapi import Limiter
from slowapi.util import get_remote_address

from timbang.modules.parser.schemas import ParserExtractResponse
from timbang.modules.parser.service import ParserService
from timbang.shared.schemas.document import DocumentType

router = APIRouter(prefix="/parser", tags=["parser"])
limiter = Limiter(key_func=get_remote_address)


def _build_parser_service() -> ParserService:
    return ParserService()


@router.post("/extract", response_model=ParserExtractResponse)
@limiter.limit("10/minute")
async def parser_extract(
    request: Request,
    file: UploadFile = File(...),
    doc_type: DocumentType | None = Query(None),
    service: ParserService = Depends(_build_parser_service),
) -> ParserExtractResponse:
    """
    Extract structured data dari PDF atau Excel.
    Output: list ParsedDocument.
    """
    documents = await service.extract(file, doc_type=doc_type)
    return ParserExtractResponse(
        documents=documents,
        source_format=Path(file.filename or "").suffix.lower().lstrip("."),
        total=len(documents),
    )
