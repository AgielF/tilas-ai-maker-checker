"""Excel parser for document documents.

Parses multi-sheet Excel files with multiple document sections per sheet.
Handles variations in headers, typo "SUPLIER" vs "SUPPLIER", and formula literals.
"""

from __future__ import annotations

import io
import re
from typing import Any

import pandas as pd

from timbang.shared.schemas.document import DocumentType, ExtractedItem, ParsedDocument


_BON_KEYWORDS = [
    "BON PERMINTAAN BARANG",
    "BON PETMINTAAN BARANG",  # typo in sample
]

_DIVISION_KEYWORDS = [
    "PPIC",
    "PURCHASING",
    "PACKING",
    "PACK",
    "SAMPLE",
    "OFFICE",
]

_FOOTER_KEYWORDS = ["DIBUAT", "MENYETUJUI"]


def _is_bon_header_row(row: pd.Series) -> bool:
    """Check if row contains a BON header marker."""
    for cell in row:
        if isinstance(cell, str):
            cell_upper = cell.strip().upper()
            if any(kw in cell_upper for kw in _BON_KEYWORDS):
                return True
    return False


def _extract_bon_number(row: pd.Series) -> str:
    """Extract BON number from header row."""
    for cell in row:
        if isinstance(cell, str):
            cell_str = cell.strip()
            if cell_str.upper().startswith("NO.:"):
                parts = cell_str.split(":")
                if len(parts) > 1:
                    return parts[1].strip()
    return ""


def _extract_date_from_row(row: pd.Series) -> str:
    """Extract date from a row containing TANGGAL."""
    for cell in row:
        if isinstance(cell, str):
            cell_str = cell.strip()
            if cell_str.upper().startswith("TANGGAL:") or cell_str.upper().startswith("TANGGAL."):
                if ": " in cell_str:
                    parts = cell_str.split(": ", 1)
                    if len(parts) > 1:
                        return parts[1].strip()
                elif "TANGGAL.:" in cell_str.upper():
                    parts = cell_str.split("TANGGAL.:", 1)
                    if len(parts) > 1:
                        return parts[1].strip()
    return ""


def _extract_division_from_header_row(row: pd.Series) -> str:
    """Extract division from header row - look for PPIC, PURCHASING, etc. in column 2."""
    if len(row) > 2:
        cell = row.iloc[2]
        if isinstance(cell, str):
            cell_upper = cell.strip().upper()
            if cell_upper in _DIVISION_KEYWORDS:
                return cell_upper
    for cell in row:
        if isinstance(cell, str):
            cell_upper = cell.strip().upper()
            if cell_upper in _DIVISION_KEYWORDS:
                return cell_upper
    return ""


def _is_footer_row(row: pd.Series) -> bool:
    """Check if row is a footer (DIBUAT / MENYETUJUI)."""
    for cell in row:
        if isinstance(cell, str):
            cell_upper = cell.strip().upper()
            if any(kw in cell_upper for kw in _FOOTER_KEYWORDS):
                return True
    return False


def _parse_qty(val: Any) -> float | None:
    """Parse quantity from cell, handling formulas and non-numeric values."""
    if val is None:
        return None
    if isinstance(val, (int, float)):
        if isinstance(val, float) and pd.isna(val):
            return None
        return float(val)
    if isinstance(val, str):
        s = val.strip()
        if not s or s.startswith("="):
            return None
        s = s.replace(",", ".")
        try:
            return float(s)
        except ValueError:
            return None
    return None


def _is_header_row(row: pd.Series) -> bool:
    """Check if row is a column header row."""
    row_text = " ".join(str(c).upper() for c in row if pd.notna(c))
    return "NAMA BARANG" in row_text and "STOCK GUDANG" in row_text


def _detect_columns(header_row: pd.Series) -> dict[str, int]:
    """Detect column indices from header row."""
    cols = {}
    for idx, cell in enumerate(header_row):
        if isinstance(cell, str):
            cell_upper = cell.strip().upper()
            if "NO" in cell_upper and ("." in cell or "NO" == cell_upper):
                cols["no"] = idx
            elif "NAMA BARANG" in cell_upper:
                cols["nama_barang"] = idx
            elif "ORDER TO PRC" in cell_upper:
                cols["qty"] = idx
                cols["qty_source"] = "ORDER TO PRC"
            elif "QTY" in cell_upper and "qty" not in cols:
                cols["qty"] = idx
                cols["qty_source"] = "QTY"
            elif "SATUAN" in cell_upper or "UNIT" in cell_upper:
                cols["satuan"] = idx
            elif "STOCK GUDANG" in cell_upper:
                cols["stock_gudang"] = idx
            elif "UNIT" in cell_upper:
                cols["satuan"] = idx
            elif "KETERANGAN" in cell_upper:
                cols["keterangan"] = idx
            elif "HARGA" in cell_upper:
                cols["harga"] = idx
    return cols


