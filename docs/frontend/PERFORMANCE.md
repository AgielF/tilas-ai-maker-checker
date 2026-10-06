# Performance — Tilas Frontend

Panduan optimasi performa React untuk memastikan aplikasi tetap responsif,
bebas memory leak, dan lolos audit Lighthouse sebelum submission.

---

## 1. Prinsip: "Measure, don't guess"

Jangan mengoptimasi kode yang belum terbukti lambat.

**Alur kerja yang benar:**
1. Buka React DevTools → tab **Profiler**.
2. Record interaksi yang terasa lambat.
3. Identifikasi komponen yang render >16ms atau re-render tidak perlu.
4. Baru tambahkan `React.memo`, `useMemo`, atau `useCallback`.

Memoize semua hal "biar aman" justru membuat kode lebih lambat karena overhead
perbandingan dependency yang tidak perlu.

---

## 2. `React.memo` — Kapan Pakai

Gunakan `React.memo` **hanya** untuk:

| Kondisi | Contoh |
|---|---|
| Atom/molecule di-render dalam **list besar** (>20 item) | `VendorRow`, `FindingRow` |
| Komponen yang menerima **props objek/array** dari parent yang sering re-render | `SeverityBadge` dalam loop |
| Terbukti sering re-render di React Profiler tanpa perubahan props nyata | — |

```jsx
// BENAR — FindingRow dalam list bisa > 50 item
const FindingRow = React.memo(function FindingRow({ finding }) {
  return (
    <tr>
      <td>{finding.transaction_id}</td>
      <td><SeverityBadge severity={finding.severity} /></td>
      <td className="tabular-nums">{formatCurrency(finding.amount)}</td>
    </tr>
  );
});

// SALAH — DashboardPage jarang re-render, memo tidak perlu
const DashboardPage = React.memo(DashboardPageImpl); // ❌ overhead tanpa manfaat
```

---

## 3. `useMemo` / `useCallback` — Kapan Pakai

### Pakai `useMemo` untuk:

- Nilai yang menjadi **dependency `useEffect`** (agar referensi stabil).
- Kalkulasi berat (sort, filter list besar) yang dipanggil setiap render.

```jsx
// BENAR — stabil sebagai dep useEffect
const filters = useMemo(() => ({ severity: selectedSeverity }), [selectedSeverity]);
useEffect(() => { fetchFindings(filters); }, [filters]);

// BENAR — kalkulasi berat
const sortedFindings = useMemo(
  () => findings.slice().sort((a, b) => SEVERITY_ORDER[b.severity] - SEVERITY_ORDER[a.severity]),
  [findings]
);
```

### Pakai `useCallback` untuk:

- Handler yang di-pass ke **`React.memo` child** sebagai prop.

```jsx
// BENAR — onRetry di-pass ke React.memo ErrorBanner
const handleRetry = useCallback(() => fetchData(item), [item]);
return <ErrorBanner onRetry={handleRetry} />;
```

### Jangan Pakai untuk:

```jsx
// SALAH — operasi murah, tidak ada React.memo child
const total = useMemo(() => price * qty, [price, qty]); // ❌ hitung langsung saja

// SALAH — handler tidak di-pass ke React.memo
const handleClick = useCallback(() => setOpen(true), []); // ❌ tidak perlu
```

---

## 4. Memory Safety — Wajib

Kegagalan cleanup menyebabkan:
- State update pada komponen yang sudah unmount (React warning).
- Memory leak: listener, timer, dan fetch yang terus berjalan di background.
- Detached DOM node yang tertahan di memory.

### a) Pola Cleanup `useEffect`

| Side effect | Cleanup |
|---|---|
| `addEventListener` | `removeEventListener` |
| `setInterval` | `clearInterval` |
| `setTimeout` | `clearTimeout` |
| `requestAnimationFrame` | `cancelAnimationFrame` |
| Subscription / observable | `unsubscribe()` / `.cancel()` |
| `fetch` / async request | `AbortController.abort()` |

```jsx
// Template lengkap — copy-paste untuk kasus umum
useEffect(() => {
  const controller = new AbortController();
  let timerId = null;

  timerId = setTimeout(() => doSomething(), 1000);

  window.addEventListener('resize', handleResize);

  return () => {
    clearTimeout(timerId);
    window.removeEventListener('resize', handleResize);
    controller.abort();
  };
}, []);
```

### b) AbortController untuk Setiap Fetch

```jsx
useEffect(() => {
  const controller = new AbortController();

  api.recommend(itemName, controller.signal)
    .then(data => {
      if (!controller.signal.aborted) setData(data);
    })
    .catch(err => {
      if (err.name !== 'AbortError') setError(err);
    });

  return () => controller.abort(); // abort saat unmount atau deps berubah
}, [itemName]);
```

### c) DOM Node — Gunakan `useRef`, Bukan `state`

```jsx
// SALAH — menyimpan DOM node di state mencegah GC
const [node, setNode] = useState(null);
<div ref={el => setNode(el)} />

// BENAR — ref tidak trigger re-render, tidak block GC
const nodeRef = useRef(null);
<div ref={nodeRef} />
```

### d) Custom Hook `useAbortableFetch`

Hook ini mengenkapsulasi pola abort agar tidak diulang di setiap komponen:

```js
// src/hooks/useAbortableFetch.js
import { useState, useEffect } from 'react';

/**
 * Fetch dengan auto-abort saat unmount atau saat `key` berubah.
 * @param {Function} fetcher - fungsi (signal) => Promise
 * @param {any} key - dependency; fetch diulang saat key berubah
 */
export function useAbortableFetch(fetcher, key) {
  const [state, setState] = useState({ data: null, loading: !!key, error: null });

  useEffect(() => {
    if (!key) return;

    const controller = new AbortController();
    setState({ data: null, loading: true, error: null });

    fetcher(controller.signal)
      .then(data => {
        if (!controller.signal.aborted)
          setState({ data, loading: false, error: null });
      })
      .catch(err => {
        if (err.name !== 'AbortError')
          setState({ data: null, loading: false, error: err });
      });

    return () => controller.abort();
  }, [key]); // eslint-disable-line react-hooks/exhaustive-deps

  return state;
}
```

Penggunaan:

```jsx
// Di organism/page
const { data, loading, error } = useAbortableFetch(
  (signal) => api.recommend(itemName, signal),
  itemName
);
```

---

## 5. Code Splitting

Vite secara otomatis membagi bundle berdasarkan `import()` dinamis.
Gunakan `React.lazy` + `Suspense` untuk halaman non-landing.

```jsx
// src/App.jsx
import { lazy, Suspense } from 'react';
import { Routes, Route } from 'react-router-dom';
import Spinner from './components/atoms/Spinner';
import LandingPage from './pages/LandingPage'; // TIDAK di-lazy — harus instant

const MakerPage      = lazy(() => import('./pages/MakerPage'));
const CheckerPage    = lazy(() => import('./pages/CheckerPage'));
const ValidatePage   = lazy(() => import('./pages/ValidatePage'));
const RiskReportPage = lazy(() => import('./pages/RiskReportPage'));
const DashboardPage  = lazy(() => import('./pages/DashboardPage'));
const NotFoundPage   = lazy(() => import('./pages/NotFoundPage'));

export default function App() {
  return (
    <Suspense fallback={<div className="min-h-screen flex items-center justify-center"><Spinner size="lg" /></div>}>
      <Routes>
        <Route path="/"                        element={<LandingPage />} />
        <Route path="/maker"                   element={<MakerPage />} />
        <Route path="/checker"                 element={<CheckerPage />} />
        <Route path="/validate"                element={<ValidatePage />} />
        <Route path="/risk/:transactionId"     element={<RiskReportPage />} />
        <Route path="/dashboard"               element={<DashboardPage />} />
        <Route path="*"                        element={<NotFoundPage />} />
      </Routes>
    </Suspense>
  );
}
```

**Mengapa `LandingPage` tidak di-lazy?** Halaman pertama yang dilihat pengguna harus
ter-load instan. Lazy loading menambah waterfall request yang tidak perlu untuk entry point.

---

## 6. Bundle Budget (Target Submission)

| Asset | Target Gzip |
|---|---|
| `main.js` (core bundle) | < 150 KB |
| `tailwind.css` (JIT) | < 30 KB |
| Total first-load JS | < 250 KB |

Cara cek:

```bash
# Dari folder frontend/
npx vite-bundle-visualizer

# Atau build + analisa
npm run build
npx source-map-explorer dist/assets/*.js
```

Tailwind JIT secara otomatis membuang class yang tidak dipakai. Pastikan tidak ada
`safelist` yang terlalu luas di `tailwind.config.js`.

---

## 7. Optimasi Runtime

| Teknik | Implementasi |
|---|---|
| Cursor `mousemove` | Via `rAF` + `el.style.setProperty` — bukan React state (lihat `HERO_INTERACTION.md`) |
| Debounce search input | `useDebounce(query, 300)` sebelum panggil API |
| Angka uang | `font-variant-numeric: tabular-nums` via Tailwind `tabular-nums` — tidak pakai JS formatter di render loop |
| Image | Lazy load dengan `loading="lazy"` dan `decoding="async"` |

```js
// src/hooks/useDebounce.js
import { useState, useEffect } from 'react';

export function useDebounce(value, delay) {
  const [debounced, setDebounced] = useState(value);
  useEffect(() => {
    const id = setTimeout(() => setDebounced(value), delay);
    return () => clearTimeout(id); // WAJIB cleanup
  }, [value, delay]);
  return debounced;
}
```

---

## 8. Audit Checklist Sebelum Submit

```
[ ] React DevTools Profiler: tidak ada komponen render >16ms berulang
[ ] Lighthouse Performance score >= 90 (mode Incognito)
[ ] Network tab: tidak ada duplicate fetch untuk endpoint yang sama
[ ] Memory tab: tidak ada detached DOM node setelah navigate antar halaman
[ ] Semua useEffect punya cleanup:
      grep -c "useEffect"  src/**/*.jsx | awk '{sum+=$1} END {print sum}'
      grep -c "return ()"  src/**/*.jsx | awk '{sum+=$1} END {print sum}'
      (jumlah harus sebanding)
[ ] Bundle size: npm run build && du -sh dist/assets/*
[ ] Tidak ada console.error atau React warning di console
[ ] Semua loading/error/empty state dirender (coba matikan backend sementara)
```
