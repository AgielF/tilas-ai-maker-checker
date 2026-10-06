"""Excel parser for Bon Permintaan (Purchase Request) documents.

Parses multi-sheet Excel files with multiple BON sections per sheet.
Handles variations in headers, typo "SUPLIER" vs "SUPPLIER", and formula literals.
"""

from __future__ import annotations

import io
import re
from typing import Any

import pandas as pd

from timbang.modules.procurement.schemas import BonItem, ParsedBon

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
            # Handle both "TANGGAL:" and "TANGGAL.:"
            if cell_str.upper().startswith("TANGGAL:") or cell_str.upper().startswith("TANGGAL."):
                # Find the first colon or period+colon
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


def _parse_items_from_df(df: pd.DataFrame, start_row: int, header_row: int) -> list[BonItem]:
    """Parse item rows into BonItem objects.

    Data row structure (based on observed Excel):
    - Col 0: NO. (item number like 1, 2, 1., etc.)
    - Col 1: NAMA BARANG
    - Col 2: QTY (ORDER TO PRC)
    - Col 3: SATUAN (unit like YARD, PACK, PCS, CONES, DUS, etc.)
    - Col 8: KETERANGAN
    """
    items: list[BonItem] = []

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

        if len(df.columns) > 1:
            nb = df.iloc[row_idx, 1]
            if nb is not None and not (isinstance(nb, float) and pd.isna(nb)):
                nama_barang = str(nb).strip()

        if len(df.columns) > 2:
            qty_val = df.iloc[row_idx, 2]
            qty = _parse_qty(qty_val)

        if len(df.columns) > 3:
            sat_val = df.iloc[row_idx, 3]
            if sat_val is not None and not (isinstance(sat_val, float) and pd.isna(sat_val)):
                satuan = str(sat_val).strip()

        if len(df.columns) > 8:
            ket = df.iloc[row_idx, 8]
            if ket is not None and not (isinstance(ket, float) and pd.isna(ket)):
                keterangan = str(ket).strip()

        if nama_barang:
            items.append(
                BonItem(
                    no=no_str,
                    nama_barang=nama_barang,
                    qty=qty,
                    satuan=satuan,
                    keterangan=keterangan,
                )
            )

    return items


def _process_sheet(df: pd.DataFrame, sheet_name: str) -> list[ParsedBon]:
    """Process a single sheet DataFrame and extract all BON sections."""
    bons: list[ParsedBon] = []

    # Find all BON header rows
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

        # Find date in next few rows after BON header
        date = ""
        for look_ahead in range(1, 4):
            if bon_header_idx + look_ahead < len(df):
                date = _extract_date_from_row(df.iloc[bon_header_idx + look_ahead])
                if date:
                    break

        # Find the actual header row (contains NAMA BARANG and STOCK GUDANG)
        header_row_idx = None
        for look_ahead in range(1, 5):
            if bon_header_idx + look_ahead < len(df):
                if _is_header_row(df.iloc[bon_header_idx + look_ahead]):
                    header_row_idx = bon_header_idx + look_ahead
                    break

        if header_row_idx is None:
            # Fallback
            header_row_idx = bon_header_idx + 2

        # Extract division from header row
        division = ""
        if header_row_idx is not None and header_row_idx < len(df):
            division = _extract_division_from_header_row(df.iloc[header_row_idx])

        # Parse items
        items = _parse_items_from_df(df, bon_header_idx, header_row_idx)

        if items:
            bons.append(
                ParsedBon(
                    bon_number=bon_number,
                    date=date,
                    division=division,
                    sheet_name="",
                    items=items,
                    source_file="",
                    raw_metadata={"bon_header_row": bon_header_idx, "header_row": header_row_idx},
                )
            )

    return bons


def parse_bon_excel(file_bytes: bytes) -> list[ParsedBon]:
    """Parse Bon Permintaan Excel file bytes into structured ParsedBon objects.

    Args:
        file_bytes: Raw bytes of the Excel file (.xlsx or .xls)

    Returns:
        List of ParsedBon objects, one per BON section found in the file.
    """
    all_bons: list[ParsedBon] = []

    sheets = pd.read_excel(io.BytesIO(file_bytes), sheet_name=None, header=None)

    for sheet_name, df in sheets.items():
        if df.empty:
            continue
        sheet_bons = _process_sheet(df, sheet_name)
        for b in sheet_bons:
            b.sheet_name = sheet_name
        all_bons.extend(sheet_bons)

    return all_bons