def _parse_items_from_df(df: pd.DataFrame, start_row: int, header_row: int) -> list[ExtractedItem]:
    """Parse item rows into ExtractedItem objects.

    Dynamically detects column positions from header row.
    """
    header_row_data = df.iloc[header_row]
    col_map = _detect_columns(header_row_data)
    
    no_col = col_map.get("no", 0)
    nama_col = col_map.get("nama_barang", 1)
    qty_col = col_map.get("qty", 2)
    
    # Smart satuan column detection
    satuan_col = col_map.get("satuan")
    if satuan_col is not None and "stock_gudang" in col_map and col_map.get("stock_gudang") == satuan_col:
        satuan_col = qty_col + 1
    elif satuan_col is None:
        satuan_col = qty_col + 1
    else:
        satuan_col = col_map["satuan"]
    
    keterangan_col = col_map.get("keterangan", 8)

    items: list[ExtractedItem] = []

    for row_idx in range(header_row + 1, len(df)):
        if _is_footer_row(df.iloc[row_idx]):
            break

        no_val = df.iloc[row_idx, 0] if len(df.columns) > 0 else None
        if no_val is None or (isinstance(no_val, float) and pd.isna(no_val)):
            continue

        no_str = str(no_val).strip()
        if not re.match(r"^\d+[.\s]?$", no_str) and not re.match(r"^\d+$", no_str):
            if not no_str[0].isdigit():
                continue

        nama_barang = ""
        qty = None
        satuan = ""
        keterangan = ""

        if len(df.columns) > nama_col:
            nb = df.iloc[row_idx, nama_col]
            if nb is not None and not (isinstance(nb, float) and pd.isna(nb)):
                nama_barang = str(nb).strip()

        if len(df.columns) > qty_col:
            qty_val = df.iloc[row_idx, qty_col]
            qty = _parse_qty(qty_val)

        if len(df.columns) > satuan_col:
            sat_val = df.iloc[row_idx, satuan_col]
            if sat_val is not None and not (isinstance(sat_val, float) and pd.isna(sat_val)):
                satuan = str(sat_val).strip()

        if len(df.columns) > keterangan_col:
            ket = df.iloc[row_idx, keterangan_col]
            if ket is not None and not (isinstance(ket, float) and pd.isna(ket)):
                keterangan = str(ket).strip()

        if nama_barang:
            items.append(
                ExtractedItem(
                    no=no_str,
                    nama_barang=nama_barang,
                    qty=qty,
                    satuan=satuan,
                    keterangan=keterangan,
                )
            )

    return items


def _process_sheet(df: pd.DataFrame, sheet_name: str) -> list[ParsedDocument]:
    docs: list[ParsedDocument] = []

    bon_header_indices = []
    bon_numbers = []
    for i, row in df.iterrows():
        if _is_bon_header_row(row):
            bon_number = _extract_bon_number(row)
            if bon_number:
                bon_header_indices.append(i)
                bon_numbers.append(bon_number)

    if not bon_header_indices:
        return []

    for idx, bon_header_idx in enumerate(bon_header_indices):
        bon_number = bon_numbers[idx]

        date = ""
        for look_ahead in range(1, 4):
            if bon_header_idx + look_ahead < len(df):
                date = _extract_date_from_row(df.iloc[bon_header_idx + look_ahead])
                if date:
                    break

        header_row_idx = None
        for look_ahead in range(1, 5):
            if bon_header_idx + look_ahead < len(df):
                if _is_header_row(df.iloc[bon_header_idx + look_ahead]):
                    header_row_idx = bon_header_idx + look_ahead
                    break

        if header_row_idx is None:
            header_row_idx = bon_header_idx + 2

        date = ""
        for look_ahead in range(1, 4):
            if bon_header_idx + look_ahead < len(df):
                date = _extract_date_from_row(df.iloc[bon_header_idx + look_ahead])
                if date:
                    break

        division = ""
        if header_row_idx is not None and header_row_idx < len(df):
            division = _extract_division_from_header_row(df.iloc[header_row_idx])

        items = _parse_items_from_df(df, bon_header_idx, header_row_idx)

        if items:
            docs.append(
                ParsedDocument(
                    doc_type=DocumentType.BON,
                    doc_number=bon_number,
                    doc_date=date,
                    division=division,
                    sheet_name="",
                    items=items,
                    source_file="",
                    raw_metadata={"bon_header_row": bon_header_idx, "header_row": header_row_idx},
                )
            )

    return docs


def parse_excel_document(file_bytes: bytes) -> list[ParsedDocument]:
    all_docs: list[ParsedDocument] = []

    sheets = pd.read_excel(io.BytesIO(file_bytes), sheet_name=None, header=None)

    for sheet_name, df in sheets.items():
        if df.empty:
            continue
        sheet_docs = _process_sheet(df, sheet_name)
        for d in sheet_docs:
            d.sheet_name = sheet_name
        all_docs.extend(sheet_docs)

    return all_docs


parse_bon_excel = parse_excel_document