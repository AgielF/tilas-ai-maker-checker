# Inventaris Komponen — Tilas Frontend

Dokumen ini mendaftar seluruh komponen UI yang direncanakan, diorganisir per level atomic design.
Setiap komponen tinggal dalam satu file `.jsx`, di-export sebagai `default export`.

---

## Aturan Umum

- Satu komponen = satu file `.jsx` dengan nama PascalCase.
- Props didestrukturisasi di function signature.
- Tidak ada `defaultProps` — gunakan default parameter JavaScript.
- Tidak ada inline style kecuali CSS variable dinamis (contoh: `style={{ '--score': value }}`).

---

## Atoms

> Stateless, pure, tanpa logika bisnis, tanpa `useEffect`.
> Folder: `src/components/atoms/`

| Komponen | Props Utama | Dipakai Di |
|---|---|---|
| `Button` | `variant` ('primary'\|'ghost'\|'danger'), `size` ('sm'\|'md'\|'lg'), `loading`, `disabled`, `children`, `onClick` | Semua level di atasnya |
| `Badge` | `variant` ('neutral'\|'success'\|'warning'\|'danger'\|'electric'), `children` | `SeverityBadge`, `ComingSoonBadge`, `PageHeader` |
| `Input` | `id`, `name`, `type`, `value`, `placeholder`, `error`, `disabled`, `onChange` | `FormField`, `SearchBar` |
| `Label` | `htmlFor`, `children`, `required` | `FormField` |
| `Spinner` | `size` ('sm'\|'md'\|'lg'), `label` (screen reader text) | `Button`, `LoadingSteps`, `DashboardLayout` |
| `Icon` | `name` (string → key map ke inline SVG), `size`, `className` | Semua level, tidak boleh import library ikon eksternal |
| `Skeleton` | `width`, `height`, `rounded`, `className` | `RecommendationCard`, `PriceTable`, `MatchGrid` |
| `Divider` | `orientation` ('horizontal'\|'vertical'), `className` | `NavBar`, `Footer`, `DashboardLayout` |

### Catatan Icon

`Icon` hanya merender inline SVG dari map internal (`src/lib/icons.js`). Tidak ada
dependency pada `lucide-react`, `heroicons`, atau library ikon eksternal lainnya.

```jsx
// src/components/atoms/Icon.jsx
const ICONS = {
  check: <path d="M5 13l4 4L19 7" />,
  alert: <path d="M12 9v4m0 4h.01M10.29 3.86L1.82..." />,
  // ... dst
};

function Icon({ name, size = 20, className = '' }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24"
         fill="none" stroke="currentColor" strokeWidth={2}
         className={className} aria-hidden="true">
      {ICONS[name]}
    </svg>
  );
}
export default Icon;
```

---

## Molecules

> Gabungan atoms, satu tanggung jawab UI. Boleh `useState` lokal. Tidak fetch API.
> Folder: `src/components/molecules/`

| Komponen | Props Utama | Dipakai Di |
|---|---|---|
| `FormField` | `label`, `htmlFor`, `error`, `required`, `children` (slot untuk Input/Select) | `MakerPage`, `CheckerPage` |
| `SearchBar` | `placeholder`, `onSearch`, `loading` | `ValidatePage`, `MakerPage` |
| `SeverityBadge` | `severity` ('HIGH'\|'MEDIUM'\|'LOW'\|'INFO') | `FindingsList`, `RiskReportPage`, `RiskGauge` |
| `StatCell` | `value`, `label`, `unit`, `highlight` | `StatStrip`, `RiskReportPage` |
| `NavItem` | `to` (route path), `label`, `icon` | `NavBar` |
| `EmptyState` | `icon`, `label`, `description`, `action` (Button slot) | `PriceTable`, `FindingsList`, semua organism kosong |
| `ErrorBanner` | `message`, `onRetry`, `code` | Semua organism yang fetch data |
| `ComingSoonBadge` | — (tidak ada props wajib, teks dan warna sudah tetap) | `PAGES.md` Coming Soon items, `NavBar` |

### Contoh StatCell

```jsx
// src/components/molecules/StatCell.jsx
function StatCell({ value, label, unit = '', highlight = false }) {
  return (
    <div className={`flex flex-col gap-1 ${highlight ? 'text-electric' : 'text-slate-200'}`}>
      <span className="text-3xl font-bold tabular-nums">
        {value}{unit}
      </span>
      <span className="text-xs text-slate-400 uppercase tracking-widest">{label}</span>
    </div>
  );
}
export default StatCell;
```

