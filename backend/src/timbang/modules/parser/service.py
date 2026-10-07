"""Parser Agent — facade untuk shared parsers (excel + pdf)."""

from __future__ import annotations

from pathlib import Path

import structlog
from fastapi import UploadFile

from timbang.shared.core.exceptions import ValidationError
from timbang.shared.parsers.excel import parse_excel_document
from timbang.shared.parsers.pdf import extract_pdf_document
from timbang.shared.schemas.document import DocumentType, ParsedDocument

log = structlog.get_logger(__name__)

_MAX_FILE_SIZE_BYTES = 10 * 1024 * 1024


class ParserService:
    """Orchestrator: detect file type → route ke shared parser."""

    async def extract(
        self,
        file: UploadFile,
        doc_type: DocumentType | None = None,
    ) -> list[ParsedDocument]:
        """
        Detect extension + route:
        - .xlsx / .xls → excel parser (deterministic)
        - .pdf → pdf parser (Langflow)
        - .jpg/.jpeg/.png → Phase 2 (raise ValidationError)
        """
        filename = file.filename or ""
        extension = Path(filename).suffix.lower()

        content = await file.read()
        if len(content) < 4:
            raise ValidationError("File kosong atau tidak valid.")
        if len(content) > _MAX_FILE_SIZE_BYTES:
            raise ValidationError(
                f"File terlalu besar (>{_MAX_FILE_SIZE_BYTES // (1024 * 1024)} MB)."
            )

        log.info(
            "parser_extract_started",
            filename=filename,
            extension=extension,
            size_bytes=len(content),
            doc_type=doc_type.value if doc_type else None,
        )

        if extension in {".xlsx", ".xls"}:
            documents = parse_excel_document(content)
            log.info(
                "parser_extract_excel_done",
                filename=filename,
                documents=len(documents),
            )
            return documents

        if extension == ".pdf":
            await file.seek(0)
            documents = await extract_pdf_document(file, doc_type=doc_type)
            log.info(
                "parser_extract_pdf_done",
                filename=filename,
                documents=len(documents),
            )
            return documents

        if extension in {".jpg", ".jpeg", ".png"}:
            raise ValidationError("Format foto (OCR) belum diimplementasi. Gunakan PDF atau Excel.")

        raise ValidationError(f"Format '{extension}' tidak didukung. Gunakan PDF atau Excel.")
