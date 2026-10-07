"""PDF parser -- extract structured data via Langflow document_extractor flow."""

from __future__ import annotations

import json
import os
import re
import time
from pathlib import Path

import httpx
import structlog
from fastapi import UploadFile

from timbang.modules.audit.schemas import DocumentExtraction, MultiDocumentExtraction
from timbang.shared.core.config import get_settings
from timbang.shared.core.exceptions import UpstreamError, ValidationError
from timbang.shared.parsers.excel import excel_to_csv_text
from timbang.shared.schemas.document import DocumentType, ExtractedItem, ParsedDocument

log = structlog.get_logger(__name__)

_MAX_PDF_SIZE_MB = 10
_MARKDOWN_FENCE_RE = re.compile(r"```(?:json)?\s*(.+?)\s*```", re.DOTALL)


def _extract_langflow_text(data: dict) -> str:
    """Extract output text from Langflow's common response envelope shapes."""
    try:
        text = data["outputs"][0]["outputs"][0]["results"]["message"]["text"]
        if isinstance(text, str):
            return text
    except (KeyError, IndexError, TypeError):
        pass

    def search(value: object) -> str | None:
        if isinstance(value, dict):
            text_value = value.get("text")
            if isinstance(text_value, str) and text_value.strip():
                return text_value
            for child in value.values():
                found = search(child)
                if found:
                    return found
        elif isinstance(value, list):
            for child in value:
                found = search(child)
                if found:
                    return found
        return None

    return search(data) or json.dumps(data, ensure_ascii=False)


def _get_file_node_keys() -> dict[str, str]:
    """Return configured Langflow File node IDs or the standard node IDs."""
    settings = get_settings()
    raw = getattr(settings, "langflow_file_node_ids", "")
    if not raw:
        return {
            "po": "File-po",
            "gr": "File-gr",
            "invoice": "File-invoice",
            "tax_invoice": "File-tax-invoice",
        }
    try:
        node_keys = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise UpstreamError("LANGFLOW_FILE_NODE_IDS harus berisi JSON object yang valid.") from exc
    if not isinstance(node_keys, dict) or any(
        key not in ("po", "gr", "invoice", "tax_invoice") or not isinstance(value, str) or not value
        for key, value in node_keys.items()
    ):
        raise UpstreamError(
            "LANGFLOW_FILE_NODE_IDS harus berupa JSON object dengan nama dokumen "
            "dan node ID berupa string."
        )
    return node_keys


async def _upload_file_to_langflow(
    client: httpx.AsyncClient,
    upload_url: str,
    headers: dict[str, str],
    document_key: str,
    filename: str,
    content: bytes,
    content_type: str,
) -> str:
    """Upload a single file to Langflow and return the file_path."""
    upload_response = await client.post(
        upload_url,
        headers=headers,
        files={
            "file": (
                filename,
                content,
                content_type,
            )
        },
    )
    if upload_response.status_code not in (200, 201):
        raise UpstreamError(
            f"Langflow file upload failed HTTP {upload_response.status_code}: "
            f"{upload_response.text[:300]}"
        )
    try:
        upload_data = upload_response.json()
        file_path = upload_data["file_path"]
    except (json.JSONDecodeError, KeyError, TypeError) as exc:
        raise UpstreamError("Langflow upload response tidak memiliki file_path.") from exc
    if not isinstance(file_path, str) or not file_path:
        raise UpstreamError("Langflow upload response tidak memiliki file_path.")
    return file_path


