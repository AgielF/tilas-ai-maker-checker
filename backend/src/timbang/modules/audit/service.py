"""Audit service — business logic layer (Checker Agent).

Rules (docs/agents/BACKEND_AGENTS.md):
- Does NOT import AsyncSession — only repository interfaces.
- Orchestrates matching, SOP validation, and tax-invoice validation.
"""

from __future__ import annotations

import json
import re
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

import httpx
import structlog
from fastapi import UploadFile

from timbang.modules.audit.repository import AuditFindingRepository, CheckResultRepository
from timbang.modules.audit.schemas import (
    AuditFindingCreate,
    AuditFindingRead,
    CheckResultCreate,
    DocumentData,
    DocumentExtraction,
    FraudIndication,
    MatchResult,
    MultiDocumentExtraction,
    RiskNarrative,
    RiskReportResponse,
    SopValidationResult,
    TaxInvoiceValidationResult,
)
from timbang.shared.core.config import get_settings
from timbang.shared.core.exceptions import UpstreamError, ValidationError
from timbang.shared.langflow.flow_meta import build_tweaks
from timbang.shared.parsers.excel import excel_to_csv_text
from timbang.shared.parsers.pdf import (
    _extract_langflow_text,
    _get_file_node_keys,
    _parse_multi_document_extraction,
    _upload_file_to_langflow,
    extract_all_pdf_documents,
)

log = structlog.get_logger(__name__)

# SOP thresholds
_SOP_L2_APPROVAL_THRESHOLD = Decimal("100_000_000")  # 100 juta IDR -> level 2 approval required
_SPLIT_PO_WINDOW_DAYS = 7
_SOP_05_SPLIT_PO = "SOP-05: Transaksi tidak boleh dipecah untuk hindari batas approval"
_DUPLICATE_INVOICE_WINDOW_DAYS = 3
_SOP_06_DUPLICATE_INVOICE = (
    "SOP-06: Setiap invoice harus unik per transaksi -- "
    "tidak boleh duplikat reference atau nominal"
)
_MAX_PDF_SIZE_MB = 10
_MARKDOWN_FENCE_RE = re.compile(r"```(?:json)?\s*(.+?)\s*```", re.DOTALL)


def _is_valid_tax_invoice_ref(ref: str) -> bool:
    if not ref:
        return False
    digits = "".join(character for character in ref if character.isdigit())
    return len(digits) == 16


def _citation_guard(findings: list[dict]) -> list[dict]:
    """Drop findings that have neither a source document nor an SOP citation."""
    valid: list[dict] = []
    for finding in findings:
        has_evidence = bool(finding.get("evidence_url")) or bool(finding.get("sop_clause_citation"))
        if has_evidence:
            valid.append(finding)
        else:
            log.warning(
                f"Citation guard: dropped finding without evidence: "
                f"{finding.get('description', '?')[:80]}"
            )
    return valid


def _indication_for_discrepancy(discrepancy: str) -> FraudIndication:
    text = discrepancy.lower()
    if "quantity" in text:
        return FraudIndication.QTY_DISCREPANCY
    if "amount" in text or "dpp" in text:
        return FraudIndication.PRICE_MANIPULATION
    if "duplicate" in text:
        return FraudIndication.DUPLICATE_INVOICE
    if "split" in text:
        return FraudIndication.SPLIT_PO
    return FraudIndication.UNKNOWN


def _indication_for_sop_violation(violation: str) -> FraudIndication:
    text = violation.lower()
    if "level2" in text or "approval" in text or "l2" in text:
        return FraudIndication.UNAUTHORIZED_APPROVAL
    if "complete" in text or "docs" in text:
        return FraudIndication.INCOMPLETE_DOCS
    return FraudIndication.UNKNOWN


