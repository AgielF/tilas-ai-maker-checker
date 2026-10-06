# Pages — Tilas

Peta halaman, route, dan spesifikasi konten untuk setiap page di frontend Tilas.

---

## 1. Peta Route

| Route | Page | Template | Wajib | Endpoint |
|---|---|---|---|---|
| `/` | Landing | `LandingTemplate` | ✅ | — |
| `/dashboard` | Dashboard | `AppTemplate` | ✅ | `GET /vendors` |
| `/maker` | Maker ⭐ | `WorkbenchTemplate` | ✅ | `GET /items/{name}/recommend` |
| `/maker/validate` | Validate | `WorkbenchTemplate` | ✅ | `GET /items/{name}/validate` |
| `/checker` | Checker | `WorkbenchTemplate` | ✅ | `POST /transactions/{id}/match` |
| `/checker/risk-report` | RiskReport | `WorkbenchTemplate` | ✅ | `POST /transactions/{id}/risk-report` |
| `/vendors` | Vendors | `AppTemplate` | opsional | `GET/POST /vendors` |
| `/findings` | Findings | `AppTemplate` | opsional | `GET/POST /findings` |
| `/about` | About | `AppTemplate` | opsional | — |
| `*` | NotFound | `AppTemplate` | ✅ | — |

---

## Landing (`/`)

Hero bilingual EN↔ID (detail lengkap di [`HERO_INTERACTION.md`](HERO_INTERACTION.md)).

### Struktur

1. **Hero bilingual**
   - Copy EN: *"Detect procurement fraud before it costs you."*
   - Copy ID: *"Deteksi fraud pengadaan sebelum jadi kerugian."*
   - Toggle bahasa + mouse-reveal spotlight (lihat HERO_INTERACTION.md)
   - Circle motif dua lingkaran (simbol Maker–Checker)

2. **StatStrip** — 3 metrik highlight:
   - `5%` — rata-rata penghematan pengadaan
   - `62.9s` — rata-rata waktu analisis
   - `39` — temuan fraud terdeteksi (demo)

3. **FeatureGrid** — grid 2×2:
   - Maker Agent (Live)
   - Validate Price (Live)
   - Three-Way Match / Checker (Live)
   - Risk Report (Live)

4. **HowItWorks** — 3 langkah horizontal:
   1. Masukkan item pengadaan
   2. Maker Agent menganalisis harga pasar
   3. Checker Agent memverifikasi dokumen

5. **ComingSoonGrid** — fitur-fitur Coming Soon (lihat §3)

6. **CTA Strip** — tombol utama ke `/maker`

7. **Footer** — copyright, link docs

---

## Dashboard (`/dashboard`)

### Struktur

1. **NavBar** — logo + navigasi utama
2. **PageHeader** — judul halaman + breadcrumb
3. **StatStrip** — 4 cell metrik:
   - Total Vendor
   - Total Quote
   - Open Findings
   - Risk Score
4. **VendorTable** — 5 baris teratas vendor terdaftar
5. **FindingList** — 5 temuan terbaru
6. **ComingSoonGrid** — lihat §3
7. **Footer**

### Coming Soon di Dashboard

- Real-time Anomaly Alerts
- Email / Slack Alerts
- Historical Trend Analytics

---

## Maker ⭐ (`/maker`)

Halaman utama — AI Maker Agent untuk rekomendasi harga pengadaan.

### Struktur

1. **NavBar**
2. **PageHeader** — "Maker Agent" + badge `Live` (electric)
3. **SearchBar** — input nama item, submit trigger analisis
4. **RecommendationPanel** — area hasil analisis

### State Machine (4 state)

| State | UI |
|---|---|
| `idle` | EmptyState — "Masukkan nama item untuk memulai." |
| `loading` | `LoadingSteps` — 4 tahap animasi (~60 detik expected) |
| `error` | `ErrorBanner` — pesan error + tombol Retry |
| `success` | `RecommendationCard` — hasil analisis lengkap |

### LoadingSteps — 4 Tahap

