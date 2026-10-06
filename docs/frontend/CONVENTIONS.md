# Konvensi Frontend — Tilas

Panduan konsistensi kode untuk semua kontributor (termasuk AI agent).
Baca dokumen ini sebelum membuat atau memodifikasi file apapun di `frontend/`.

---

## Struktur Folder

```
frontend/
├── index.html
├── package.json
├── vite.config.js
├── tailwind.config.js
├── postcss.config.js
├── .env.example              # template variabel env
├── .env.local                # gitignored — diisi developer
└── src/
    ├── main.jsx              # ReactDOM.createRoot entry point
    ├── App.jsx               # Router root + route definitions
    ├── index.css             # Tailwind directives + CSS vars + @property
    ├── components/
    │   ├── atoms/            # Button, Badge, Input, Label, Spinner, Icon, Skeleton, Divider
    │   ├── molecules/        # FormField, SearchBar, SeverityBadge, StatCell, NavItem, ...
    │   ├── organisms/        # NavBar, HeroBilingual, RecommendationCard, MatchGrid, ...
    │   └── templates/        # LandingLayout, DashboardLayout, PageHeader
    ├── hooks/                # useApi.js, useDebounce.js, useMediaQuery.js, useAbortableFetch.js
    ├── pages/                # LandingPage.jsx, MakerPage.jsx, CheckerPage.jsx, ...
    ├── lib/                  # api.js, constants.js, format.js, icons.js
    └── styles/               # CSS modular tambahan (opsional, scope per komponen)
```

---

## Konvensi Penamaan

| Entitas | Konvensi | Contoh |
|---|---|---|
| Komponen React | `PascalCase` (file dan export) | `RecommendationCard.jsx` |
| Custom hook | `useXxx` camelCase | `useApi.js`, `useDebounce.js` |
| Fungsi utilitas | `camelCase` | `formatCurrency`, `parseIdr` |
| Konstanta | `SCREAMING_SNAKE_CASE` | `API_BASE_URL`, `MAKER_STEPS` |
| CSS variable | `--kebab-case` | `--color-electric`, `--color-navy` |
| File lib | `camelCase.js` | `api.js`, `format.js` |
| Route path | `kebab-case` | `/risk-report`, `/maker` |

---

## API Client — `src/lib/api.js`

**Seluruh fetch wajib melewati `api.js`.** Tidak ada `fetch()` langsung di komponen,
tidak terkecuali untuk "satu kali pakai".

```js
// src/lib/api.js
const BASE = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000';

async function request(path, options = {}) {
  const res = await fetch(`${BASE}${path}`, {
    headers: { 'Content-Type': 'application/json', ...options.headers },
    ...options,
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    const err = new Error(body.detail ?? `HTTP ${res.status}`);
    err.status = res.status;
    throw err;
  }
  return res.json();
}

export const api = {
  health:            ()         => request('/health'),
  listVendors:       ()         => request('/api/v1/procurement/vendors'),
  registerVendor:    (data)     => request('/api/v1/procurement/vendors', { method: 'POST', body: JSON.stringify(data) }),
  submitQuote:       (id, data) => request(`/api/v1/procurement/vendors/${id}/quotes`, { method: 'POST', body: JSON.stringify(data) }),
  validatePrice:     (item)     => request(`/api/v1/procurement/items/${encodeURIComponent(item)}/validate`),
  recommend:         (item, signal) => request(`/api/v1/procurement/items/${encodeURIComponent(item)}/recommend`, { signal }),
  createFinding:     (data)     => request('/api/v1/audit/findings', { method: 'POST', body: JSON.stringify(data) }),
  getFinding:        (id)       => request(`/api/v1/audit/findings/${id}`),
  threeWayMatch:     (txId, body) => request(`/api/v1/audit/transactions/${txId}/match`, { method: 'POST', body: JSON.stringify(body) }),
  riskReport:        (txId, body) => request(`/api/v1/audit/transactions/${txId}/risk-report`, { method: 'POST', body: JSON.stringify(body) }),
};
```

---

## Loading / Error / Empty State

Setiap halaman atau organism yang melakukan fetch **wajib** menangani tiga state:

```jsx
function MakerPage() {
  const [state, setState] = useState({ data: null, loading: false, error: null });

  async function handleSearch(item) {
    setState({ data: null, loading: true, error: null });
    try {
      const data = await api.recommend(item);
      setState({ data, loading: false, error: null });
    } catch (err) {
      setState({ data: null, loading: false, error: err });
    }
  }

  if (state.loading) return <LoadingSteps steps={MAKER_STEPS} />;
  if (state.error)   return <ErrorBanner message={state.error.message} onRetry={() => handleSearch(lastItem)} />;
  if (!state.data)   return <EmptyState label="Masukkan nama item untuk memulai." />;
  return <RecommendationCard data={state.data} />;
}
```

---

## Abort Controller — Endpoint Berlatency Tinggi

Endpoint `/recommend` bisa memakan ~60 detik. Wajib pakai `AbortController` dengan
timeout manual. Abort juga dipanggil saat komponen unmount.

```jsx
// Pattern abort di organism/page
useEffect(() => {
  if (!itemName) return;

  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), 120_000); // 2 menit

  setLoading(true);
  api.recommend(itemName, controller.signal)
    .then(data => { if (!controller.signal.aborted) setData(data); })
    .catch(err => {
      if (err.name !== 'AbortError') setError(err);
    })
    .finally(() => {
      clearTimeout(timeoutId);
      setLoading(false);
    });

  return () => {
    controller.abort();
    clearTimeout(timeoutId);
  };
}, [itemName]);
```

---

## Memory Safety

> Detail lengkap di [`PERFORMANCE.md`](PERFORMANCE.md).

Aturan ringkas yang wajib dipatuhi:

- **Setiap `useEffect` yang subscribe** (event listener, subscription, timer, fetch)
  **wajib return cleanup function.**
- **AbortController** untuk setiap fetch yang di-trigger dari `useEffect`.
- **Jangan simpan referensi DOM di state** — gunakan `useRef`.
- Jangan buat object/array literal sebagai props ke `React.memo` child tanpa `useMemo`.

---

## Commits — Conventional Commits

Prefix untuk semua commit yang menyentuh `frontend/` atau `docs/frontend/`:

| Prefix | Kapan |
|---|---|
| `feat(frontend):` | Fitur baru / komponen baru |
| `fix(frontend):` | Bug fix |
| `style(frontend):` | Perubahan CSS / Tailwind tanpa perubahan logika |
| `chore(frontend):` | Config, dependency update, boilerplate |
| `docs(frontend):` | Perubahan dokumen di `docs/frontend/` |
| `refactor(frontend):` | Refactor tanpa perubahan perilaku |

---

## Yang Dilarang

| Larangan | Alasan |
|---|---|
| Class component | React 18 idiomatik functional + hooks |
| `fetch()` langsung di atom/molecule/organism | Semua lewat `src/lib/api.js` |
| Hardcode warna hex di JSX | Gunakan token Tailwind / CSS variable |
| `shadow-2xl`, `rounded-3xl`, gradient berulang | Melanggar prinsip visual minimalis |
| Emoji sebagai ikon produksi | Gunakan `Icon` atom dengan inline SVG |
| Commit `.env.local` atau `node_modules/` | Sudah di `.gitignore` |
| `onMouseMove` React untuk high-frequency event | Gunakan rAF + CSS variable (lihat HERO_INTERACTION.md) |
| Memoize semua handler "biar aman" | Memoize hanya jika terbukti perlu (lihat PERFORMANCE.md) |