class AuditService:
    """Business logic for the Checker Agent audit context."""

    def __init__(
        self,
        finding_repo: AuditFindingRepository,
        check_repo: CheckResultRepository,
    ) -> None:
        self._finding_repo = finding_repo
        self._check_repo = check_repo

    # ── Findings CRUD ─────────────────────────────────────────────────────────

    async def create_finding(self, data: AuditFindingCreate) -> AuditFindingRead:
        """Create and persist a new audit finding."""
        finding = await self._finding_repo.create(data)
        log.info(
            "audit_finding_created",
            finding_id=str(finding.id),
            transaction_id=finding.transaction_id,
            severity=finding.severity,
        )
        return AuditFindingRead.model_validate(finding)

    async def get_finding(self, finding_id: str) -> AuditFindingRead | None:
        """Return a single audit finding by ID."""
        import uuid as _uuid

        try:
            uid = _uuid.UUID(finding_id)
        except ValueError:
            return None
        finding = await self._finding_repo.get(uid)
        return AuditFindingRead.model_validate(finding) if finding else None

    async def list_findings(self, limit: int = 50) -> list[AuditFindingRead]:
        """Return a list of audit findings."""
        findings = await self._finding_repo.list(limit=limit)
        return [AuditFindingRead.model_validate(f) for f in findings]

    async def _enrich_with_narrative(
        self,
        findings: list[AuditFindingRead],
        transaction_id: str,
        has_level2_approval: bool,
    ) -> RiskNarrative:
        """Ask the optional risk narrator for a second opinion on deterministic findings."""
        settings = get_settings()
        flow_id = settings.langflow_narrator_flow_id
        if not flow_id:
            return RiskNarrative()

        findings_text = "\n".join(
            f"- [{finding.indication_label}] {finding.severity}: {finding.description}"
            for finding in findings
        )
        context = (
            f"Transaction: {transaction_id}\n"
            f"Has Level 2 Approval: {has_level2_approval}\n"
            f"Total Findings: {len(findings)}\n\n"
            f"Findings:\n{findings_text}"
        )
        headers: dict[str, str] = {"Content-Type": "application/json"}
        if settings.langflow_api_key:
            headers["x-api-key"] = settings.langflow_api_key

        sid, tweaks = build_tweaks("risk_narrator.json")

        try:
            async with httpx.AsyncClient(timeout=settings.langflow_timeout_seconds) as client:
                response = await client.post(
                    f"{settings.langflow_base_url}/api/v1/run/{flow_id}",
                    headers=headers,
                    json={
                        "input_value": context,
                        "input_type": "chat",
                        "output_type": "chat",
                        "session_id": sid,
                        "tweaks": tweaks,
                    },
                )
            if response.status_code != 200:
                raise UpstreamError(
                    f"Langflow narrator returned HTTP {response.status_code}: "
                    f"{response.text[:300]}"
                )
            try:
                response_data = response.json()
            except json.JSONDecodeError as exc:
                raise UpstreamError(f"Langflow narrator response is not valid JSON: {exc}") from exc

            text = _extract_langflow_text(response_data)
            parsed: object = None
            candidates = [text.strip()]
            markdown_match = _MARKDOWN_FENCE_RE.search(text)
            if markdown_match:
                candidates.insert(0, markdown_match.group(1).strip())
            for candidate in candidates:
                try:
                    parsed = json.loads(candidate)
                    break
                except (json.JSONDecodeError, ValueError):
                    continue

            if isinstance(parsed, dict):
                return RiskNarrative.model_validate(parsed)
            raise ValueError("Risk narrator output did not contain a JSON object.")
        except Exception as exc:  # narrator is optional; deterministic report must remain available
            log.warning(
                "risk_narrative_enrichment_failed",
                transaction_id=transaction_id,
                flow_id=flow_id,
                error=str(exc),
            )
            return RiskNarrative()

    async def _extract_all_documents(
        self,
        po_file: UploadFile,
        gr_file: UploadFile,
        invoice_file: UploadFile,
        tax_invoice_file: UploadFile | None = None,
    ) -> MultiDocumentExtraction:
        """Backward-compatible wrapper returning MultiDocumentExtraction object."""
        import os

        settings = get_settings()
        flow_id = settings.langflow_checker_flow_id
        if not flow_id:
            raise UpstreamError("LANGFLOW_CHECKER_FLOW_ID belum dikonfigurasi.")

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
                    "Format file tidak didukung untuk "
                    f"{document_key}. Unggah dokumen PDF atau Excel."
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
                if b"%PDF-" not in content[:1024]:
                    raise ValidationError(f"File '{filename}' bukan PDF yang valid.")
                upload_content = content
                upload_filename = filename
                content_type = file.content_type or "application/pdf"

            file_contents.append(
                (document_key, file, upload_filename, content_type, upload_content)
            )

        file_node_keys = _get_file_node_keys()
        missing_node_keys = [
            document_key
            for document_key, _file, _filename, _content_type, _content in file_contents
            if not file_node_keys.get(document_key)
        ]
        if missing_node_keys:
            raise UpstreamError(
                "LANGFLOW_FILE_NODE_IDS belum memiliki node untuk: " + ", ".join(missing_node_keys)
            )

        headers = {}
        if settings.langflow_api_key:
            headers["x-api-key"] = settings.langflow_api_key

        async with httpx.AsyncClient(timeout=settings.langflow_timeout_seconds) as client:
            uploaded_paths = {}
            for document_key, _file, upload_filename, content_type, upload_content in file_contents:
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
            fallback_path = next(iter(uploaded_paths.values()))
            file_paths_for_tweaks = {
                file_node_keys[document_key]: file_path
                for document_key, file_path in uploaded_paths.items()
            }
            missing_slots = [k for k in file_node_keys if k not in uploaded_paths]
            for slot in missing_slots:
                file_paths_for_tweaks[file_node_keys[slot]] = fallback_path

            input_value = "Ekstrak semua dokumen pengadaan"
            if missing_slots:
                input_value += (
                    " Dokumen berikut TIDAK disediakan oleh user: "
                    + ", ".join(missing_slots)
                    + ". Isi field terkait dengan null/kosong, jangan halusinasi."
                )

            sid, tweaks = build_tweaks(
                "checker_agent.json",
                input_value=input_value,
                file_paths=file_paths_for_tweaks,
            )
            run_response = await client.post(
                f"{settings.langflow_base_url}/api/v1/run/{flow_id}",
                headers={**headers, "Content-Type": "application/json"},
                json={
                    "input_type": "chat",
                    "output_type": "chat",
                    "session_id": sid,
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
        parsed = _parse_multi_document_extraction(text)

        def to_extraction(data: DocumentExtraction | None) -> DocumentExtraction | None:
            return data

        return MultiDocumentExtraction(
            po=to_extraction(parsed.po),
            gr=to_extraction(parsed.gr),
            invoice=to_extraction(parsed.invoice),
            tax_invoice=to_extraction(parsed.tax_invoice),
            raw_text=parsed.raw_text,
        )

    async def get_risk_report_from_files(
        self,
        tx_id: str,
        po_file: UploadFile,
        gr_file: UploadFile,
        invoice_file: UploadFile,
        tax_invoice_file: UploadFile | None = None,
        has_level2_approval: bool = False,
        has_complete_docs: bool = True,
    ) -> RiskReportResponse:
        """Extract three or four PDFs in one flow call and generate a risk report."""
        # Extract all PDF documents using shared parser
        extraction = await extract_all_pdf_documents(
            po_file=po_file,
            gr_file=gr_file,
            invoice_file=invoice_file,
            tax_invoice_file=tax_invoice_file,
        )

        def to_decimal(value: float | None) -> Decimal | None:
            return Decimal(str(value)) if value is not None else None

        po_extraction = extraction[0] if len(extraction) > 0 else None
        gr_extraction = extraction[1] if len(extraction) > 1 else None
        invoice_extraction = extraction[2] if len(extraction) > 2 else None
        tax_invoice_extraction = extraction[3] if len(extraction) > 3 else None

        po_data = DocumentData(
            quantity=to_decimal(po_extraction.get("quantity") if po_extraction else None)
            or Decimal("0"),
            amount=to_decimal(po_extraction.get("amount") if po_extraction else None)
            or Decimal("0"),
            currency=po_extraction.get("currency") if po_extraction else "IDR",
            reference=po_extraction.get("reference") if po_extraction else "",
            npwp_vendor=po_extraction.get("npwp_vendor") if po_extraction else "",
        )
        gr_data = DocumentData(
            quantity=to_decimal(gr_extraction.get("quantity") if gr_extraction else None)
            or Decimal("0"),
            amount=to_decimal(gr_extraction.get("amount") if gr_extraction else None)
            or Decimal("0"),
            currency=gr_extraction.get("currency") if gr_extraction else "IDR",
            reference=gr_extraction.get("reference") if gr_extraction else "",
            npwp_vendor=gr_extraction.get("npwp_vendor") if gr_extraction else "",
        )
        # Deterministic fallback: derive GR value from received quantity only
        # when the LLM did not extract a financial amount.
        if gr_data.amount is None or gr_data.amount == 0:
            if po_data.amount > 0 and po_data.quantity > 0 and gr_data.quantity > 0:
                gr_data.amount = po_data.amount * (gr_data.quantity / po_data.quantity)
                log.info(
                    "gr_amount_fallback_computed",
                    po_amount=str(po_data.amount),
                    po_qty=str(po_data.quantity),
                    gr_qty=str(gr_data.quantity),
                    computed_gr_amount=str(gr_data.amount),
                )

        invoice_data = DocumentData(
            quantity=to_decimal(invoice_extraction.get("quantity")) or Decimal("0"),
            amount=to_decimal(invoice_extraction.get("amount")) or Decimal("0"),
            currency=invoice_extraction.get("currency", "IDR"),
            reference=invoice_extraction.get("reference", ""),
            tax_invoice_ref=invoice_extraction.get("tax_invoice_ref", ""),
            ppn_amount=to_decimal(invoice_extraction.get("ppn_amount")),
            npwp_vendor=invoice_extraction.get("npwp_vendor", ""),
            dpp_amount=to_decimal(invoice_extraction.get("dpp_amount")),
        )

        if not gr_data.currency:
            gr_data.currency = po_data.currency or "IDR"
        if not invoice_data.currency:
            invoice_data.currency = po_data.currency or "IDR"

        if tax_invoice_extraction:
            invoice_data.tax_invoice_ref = (
                tax_invoice_extraction.get("reference", "") or invoice_data.tax_invoice_ref
            )
            invoice_data.dpp_amount = (
                to_decimal(tax_invoice_extraction.get("dpp_amount"))
                if tax_invoice_extraction.get("dpp_amount") is not None
                else invoice_data.dpp_amount
            )
            invoice_data.ppn_amount = (
                to_decimal(tax_invoice_extraction.get("ppn_amount"))
                if tax_invoice_extraction.get("ppn_amount") is not None
                else invoice_data.ppn_amount
            )
            invoice_data.npwp_vendor = (
                tax_invoice_extraction.get("npwp_vendor", "") or invoice_data.npwp_vendor
            )

        return await self.generate_risk_report(
            transaction_id=tx_id,
            po_data=po_data,
            gr_data=gr_data,
            invoice_data=invoice_data,
            has_level2_approval=has_level2_approval,
            has_complete_docs=has_complete_docs,
        )

    # ── Three-way matching ────────────────────────────────────────────────────

    def three_way_matching(
        self,
        po_data: DocumentData,
        gr_data: DocumentData,
        invoice_data: DocumentData,
    ) -> MatchResult:
        """Compare quantity and value between PO, Goods Receipt, and Invoice.

        Tolerance: quantity ±2%, amount/DPP ±1%.
        Pure business logic — no I/O needed, no async.
        """
        discrepancies: list[str] = []

        qty_tolerance = Decimal("0.02")
        amt_tolerance = Decimal("0.01")

        # Quantity checks
        if po_data.quantity > 0:
            qty_diff_gr = abs(gr_data.quantity - po_data.quantity) / po_data.quantity
            if qty_diff_gr > qty_tolerance:
                discrepancies.append(
                    f"GR quantity {gr_data.quantity} deviates from PO {po_data.quantity} "
                    f"by {qty_diff_gr * 100:.2f}% (tolerance 2%)"
                )
            qty_diff_inv = abs(invoice_data.quantity - po_data.quantity) / po_data.quantity
            if qty_diff_inv > qty_tolerance:
                discrepancies.append(
                    f"Invoice quantity {invoice_data.quantity} deviates from PO {po_data.quantity} "
                    f"by {qty_diff_inv * 100:.2f}% (tolerance 2%)"
                )

        # Amount checks
        if po_data.amount > 0:
            if invoice_data.dpp_amount is not None and invoice_data.dpp_amount > 0:
                invoice_amount_to_compare = invoice_data.dpp_amount
                invoice_amount_label = "DPP"
            else:
                invoice_amount_to_compare = invoice_data.amount
                invoice_amount_label = "amount"
            amt_diff_inv = abs(invoice_amount_to_compare - po_data.amount) / po_data.amount
            if amt_diff_inv > amt_tolerance:
                discrepancies.append(
                    f"Invoice {invoice_amount_label} {invoice_amount_to_compare} "
                    f"deviates from PO {po_data.amount} "
                    f"by {amt_diff_inv * 100:.2f}% (tolerance 1%)"
                )
            amt_diff_gr = abs(gr_data.amount - po_data.amount) / po_data.amount
            if amt_diff_gr > amt_tolerance:
                discrepancies.append(
                    f"GR amount {gr_data.amount} deviates from PO {po_data.amount} "
                    f"by {amt_diff_gr * 100:.2f}% (tolerance 1%)"
                )

        return MatchResult(matched=len(discrepancies) == 0, discrepancies=discrepancies)

    def validate_tax_invoice(
        self,
        po_data: DocumentData,
        invoice_data: DocumentData,
    ) -> TaxInvoiceValidationResult:
        """Validate the invoice's NPWP, VAT amount, and tax invoice number."""
        violations: list[str] = []
        po_npwp = po_data.npwp_vendor.strip()
        invoice_npwp = invoice_data.npwp_vendor.strip()
        npwp_values = [value for value in (po_npwp, invoice_npwp) if value]

        if not npwp_values:
            violations.append("NPWP vendor kosong — harus 15 digit numerik")
        for npwp in npwp_values:
            digits_only = "".join(character for character in npwp if character.isdigit())
            if len(digits_only) != 15:
                violations.append(f"NPWP '{npwp}' tidak valid — harus 15 digit numerik")

        if po_npwp and invoice_npwp:
            po_digits = "".join(character for character in po_npwp if character.isdigit())
            invoice_digits = "".join(character for character in invoice_npwp if character.isdigit())
            if po_digits != invoice_digits:
                violations.append("NPWP vendor pada PO dan faktur pajak tidak konsisten")

        if invoice_data.ppn_amount is not None and invoice_data.dpp_amount is not None:
            if invoice_data.dpp_amount > 0:
                expected_ppn = invoice_data.dpp_amount * Decimal("0.11")
                actual_ppn = invoice_data.ppn_amount
                diff_pct = abs(actual_ppn - expected_ppn) / expected_ppn * Decimal("100")
                if diff_pct > Decimal("2.0"):
                    violations.append(
                        f"PPN {actual_ppn:,.0f} tidak sesuai — "
                        f"seharusnya ≈{expected_ppn:,.0f} (11% dari DPP)"
                    )

        if invoice_data.ppn_amount is not None and invoice_data.ppn_amount > 0:
            if not invoice_data.tax_invoice_ref.strip():
                violations.append("PPN > 0 tapi nomor faktur pajak kosong")

        tax_invoice_ref = invoice_data.tax_invoice_ref.strip()
        if tax_invoice_ref and not _is_valid_tax_invoice_ref(tax_invoice_ref):
            violations.append(
                f"Nomor faktur pajak '{tax_invoice_ref}' tidak valid — "
                "harus 3 digit kode pajak + 13 digit"
            )

        return TaxInvoiceValidationResult(passed=not violations, violations=violations)

    # ── SOP validation ────────────────────────────────────────────────────────

    def validate_sop(
        self,
        amount: Decimal,
        currency: str,
        has_level2_approval: bool = False,
        has_complete_docs: bool = True,
    ) -> SopValidationResult:
        """Rule-based SOP validation.

        Rules:
        - SOP-02: Transactions > 100 juta IDR require level-2 approval.
        - All documents must be complete.
        - SOP-05: Transactions must not be split to avoid the approval threshold
          (enforced separately by detect_split_po).
        """
        violations: list[str] = []

        if currency == "IDR" and amount > _SOP_L2_APPROVAL_THRESHOLD:
            if not has_level2_approval:
                violations.append(
                    f"Transaction amount {amount:,.0f} IDR exceeds 100.000.000 IDR threshold "
                    "— level-2 approval required."
                )

        if not has_complete_docs:
            violations.append("Incomplete documentation — all supporting documents are required.")

        return SopValidationResult(passed=len(violations) == 0, violations=violations)

    def _split_po_finding(
        self,
        *,
        current_po: DocumentData,
        vendor_reference: str,
        po_count: int,
        total_amount: Decimal,
        transaction_id: str = "",
    ) -> dict:
        description = (
            f"Terdeteksi {po_count} PO dari vendor {vendor_reference} "
            f"dalam {_SPLIT_PO_WINDOW_DAYS} hari dengan total Rp {total_amount:,.0f} "
            "melebihi threshold L2"
        )
        finding_data = AuditFindingCreate(
            transaction_id=transaction_id,
            po_number=current_po.reference,
            severity="HIGH",
            amount=total_amount,
            currency=current_po.currency or "IDR",
            description=description,
            sop_reference="SOP-05",
            evidence_url=f"po:{current_po.reference}" if current_po.reference else None,
            sop_clause_citation=_SOP_05_SPLIT_PO,
            evidence_type="SPLIT_PO",
            indication_label=FraudIndication.SPLIT_PO,
            vendor_reference=vendor_reference,
        )
        return {
            "description": description,
            "evidence_url": finding_data.evidence_url,
            "sop_clause_citation": finding_data.sop_clause_citation,
            "finding_data": finding_data,
            "check_status": "FAIL",
            "check_notes": description,
            "recommendation": f"Investigate split PO pattern: {description}",
        }

    async def detect_split_po(
        self,
        current_po: DocumentData,
        vendor_reference: str,
        transaction_id: str = "",
    ) -> list[dict]:
        """Detect POs split below the L2 threshold to avoid executive approval.

        Pattern: ≥2 POs in 7 days, same vendor, each amount < L2 threshold,
        combined total > L2 threshold.
        """
        vendor = (vendor_reference or current_po.npwp_vendor or "").strip()
        if not vendor:
            return []
        if current_po.currency and current_po.currency != "IDR":
            return []
        if current_po.amount <= 0 or current_po.amount >= _SOP_L2_APPROVAL_THRESHOLD:
            return []

        since = datetime.now(UTC) - timedelta(days=_SPLIT_PO_WINDOW_DAYS)
        history = await self._finding_repo.list_recent_by_vendor(
            vendor_reference=vendor,
            since=since,
            exclude_po_number=current_po.reference,
        )

        amounts_by_po: dict[str, Decimal] = {}
        unnamed_index = 0
        for finding in history:
            amount = Decimal(str(finding.amount))
            if amount <= 0 or amount >= _SOP_L2_APPROVAL_THRESHOLD:
                continue
            po_number = (finding.po_number or "").strip()
            if not po_number:
                unnamed_index += 1
                po_number = f"_history_{unnamed_index}"
            amounts_by_po[po_number] = amount

        current_key = current_po.reference.strip() or "_current"
        amounts_by_po[current_key] = current_po.amount
        if len(amounts_by_po) < 2:
            return []

        total_amount = sum(amounts_by_po.values(), Decimal("0"))
        if total_amount <= _SOP_L2_APPROVAL_THRESHOLD:
            return []

        return [
            self._split_po_finding(
                current_po=current_po,
                vendor_reference=vendor,
                po_count=len(amounts_by_po),
                total_amount=total_amount,
                transaction_id=transaction_id,
            )
        ]

    async def detect_duplicate_invoice(
        self,
        current_invoice: DocumentData,
        vendor_reference: str,
        transaction_id: str = "",
    ) -> list[dict]:
        """Deteksi duplicate invoice via history query di audit_findings.

        Filter: vendor_reference sama.
        Cek: reference sama persis, ATAU amount sama + dalam 3 hari.
        Return list of findings (dict).
        """
        vendor = (vendor_reference or current_invoice.npwp_vendor or "").strip()
        if not vendor:
            return []
        if current_invoice.currency and current_invoice.currency != "IDR":
            return []
        if current_invoice.amount <= 0:
            return []

        since = datetime.now(UTC) - timedelta(days=_DUPLICATE_INVOICE_WINDOW_DAYS)
        history = await self._finding_repo.list_recent_invoices_by_vendor(
            vendor_reference=vendor,
            since=since,
            exclude_invoice_ref="",
        )

        current_ref = (current_invoice.reference or "").strip().upper()
        current_amount = current_invoice.amount

        for finding in history:
            raw_desc = (finding.description or "").strip()
            hist_ref = raw_desc.replace("Invoice history ", "").strip().upper()
            hist_amount = Decimal(str(finding.amount))

            if current_ref and hist_ref and current_ref == hist_ref:
                return [
                    self._duplicate_invoice_finding(
                        current_invoice=current_invoice,
                        vendor_reference=vendor,
                        match_type="EXACT_REFERENCE",
                        matched_ref=hist_ref,
                        severity="CRITICAL",
                        transaction_id=transaction_id,
                    )
                ]

            if current_amount == hist_amount:
                return [
                    self._duplicate_invoice_finding(
                        current_invoice=current_invoice,
                        vendor_reference=vendor,
                        match_type="SAME_AMOUNT_RECENT",
                        matched_ref=hist_ref,
                        severity="HIGH",
                        transaction_id=transaction_id,
                    )
                ]

        return []

    def _duplicate_invoice_finding(
        self,
        *,
        current_invoice: DocumentData,
        vendor_reference: str,
        match_type: str,
        matched_ref: str,
        severity: str,
        transaction_id: str = "",
    ) -> dict:
        if match_type == "EXACT_REFERENCE":
            description = (
                f"Invoice {current_invoice.reference} duplikat terdeteksi — "
                f"reference sama persis dengan invoice {matched_ref} dari vendor {vendor_reference}"
            )
        else:
            description = (
                f"Invoice {current_invoice.reference} duplikat terdeteksi — "
                f"amount Rp {current_invoice.amount:,.0f} sama dengan invoice {matched_ref} "
                f"dari vendor {vendor_reference} dalam {_DUPLICATE_INVOICE_WINDOW_DAYS} hari"
            )
        evidence_url = f"invoice:{current_invoice.reference}" if current_invoice.reference else None
        finding_data = AuditFindingCreate(
            transaction_id=transaction_id,
            po_number=current_invoice.reference,
            severity=severity,
            amount=current_invoice.amount,
            currency=current_invoice.currency or "IDR",
            description=description,
            sop_reference="SOP-06",
            evidence_url=evidence_url,
            sop_clause_citation=_SOP_06_DUPLICATE_INVOICE,
            evidence_type="DUPLICATE_INVOICE",
            indication_label=FraudIndication.DUPLICATE_INVOICE,
            vendor_reference=vendor_reference,
        )
        return {
            "description": description,
            "evidence_url": finding_data.evidence_url,
            "sop_clause_citation": finding_data.sop_clause_citation,
            "finding_data": finding_data,
            "check_status": "FAIL",
            "check_notes": description,
            "recommendation": f"Investigate duplicate invoice: {description}",
        }

    async def _record_invoice_history(
        self,
        transaction_id: str,
        invoice_data: DocumentData,
        vendor_reference: str,
    ) -> None:
        """Persist processed invoice so later checks can detect duplicate patterns."""
        if not invoice_data.reference and not vendor_reference:
            return
        await self._finding_repo.create(
            AuditFindingCreate(
                transaction_id=transaction_id,
                po_number=invoice_data.reference,
                severity="LOW",
                amount=invoice_data.amount,
                currency=invoice_data.currency or "IDR",
                description=f"Invoice history {invoice_data.reference or transaction_id}",
                sop_reference="INVOICE_HISTORY",
                evidence_url=(
                    f"invoice:{invoice_data.reference}" if invoice_data.reference else None
                ),
                sop_clause_citation=_SOP_06_DUPLICATE_INVOICE,
                evidence_type="INVOICE_HISTORY",
                indication_label=FraudIndication.UNKNOWN,
                vendor_reference=vendor_reference,
            )
        )

    async def _record_po_history(
        self,
        transaction_id: str,
        po_data: DocumentData,
        vendor_reference: str,
    ) -> None:
        """Persist processed PO so later checks can detect split patterns."""
        if not po_data.reference and not vendor_reference:
            return
        await self._finding_repo.create(
            AuditFindingCreate(
                transaction_id=transaction_id,
                po_number=po_data.reference,
                severity="LOW",
                amount=po_data.amount,
                currency=po_data.currency or "IDR",
                description=f"PO history {po_data.reference or transaction_id}",
                sop_reference="PO_HISTORY",
                evidence_url=f"po:{po_data.reference}" if po_data.reference else None,
                sop_clause_citation=_SOP_05_SPLIT_PO,
                evidence_type="PO_HISTORY",
                indication_label=FraudIndication.UNKNOWN,
                vendor_reference=vendor_reference,
            )
        )

    # ── Risk report ───────────────────────────────────────────────────────────

    async def generate_risk_report(
        self,
        transaction_id: str,
        po_data: DocumentData | None = None,
        gr_data: DocumentData | None = None,
        invoice_data: DocumentData | None = None,
        has_level2_approval: bool = False,
        has_complete_docs: bool = True,
    ) -> RiskReportResponse:
        """Orchestrate three-way matching, SOP and tax validation; persist findings."""
        findings: list[AuditFindingRead] = []
        overall_status = "PASS"
        severity = "LOW"
        recommendations: list[str] = []
        pending_findings: list[dict] = []

        # 1. Three-way matching (only if all three documents provided)
        if po_data and gr_data and invoice_data:
            match_result = self.three_way_matching(po_data, gr_data, invoice_data)
            if not match_result.matched:
                overall_status = "FAIL"
                severity = "HIGH"
                for disc in match_result.discrepancies:
                    finding_data = AuditFindingCreate(
                        transaction_id=transaction_id,
                        po_number=po_data.reference,
                        severity="HIGH",
                        amount=po_data.amount,
                        description=disc,
                        sop_reference="THREE_WAY_MATCH",
                        evidence_url=f"po:{po_data.reference}" if po_data.reference else None,
                        sop_clause_citation=(
                            "SOP-01: Three-way match tolerance ±2% qty, ±1% amount"
                        ),
                        evidence_type="DISCREPANCY",
                        indication_label=_indication_for_discrepancy(disc),
                        vendor_reference=(po_data.npwp_vendor or "").strip(),
                    )
                    pending_findings.append(
                        {
                            "description": disc,
                            "evidence_url": finding_data.evidence_url,
                            "sop_clause_citation": finding_data.sop_clause_citation,
                            "finding_data": finding_data,
                            "check_status": "FAIL",
                            "check_notes": disc,
                            "recommendation": f"Resolve discrepancy: {disc}",
                        }
                    )

        # 2. SOP validation
        amount = po_data.amount if po_data else Decimal("0")
        currency = po_data.currency if po_data else "IDR"
        sop_result = self.validate_sop(
            amount=amount,
            currency=currency,
            has_level2_approval=has_level2_approval,
            has_complete_docs=has_complete_docs,
        )
        tax_invoice_result = (
            self.validate_tax_invoice(po_data, invoice_data)
            if po_data is not None and invoice_data is not None
            else None
        )
        if not sop_result.passed:
            if overall_status == "PASS":
                overall_status = "WARN"
                severity = "MEDIUM"
            for violation in sop_result.violations:
                sop_citation = (
                    "SOP: Transactions above IDR 100,000,000 require level-2 approval"
                    if "level-2 approval" in violation
                    else "SOP: All supporting procurement documents must be complete"
                )
                finding_data = AuditFindingCreate(
                    transaction_id=transaction_id,
                    po_number=po_data.reference if po_data else "",
                    severity="MEDIUM",
                    amount=amount,
                    description=violation,
                    sop_reference="SOP_VALIDATION",
                    sop_clause_citation=sop_citation,
                    evidence_type="SOP_THRESHOLD",
                    indication_label=_indication_for_sop_violation(violation),
                    vendor_reference=(po_data.npwp_vendor or "").strip() if po_data else "",
                )
                pending_findings.append(
                    {
                        "description": violation,
                        "evidence_url": finding_data.evidence_url,
                        "sop_clause_citation": finding_data.sop_clause_citation,
                        "finding_data": finding_data,
                        "check_status": "WARN",
                        "check_notes": violation,
                        "recommendation": f"SOP violation: {violation}",
                    }
                )

        if tax_invoice_result and not tax_invoice_result.passed:
            if overall_status == "PASS":
                overall_status = "WARN"
            tax_has_price_violation = any(
                "ppn" in violation.lower() and "tidak sesuai" in violation.lower()
                for violation in tax_invoice_result.violations
            )
            if tax_has_price_violation:
                severity = "HIGH"
            elif overall_status != "FAIL":
                severity = "MEDIUM"

            for violation in tax_invoice_result.violations:
                is_price_violation = (
                    "ppn" in violation.lower() and "tidak sesuai" in violation.lower()
                )
                finding_data = AuditFindingCreate(
                    transaction_id=transaction_id,
                    po_number=po_data.reference,
                    severity="HIGH" if is_price_violation else "MEDIUM",
                    amount=invoice_data.amount,
                    description=violation,
                    sop_reference="TAX_INVOICE_VALIDATION",
                    evidence_url=f"invoice:{invoice_data.reference}",
                    sop_clause_citation=(
                        "SOP-03: Faktur pajak harus valid — NPWP 15 digit, PPN 11% dari DPP"
                    ),
                    evidence_type="TAX_INVOICE",
                    indication_label=(
                        FraudIndication.PRICE_MANIPULATION
                        if is_price_violation
                        else FraudIndication.INCOMPLETE_DOCS
                    ),
                    vendor_reference=(po_data.npwp_vendor or "").strip(),
                )
                pending_findings.append(
                    {
                        "description": violation,
                        "evidence_url": finding_data.evidence_url,
                        "sop_clause_citation": finding_data.sop_clause_citation,
                        "finding_data": finding_data,
                        "check_status": "WARN",
                        "check_notes": violation,
                        "recommendation": f"Tax invoice violation: {violation}",
                    }
                )

        # 4. Split PO detection (same vendor, sub-threshold POs that sum above L2)
        if po_data is not None:
            vendor_reference = (po_data.npwp_vendor or "").strip()
            split_findings = await self.detect_split_po(
                po_data,
                vendor_reference,
                transaction_id=transaction_id,
            )
            if split_findings:
                overall_status = "FAIL"
                severity = "HIGH"
                pending_findings.extend(split_findings)

        # 5. Duplicate Invoice detection (same vendor, same reference or same amount within 3 days)
        if invoice_data is not None:
            vendor_reference = (invoice_data.npwp_vendor or "").strip() or (
                po_data.npwp_vendor or ""
            ).strip()
            duplicate_findings = await self.detect_duplicate_invoice(
                invoice_data,
                vendor_reference,
                transaction_id=transaction_id,
            )
            if duplicate_findings:
                overall_status = "FAIL"
                has_critical = any(
                    f["finding_data"].severity == "CRITICAL" for f in duplicate_findings
                )
                severity = "CRITICAL" if has_critical else "HIGH"
                pending_findings.extend(duplicate_findings)

        # Citation Guard runs before any finding or check result is persisted.
        for candidate in _citation_guard(pending_findings):
            finding = await self._finding_repo.create(candidate["finding_data"])
            await self._check_repo.create(
                CheckResultCreate(
                    finding_id=finding.id,
                    status=candidate["check_status"],
                    notes=candidate["check_notes"],
                )
            )
            findings.append(AuditFindingRead.model_validate(finding))
            recommendations.append(candidate["recommendation"])

        if po_data is not None:
            await self._record_po_history(
                transaction_id=transaction_id,
                po_data=po_data,
                vendor_reference=(po_data.npwp_vendor or "").strip(),
            )

        if invoice_data is not None:
            vendor_ref = (invoice_data.npwp_vendor or "").strip()
            if not vendor_ref and po_data is not None:
                vendor_ref = (po_data.npwp_vendor or "").strip()
            await self._record_invoice_history(
                transaction_id=transaction_id,
                invoice_data=invoice_data,
                vendor_reference=vendor_ref,
            )

        log.info(
            "risk_report_generated",
            transaction_id=transaction_id,
            status=overall_status,
            finding_count=len(findings),
        )

        response = RiskReportResponse(
            transaction_id=transaction_id,
            severity=severity,
            findings=findings,
            overall_status=overall_status,
            recommendation="; ".join(recommendations) if recommendations else "No issues found.",
        )
        if get_settings().langflow_narrator_flow_id:
            response.narrative = await self._enrich_with_narrative(
                findings=findings,
                transaction_id=transaction_id,
                has_level2_approval=has_level2_approval,
            )
        return response