1. Menghubungi Maker Agent…
2. Mengambil data harga pasar…
3. Menganalisis pola harga…
4. Menyiapkan rekomendasi…

### Abort Controller

```js
// Timeout 120_000ms (2 menit)
const controller = new AbortController();
const timeoutId = setTimeout(() => controller.abort(), 120_000);
```

Wajib cleanup di `useEffect` return function (lihat [`CONVENTIONS.md`](CONVENTIONS.md)).

### Rate Limit

- Maksimum **10 request / menit** per client.
- Tampilkan pesan informatif jika rate limit tercapai.

---

## Validate (`/maker/validate`)

Validasi harga item pengadaan terhadap referensi pasar.

### Struktur

1. **NavBar**
2. **SearchBar** — prefill dari query string `?item=` jika tersedia
3. **PriceTable** — tabel harga referensi (vendor, harga, tanggal)
4. **Verdict Banner** — hasil validasi:

| Verdict | Warna | Keterangan |
|---|---|---|
| Fair | `emerald` | Harga wajar sesuai pasar |
| Overpriced | `sev-critical` | Harga di atas batas wajar |
| Underpriced | `amber` | Harga mencurigakan terlalu murah |

---

## Checker (`/checker`)

Three-Way Match: PO vs GR vs Invoice.

### Struktur

1. **NavBar**
2. **SearchBar** — input `transaction_id`
3. **MatchGrid** — 3 kolom:
   - PO (Purchase Order)
   - GR (Goods Receipt)
   - Invoice
4. **Verdict Banner**:

| Verdict | Warna |
|---|---|
| MATCHED | `emerald` |
| DISCREPANCY | `sev-high` |
| FAILED | `sev-critical` |

5. **Tombol** → navigasi ke `/checker/risk-report`

---

## Risk Report (`/checker/risk-report`)

Laporan risiko terperinci untuk transaksi yang dianalisis.

### Struktur

1. **NavBar**
2. **PageHeader** — judul + transaction ID
3. **RiskGauge** — skor risiko 0–100 (visual gauge / progress arc)
4. **SeverityBreakdown** — 4 bar horizontal:
   - CRITICAL (merah)
   - HIGH (oranye)
   - MEDIUM (kuning)
   - LOW (hijau)
5. **FindingList** — daftar temuan dengan severity badge
6. **SOP Validation** — apakah transaksi melanggar SOP pengadaan
7. **Tombol Export PDF** → **Coming Soon** (badge amber, tidak berfungsi)

---

## Vendors (`/vendors`) — Opsional

Manajemen daftar vendor.

- Tabel vendor + form tambah vendor baru
- Endpoint: `GET/POST /api/v1/procurement/vendors`
- Coming Soon: **Vendor Reputation Score**

---

## Findings (`/findings`) — Opsional

Daftar semua temuan fraud / anomali.

- Filter by severity, status, tanggal
- Endpoint: `GET/POST /api/v1/audit/findings`

---

## About (`/about`) — Opsional

Informasi tim, teknologi, dan konteks proyek Tilas.

---

## NotFound (`*`)

Halaman 404 — route tidak ditemukan.

- Pesan ramah + tombol kembali ke `/`
- Menggunakan `AppTemplate`

---

## 3. Fitur "Coming Soon"

> **Aturan wajib:** Tampilkan dengan badge amber `Coming Soon`.
> **JANGAN** buat mock yang berfungsi untuk fitur-fitur ini.

| Fitur | Lokasi |
|---|---|
| Real-time Anomaly Alerts | Landing, Dashboard |
| Checker Agent di Langflow | Landing |
| Multi-tenant Workspace | Landing |
| SAP / Oracle Integration | Landing |
| Export PDF Report | Risk Report |
| Email / Slack Alerts | Dashboard |
| Historical Trend Analytics | Dashboard |
| Vendor Reputation Score | Vendors |

### Coming Soon Badge — Referensi

```jsx
<span className="bg-amber/10 text-amber border border-amber/30
  uppercase tracking-wider text-[11px] px-2 py-0.5 rounded-full font-medium">
  Coming Soon
</span>
```