---

## Organisms

> Gabungan molecules (dan atoms). Satu section utuh. Boleh fetch via hook.
> Wajib render state loading / error / empty.
> Folder: `src/components/organisms/`

| Komponen | Props Utama | Dipakai Di |
|---|---|---|
| `NavBar` | `links` (array NavItem config), `ctaLabel`, `ctaTo` | `LandingLayout`, `DashboardLayout` |
| `Footer` | `year`, `author` | `LandingLayout` |
| `HeroBilingual` | `headlineEn`, `headlineId`, `ctaLabel`, `ctaTo` | `LandingPage` |
| `FeatureGrid` | `features` (array `{icon, title, description}`) | `LandingPage` |
| `StatStrip` | `stats` (array `{value, label, unit}`) | `LandingPage` |
| `RecommendationCard` | `itemName`, `data` (RecommendationResponse schema), `loading`, `error`, `onRetry` | `MakerPage` |
| `LoadingSteps` | `steps` (array string), `currentStep` | `MakerPage` (selama request ~60 detik) |
| `PriceTable` | `itemName`, `quotes` (array PriceQuoteRead), `loading`, `error` | `ValidatePage` |
| `MatchGrid` | `po`, `gr`, `invoice` (DocumentData), `result` (MatchResult), `loading` | `CheckerPage` |
| `RiskGauge` | `score` (0–100), `status` ('PASS'\|'WARN'\|'FAIL'), `loading` | `RiskReportPage` |
| `SeverityBreakdown` | `counts` (`{HIGH, MEDIUM, LOW, INFO}`), `loading` | `RiskReportPage` |
| `FindingsList` | `findings` (array AuditFindingRead), `loading`, `error` | `RiskReportPage`, `CheckerPage` |

### Pola Wajib: Loading / Error / Empty

Setiap organism yang fetch data wajib mengikuti pola ini:

```jsx
function RecommendationCard({ itemName }) {
  const { data, loading, error, retry } = useApi.recommend(itemName);

  if (loading) return <LoadingSteps steps={MAKER_STEPS} />;
  if (error)   return <ErrorBanner message={error.message} onRetry={retry} />;
  if (!data)   return <EmptyState label="Belum ada rekomendasi." />;

  return (
    <article className="...">
      {/* render data */}
    </article>
  );
}
```

---

## Templates

> Layout skeleton tanpa data nyata. Mendefinisikan slot (children).
> Folder: `src/components/templates/`

| Komponen | Props Utama | Dipakai Di |
|---|---|---|
| `LandingLayout` | `children` | `LandingPage` |
| `DashboardLayout` | `children`, `title`, `sidebar` (opsional) | `MakerPage`, `CheckerPage`, `ValidatePage`, `RiskReportPage` |
| `PageHeader` | `title`, `subtitle`, `badge` (BadgeProps opsional) | Di dalam `DashboardLayout` per page |

### Contoh DashboardLayout

```jsx
// src/components/templates/DashboardLayout.jsx
function DashboardLayout({ children, title }) {
  return (
    <div className="min-h-screen bg-navy-950 text-slate-100">
      <NavBar />
      <main className="mx-auto max-w-5xl px-6 py-10">
        {title && <PageHeader title={title} />}
        {children}
      </main>
      <Footer />
    </div>
  );
}
export default DashboardLayout;
```

---

## Pages

> Template + data nyata + react-router route.
> Folder: `src/pages/`

| Halaman | Route | Template | Organism Utama |
|---|---|---|---|
| `LandingPage` | `/` | `LandingLayout` | `HeroBilingual`, `FeatureGrid`, `StatStrip` |
| `DashboardPage` | `/dashboard` | `DashboardLayout` | `StatStrip`, `FindingsList` |
| `MakerPage` | `/maker` | `DashboardLayout` | `SearchBar`, `RecommendationCard`, `LoadingSteps` |
| `ValidatePage` | `/validate` | `DashboardLayout` | `SearchBar`, `PriceTable` |
| `CheckerPage` | `/checker` | `DashboardLayout` | `MatchGrid`, `FindingsList` |
| `RiskReportPage` | `/risk/:transactionId` | `DashboardLayout` | `RiskGauge`, `SeverityBreakdown`, `FindingsList` |
| `NotFoundPage` | `*` | — (minimal) | `EmptyState` |
