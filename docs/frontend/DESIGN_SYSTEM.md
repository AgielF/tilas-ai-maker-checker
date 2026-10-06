# Design System — Tilas

Panduan visual dan token desain untuk seluruh komponen frontend Tilas.
Semua keputusan estetik bersumber dari dokumen ini.

---

## 1. Prinsip Visual

| Prinsip | Penjelasan |
|---|---|
| **Grid editorial** | Gunakan border 1px hairline sebagai pemisah, **bukan** shadow tebal. |
| **Monokrom base** | Palet dasar off-white / charcoal. Satu aksen warna: **electric blue** (`#508DFF`). |
| **Tipografi ekspresif** | Headline besar dengan `tracking-tight` / `tracking-tighter`. |
| **Background pattern** | Teks berulang "T I M B A N G" dengan opacity 3–4% sebagai tekstur subtle. |
| **Circle motif** | Dua lingkaran tumpang tindih di hero = simbol dualitas Maker–Checker. |
| **Whitespace generous** | Breathing room lebih baik dari kepadatan. Jangan kompres layout. |

---

## 2. Color Tokens

### CSS Variables — `src/index.css`

```css
:root {
  /* Brand */
  --color-navy:       #0F2A47;
  --color-electric:   #508DFF;

  /* Semantic state */
  --color-emerald:    #10B981;
  --color-amber:      #F59E0B;
  --color-red:        #EF4444;

  /* Surface */
  --color-canvas:     #FAFAF8;
  --color-ink:        #0A0A0B;
  --color-surface:    #1E293B;
  --color-surface-2:  #0F172A;

  /* Text */
  --color-text:           #0A0A0B;
  --color-text-mute:      #64748B;
  --color-text-inv:       #FAFAF8;
  --color-text-inv-mute:  #94A3B8;

  /* Border */
  --border-light: rgba(15, 42, 71, 0.10);
  --border-dark:  rgba(250, 250, 248, 0.10);

  /* Severity */
  --sev-critical: #EF4444;
  --sev-high:     #F97316;
  --sev-medium:   #EAB308;
  --sev-low:      #22C55E;
}

@property --mx { syntax: '<percentage>'; inherits: true; initial-value: 50%; }
@property --my { syntax: '<percentage>'; inherits: true; initial-value: 50%; }
```

### Referensi Warna Cepat

| Token | Hex | Dipakai untuk |
|---|---|---|
| `navy` | `#0F2A47` | Dark background, teks utama, border |
| `electric` | `#508DFF` | CTA, highlight, link aktif |
| `emerald` | `#10B981` | Status sukses, MATCHED |
| `amber` | `#F59E0B` | Coming Soon badge, peringatan |
| `red` | `#EF4444` | Error, severity CRITICAL |
| `canvas` | `#FAFAF8` | Background halaman light |
| `ink` | `#0A0A0B` | Teks utama light mode |
| `surface` | `#1E293B` | Background card dark |
| `surface-2` | `#0F172A` | Background page dark |

---

## 3. Tailwind Config Mapping — `tailwind.config.js`

```js
/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,jsx}'],
  theme: {
    extend: {
      colors: {
        navy:        'var(--color-navy)',
        electric:    'var(--color-electric)',
        emerald:     'var(--color-emerald)',
        amber:       'var(--color-amber)',
        ink:         'var(--color-ink)',
        canvas:      'var(--color-canvas)',
        surface:     'var(--color-surface)',
        'surface-2': 'var(--color-surface-2)',
        sev: {
          critical: 'var(--sev-critical)',
          high:     'var(--sev-high)',
          medium:   'var(--sev-medium)',
          low:      'var(--sev-low)',
        },
      },
      fontFamily: {
        sans: ['"Inter Variable"', 'system-ui', 'sans-serif'],
        mono: ['"JetBrains Mono Variable"', 'ui-monospace', 'monospace'],
      },
    },
  },
  plugins: [],
};
```

---

## 4. Tipografi

### Font

| Font | Package | Dipakai untuk |
|---|---|---|
| **Inter Variable** | `@fontsource-variable/inter` | Semua UI text, heading, body |
| **JetBrains Mono Variable** | `@fontsource-variable/jetbrains-mono` | Angka uang, kode, nilai metrik |

> **Aturan wajib:** Semua angka uang dan nilai metrik numerik **WAJIB** menggunakan
> `font-mono tabular-nums`.

### Skala Tipografi

| Level | Class Tailwind | Dipakai untuk |
|---|---|---|
| Display | `text-7xl md:text-8xl font-black tracking-tighter` | Hero headline utama |
| H1 | `text-5xl md:text-6xl font-bold tracking-tight` | Judul halaman |
| H2 | `text-3xl md:text-4xl font-semibold tracking-tight` | Section title |
| H3 | `text-xl font-semibold` | Card title, sub-section |
| Body | `text-base` | Konten paragraf |
| Caption | `text-sm` | Label, helper text, metadata |
| Mono | `font-mono text-sm tabular-nums` | Harga, angka, kode |

