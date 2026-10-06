"""Generate four realistic sample PDFs for Checker multi-file upload testing."""

from __future__ import annotations

from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer

PROJECT_ROOT = Path(__file__).resolve().parents[2]
OUTPUT_DIR = PROJECT_ROOT / "sample-docs"

SAMPLE_DOCUMENTS = {
    "sample-po.pdf": (
        "PURCHASE ORDER",
        [
            "Nomor: PO-2026-001",
            "Tanggal: 15 September 2026",
            "Vendor: PT Maju Jaya Teknologi",
            "NPWP Vendor: 012345678901234",
            "",
            "Item: Laptop Asus VivoBook 14",
            "Quantity: 100 unit",
            "Harga Satuan: Rp 1.000.000",
            "Total: Rp 100.000.000",
            "",
            "Disetujui: Budi Santoso (Manager Purchasing)",
        ],
    ),
    "sample-gr.pdf": (
        "GOODS RECEIPT",
        [
            "Nomor: GR-2026-001",
            "Tanggal: 25 September 2026",
            "Referensi PO: PO-2026-001",
            "Vendor: PT Maju Jaya Teknologi",
            "",
            "Item: Laptop Asus VivoBook 14",
            "Quantity Diterima: 95 unit",
            "Harga Satuan: Rp 1.000.000",
            "Total: Rp 95.000.000",
            "Currency: IDR",
            "Kondisi: Baik",
            "",
            "Diterima: Andi Wijaya (Staff Gudang)",
        ],
    ),
    "sample-invoice.pdf": (
        "INVOICE",
        [
            "Nomor: INV-2026-001",
            "Tanggal: 30 September 2026",
            "Referensi PO: PO-2026-001",
            "Vendor: PT Maju Jaya Teknologi",
            "NPWP: 012345678901234",
            "",
            "Item: Laptop Asus VivoBook 14",
            "Quantity: 100 unit",
            "Harga Satuan: Rp 1.000.000",
            "DPP: Rp 100.000.000",
            "PPN (11%): Rp 11.000.000",
            "Total Invoice: Rp 111.000.000",
            "",
            "Faktur Pajak: 010.000-26.00000001",
            "Jatuh Tempo: 30 Oktober 2026",
        ],
    ),
    "sample-faktur-pajak.pdf": (
        "FAKTUR PAJAK",
        [
            "Nomor Seri: 010.000-26.00000001",
            "Tanggal: 30 September 2026",
            "",
            "Penjual:",
            "Nama: PT Maju Jaya Teknologi",
            "NPWP: 012345678901234",
            "",
            "Pembeli:",
            "Nama: PT Pembeli Contoh",
            "NPWP: 987654321098765",
            "",
            "DPP: Rp 100.000.000",
            "PPN: Rp 11.000.000",
            "Total: Rp 111.000.000",
        ],
    ),
}


def generate_pdf(filename: str, title: str, lines: list[str]) -> Path:
    """Render one document with selectable text for OCR/extraction testing."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    output_path = OUTPUT_DIR / filename

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "SampleDocumentTitle",
        parent=styles["Title"],
        alignment=TA_CENTER,
        textColor=colors.HexColor("#17324D"),
        fontName="Helvetica-Bold",
        fontSize=18,
        leading=24,
        spaceAfter=14 * mm,
    )
    body_style = ParagraphStyle(
        "SampleDocumentBody",
        parent=styles["BodyText"],
        fontName="Helvetica",
        fontSize=11,
        leading=17,
        textColor=colors.HexColor("#202B36"),
    )

    document = SimpleDocTemplate(
        str(output_path),
        pagesize=A4,
        rightMargin=22 * mm,
        leftMargin=22 * mm,
        topMargin=22 * mm,
        bottomMargin=22 * mm,
        title=title,
        author="Tilas Checker Sample Documents",
    )
    story = [Paragraph(title, title_style)]
    for line in lines:
        story.append(Paragraph(line or "&nbsp;", body_style))
        if not line:
            story.append(Spacer(1, 2 * mm))

    document.build(story)
    return output_path


def main() -> None:
    """Create all sample documents in the project-level sample-docs folder."""
    for filename, (title, lines) in SAMPLE_DOCUMENTS.items():
        path = generate_pdf(filename, title, lines)
        print(f"Generated {path.relative_to(PROJECT_ROOT)} ({path.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