async def extract_all_pdf_documents(
    po_file: UploadFile,
    gr_file: UploadFile,
    invoice_file: UploadFile,
    tax_invoice_file: UploadFile | None = None,
) -> list[dict]:
    """Upload 3-4 PDFs or Excel files, run the Checker flow once, and parse all extractions.

    Returns a list of dicts in order: [po, gr, invoice, tax_invoice].
    Each dict contains at minimum:
      - reference: str
      - quantity: float | None
      - amount: float | None
      - currency: str
      - npwp_vendor: str
      - raw_text: str (optional, for fallback)
    If a document fails to extract, that position will be None or empty dict.
    """
    settings = get_settings()
    flow_id = settings.langflow_checker_flow_id
    if not flow_id:
        raise UpstreamError(
            "LANGFLOW_CHECKER_FLOW_ID belum dikonfigurasi. "
            "Set env var LANGFLOW_CHECKER_FLOW_ID sebelum menggunakan endpoint ini."
        )

    named_files = [
        ("po", po_file),
        ("gr", gr_file),
        ("invoice", invoice_file),
    ]
    if tax_invoice_file is not None:
        named_files.append(("tax_invoice", tax_invoice_file))

    file_contents = []
    for document_key, file in named_files:
        filename = file.filename or ""
        extension = os.path.splitext(filename)[1].lower()
        if extension not in {".pdf", ".xlsx", ".xls"}:
            raise ValidationError(
                f"Format file tidak didukung untuk {document_key}. Unggah dokumen PDF atau Excel."
            )

        content = await file.read()
        if len(content) > 10 * 1024 * 1024:
            raise ValidationError(f"File {filename} terlalu besar. Maks 10 MB.")
        if len(content) < 4:
            raise ValidationError("File kosong atau tidak valid.")

        # Handle Excel -> convert to CSV text
        if extension in {".xlsx", ".xls"}:
            csv_text = excel_to_csv_text(content)
            upload_content = csv_text.encode("utf-8")
            upload_filename = Path(filename).stem + ".csv"
            content_type = "text/csv"
        else:
            # Validate PDF
            if b"%PDF-" not in content[:1024]:
                raise ValidationError(f"File '{filename}' bukan PDF yang valid.")
            upload_content = content
            upload_filename = filename
            content_type = file.content_type or "application/pdf"

        file_contents.append((document_key, upload_filename, content_type, upload_content))

    file_node_keys = _get_file_node_keys()
    missing_node_keys = [
        document_key
        for document_key, _filename, _content_type, _content in file_contents
        if not file_node_keys.get(document_key)
    ]
    if missing_node_keys:
        raise UpstreamError(
            "LANGFLOW_FILE_NODE_IDS belum memiliki node untuk: " + ", ".join(missing_node_keys)
        )

    headers = {}
    if settings.langflow_api_key:
        headers["x-api-key"] = settings.langflow_api_key

    try:
        async with httpx.AsyncClient(timeout=settings.langflow_timeout_seconds) as client:
            uploaded_paths = {}
            for document_key, upload_filename, content_type, upload_content in file_contents:
                file_path = await _upload_file_to_langflow(
                    client,
                    f"{settings.langflow_base_url}/api/v1/files/upload/{flow_id}",
                    headers,
                    document_key,
                    upload_filename,
                    upload_content,
                    content_type,
                )
                uploaded_paths[document_key] = file_path

            file_node_keys = _get_file_node_keys()
            tweaks = {
                file_node_keys[document_key]: {"file_path": file_path}
                for document_key, file_path in uploaded_paths.items()
            }
            started_at = time.monotonic()
            try:
                run_response = await client.post(
                    f"{settings.langflow_base_url}/api/v1/run/{flow_id}",
                    headers={**headers, "Content-Type": "application/json"},
                    json={
                        "input_value": "Ekstrak semua dokumen pengadaan",
                        "input_type": "chat",
                        "output_type": "chat",
                        "tweaks": tweaks,
                    },
                )
            except httpx.TimeoutException as exc:
                raise UpstreamError(f"Langflow request timed out: {exc}") from exc
            except httpx.HTTPError as exc:
                raise UpstreamError(f"Langflow HTTP error: {exc}") from exc

        elapsed_ms = int((time.monotonic() - started_at) * 1000)
        log.info(
            "langflow_checker_documents_extracted",
            flow_id=flow_id,
            document_count=len(file_contents),
            status_code=run_response.status_code,
            elapsed_ms=elapsed_ms,
        )
        if run_response.status_code != 200:
            raise UpstreamError(
                f"Langflow returned HTTP {run_response.status_code}: {run_response.text[:300]}"
            )
        try:
            response_data = run_response.json()
        except json.JSONDecodeError as exc:
            raise UpstreamError(f"Langflow response is not valid JSON: {exc}") from exc

        text = _extract_langflow_text(response_data)
        parsed = _parse_multi_document_extraction(text)

        def to_dict(extraction: DocumentExtraction | None) -> dict:
            if extraction is None:
                return {}
            data = extraction.model_dump()
            data.setdefault("raw_text", "")
            return data

        result_list = [
            to_dict(parsed.po),
            to_dict(parsed.gr),
            to_dict(parsed.invoice),
            to_dict(parsed.tax_invoice),
        ]
        return result_list
    except UpstreamError:
        raise
    except Exception as exc:
        raise UpstreamError(f"Unexpected error during PDF extraction: {exc}") from exc


def _parse_multi_document_extraction(text: str) -> MultiDocumentExtraction:
    """Parse the combined output or retain unstructured output for diagnosis.

    Returns a MultiDocumentExtraction object for backward compatibility.
    """
    from timbang.modules.audit.schemas import MultiDocumentExtraction

    parsed = None
    candidates = [text.strip()]
    markdown_match = re.compile(r"```(?:json)?\s*(.+?)\s*```", re.DOTALL).search(text)
    if markdown_match:
        candidates.insert(0, markdown_match.group(1).strip())
    for candidate in candidates:
        try:
            parsed = json.loads(candidate)
            break
        except (json.JSONDecodeError, ValueError):
            continue

    if isinstance(parsed, dict):
        try:
            return MultiDocumentExtraction.model_validate(parsed)
        except Exception:
            pass

    return MultiDocumentExtraction(raw_text=text)


