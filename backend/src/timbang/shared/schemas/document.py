"""Shared document schemas for cross-module use.

This module contains schemas that are used across multiple modules
(Procurement, Audit, etc.) for document parsing and validation.
"""

from enum import StrEnum

from pydantic import BaseModel, computed_field


class DocumentType(StrEnum):
    BON = "BON"
    PENAWARAN = "PENAWARAN"
    PO = "PO"
    SURAT_JALAN = "SJ"
    BPB = "BPB"
    INVOICE = "INVOICE"
    FAKTUR_PAJAK = "FP"
    NOTA = "NOTA"
    KASBON = "KASBON"
    BUKTI_PENGELUARAN = "BPK"
    UNKNOWN = "UNKNOWN"


class ExtractedItem(BaseModel):
    no: str = ""
    nama_barang: str = ""
    qty: float | None = None
    satuan: str = ""
    harga_satuan: float | None = None
    total: float | None = None
    keterangan: str = ""


class ParsedDocument(BaseModel):
    doc_type: DocumentType = DocumentType.UNKNOWN
    doc_number: str = ""
    doc_date: str = ""
    division: str = ""
    vendor_reference: str = ""
    vendor_name: str = ""
    amount: float | None = None
    currency: str = "IDR"
    items: list[ExtractedItem] = []
    raw_text: str = ""
    raw_metadata: dict = {}
    source_file: str = ""
    source_format: str = ""
    sheet_name: str = ""

    @computed_field
    @property
    def bon_number(self) -> str:
        """Alias for doc_number for backward compatibility with BON-specific code."""
        return self.doc_number

    @computed_field
    @property
    def date(self) -> str:
        """Alias for doc_date for backward compatibility with BON-specific code."""
        return self.doc_date
