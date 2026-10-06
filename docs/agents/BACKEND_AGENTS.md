# Backend Agents — Tilas

Panduan untuk AI agent yang menulis kode di `backend/`.

## Aturan Kode
- Setiap service method wajib punya unit test di `backend/tests/`.
- Router tidak boleh memanggil repository langsung — selalu lewat service.
- Repository adalah satu-satunya tempat SQLAlchemy session dipakai.
- Validasi input & output pakai Pydantic v2 (schema terpisah untuk request/response).
- Tidak ada akses DB di dalam router atau model.

## Konvensi
- Python 3.12, src-layout (`backend/src/timbang/`).
- Nama file: `snake_case.py`.
- Nama kelas: `PascalCase`.
- Async di mana pun I/O terjadi (DB, HTTP, Redis).
- Type hints wajib untuk semua fungsi publik.

## Modul & Tanggung Jawab

| Modul | Tanggung Jawab | Output |
|---|---|---|
| procurement | Maker Agent backend — analisis vendor, cross-validate harga, rekomendasi | Rekomendasi vendor + estimasi penghematan |
| audit | Checker Agent backend — three-way matching, validasi SOP, laporan risiko | Laporan risiko + status kepatuhan |

## Public API
Hanya `public_api.py` di tiap modul yang boleh di-import modul lain. Isi `public_api.py` adalah re-export dari service (bukan implementasi).

## Error Handling
- Gunakan exception domain di service, mapping ke HTTP di router.
- Jangan biarkan stack trace bocor ke response produksi.

## Testing
- Setiap service method → minimal 1 unit test happy path + 1 edge case.
- Gunakan `httpx.AsyncClient` + `ASGITransport` untuk endpoint test.
- Fixture di `backend/tests/conftest.py`.

## Commands

```bash
cd backend
pip install -e ".[dev]"
pytest -q
ruff check .
black --check .
uvicorn timbang.main:app --reload
```

## Referensi
- Clean Architecture (Robert C. Martin)
- Repository Pattern (Martin Fowler, PoEAA)
- FastAPI best practices (Sebastián Ramírez, zhanymkanov)
- OWASP API Security Top 10 (2023)