async def extract_pdf_document(
    file: UploadFile, doc_type: str | None = None
) -> list[ParsedDocument]:
    """Extract ONE PDF -> list[ParsedDocument]. For Task 2.3 parser.

    Upload 1 PDF -> call maker flow -> parse -> return list of ParsedDocument.
    """
    settings = get_settings()
    flow_id = settings.langflow_maker_flow_id
    if not flow_id:
        raise UpstreamError(
            "LANGFLOW_MAKER_FLOW_ID belum dikonfigurasi. "
            "Set env var LANGFLOW_MAKER_FLOW_ID sebelum menggunakan endpoint ini."
        )

    filename = file.filename or ""
    extension = os.path.splitext(filename)[1].lower()
    if extension != ".pdf":
        raise ValidationError("Format file tidak didukung. Unggah dokumen PDF.")

    content = await file.read()
    if len(content) > 10 * 1024 * 1024:
        raise ValidationError(f"File {filename} terlalu besar. Maks 10 MB.")
    if b"%PDF-" not in content[:1024]:
        raise ValidationError(f"File '{filename}' bukan PDF yang valid.")

    headers = {}
    if settings.langflow_api_key:
        headers["x-api-key"] = settings.langflow_api_key

    async with httpx.AsyncClient(timeout=settings.langflow_timeout_seconds) as client:
        upload_url = f"{settings.langflow_base_url}/api/v1/files/upload/{flow_id}"
        upload_response = await client.post(
            upload_url,
            headers=headers,
            files={
                "file": (
                    filename,
                    content,
                    file.content_type or "application/pdf",
                )
            },
        )
        if upload_response.status_code not in (200, 201):
            raise UpstreamError(
                f"Langflow file upload failed HTTP {upload_response.status_code}: "
                f"{upload_response.text[:300]}"
            )
        try:
            upload_data = upload_response.json()
            file_path = upload_data["file_path"]
        except (json.JSONDecodeError, KeyError, TypeError) as exc:
            raise UpstreamError("Langflow upload response tidak memiliki file_path.") from exc

        tweaks = {"File-bHzNP": {"file_path": file_path}}

        run_response = await client.post(
            f"{settings.langflow_base_url}/api/v1/run/{flow_id}",
            headers={**headers, "Content-Type": "application/json"},
            json={
                "input_value": "Ekstrak data dari dokumen ini",
                "input_type": "chat",
                "output_type": "chat",
                "tweaks": tweaks,
            },
        )

    if run_response.status_code != 200:
        raise UpstreamError(
            f"Langflow returned HTTP {run_response.status_code}: {run_response.text[:300]}"
        )

    try:
        response_data = run_response.json()
    except json.JSONDecodeError as exc:
        raise UpstreamError(f"Langflow response is not valid JSON: {exc}") from exc

    text = _extract_langflow_text(response_data)

    parsed_doc = ParsedDocument(
        doc_type=DocumentType.UNKNOWN,
        doc_number="",
        doc_date="",
        vendor_reference="",
        vendor_name="",
        amount=None,
        currency="IDR",
        items=[],
        raw_text=text,
        source_file=filename,
        source_format="pdf",
    )

    candidates = [text.strip()]
    markdown_match = _MARKDOWN_FENCE_RE.search(text)
    if markdown_match:
        candidates.insert(0, markdown_match.group(1).strip())

    for candidate in candidates:
        try:
            data = json.loads(candidate)
            if isinstance(data, dict):
                parsed_doc.doc_type = DocumentType(data.get("document_type", "UNKNOWN").upper())
                parsed_doc.doc_number = data.get("reference", "") or data.get("doc_number", "")
                parsed_doc.doc_date = data.get("doc_date", "") or data.get("date", "")
                parsed_doc.vendor_reference = data.get("npwp_vendor", "") or data.get(
                    "vendor_reference", ""
                )
                parsed_doc.vendor_name = data.get("vendor_name", "")
                parsed_doc.amount = data.get("amount")
                parsed_doc.currency = data.get("currency", "IDR")
                if "items" in data and isinstance(data["items"], list):
                    parsed_doc.items = [
                        ExtractedItem(
                            no=str(item.get("no", "")),
                            nama_barang=item.get("nama_barang", ""),
                            qty=item.get("qty"),
                            satuan=item.get("satuan", ""),
                            harga_satuan=item.get("harga_satuan"),
                            total=item.get("total"),
                            keterangan=item.get("keterangan", ""),
                        )
                        for item in data["items"]
                    ]
                break
        except (json.JSONDecodeError, ValueError, KeyError):
            continue

    return [parsed_doc]
