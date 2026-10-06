# API Contract — Tilas Frontend

Dokumen ini mendefinisikan kontrak antara frontend dan backend FastAPI.
Semua panggilan API wajib melalui `src/lib/api.js` dan di-consume via hook di `src/hooks/useApi.js`.

---

## Hook Mapping

Tabel berikut menunjukkan hook mana yang bertanggung jawab untuk endpoint mana.
Hook tinggal di `src/hooks/useApi.js` dan **hanya boleh di-consume oleh organism atau page**,
tidak oleh atom atau molecule.

| Hook | HTTP Method + Endpoint | Digunakan Di |
|---|---|---|
| `useApi.health()` | `GET /health` | `App.jsx` (startup check) |
| `useApi.listVendors()` | `GET /api/v1/procurement/vendors` | `ValidatePage`, `DashboardPage` |
| `useApi.validatePrice(item)` | `GET /api/v1/procurement/items/{name}/validate` | `ValidatePage` → `PriceTable` |
| `useApi.recommend(item)` | `GET /api/v1/procurement/items/{name}/recommend` | `MakerPage` → `RecommendationCard` |
| `useApi.createFinding(data)` | `POST /api/v1/audit/findings` | `CheckerPage` |
| `useApi.getFinding(id)` | `GET /api/v1/audit/findings/{id}` | `RiskReportPage` |
| `useApi.threeWayMatch(tx)` | `POST /api/v1/audit/transactions/{id}/match` | `CheckerPage` → `MatchGrid` |
| `useApi.riskReport(tx)` | `POST /api/v1/audit/transactions/{id}/risk-report` | `RiskReportPage` → `RiskGauge`, `FindingsList` |

---

## Endpoint Detail

### `GET /health`

Digunakan untuk cek konektivitas backend saat aplikasi dimuat.

**Response 200:**
```json
{ "status": "ok", "app": "Tilas" }
```

---

### `GET /api/v1/procurement/vendors`

Daftar semua vendor terdaftar.

**Response 200:**
```json
[
  {
    "id": "uuid",
    "name": "PT Sumber Makmur",
    "contact_email": "vendor@example.com",
    "created_at": "2026-01-01T00:00:00Z"
  }
]
```

---

### `POST /api/v1/procurement/vendors`

Daftarkan vendor baru.

**Request body:**
```json
{ "name": "PT Sumber Makmur", "contact_email": "vendor@example.com" }
```

**Response 201:** objek `VendorRead` (sama dengan item dalam daftar di atas).

**Error 400:** nama vendor sudah ada.

---

### `POST /api/v1/procurement/vendors/{vendor_id}/quotes`

Kirim penawaran harga untuk vendor tertentu.

**Request body:**
```json
{
  "item_name": "laptop",
  "price": 12500000,
  "currency": "IDR",
  "quantity": 10,
  "valid_until": "2026-12-31"
}
```

**Response 201:** objek `PriceQuoteRead`.

---

### `GET /api/v1/procurement/items/{item_name}/validate`

Cross-validasi harga lintas vendor untuk satu item.

**Response 200:**
```json
{
  "median": 12000000,
  "min": 10000000,
  "max": 15000000,
  "flagged_vendor_ids": ["uuid-vendor-a"],
  "spread_percent": 41.67
}
```

**Error 400:** kurang dari 2 quote tersedia.

---

### `GET /api/v1/procurement/items/{item_name}/recommend`

Panggil Maker Agent (Langflow). Latency ~60 detik. Wajib `AbortController`.

**Response 200:**
```json
{
  "vendor_name": "PT Sumber Makmur",
  "items": [
    {
      "item_name": "laptop",
      "recommended_vendor": "PT Sumber Makmur",
      "quoted_price": 12000000,
      "market_price": 11800000,
      "saving_estimate": 200000,
      "source_url": "https://..."
    }
  ],
  "raw_text": "...",
  "reason": "Harga terendah dengan reputasi vendor baik.",
  "estimated_saving": 200000
}
```

**Error 400:** tidak ada quote untuk item.
**Error 502:** Langflow timeout atau tidak dapat diakses.

> ⚠️ Frontend wajib menampilkan `LoadingSteps` selama menunggu, dan menangani timeout
> dengan `AbortController` (timeout 120 detik). Lihat `CONVENTIONS.md`.

---

### `POST /api/v1/audit/findings`

Buat audit finding baru.

**Request body:**
```json
{
  "transaction_id": "TX-001",
  "po_number": "PO-2026-001",
  "severity": "HIGH",
  "amount": 150000000,
  "description": "Invoice amount melebihi PO sebesar 5%",
  "sop_reference": "THREE_WAY_MATCH"
}
```

**Response 201:** objek `AuditFindingRead`.

---

### `GET /api/v1/audit/findings/{finding_id}`

Ambil satu audit finding berdasarkan UUID.

**Response 200:** objek `AuditFindingRead`.
**Response 404:** finding tidak ditemukan.

---

### `POST /api/v1/audit/transactions/{transaction_id}/match`

Three-way matching: PO, Goods Receipt, Invoice.

**Request body:**
```json
{
  "po":      { "reference": "PO-001", "quantity": 10, "amount": 125000000, "currency": "IDR" },
  "gr":      { "reference": "GR-001", "quantity": 10, "amount": 125000000, "currency": "IDR" },
  "invoice": { "reference": "INV-001", "quantity": 10, "amount": 131250000, "currency": "IDR" }
}
```

**Response 200:**
```json
{
  "matched": false,
  "discrepancies": [
    "Invoice amount 131250000 deviates from PO 125000000 by 5.00% (tolerance 1%)"
  ]
}
```

---

### `POST /api/v1/audit/transactions/{transaction_id}/risk-report`

Generate laporan risiko lengkap.

**Request body:**
```json
{
  "po":      { "reference": "PO-001", "quantity": 10, "amount": 125000000, "currency": "IDR" },
  "gr":      { "reference": "GR-001", "quantity": 10, "amount": 125000000, "currency": "IDR" },
  "invoice": { "reference": "INV-001", "quantity": 10, "amount": 131250000, "currency": "IDR" },
  "has_level2_approval": false,
  "has_complete_docs": true
}
```

**Response 200:**
```json
{
  "transaction_id": "TX-001",
  "severity": "HIGH",
  "overall_status": "FAIL",
  "findings": [ { ...AuditFindingRead } ],
  "recommendation": "Resolve discrepancy: Invoice amount deviates..."
}
```

---

## Format Error Standar

Semua error dari backend menggunakan format FastAPI default:

```json
{ "detail": "Pesan error yang dapat ditampilkan ke pengguna" }
```

Untuk rate limit (429):
```json
{
  "error": "rate_limit_exceeded",
  "detail": "60 per 1 minute"
}
```
Header `Retry-After` tersedia saat rate limited.

---

## Mapping Endpoint → Halaman

| Halaman | Endpoint yang Dipakai |
|---|---|
| `LandingPage` | `GET /health` (opsional, cek status) |
| `DashboardPage` | `GET /vendors`, `GET /findings/{id}` |
| `MakerPage` | `GET /items/{name}/recommend` |
| `ValidatePage` | `GET /vendors`, `GET /items/{name}/validate` |
| `CheckerPage` | `POST /transactions/{id}/match`, `POST /findings` |
| `RiskReportPage` | `POST /transactions/{id}/risk-report`, `GET /findings/{id}` |
