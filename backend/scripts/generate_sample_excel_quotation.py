"""Generate sample Excel quotation for Maker Agent testing."""

import pandas as pd
from pathlib import Path

# Create output directory
output_dir = Path("sample-docs")
output_dir.mkdir(exist_ok=True)
output_file = output_dir / "sample-quotation.xlsx"

# Build the data
header_rows = [
    ["PENAWARAN HARGA", "", "", "", "", "", ""],
    ["Nomor:", "042/PEN/PT-MJT/X/2026", "", "", "", "", ""],
    ["Tanggal:", "1 Oktober 2026", "", "", "", "", ""],
    ["Kepada:", "Divisi Pengadaan", "", "", "", "", ""],
    ["Vendor:", "PT Maju Jaya Teknologi", "", "", "", "", ""],
    ["NPWP:", "012345678901234", "", "", "", "", ""],
    ["", "", "", "", "", "", ""],
    ["No", "Nama Barang", "Spesifikasi", "Qty", "Satuan", "Harga Satuan", "Total"],
]

data_rows = [
    [1, "Laptop Asus VivoBook 14", "Core i5, RAM 8GB, SSD 512GB", 5, "unit", 9750000, 48750000],
    [2, "Printer HP LaserJet M404", "Mono laser, A4, 40ppm", 3, "unit", 4200000, 12600000],
    [3, "Kertas A4 80gsm", "500 lembar/rim", 50, "rim", 55000, 2750000],
    [4, "Tinta Printer HP 85A", "Original cartridge", 10, "pcs", 850000, 8500000],
    [5, "Flashdisk SanDisk 64GB", "USB 3.0", 20, "pcs", 120000, 2400000],
]

summary_rows = [
    ["", "", "", "", "Subtotal:", 75000000],
    ["", "", "", "", "PPN 11%:", 8250000],
    ["", "", "", "", "TOTAL:", 83250000],
    ["", "", "", "", "", ""],
    ["Syarat:", "Pembayaran 30% DP, 70% setelah barang diterima", "", "", "", ""],
    ["Garansi:", "1 tahun untuk laptop & printer", "", "", "", ""],
]

# Combine all rows
all_rows = header_rows + data_rows + summary_rows

# Create DataFrame
df = pd.DataFrame(all_rows)

# Write to Excel
with pd.ExcelWriter(output_file, engine="openpyxl") as writer:
    df.to_excel(writer, sheet_name="Penawaran", index=False, header=False)

    # Get worksheet for formatting
    ws = writer.sheets["Penawaran"]
    
    # Set column widths
    ws.column_dimensions["A"].width = 5
    ws.column_dimensions["B"].width = 35
    ws.column_dimensions["C"].width = 40
    ws.column_dimensions["D"].width = 8
    ws.column_dimensions["E"].width = 10
    ws.column_dimensions["F"].width = 15
    ws.column_dimensions["G"].width = 18

print(f"Generated: {output_file}")
print(f"Sheets: 1 (Penawaran)")
print(f"Rows: {len(all_rows)}")
print(f"Data items: {len(data_rows)}")