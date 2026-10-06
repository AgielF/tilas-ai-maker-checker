# Arsitektur Tilas

## Gaya Arsitektur
- **Clean Architecture + Modular Monolith.**
- **Flat monorepo** — bukan `apps/`, karena tim hanya 2 orang dan deadline ketat.

## Lapisan (Dependency Rule)

```text
router → service → repository → model
```

- **router** — HTTP boundary, validasi Pydantic, delegasi ke service.
- **service** — business logic, orkestrasi, panggilan ke repository & LLM.
- **repository** — akses DB, satu-satunya lapisan yang boleh berinteraksi dengan SQLAlchemy session.
- **model** — entitas domain & SQLAlchemy models.

Tidak ada lapisan yang boleh mengimpor ke luar (ke arah yang berlawanan).

## Modul
- **procurement** — konteks Maker Agent. Analisis vendor, cross-validation harga, rekomendasi.
- **audit** — konteks Checker Agent. Three-way matching, validasi SOP, laporan risiko.

## Module Boundary
Setiap modul mengekspos `public_api.py` sebagai satu-satunya pintu masuk. Modul lain hanya boleh mengimpor dari `public_api.py`, bukan dari `service.py`, `repository.py`, atau `models.py` secara langsung.

## Komponen Bersama
- `shared/core/` — middleware, rate limit, util lintas modul.
- `shared/db/` — engine, session factory, base model.

## Diagram C4 (Level 2 — Container)

```text
[User: Staf Purchasing/Finance]
            │
            ▼
[Frontend React] ──(REST)──▶ [Backend FastAPI]
                                 │
                                 ├──▶ [PostgreSQL 16]
                                 ├──▶ [Redis] (rate limit)
                                 ├──▶ [9Router] ──▶ [LLM Providers]
                                 └──▶ [Langflow] (Maker & Checker flow)
```

## Keputusan Arsitektur

| Keputusan | Alasan |
|---|---|
| Modular Monolith | Kompleksitas rendah, cocok MVP hackathon |
| Flat structure | Tim 2 orang, hindari over-engineering |
| Repository Pattern | Testable, decoupled dari DB |
| Async SQLAlchemy | Non-blocking I/O, cocok FastAPI |
