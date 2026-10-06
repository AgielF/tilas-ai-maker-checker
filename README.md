# Tilas — Jejak Pengadaan yang Tak Hilang

> Jejak yang tak pernah hilang.

[![Python 3.12+](https://img.shields.io/badge/python-3.12%2B-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115%2B-009688.svg)](https://fastapi.tiangolo.com/)
[![React 19](https://img.shields.io/badge/React-19-61DAFB.svg)](https://react.dev/)
[![Langflow](https://img.shields.io/badge/Langflow-1.12-orange.svg)](https://langflow.org/)
[![Tests](https://img.shields.io/badge/tests-72%2B-brightgreen.svg)](#testing)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

**Tilas** (Jawa: *jejak, bekas*) adalah sistem AI Maker–Checker untuk deteksi fraud pengadaan di perusahaan menengah Indonesia tanpa ERP. Target submission: IBM SkillsBuild University Education National Hackathon 2026.

---

## Table of Contents

- [Problem Statement](#problem-statement)
- [Solution](#solution)
- [Arsitektur Hybrid 3-Layer](#arsitektur-hybrid-3-layer)
- [Fitur](#fitur)
- [Cara Run](#cara-run)
- [Struktur Folder](#struktur-folder)
- [Database Schema](#database-schema)
- [Technical Requirements Document (TRD)](#technical-requirements-document-trd)
- [API Reference](#api-reference)
- [Testing](#testing)
- [Differentiator](#differentiator)
- [Tech Stack](#tech-stack)
- [Security](#security)
- [Roadmap](#roadmap)
- [Team](#team)
- [License](#license)
- [Acknowledgments](#acknowledgments)

---

## Problem Statement

Perusahaan menengah Indonesia kehilangan ~5% revenue/tahun akibat fraud pengadaan ([ACFE 2026](https://www.acfe.com/)). Tanpa ERP, tanpa sistem audit terintegrasi.

Tim purchasing mengelola quote vendor, PO, goods receipt, dan invoice lewat spreadsheet dan email. Blind spot yang sering dieksploitasi:

- **Price inflation** — penawaran di atas harga pasar tanpa benchmarking otomatis
- **Fictitious vendors** — pembayaran ke vendor fiktif tanpa barang
- **Document manipulation** — jumlah invoice diubah setelah barang diterima
- **SOP bypass** — transaksi bernilai tinggi tanpa approval L2

---

## Solution

Tilas mengotomasi kerja auditor pengadaan **sebelum pembayaran disetujui**, dengan keputusan akhir tetap di manusia.

- **Maker Agent** — analisis penawaran + cross-validate harga pasar (Serper / marketplace)
- **Checker Agent** — 4-way matching (PO / GR / Invoice / Faktur Pajak) + SOP + citation guard
- **Human-in-the-loop** — keputusan akhir di staf purchasing, bukan auto-approve

---

## Arsitektur Hybrid 3-Layer

LLM **tidak** menghitung risiko. LLM mengekstrak dan menarasikan. Aturan, angka, dan bukti dijalankan di Python.

```mermaid
flowchart LR
  FE[Frontend React 19]
  BE[Backend FastAPI]
  LF[Langflow flows]
  R9[9Router]
  LLM[Gemini / Groq / Cerebras]

  FE -->|REST /api/v1| BE
  BE --> LF
  LF --> R9
  R9 --> LLM
  BE --> PG[(PostgreSQL / SQLite)]
  BE --> RD[(Redis rate limit)]
```

Dependensi backend selalu satu arah: `router → service → repository → model`. Modul lain hanya boleh import `public_api.py`.

### Layer 1 — LLM Extraction (`checker_agent`)

Terima PDF PO / GR / Invoice / Faktur Pajak → JSON terstruktur (`reference`, qty, amount, DPP, PPN, NPWP).

Maker memakai flow terpisah: upload PDF penawaran → item, harga vendor, sitasi URL, skor vendor.

### Layer 2 — Deterministic Engine (Python)

| Check | Aturan |
|---|---|
| 4-way matching | Qty ±2%, amount/DPP ±1% (PO vs GR vs Invoice; FP sebagai dokumen ke-4) |
| SOP validation | Transaksi > IDR 100 juta wajib approval L2 |
| Faktur pajak | NPWP 15 digit, PPN ≈ 11% dari DPP, nomor FP 16 digit |
| Citation guard | Temuan tanpa `evidence_url` atau `sop_clause_citation` **dibuang** |
| Fraud labels | 6 tipe indikasi (lihat Checker) |
| Math check | Total penawaran dihitung ulang, tidak percaya angka LLM |

### Layer 3 — LLM Narrative (`risk_narrator`)

Setelah engine selesai, flow narrator (opsional, `LANGFLOW_NARRATOR_FLOW_ID`) mengisi:

- Executive summary
- Pattern analysis
- Dynamic recommendations

Narasi **tidak** mengubah skor atau temuan. Temuan sudah di-persist lewat repository (audit trail yang bisa di-replay).

Diagram C4 dan ADR: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

---

## Fitur

### Maker Agent (`/maker`)

Modul `procurement` — rekomendasi vendor dari PDF penawaran.

- Upload PDF, ekstraksi otomatis via Langflow (`POST /items/recommend-with-file`)
- **Fokus item opsional** — kosongkan untuk *general scan* seluruh dokumen
- Cross-validate harga via Serper API (di flow Langflow)
- Sitasi URL per item (Tokopedia, Shopee, Lazada, dll.)
- Skor vendor 0–100 (`kesimpulan.skor_vendor`)
- Math check deterministik: `OK` / `WARNING` / `CRITICAL` jika total item ≠ total penawaran
- Endpoint legacy: `GET /items/{item_name}/recommend` (tanpa file)

### Checker Agent (`/checker`)

Modul `audit` — matching dokumen + laporan risiko.

- Upload 4 PDF (PO, GR, Invoice, FP) → `POST /transactions/{tx_id}/risk-report-with-files`
- Tab UI: **Upload PDF** | **Input Manual**
- 4-way matching (qty ±2%, amount ±1%)
- SOP validation (threshold L2 100 juta IDR)
- Faktur pajak validation (NPWP, PPN 11%, nomor FP)
- Citation guard
- 6 fraud indication labels:
  - `PRICE_MANIPULATION`
  - `QTY_DISCREPANCY`
  - `SPLIT_PO`
  - `DUPLICATE_INVOICE`
  - `UNAUTHORIZED_APPROVAL`
  - `INCOMPLETE_DOCS`
- **Split PO Detection** — deteksi 2+ PO kecil dari vendor sama dalam 7 hari, total > Rp 100jt → finding `SPLIT_PO` (HIGH)
- **Duplicate Invoice Detection** — reference sama persis (CRITICAL) atau amount sama + vendor sama dalam 3 hari (HIGH)
- **Math check** — deterministik `OK` / `WARNING` / `CRITICAL` jika total item ≠ total penawaran
- Layer 3 narrative (jika narrator flow dikonfigurasi)
- Risk score 0–100 di UI (`/checker/risk-report`) dari severity laporan

Halaman lain: landing `/`, Coming Soon untuk Dashboard, Vendor Management, Findings, About.

---

## Database Schema

Tilas menggunakan **SQLAlchemy 2.0 async** dengan dukungan SQLite (dev) 
dan PostgreSQL (production). Database menyimpan vendor master, riwayat harga, 
audit findings, dan keputusan reviewer.

### Entity Relationship Diagram (ERD)

```mermaid
erDiagram
    VENDORS ||--o{ PRICE_QUOTES : "has many"
    VENDORS ||--o{ AUDIT_FINDINGS : "referenced in"
    AUDIT_FINDINGS ||--o{ CHECK_RESULTS : "has many"
    
    VENDORS {
        uuid id PK
        string name
        string npwp
        string contact_email
        string phone
        text address
        datetime created_at
    }
    
    PRICE_QUOTES {
        uuid id PK
        uuid vendor_id FK
        string item_name
        numeric price
        string currency
        string source_url
        datetime valid_until
        text notes
        datetime created_at
    }
    
    AUDIT_FINDINGS {
        uuid id PK
        string transaction_id
        string po_number
        string severity
        numeric amount
        string currency
        text description
        string sop_reference
        string evidence_url
        string sop_clause_citation
        string evidence_type
        string indication_label
        string vendor_reference
        datetime created_at
    }
    
    CHECK_RESULTS {
        uuid id PK
        uuid finding_id FK
        string status
        text notes
        string evidence_url
        datetime checked_at
    }
```

### Tabel Utama

#### 1. vendors — Master Data Vendor

| Kolom | Tipe | Deskripsi |
|---|---|---|
| id | UUID | Primary key |
| name | VARCHAR | Nama vendor |
| npwp | VARCHAR | NPWP 15 digit (unique constraint) |
| contact_email | VARCHAR | Email kontak |
| phone | VARCHAR | Telepon |
| address | TEXT | Alamat |
| created_at | DATETIME | Timestamp create |

**Fitur:**
- CRUD via `/api/v1/procurement/vendors`
- Unique NPWP constraint untuk prevent duplicate
- Referenced untuk split PO & duplicate invoice detection

#### 2. price_quotes — Riwayat Harga Vendor

| Kolom | Tipe | Deskripsi |
|---|---|---|
| id | UUID | Primary key |
| vendor_id | UUID FK | Refer ke vendors |
| item_name | VARCHAR | Nama item |
| price | NUMERIC(14,2) | Harga |
| currency | VARCHAR | IDR/USD |
| source_url | VARCHAR | URL sumber (opsional) |
| valid_until | DATETIME | Berlaku sampai (opsional) |
| notes | TEXT | Catatan |
| created_at | DATETIME | Timestamp |

**Fitur:**
- Cross-validate harga: outlier > 30% median → flagged
- Endpoint GET `/items/{item_name}/validate` (PriceValidationResult)

#### 3. audit_findings — Temuan Audit

| Kolom | Tipe | Deskripsi |
|---|---|---|
| id | UUID | PK |
| transaction_id | VARCHAR(255) | ID transaksi (indexed) |
| po_number | VARCHAR(100) | Nomor PO |
| severity | VARCHAR(20) | LOW/MEDIUM/HIGH/CRITICAL |
| amount | NUMERIC(14,2) | Jumlah |
| currency | VARCHAR | IDR |
| description | VARCHAR(2048) | Deskripsi temuan |
| sop_reference | VARCHAR(255) | Kode SOP |
| evidence_url | VARCHAR(512) | Bukti (URL atau po:REF) |
| sop_clause_citation | VARCHAR(512) | Kutipan klausul SOP |
| evidence_type | VARCHAR(50) | DISCREPANCY, TAX_INVOICE, PO_HISTORY, INVOICE_HISTORY, SPLIT_PO |
| indication_label | VARCHAR(50) | Fraud label (6 tipe) |
| vendor_reference | VARCHAR(64) | NPWP vendor (indexed) |
| created_at | DATETIME | Timestamp |

**Fitur database tingkat lanjut:**
- **Citation Guard** — enforce `evidence_url` ATAU `sop_clause_citation`
- **Fraud Indication Labels** — 6 tipe (`QTY_DISCREPANCY`, `PRICE_MANIPULATION`, `SPLIT_PO`, `DUPLICATE_INVOICE`, `UNAUTHORIZED_APPROVAL`, `INCOMPLETE_DOCS`)
- **History Pattern Detection:**
  - `evidence_type='PO_HISTORY'` → untuk Split PO Detection (7-day window)
  - `evidence_type='INVOICE_HISTORY'` → untuk Duplicate Invoice Detection (3-day window)
- Multi-index: `ix_audit_findings_transaction_id`, `ix_audit_findings_vendor_reference`

#### 4. check_results — Keputusan Reviewer

| Kolom | Tipe | Deskripsi |
|---|---|---|
| id | UUID | PK |
| finding_id | UUID FK | Refer ke audit_findings |
| status | VARCHAR(20) | WARN / ACCEPT / REJECT |
| notes | TEXT | Catatan reviewer |
| evidence_url | VARCHAR | Bukti tambahan |
| checked_at | DATETIME | Timestamp |

**Fitur:**
- Audit trail — setiap keputusan reviewer tersimpan
- Human-in-the-loop — keputusan akhir terekam

### Contoh Query Pattern Detection

**Split PO Detection:**

```sql
SELECT COUNT(*), SUM(amount) 
FROM audit_findings 
WHERE vendor_reference = ?
  AND evidence_type = 'PO_HISTORY'
  AND created_at >= now() - INTERVAL 7 DAY
  AND amount < 100_000_000
```
→ Kalau count ≥2 dan sum > 100jt → finding `SPLIT_PO` (HIGH)

**Duplicate Invoice Detection:**

```sql
SELECT * FROM audit_findings 
WHERE vendor_reference = ?
  AND evidence_type = 'INVOICE_HISTORY'
  AND created_at >= now() - INTERVAL 3 DAY
```
→ Cek: reference sama (CRITICAL) atau amount sama (HIGH)

### Migrasi Database

Karena project ini memakai SQLite untuk dev, migration dilakukan manual:

```bash
# Backup
cp demo.db demo.db.backup-$(date +%Y%m%d)

# Alter table (contoh)
sqlite3 demo.db "ALTER TABLE audit_findings ADD COLUMN vendor_reference VARCHAR(64) NOT NULL DEFAULT '';"
sqlite3 demo.db "CREATE INDEX ix_audit_findings_vendor_reference ON audit_findings (vendor_reference);"

# Backfill (kalau perlu)
.venv/bin/python backend/scripts/backfill_invoice_history_vendor.py
```

Untuk production (PostgreSQL), gunakan Alembic untuk versioned migration.

### Backfill Scripts

| Script | Fungsi |
|---|---|
| `backend/scripts/generate_sample_pdfs.py` | Generate 4 PDF sample (PO, GR, Invoice, FP) |
| `backend/scripts/backfill_invoice_history_vendor.py` | Backfill vendor_reference di INVOICE_HISTORY records |

---

## Technical Requirements Document (TRD)

### Functional Requirements

| ID | Requirement | Status | Implementasi |
|---|---|---|---|
| FR-01 | Upload PDF penawaran vendor (Maker) | ✅ Done | `/maker` + Langflow maker_agent |
| FR-02 | Ekstraksi otomatis item + harga dari PDF | ✅ Done | LLM extraction + Pydantic validators |
| FR-03 | Cross-validate harga pasar live | ✅ Done | Serper API + sitasi URL per item |
| FR-04 | Skor vendor 0-100 | ✅ Done | LLM analysis + deterministic rules |
| FR-05 | Upload 4 PDF (PO, GR, Invoice, FP) | ✅ Done | `/checker` tab Upload PDF |
| FR-06 | 4-way matching deterministik | ✅ Done | Toleransi qty ±2%, amount ±1% |
| FR-07 | Validasi SOP (threshold L2) | ✅ Done | Rp 100jt threshold, SOP-01/02 |
| FR-08 | Validasi faktur pajak Indonesia | ✅ Done | NPWP 15 digit, PPN 11%, e-Faktur 16 digit |
| FR-09 | Citation guard | ✅ Done | Drop finding tanpa bukti |
| FR-10 | Deteksi split PO | ✅ Done | 2+ PO kecil 7 hari, vendor sama |
| FR-11 | Deteksi duplicate invoice | ✅ Done | Reference sama (CRITICAL) atau amount sama 3 hari (HIGH) |
| FR-12 | Math check deterministik | ✅ Done | Sum items vs total penawaran |
| FR-13 | Layer 3 narrative enrichment | ✅ Done | Executive summary + pattern + dynamic recs |
| FR-14 | Risk score 0-100 | ✅ Done | Severity aggregation |
| FR-15 | Human-in-the-loop review | ✅ Done | check_results table + API |

### Non-Functional Requirements

| ID | Requirement | Target | Actual | Status |
|---|---|---|---|---|
| NFR-01 | Latency per bundle dokumen | < 2 menit | ~15-40 detik | ✅ Exceed |
| NFR-02 | Test coverage backend | ≥ 70 tests | 72 tests | ✅ |
| NFR-03 | Type safety | Pydantic v2 | Full | ✅ |
| NFR-04 | Async I/O | FastAPI async | Full | ✅ |
| NFR-05 | Deterministic decisions | Auditable | Python rules | ✅ |
| NFR-06 | Replayable | Same input → same output | ✅ | ✅ |
| NFR-07 | Security — no secret in repo | Enforced | sanitize.sh | ✅ |
| NFR-08 | Rate limiting | Per IP | slowapi 10/min | ✅ |
| NFR-09 | CORS | Allowlist | Configurable | ✅ |
| NFR-10 | Multi-LLM fallback | Auto | 9Router | ✅ |

### Constraints

- Indonesian tax regulations — NPWP 15 digit, PPN 11%, e-Faktur format DJP
- No ERP dependency — plug-and-play di atas workflow existing
- Data minimization — PII disamarkan sebelum diproses LLM (Layer 1)
- Audit compliance — findings persist dengan citation + reviewer decision

### Acceptance Criteria (MVP)

| Kriteria | Target | Actual |
|---|---|---|
| Cakupan pemeriksaan | 100% transaksi | ✅ |
| Waktu per bundle | < 2 menit | ✅ ~15-40 detik |
| Fraud detection labels | ≥ 4 tipe | ✅ 6 tipe |
| Citation coverage | 100% findings | ✅ Enforced |
| Test passing | ≥ 60 | ✅ 72 |
| Onboarding | < 10 menit | ✅ 5 menit |

### Out of Scope (Phase 1)

- Excel (.xlsx) support — roadmap Phase 2
- OCR foto — roadmap Phase 2
- Astra DB vector store untuk SOP — roadmap Phase 2
- MCP Server + Bob Host — roadmap Phase 2
- Multi-tenant SaaS — roadmap Phase 3
- Real-time monitoring (WebSocket) — roadmap Phase 2

---

## Cara Run

### Prerequisites

- Python 3.12+
- Node 20+
- Langflow 1.12 (Maker, Checker, Narrator flows)
- 9Router (gateway multi-LLM)
- Serper API key (untuk sitasi harga pasar di Maker flow)
- PostgreSQL 16 **atau** SQLite untuk dev; Redis opsional (rate limit in-memory di dev)

### Setup

```bash
git clone https://github.com/AgielF/tilas-ai-maker-checker.git
cd tilas-ai-maker-checker

python3 -m venv .venv && source .venv/bin/activate
pip install -e "backend/[dev]"
cd frontend && npm install && cd ..

cp .env.example .env   # isi config — jangan commit .env
cp frontend/.env.example frontend/.env   # VITE_API_BASE_URL

./dev.sh
```

`dev.sh` menjalankan backend `:8000` dan frontend `:5173`.

- Backend health: http://127.0.0.1:8000/health
- Swagger (jika `DEBUG=true`): http://127.0.0.1:8000/docs
- Frontend Maker: http://localhost:5173/maker
- Frontend Checker: http://localhost:5173/checker

Jalankan API saja:

```bash
uvicorn timbang.main:app --reload --app-dir backend/src
```

### Generate sample PDFs

```bash
.venv/bin/python backend/scripts/generate_sample_pdfs.py
```

Output di `sample-docs/` (PO, GR, Invoice, Faktur Pajak) untuk uji upload Checker.

### Environment variables

Salin dari [`.env.example`](.env.example). **Jangan hardcode secret.**

| Variable | Deskripsi |
|---|---|
| `APP_NAME` / `APP_ENV` / `DEBUG` | Identitas runtime; `DEBUG=true` mengaktifkan `/docs` |
| `DATABASE_URL` | SQLAlchemy async (`postgresql+asyncpg://...` atau `sqlite+aiosqlite://...`) |
| `REDIS_URL` | Redis (rate limit production) |
| `JWT_SECRET` | Signing key JWT — string acak panjang |
| `ROUTER_BASE_URL` / `ROUTER_API_KEY` | 9Router |
| `CORS_ORIGINS` | Origin frontend, mis. `http://localhost:5173` |
| `LANGFLOW_BASE_URL` / `LANGFLOW_API_KEY` | Server Langflow |
| `LANGFLOW_MAKER_FLOW_ID` | UUID flow Maker |
| `LANGFLOW_CHECKER_FLOW_ID` | UUID flow ekstraksi 4 PDF |
| `LANGFLOW_NARRATOR_FLOW_ID` | UUID flow Layer 3 (opsional) |
| `LANGFLOW_FILE_NODE_IDS` | JSON mapping node File Langflow (opsional) |
| `LANGFLOW_TIMEOUT_SECONDS` | Timeout HTTP ke Langflow (default 120) |
| `VITE_API_BASE_URL` | Base URL API di `frontend/.env` |

### Seed database (opsional)

```bash
python3 -m timbang.scripts.seed
```

---

## Struktur Folder

Frontend memakai **Atomic Design** (`atoms` → `molecules` → `organisms` → `templates` → `pages`). Backend **modular monolith**: `procurement` (Maker + vendor/quote) dan `audit` (Checker).

```
.
├── .env.example
├── AGENTS.md                 # kontrak AI agent di repo ini
├── LICENSE                   # MIT © 2026 Agiel Fernanda
├── README.md
├── dev.sh                    # backend + frontend
├── backend/
│   ├── pyproject.toml
│   ├── scripts/
│   │   └── generate_sample_pdfs.py
│   ├── tests/                # 72+ pytest
│   └── src/timbang/
│       ├── main.py
│       ├── shared/           # config, middleware, db
│       └── modules/
│           ├── procurement/  # Maker Agent
│           └── audit/        # Checker Agent
├── frontend/
│   └── src/
│       ├── pages/            # Landing, Maker, Checker, RiskReport, …
│       └── components/
│           ├── atoms/
│           ├── molecules/
│           ├── organisms/
│           └── templates/
├── docs/                     # arsitektur, security, frontend, agents
├── langflow/                 # export flow (gitignored)
├── sample-docs/              # PDF contoh (generated)
└── tools/sanitize.sh         # scan secret sebelum commit
```

---

## API Reference

Prefix `/api/v1/` kecuali `/health`.

| Method | Path | Peran |
|---|---|---|
| `GET` | `/health` | Health check |
| `GET` | `/api/v1/procurement/vendors` | Daftar vendor |
| `POST` | `/api/v1/procurement/vendors` | Daftar vendor baru |
| `POST` | `/api/v1/procurement/vendors/{id}/quotes` | Submit quote |
| `GET` | `/api/v1/procurement/items/{item}/validate` | Cross-validate harga (outlier > 30% median) |
| `GET` | `/api/v1/procurement/items/{item}/recommend` | Maker tanpa file |
| `POST` | `/api/v1/procurement/items/recommend-with-file` | **Maker** — PDF + item opsional |
| `POST` | `/api/v1/audit/findings` | Buat temuan |
| `GET` | `/api/v1/audit/findings/{id}` | Baca temuan |
| `POST` | `/api/v1/audit/transactions/{id}/match` | Matching (body PO/GR/Invoice) |
| `POST` | `/api/v1/audit/transactions/{id}/risk-report` | Risk report (input JSON) |
| `POST` | `/api/v1/audit/transactions/{id}/risk-report-with-files` | **Checker** — 4 PDF |

Rate limit per IP (slowapi). Endpoint LLM lebih ketat (`10/min` / `5/min`). Kontrak frontend: [docs/frontend/API_CONTRACT.md](docs/frontend/API_CONTRACT.md).

---

## Testing

```bash
cd backend && pytest -q
```

**Backend: pytest (72+ tests)** — service Maker/Checker, citation guard, SOP, faktur pajak, file upload, Langflow mock, E2E HTTP, rate limit.

```bash
pytest --cov=timbang --cov-report=term-missing -q
```

**Frontend:**

```bash
cd frontend
npm run lint    # oxlint
npm run build
```

**E2E manual:** buka `/checker`, tab Upload PDF, unggah 4 file dari `sample-docs/`, Run, lalu Generate Risk Report.

Lint backend: `ruff check . && black --check .` (dari `backend/`). Sanitasi: `./tools/sanitize.sh`.

---

## Differentiator

1. **Honest AI** — tidak halusinasi angka; math check dan matching di Python
2. **Deterministic + LLM** — auditable (aturan tetap) + narasi kaya (Layer 3)
3. **Citation guard** — temuan tanpa bukti tidak pernah masuk laporan
4. **Layer 3 narrative** — summary eksekutif tanpa mengubah verdict engine
5. **Multi-LLM gateway (9Router)** — Gemini / Groq / Cerebras tanpa lock-in satu provider
6. **Auditable + replayable (AuditChain)** — findings & check results tersimpan, bisa diulang dengan input yang sama

---

## Tech Stack

| Layer | Stack |
|---|---|
| Frontend | React 19, Vite 8, Tailwind 3.4, React Router 6 |
| Backend | FastAPI 0.115+, Pydantic v2, SQLAlchemy 2.0 async, slowapi, structlog |
| Agents | Langflow 1.12, 9Router, Gemini / Groq / Cerebras |
| Data | PostgreSQL 16, Redis, SQLite (dev) |
| PDF | Ekstraksi via Langflow File nodes; sample docs via reportlab |
| Quality | pytest, ruff, black, oxlint |

Modular monolith — bukan microservices. Konfigurasi 12-Factor (semua lewat env).

---

## Security

- Secret hanya dari environment — lihat [docs/SECURITY.md](docs/SECURITY.md)
- `.env`, `*.key`, `mcp.json`, `.bob/` di `.gitignore`
- Rate limit per IP; CORS allowlist; security headers
- Exception domain dipetakan di router — stack trace tidak bocor ke klien
- OWASP API Security Top 10 (2023)

---

## Roadmap

### Done

- Maker + Checker + Layer 3 + arsitektur hybrid 3-layer
- UI Maker (`/maker`) dan Checker (upload + manual)
- Citation guard, SOP L2, validasi faktur pajak, 6 fraud labels
- **Split PO detection** — 2+ PO kecil 7 hari, vendor sama, total > 100jt → finding SPLIT_PO (HIGH)
- **Duplicate invoice detection** — reference sama persis (CRITICAL) atau amount sama + vendor sama 3 hari (HIGH)
- 72+ backend tests

### Phase 2

- Excel support (`.xlsx`)
- Astra DB vector store untuk SOP clause
- PDF approval doc export
- MCP Server + Bob Host
- Real-time monitoring (WebSocket)
- Multi-tenant SaaS

---

## Team

**Agiel Fernanda** — Full-stack + AI orchestration

---

## License

MIT © 2026 Agiel Fernanda. Lihat [LICENSE](LICENSE).

---

## Acknowledgments

- IBM SkillsBuild University Education National Hackathon 2026
- Hacktiv8, Langflow, 9Router communities
- ACFE — statistik fraud 2026 yang menjadi motivasi masalah
- FastAPI, Pydantic, SQLAlchemy, ruff, black
