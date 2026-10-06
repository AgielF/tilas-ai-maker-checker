# AGENTS.md — Tilas

Panduan utama untuk AI agent yang bekerja di repo ini.

## Konteks Proyek
Tilas adalah AI Maker–Checker untuk deteksi fraud pengadaan di perusahaan menengah Indonesia tanpa ERP. Target submission: IBM SkillsBuild University Education National Hackathon 2026.

## Prinsip Non-Negotiable
1. **Dependency Rule** — arah dependensi: `router → service → repository → model`. Tidak boleh dibalik.
2. **Module Boundary** — hanya `public_api.py` per modul yang boleh di-import modul lain.
3. **Repository Pattern** — service tidak boleh akses DB langsung; selalu lewat repository.
4. **Security** — BOLA check, rate limit, validasi Pydantic v2, JANGAN hardcode secret.
5. **Testing** — setiap service method wajib punya unit test.
6. **Config** — 12-Factor App; semua config lewat env, tidak ada hardcode.

## Struktur Repo
- `backend/` — FastAPI backend (flat monorepo).
- `docs/` — arsitektur, security, panduan agent.
- `docs/agents/` — panduan khusus per agent.
- `langflow/` — export flow Langflow.
- `tools/` — utilitas (sanitasi, dsb).

## Aturan Commit
- Conventional Commits: `feat:`, `fix:`, `chore:`, `docs:`, `refactor:`, `test:`.
- Wajib lewat `tools/sanitize.sh` sebelum commit.
- Dilarang commit `.env`, `.bob/`, `mcp.json`, `*.key`.

## Tech Stack
- FastAPI 0.115+, Pydantic v2, SQLAlchemy 2.0 async, PostgreSQL 16, Redis.
- Langflow untuk agent flow, 9Router untuk routing LLM multi-provider.

## Referensi Standar
Clean Architecture (Robert C. Martin), Repository Pattern (Martin Fowler), OWASP API Security Top 10 (2023), FastAPI best practices, 12-Factor App.

## Commands
- Run: `uvicorn timbang.main:app --reload` (dari `backend/`).
- Test: `pytest`.
- Lint: `ruff check . && black --check .`.
- Sanitasi: `./tools/sanitize.sh`.

## Jangan Lakukan
- Jangan buat microservices — proyek ini modular monolith.
- Jangan pakai `apps/` — struktur flat disengaja untuk tim 2 orang.
- Jangan aktifkan Google Docs di Maker Agent — JSON output sudah cukup.
