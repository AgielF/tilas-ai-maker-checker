"""Procurement service — business logic layer (Maker Agent).

Rules (docs/agents/BACKEND_AGENTS.md):
- Does NOT import AsyncSession — only repository interfaces.
- Orchestrates repository calls and Langflow Maker Agent.
- NEVER log API keys or tokens (docs/SECURITY.md).
"""

from __future__ import annotations

import json
import os
import re
import statistics
import time
import uuid
from decimal import Decimal
from pathlib import Path

import httpx
import structlog
from fastapi import UploadFile

from timbang.modules.procurement.bon_parser import parse_bon_excel
from timbang.modules.procurement.models import ProcurementDocument
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
from timbang.shared.core.config import get_settings
from timbang.shared.core.exceptions import (
    DomainError,
    NotFoundError,
    UpstreamError,
    ValidationError,
)

log = structlog.get_logger(__name__)

_OUTLIER_THRESHOLD = Decimal("0.30")  # 30% deviation from median

# Regex to strip markdown code fences: ```json ... ``` or ``` ... ```
_MARKDOWN_FENCE_RE = re.compile(r"```(?:json)?\s*(.+?)\s*```", re.DOTALL)


# ── Langflow helpers ──────────────────────────────────────────────────────────


def _extract_chat_text(data: dict) -> str:
    """Defensively extract the chat text from a Langflow response payload.

    Tries the canonical path first, then falls back to a recursive search
    for the first non-empty "text" value in the response tree.
    """
    # Canonical Langflow chat output path
    try:
        return str(data["outputs"][0]["outputs"][0]["results"]["message"]["text"])
    except (KeyError, IndexError, TypeError):
        pass

    # Fallback: walk the nested structure looking for a "text" key
    def _search(obj: object) -> str | None:
        if isinstance(obj, dict):
            if "text" in obj and isinstance(obj["text"], str) and obj["text"].strip():
                return obj["text"]
            for v in obj.values():
                found = _search(v)
                if found:
                    return found
        elif isinstance(obj, list):
            for item in obj:
                found = _search(item)
                if found:
                    return found
        return None

    text = _search(data)
    if text:
        return text

    # Last resort: return the raw JSON as a string
    return json.dumps(data, ensure_ascii=False)


def _try_parse_json(text: str) -> dict | None:
    """Try to parse text as JSON. Strips markdown fences if present.

    Returns the parsed dict, or None if parsing fails in all attempts.
    """
    # Attempt 1: direct parse
    try:
        parsed = json.loads(text)
        if isinstance(parsed, dict):
            return parsed
    except (json.JSONDecodeError, ValueError):
        pass

    # Attempt 2: strip markdown code fence then parse
    match = _MARKDOWN_FENCE_RE.search(text)
    if match:
        try:
            parsed = json.loads(match.group(1))
            if isinstance(parsed, dict):
                return parsed
        except (json.JSONDecodeError, ValueError):
            pass

    return None


_NA_SENTINEL = "Data tidak tersedia"


def _normalize_num(v: object) -> float | None:
    """Coerce a value to float, nulling out the 'Data tidak tersedia' sentinel."""
    if v is None:
        return None
    if isinstance(v, (int, float)):
        return float(v)
    if isinstance(v, str):
        stripped = v.strip()
        if stripped in (_NA_SENTINEL, ""):
            return None
        try:
            return float(stripped.replace(",", "").replace("Rp", "").strip())
        except ValueError:
            return None
    return None


def _normalize_sumber(sumber: object) -> list[str]:
    """Keep only valid URL strings from a sumber field.

    Handles: list of URLs, single URL string, sentinel string, None.
    """
    if sumber is None:
        return []
    if isinstance(sumber, str):
        s = sumber.strip()
        if s == _NA_SENTINEL or not s.startswith("http"):
            return []
        return [s]
    if not isinstance(sumber, list):
        return []
    return [s for s in sumber if isinstance(s, str) and s.startswith("http")]


