# Security — Tilas

## Aturan Wajib
- ❌ JANGAN commit `.env`, `.bob/`, `mcp.json`, API keys, `*.key`.
- ✅ SELALU pakai `.env` + `.gitignore`.
- ✅ SELALU jalankan `tools/sanitize.sh` sebelum commit.
- ✅ SELALU pakai Personal Access Token (bukan password) untuk `git push`.

## Secret yang Sudah Di-revoke
- `sk-9YD6Y15...` — SUDAH DI-REVOKE, jangan dipakai.
- History Git sudah dibersihkan via `git filter-branch`.

## File yang WAJIB di-.gitignore

```text
.env
.bob/
mcp.json
*.key
.langflow/
```

## OWASP API Security Top 10 (2023) — Kontrol di Tilas

| Risiko | Kontrol |
|---|---|
| API1: BOLA | Ownership check di service sebelum akses resource |
| API2: Broken Auth | JWT via python-jose, expiry 30 menit |
| API3: Broken Object Property Level Auth | Pydantic response model eksplisit |
| API4: Unrestricted Resource Consumption | slowapi rate limit + Redis backend |
| API5: Broken Function Level Auth | Role guard per router |
| API7: SSRF | Allowlist domain untuk cross-validation harga |
| API8: Security Misconfiguration | Security headers middleware, CORS ketat |
| API10: Unsafe Consumption of APIs | Validasi skema respons dari 9Router & vendor |

## Rate Limiting
- Hybrid — di level aplikasi (slowapi) dan gateway (Cloudflare/NGINX) untuk produksi.
- Key: remote address + user ID (kalau terautentikasi).

## Logging
- `structlog` untuk structured logging.
- JANGAN log PII, token, atau API key.
- Log audit trail untuk aksi maker & checker.

## Review Checklist Sebelum Commit
1. Jalankan `./tools/sanitize.sh`.
2. Cek `git diff --cached` — tidak ada secret.
3. Pastikan `.env` tidak masuk staging.
4. Commit pakai Conventional Commits.
