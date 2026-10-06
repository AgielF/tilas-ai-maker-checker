# Dokumentasi Frontend — Tilas

Indeks dokumentasi frontend untuk proyek Tilas. Semua file berada di folder `docs/frontend/`.

## Stack

| Layer | Teknologi |
|---|---|
| Bundler | Vite 5+ |
| UI Library | React 18 |
| Bahasa | JavaScript (bukan TypeScript) |
| Styling | Tailwind CSS 3.4 |
| Routing | react-router-dom v6 |
| HTTP Client | `fetch` native (via `src/lib/api.js`) |

## Prinsip Desain

- **Atomic Design** (Brad Frost, 5 level): atoms → molecules → organisms → templates → pages.
- **Satu aksen** — `electric` (`#00FFAA`), base monokrom (`navy` / `slate`).
- **Border hairline** — 1px, tidak ada shadow tebal.
- **Whitespace generous** — breathing room > kepadatan.
- **Tabular-nums** untuk semua angka uang / metrik.
- **Dark mode** untuk halaman kerja (Maker, Checker, RiskReport).

## Daftar Dokumen

| File | Isi |
|---|---|
| `ATOMIC_DESIGN.md` | Metodologi Brad Frost, aturan dependensi per level, contoh salah → benar |
| `DESIGN_SYSTEM.md` | Color tokens, typography, spacing scale, severity palette |
| `PAGES.md` | 6 halaman utama + Coming Soon features + routing map |
| `COMPONENTS.md` | Inventaris komponen per atomic level (props, dipakai di) |
| `CONVENTIONS.md` | Struktur folder, naming rules, API client pattern, memory safety |
| `API_CONTRACT.md` | Hook mapping, endpoint detail, request/response shape, error format |
| `HERO_INTERACTION.md` | Bilingual hero dengan mouse-reveal spotlight, rAF + CSS var |
| `PERFORMANCE.md` | Memoization rules, code splitting, memory safety, bundle budget |