def _normalize_llm_output(data: dict) -> dict:
    """Normalise LLM output so Pydantic model_validate won't fail.

    - Converts 'Data tidak tersedia' sentinel strings to None for numeric fields.
    - Tries to parse numeric strings (e.g. "9750000") to float.
    - Filters sumber lists so only valid URLs remain.
    """
    if not isinstance(data, dict):
        return data

    # Normalise items[]
    if not isinstance(data.get("items"), list):
        data["items"] = []
    for item in data.get("items") or []:
        if not isinstance(item, dict):
            continue
        for k in ("harga_vendor", "harga_pasar_rata", "selisih_persen", "total_price_vendor"):
            if k in item:
                item[k] = _normalize_num(item[k])
        if "sumber" in item:
            item["sumber"] = _normalize_sumber(item["sumber"])

    # Normalise kesimpulan{}
    kesimpulan = data.get("kesimpulan")
    if isinstance(kesimpulan, str):
        # LLM kadang return kesimpulan sebagai string narasi
        data["kesimpulan"] = {"ringkasan_alasan": kesimpulan.strip()}
    elif isinstance(kesimpulan, dict):
        for k in (
            "total_penawaran",
            "total_pasar",
            "total_selisih_persen",
            "skor_vendor",
            "estimasi_penghematan",
        ):
            if k in kesimpulan:
                kesimpulan[k] = _normalize_num(kesimpulan[k])
    else:
        # None atau tipe lain → set None (schema terima None)
        data["kesimpulan"] = None

    return data


def _build_response(parsed: dict) -> RecommendationResponse:
    """Normalise + validate a parsed Langflow JSON dict into RecommendationResponse.

    Raises pydantic.ValidationError on schema mismatch (caller should catch).
    """
    normalised = _normalize_llm_output(parsed)
    return RecommendationResponse.model_validate(normalised)


def _apply_math_check(response: RecommendationResponse) -> RecommendationResponse:
    """Deterministic math check: verify sum(items.total_price_vendor) == kesimpulan.total_penawaran.

    Populates kesimpulan math_check_* fields in-place and returns the response.
    Skips silently if kesimpulan is None or total_penawaran is None.
    """
    if response.kesimpulan is None:
        return response

    calculated = sum(
        item.total_price_vendor for item in response.items if item.total_price_vendor is not None
    )

    k = response.kesimpulan
    k.total_penawaran_calculated = calculated if calculated > 0 else None

    if k.total_penawaran is None or calculated == 0:
        k.math_check_status = "OK"
        k.math_check_note = "Total penawaran tidak dapat diverifikasi (data tidak lengkap)."
        return response

    discrepancy = k.total_penawaran - calculated
    percent = (discrepancy / k.total_penawaran) * 100

    k.math_discrepancy = round(discrepancy, 2)
    k.math_discrepancy_percent = round(percent, 4)

    abs_pct = abs(percent)
    if abs_pct > 5.0:
        k.math_check_status = "CRITICAL"
        k.math_check_note = (
            f"Ditemukan inkonsistensi matematis {percent:.2f}% (Rp {discrepancy:,.0f}) "
            f"antara total penawaran dan jumlah item."
        )
    elif abs_pct > 1.0:
        k.math_check_status = "WARNING"
        k.math_check_note = (
            f"Selisih {percent:.2f}% antara total penawaran dan penjumlahan item — periksa kembali."
        )
    else:
        k.math_check_status = "OK"
        k.math_check_note = "Konsisten."

    return response