---

## 5. Spacing

- Kelipatan **4px** — gunakan class Tailwind standar (`p-4`, `gap-8`, dll.).
- Section landing: `py-24 md:py-32`
- Section dashboard: `py-8 md:py-12`
- Cell / card padding: `p-6 md:p-8`
- Gunakan whitespace generous; hindari memadatkan konten.

---

## 6. Border & Radius

### Border

```
Border light (background putih/canvas):
  border border-[var(--border-light)]   ← 1px navy 10% opacity

Border dark (background surface/navy):
  border border-[var(--border-dark)]    ← 1px white 10% opacity
```

### Radius

| Konteks | Class |
|---|---|
| Default (card, container) | `rounded-none` |
| Button, Input | `rounded-md` |
| Badge, circle motif | `rounded-full` |

### Shadow

**Hindari shadow.** Jika perlu depth: gunakan `ring-1 ring-black/5`.

---

## 7. Background Pattern

Snippet HeroPattern — teks "T I M B A N G" berulang sebagai tekstur:

```jsx
// src/components/atoms/HeroPattern.jsx
export default function HeroPattern({ dark = false }) {
  const cls = dark
    ? 'text-white/[0.03]'
    : 'text-navy/[0.04]';

  return (
    <div
      aria-hidden="true"
      className={`pointer-events-none absolute inset-0 select-none overflow-hidden
        ${cls} font-black tracking-[0.5em] text-[clamp(1.5rem,4vw,3rem)]
        leading-[2] flex flex-col justify-start`}
    >
      {Array.from({ length: 20 }).map((_, i) => (
        <div key={i} className="whitespace-nowrap">
          {Array.from({ length: 10 }).map((_, j) => (
            <span key={j}>T I M B A N G&nbsp;&nbsp;&nbsp;</span>
          ))}
        </div>
      ))}
    </div>
  );
}
```

---

## 8. Severity Scale

Dipakai di: `SeverityBadge`, `FindingList`, `RiskGauge`, `SeverityBreakdown`.

| Level | Badge class |
|---|---|
| CRITICAL | `bg-sev-critical/10 text-sev-critical border border-sev-critical/30` |
| HIGH | `bg-sev-high/10 text-sev-high border border-sev-high/30` |
| MEDIUM | `bg-sev-medium/10 text-sev-medium border border-sev-medium/30` |
| LOW | `bg-sev-low/10 text-sev-low border border-sev-low/30` |

> **Larangan:** Jangan gunakan warna severity untuk konteks non-severity
> (mis. warna merah sebagai brand atau aksen umum).

---

## 9. Contoh Komponen (Preview Token)

### Button

```jsx
// Primary
<button className="bg-electric text-white px-4 py-2 rounded-md
  hover:bg-electric/90 transition-colors font-medium">
  Mulai Analisis
</button>

// Ghost
<button className="border border-[var(--border-light)] px-4 py-2 rounded-md
  hover:bg-navy/5 transition-colors font-medium">
  Pelajari Lebih
</button>
```

### Card

```jsx
// Light
<div className="border border-[var(--border-light)] bg-white p-6 rounded-none">
  …
</div>

// Dark
<div className="border border-[var(--border-dark)] bg-surface p-6 rounded-none">
  …
</div>
```

### Coming Soon Badge

```jsx
<span className="bg-amber/10 text-amber border border-amber/30
  uppercase tracking-wider text-[11px] px-2 py-0.5 rounded-full font-medium">
  Coming Soon
</span>
```

---

## 10. Do & Don't

### ✅ Lakukan

- Gunakan border 1px hairline (`border-[var(--border-light)]`)
- Whitespace generous — `py-24`, `p-8`, `gap-8`
- Satu aksen warna (`electric`) untuk semua CTA
- `font-mono tabular-nums` untuk semua angka uang dan metrik
- `rounded-none` untuk card, `rounded-md` untuk button/input
- Severity palette **hanya** untuk severity

### ❌ Jangan

- Shadow berlebihan (`shadow-2xl`, `shadow-lg` tanpa alasan)
- Merah (`red`/`sev-critical`) sebagai warna brand atau aksen umum
- `rounded-3xl` atau border-radius besar pada card/container
- Gradient chaotik atau warna-warni tanpa struktur
- Emoji sebagai ikon produksi (gunakan `Icon` atom dengan inline SVG)
- Hardcode hex di JSX — selalu gunakan token Tailwind atau CSS variable
