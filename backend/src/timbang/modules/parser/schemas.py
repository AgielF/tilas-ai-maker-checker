"""Parser module schemas."""

from pydantic import BaseModel

from timbang.shared.schemas.document import ParsedDocument


class ParserExtractResponse(BaseModel):
    documents: list[ParsedDocument] = []
    source_format: str = ""
    total: int = 0