class ProcurementService:
    """Business logic for the Maker Agent procurement context."""

    def __init__(
        self,
        vendor_repo: VendorRepository,
        quote_repo: PriceQuoteRepository,
        doc_repo: ProcurementDocumentRepository,
    ) -> None:
        self._vendor_repo = vendor_repo
        self._quote_repo = quote_repo
        self._doc_repo = doc_repo

    # ── Vendors ──────────────────────────────────────────────────────────────

    async def list_vendors(self, limit: int = 50) -> list[VendorRead]:
        """Return a list of all vendors."""
        vendors = await self._vendor_repo.list(limit=limit)
        return [VendorRead.model_validate(v) for v in vendors]

    async def register_vendor(self, data: VendorCreate) -> VendorRead:
        """Register a new vendor. Raises ValidationError if name already exists."""
        existing = await self._vendor_repo.get_by_name(data.name)
        if existing is not None:
            raise ValidationError(f"Vendor with name '{data.name}' already exists.")
        vendor = await self._vendor_repo.create(data)
        log.info("vendor_registered", vendor_id=str(vendor.id), name=vendor.name)
        return VendorRead.model_validate(vendor)

    # ── Quotes ───────────────────────────────────────────────────────────────

    async def submit_quote(self, vendor_id: uuid.UUID, data: PriceQuoteCreate) -> PriceQuoteRead:
        """Submit a price quote for a vendor. Raises NotFoundError if vendor missing."""
        vendor = await self._vendor_repo.get(vendor_id)
        if vendor is None:
            raise NotFoundError(f"Vendor {vendor_id} not found.")
        # Ensure vendor_id on data matches path param
        data_dict = data.model_dump()
        data_dict["vendor_id"] = vendor_id
        quote = await self._quote_repo.create(PriceQuoteCreate(**data_dict))
        log.info("quote_submitted", quote_id=str(quote.id), item=quote.item_name)
        return PriceQuoteRead.model_validate(quote)

    # ── Cross-validation ─────────────────────────────────────────────────────

    async def cross_validate_price(
        self, item_name: str, quotes: list[PriceQuoteRead] | None = None
    ) -> PriceValidationResult:
        """Calculate median price and flag outliers.

        Requires at least 2 quotes. Outlier threshold: |price-median|/median > 30%.
        """
        if quotes is None:
            db_quotes = await self._quote_repo.list_by_item(item_name)
            quotes = [PriceQuoteRead.model_validate(q) for q in db_quotes]

        if len(quotes) < 2:
            raise ValidationError(
                f"Cross-validation requires at least 2 quotes for '{item_name}', "
                f"got {len(quotes)}."
            )

        prices = [float(q.price) for q in quotes]
        median_f = statistics.median(prices)
        median = Decimal(str(median_f))
        min_price = Decimal(str(min(prices)))
        max_price = Decimal(str(max(prices)))
        spread = (max_price - min_price) / median * 100 if median else Decimal("0")

        flagged: list[uuid.UUID] = []
        for q in quotes:
            deviation = abs(q.price - median) / median if median else Decimal("0")
            if deviation > _OUTLIER_THRESHOLD:
                flagged.append(q.vendor_id)

        return PriceValidationResult(
            median=median,
            min=min_price,
            max=max_price,
            flagged_vendor_ids=flagged,
            spread_percent=spread.quantize(Decimal("0.01")),
        )

    # ── Private helpers ───────────────────────────────────────────────────────

    async def _load_quotes_for_item(self, item_name: str) -> list[PriceQuoteRead]:
        """Load and validate quotes from the repository for a given item."""
        db_quotes = await self._quote_repo.list_by_item(item_name)
        return [PriceQuoteRead.model_validate(q) for q in db_quotes]

    # ── Recommendation (Langflow Maker Agent) ─────────────────────────────────

    async def get_recommendation(
        self,
        item_name: str,
        quotes: list[PriceQuoteRead] | None = None,
    ) -> RecommendationResponse:
        """Call Langflow Maker Agent to recommend the best vendor for an item.

        Raises UpstreamError on timeout, non-200 response, or missing config.
        NEVER logs api_key.
        """
        settings = get_settings()

        # 1. Guard: flow ID must be configured
        if not settings.langflow_maker_flow_id:
            raise UpstreamError(
                "LANGFLOW_MAKER_FLOW_ID belum dikonfigurasi. "
                "Set env var LANGFLOW_MAKER_FLOW_ID sebelum menggunakan endpoint ini."
            )

        # 2. Load quotes from DB if not supplied
        if quotes is None:
            quotes = await self._load_quotes_for_item(item_name)

        if not quotes:
            raise DomainError(f"No price quotes found for item '{item_name}'.")

        # 3. Build prompt
        quotes_payload = [q.model_dump(mode="json") for q in quotes]
        prompt = (
            "Ekstrak data penawaran vendor, bandingkan harga dengan harga pasar "
            "terkini, dan berikan rekomendasi lengkap dengan sumber URL.\n\n"
            f"Item yang dianalisis: {item_name}\n"
            f"Data quote vendor: {json.dumps(quotes_payload, ensure_ascii=False)}"
        )

        # 4. Call Langflow
        url = f"{settings.langflow_base_url}/api/v1/run/{settings.langflow_maker_flow_id}"
        headers: dict[str, str] = {"Content-Type": "application/json"}
        if settings.langflow_api_key:
            headers["x-api-key"] = settings.langflow_api_key  # only if configured

        t0 = time.monotonic()
        try:
            async with httpx.AsyncClient(timeout=settings.langflow_timeout_seconds) as client:
                resp = await client.post(
                    url,
                    headers=headers,
                    json={
                        "input_value": prompt,
                        "input_type": "chat",
                        "output_type": "chat",
                    },
                )
        except httpx.TimeoutException as exc:
            raise UpstreamError(f"Langflow request timed out: {exc}") from exc
        except httpx.HTTPError as exc:
            raise UpstreamError(f"Langflow HTTP error: {exc}") from exc

        elapsed_ms = int((time.monotonic() - t0) * 1000)
        log.info(
            "langflow_maker_called",
            flow_id=settings.langflow_maker_flow_id,
            item_name=item_name,
            status_code=resp.status_code,
            elapsed_ms=elapsed_ms,
            # api_key intentionally NOT logged
        )

        # 5. Check status
        if resp.status_code != 200:
            raise UpstreamError(f"Langflow returned HTTP {resp.status_code}: {resp.text[:300]}")

        # 6. Extract chat text from Langflow response envelope
        try:
            data = resp.json()
        except json.JSONDecodeError as exc:
            raise UpstreamError(f"Langflow response is not valid JSON: {exc}") from exc

        text = _extract_chat_text(data)

        # 7. Parse text as structured JSON (handles plain JSON and markdown fences)
        parsed = _try_parse_json(text)
        if parsed is not None:
            try:
                return _build_response(parsed)
            except Exception as exc:  # noqa: BLE001 — validation errors from Pydantic
                log.warning(
                    "recommendation_parse_failed",
                    error=str(exc),
                    raw_preview=text[:300],
                )

        # 8. Fallback: wrap raw text (e.g. purely natural-language LLM output)
        return RecommendationResponse(raw_text=text, reason=text)

    # ── Recommendation with file (Langflow Maker Agent) ───────────────────────

    # Discovery notes (from /openapi.json, 2025):
    #   Upload endpoint : POST /api/v1/files/upload/{flow_id}
    #     - multipart/form-data, field "file"
    #     - Returns: {"flowId": str, "file_path": str}
    #   Run endpoint    : POST /api/v1/run/{flow_id_or_name}
    #     - JSON body with "input_value", tweaks, etc.
    #     - Tweaks keys: "File-bHzNP" (Read File node), "ChatInput-wh9pO" (Chat Input node)

    _ALLOWED_EXTENSIONS = frozenset(
        {".pdf", ".docx", ".doc", ".txt", ".csv", ".xlsx", ".xls", ".json"}
    )
    _MAX_FILE_SIZE_MB = 10

    async def get_recommendation_from_file(
        self,
        item_name: str,
        file: UploadFile,
    ) -> RecommendationResponse:
        """Upload file → Langflow Read File node → Maker Agent → Recommendation.

        Steps:
          1. Validate extension and size (≤ 10 MB).
          2. Upload file to Langflow /api/v1/files/upload/{flow_id}.
          3. Call /api/v1/run/{flow_id} with file_path tweak.
          4. Parse Langflow response → RecommendationResponse.

        Raises ValidationError on bad input, UpstreamError on Langflow failure.
        NEVER logs api_key.
        """
        settings = get_settings()

        # 1. Guard: flow ID must be configured
        if not settings.langflow_maker_flow_id:
            raise UpstreamError(
                "LANGFLOW_MAKER_FLOW_ID belum dikonfigurasi. "
                "Set env var LANGFLOW_MAKER_FLOW_ID sebelum menggunakan endpoint ini."
            )

        # 2. Validate extension
        ext = os.path.splitext(file.filename or "")[1].lower()
        if ext not in self._ALLOWED_EXTENSIONS:
            raise ValidationError(
                f"Format file tidak didukung: '{ext}'. "
                f"Gunakan: {', '.join(sorted(self._ALLOWED_EXTENSIONS))}"
            )

        # 3. Read and validate size
        content = await file.read()
        max_bytes = self._MAX_FILE_SIZE_MB * 1024 * 1024
        if len(content) > max_bytes:
            raise ValidationError(
                f"File terlalu besar: {len(content) / (1024*1024):.1f} MB. "
                f"Maks {self._MAX_FILE_SIZE_MB} MB."
            )

        flow_id = settings.langflow_maker_flow_id
        headers: dict[str, str] = {}
        if settings.langflow_api_key:
            headers["x-api-key"] = settings.langflow_api_key  # NEVER logged

        content_type = file.content_type or "application/octet-stream"

        try:
            async with httpx.AsyncClient(timeout=settings.langflow_timeout_seconds) as client:
                # 4. Upload file to Langflow (v1 files API — returns file_path)
                upload_url = f"{settings.langflow_base_url}/api/v1/files/upload/{flow_id}"
                upload_resp = await client.post(
                    upload_url,
                    headers=headers,
                    files={"file": (file.filename, content, content_type)},
                )
                if upload_resp.status_code not in (200, 201):
                    raise UpstreamError(
                        f"Langflow file upload failed HTTP {upload_resp.status_code}: "
                        f"{upload_resp.text[:300]}"
                    )
                upload_data = upload_resp.json()
                file_path: str = upload_data["file_path"]

                log.info(
                    "langflow_file_uploaded",
                    flow_id=flow_id,
                    filename=file.filename,
                    file_path=file_path,
                )

                if item_name and item_name.strip():
                    user_instruksi = f"Ekstrak dan analisis khusus item: {item_name.strip()}"
                else:
                    user_instruksi = (
                        "Ekstrak dan analisis SEMUA item yang ada "
                        "dalam dokumen penawaran vendor ini."
                    )

                # 5. Run flow with file_path tweak
                run_url = f"{settings.langflow_base_url}/api/v1/run/{flow_id}"
                t0 = time.monotonic()
                run_resp = await client.post(
                    run_url,
                    headers={**headers, "Content-Type": "application/json"},
                    json={
                        # input_value feeds ChatInput — do NOT repeat it in tweaks
                        "input_value": user_instruksi,
                        "input_type": "chat",
                        "output_type": "chat",
                        "tweaks": {
                            "File-bHzNP": {"file_path": file_path},
                        },
                    },
                )
        except httpx.TimeoutException as exc:
            raise UpstreamError(f"Langflow request timed out: {exc}") from exc
        except httpx.HTTPError as exc:
            raise UpstreamError(f"Langflow HTTP error: {exc}") from exc

        elapsed_ms = int((time.monotonic() - t0) * 1000)
        log.info(
            "langflow_maker_file_called",
            flow_id=flow_id,
            item_name=item_name,
            status_code=run_resp.status_code,
            elapsed_ms=elapsed_ms,
            # api_key intentionally NOT logged
        )

        if run_resp.status_code != 200:
            raise UpstreamError(
                f"Langflow returned HTTP {run_resp.status_code}: {run_resp.text[:300]}"
            )

        try:
            data = run_resp.json()
        except json.JSONDecodeError as exc:
            raise UpstreamError(f"Langflow response is not valid JSON: {exc}") from exc

        text = _extract_chat_text(data)
        parsed = _try_parse_json(text)
        if parsed is not None:
            try:
                return _apply_math_check(_build_response(parsed))
            except Exception as exc:  # noqa: BLE001
                log.warning(
                    "recommendation_parse_failed",
                    error=str(exc),
                    raw_preview=text[:300],
                )

        return RecommendationResponse(raw_text=text, reason=text)

    # ── Bon Permintaan Parser ───────────────────────────────────────────────────

    async def parse_bon_from_file(self, file: UploadFile) -> list[ParsedBon]:
        """Parse Bon Permintaan Excel → list of ParsedBon.

        Validates file extension and size, then delegates to bon_parser.
        Auto-saves each ParsedBon to procurement_documents.
        Raises ValidationError on bad input.
        """
        ext = Path(file.filename or "").suffix.lower()
        if ext not in {".xlsx", ".xls"}:
            raise ValidationError(
                f"Format {ext} tidak didukung untuk Bon. " f"Gunakan Excel (.xlsx, .xls)."
            )

        content = await file.read()
        max_bytes = self._MAX_FILE_SIZE_MB * 1024 * 1024
        if len(content) > max_bytes:
            raise ValidationError(
                f"File terlalu besar: {len(content) / (1024 * 1024):.1f} MB. "
                f"Maks {self._MAX_FILE_SIZE_MB} MB."
            )
        if len(content) < 4:
            raise ValidationError("File kosong atau tidak valid")

        parsed_bons = parse_bon_excel(content)

        # Auto-save each parsed BON to procurement_documents
        source_filename = file.filename or "unknown.xlsx"
        for bon in parsed_bons:
            items_json = {"items": [item.model_dump() for item in bon.items]}
            await self._doc_repo.create(
                doc_type="BON",
                doc_number=bon.bon_number,
                doc_date=bon.date,
                division=bon.division,
                vendor_reference="",
                amount=None,
                currency="IDR",
                items_json=items_json,
                raw_metadata=bon.raw_metadata,
                source_file=source_filename,
            )

        return parsed_bons

    # ── Procurement Documents ──────────────────────────────────────────────────

    def _to_list_item(self, doc: ProcurementDocument) -> DocumentListItem:
        """Convert ProcurementDocument to DocumentListItem."""
        item_count = len(doc.items_json.get("items", [])) if doc.items_json else 0
        return DocumentListItem(
            id=doc.id,
            doc_type=doc.doc_type,
            doc_number=doc.doc_number,
            doc_date=doc.doc_date,
            division=doc.division,
            vendor_reference=doc.vendor_reference,
            amount=doc.amount,
            currency=doc.currency,
            item_count=item_count,
            source_file=doc.source_file,
            created_at=doc.created_at,
        )

    def _to_detail(self, doc: ProcurementDocument) -> DocumentDetail:
        """Convert ProcurementDocument to DocumentDetail."""
        items = doc.items_json.get("items", []) if doc.items_json else []
        return DocumentDetail(
            id=doc.id,
            doc_type=doc.doc_type,
            doc_number=doc.doc_number,
            doc_date=doc.doc_date,
            division=doc.division,
            vendor_reference=doc.vendor_reference,
            amount=doc.amount,
            currency=doc.currency,
            items=items,
            raw_metadata=doc.raw_metadata or {},
            source_file=doc.source_file,
            created_at=doc.created_at,
        )

    async def list_documents(
        self,
        doc_type: str | None = None,
        division: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[DocumentListItem]:
        """List procurement documents with optional filters."""
        docs = await self._doc_repo.list_documents(
            doc_type=doc_type,
            division=division,
            limit=limit,
            offset=offset,
        )
        return [self._to_list_item(doc) for doc in docs]

    async def get_document(self, doc_id: uuid.UUID) -> DocumentDetail:
        """Get document detail by ID. Raises NotFoundError if not found."""
        doc = await self._doc_repo.get_by_id(doc_id)
        if doc is None:
            raise NotFoundError(f"Document {doc_id} not found.")
        return self._to_detail(doc)
