# Atomic Design — Tilas Frontend

Metodologi berdasarkan [Brad Frost Atomic Design](https://atomicdesign.bradfrost.com/).
Sistem ini memastikan komponen reusable, testable, dan tidak punya dependensi siklik.

---

## 1. Prinsip Utama

- **SATU komponen hanya berada di SATU level.** Tidak boleh ada komponen yang bisa
  diklasifikasikan di dua level sekaligus.
- **Tidak boleh skip level**, kecuali wrapper trivial tanpa logika (div pembungkus layout).
- **Dependensi hanya ke bawah**: level atas boleh import level bawah, tidak sebaliknya.

---

## 2. Lima Level

| Level | Definisi | Contoh untuk Tilas | Folder |
|---|---|---|---|
| **atoms** | Elemen terkecil, stateless, tanpa logika bisnis. Output murni dari props. | `Button`, `Badge`, `Input`, `Label`, `Icon`, `Spinner`, `Skeleton`, `Divider` | `src/components/atoms/` |
| **molecules** | Gabungan atom, satu tanggung jawab UI, boleh local state. | `FormField`, `SearchBar`, `SeverityBadge`, `StatCell`, `NavItem`, `EmptyState`, `ErrorBanner`, `ComingSoonBadge` | `src/components/molecules/` |
| **organisms** | Gabungan molekul, satu section utuh halaman. Boleh fetch via hook. | `NavBar`, `HeroBilingual`, `RecommendationCard`, `MatchGrid`, `RiskGauge`, `Footer`, `FeatureGrid`, `PriceTable`, `FindingsList` | `src/components/organisms/` |
| **templates** | Layout skeleton tanpa data nyata. Slot untuk organism/molecule. | `LandingLayout`, `DashboardLayout`, `PageHeader` | `src/components/templates/` |
| **pages** | Template + data nyata + routing. Entry point react-router. | `LandingPage`, `MakerPage`, `CheckerPage`, `ValidatePage`, `RiskReportPage`, `NotFoundPage` | `src/pages/` |

---

## 3. Aturan Dependensi (Wajib Dipatuhi)

```
atoms       ← tidak boleh import dari level manapun
molecules   ← hanya import dari atoms
organisms   ← hanya import dari atoms + molecules
templates   ← hanya import dari atoms + molecules + organisms
pages       ← boleh import semua level, tapi TIDAK boleh diimpor balik
```

Pelanggaran aturan ini menyebabkan dependensi siklik dan komponen yang sulit di-test.

---

## 4. Aturan Kode — Atoms

- **Stateless**: jika membutuhkan state lokal, komponen tersebut adalah molecule.
- **Pure**: output sepenuhnya fungsi dari props. Sama props → sama output.
- **Tidak ada fetch / API call / business logic** di dalam atom.
- **Tidak ada `useEffect`**: side-effect menjadi tanggung jawab molecule ke atas.
- **Boleh `React.memo`** jika terbukti sering re-render (lihat `PERFORMANCE.md`).

```jsx
// BENAR — atom murni
function Button({ variant = 'primary', size = 'md', loading = false,
                  disabled = false, children, onClick }) {
  return (
    <button
      className={`btn btn-${variant} btn-${size}`}
      disabled={disabled || loading}
      onClick={onClick}
    >
      {loading ? <Spinner size="sm" /> : children}
    </button>
  );
}
export default Button;
```

---

## 5. Aturan Kode — Molecules

- **Boleh `useState`** untuk local UI state (hover, focus, toggle, form value).
- **Boleh `useEffect` HANYA dengan cleanup** (event listener, subscription, timer).
  Fetch data tetap dilarang.
- **Tidak boleh fetch API** dalam kondisi apapun.

```jsx
// BENAR — molecule dengan local state
function SearchBar({ onSearch }) {
  const [query, setQuery] = useState('');
  return (
    <div className="flex gap-2">
      <Input value={query} onChange={e => setQuery(e.target.value)} placeholder="Cari item..." />
      <Button onClick={() => onSearch(query)}>Cari</Button>
    </div>
  );
}
```

---

## 6. Aturan Kode — Organisms

- **Boleh fetch** data via custom hook (`useApi`) dari `src/hooks/`.
- **Boleh compose** section yang kompleks dari beberapa molecules.
- **Wajib render** tiga state: `loading`, `error`, `empty/data`.

```jsx
function PriceTable({ itemName }) {
  const { data, loading, error } = useApi.listQuotes(itemName);
  if (loading) return <Spinner />;
  if (error) return <ErrorBanner message={error.message} />;
  if (!data?.length) return <EmptyState label="Belum ada quote." />;
  return <table>...</table>;
}
```

---

## 7. Contoh Salah → Benar

### a) Atom mengimpor organism (reverse dependency)

```jsx
// SALAH — Button (atom) mengimpor RecommendationCard (organism)
import RecommendationCard from '../organisms/RecommendationCard';
function Button({ showPreview }) {
  return showPreview ? <RecommendationCard /> : <button>...</button>;
}

// BENAR — pindahkan logika ke organism, atau terima JSX via prop
function Button({ suffix = null, children, onClick }) {
  return <button onClick={onClick}>{children}{suffix}</button>;
}
// Pemanggil (organism) yang menyusun:
<Button suffix={<RecommendationCard />}>Lihat Rekomendasi</Button>
```

### b) Molecule fetch API di useEffect

```jsx
// SALAH — molecule fetch sendiri
function SeverityBadge({ findingId }) {
  const [data, setData] = useState(null);
  useEffect(() => {
    fetch(`/api/findings/${findingId}`).then(r => r.json()).then(setData);
  }, [findingId]);
  return <Badge variant={data?.severity}>{data?.severity}</Badge>;
}

// BENAR — terima data via props, fetch di organism/page
function SeverityBadge({ severity }) {
  const map = { HIGH: 'danger', MEDIUM: 'warning', LOW: 'success' };
  return <Badge variant={map[severity] ?? 'neutral'}>{severity}</Badge>;
}
```

### c) useEffect tanpa cleanup

```jsx
// SALAH — memory leak jika komponen unmount sebelum timeout selesai
useEffect(() => {
  const id = setTimeout(() => setVisible(true), 2000);
}, []);

// BENAR — cleanup mencegah update setelah unmount
useEffect(() => {
  const id = setTimeout(() => setVisible(true), 2000);
  return () => clearTimeout(id);
}, []);
```

---

## 8. Struktur File Final

```
src/
├── components/
│   ├── atoms/           # Button.jsx, Badge.jsx, Input.jsx, ...
│   ├── molecules/       # FormField.jsx, SearchBar.jsx, ...
│   ├── organisms/       # NavBar.jsx, HeroBilingual.jsx, ...
│   └── templates/       # LandingLayout.jsx, DashboardLayout.jsx, ...
├── hooks/               # useApi.js, useDebounce.js, useAbortableFetch.js
├── pages/               # LandingPage.jsx, MakerPage.jsx, ...
├── lib/                 # api.js, constants.js, format.js
└── styles/              # CSS modular tambahan (opsional)
```

Custom hooks (`hooks/`) **bukan komponen** — tidak punya JSX, tidak termasuk 5 level.
Mereka adalah lapisan akses data yang bisa dipakai organism dan page.
