# Hero Interaction — Tilas

Dokumen ini menjelaskan interaksi bilingual hero dengan efek spotlight berbasis mouse
pada `LandingPage`. Komponen bernama `HeroBilingual` dan berada di level **organism**.

---

## Level Atomic — HeroBilingual adalah Organism

`HeroBilingual` dikategorikan sebagai **organism** karena:

- Mengandung beberapa **atoms**: elemen `Logo`, lingkaran dekoratif (`Circle`), teks heading.
- Mengandung **molecules**: kelompok tombol CTA (`Button` + `ComingSoonBadge`).
- Boleh menggunakan `useEffect` untuk memasang event listener `mousemove` —
  **wajib disertai cleanup**.
- **Tidak** fetch API dalam kondisi apapun.

```
HeroBilingual (organism)
├── Logo mark (atom — inline SVG)
├── Circle decorative (atom — div)
├── Headline EN / ID (atom — h1)
├── Subtitle (atom — p)
└── CTA group (molecule)
    ├── Button (atom)
    └── ComingSoonBadge (atom wrapped)
```

---

## Opsi A — Spotlight Mask

Headline ditampilkan dalam dua bahasa (Inggris dan Indonesia) dalam satu
elemen overlay. Spotlight mengikuti posisi mouse melalui CSS mask.

### HTML / JSX Structure

```jsx
<section
  ref={heroRef}
  className="hero relative overflow-hidden bg-navy-950 min-h-screen"
  aria-label="Hero section — Tilas"
>
  {/* Layer 1 — teks Indonesia (selalu terlihat, base layer) */}
  <div className="hero__base absolute inset-0 flex items-center justify-center">
    <h1 className="text-5xl font-bold text-slate-400">
      {headlineId}
    </h1>
  </div>

  {/* Layer 2 — spotlight overlay, teks Inggris (terlihat di area spotlight) */}
  <div
    ref={overlayRef}
    className="hero__overlay absolute inset-0 flex items-center justify-center"
    style={{ '--mx': '50%', '--my': '50%' }}
    aria-hidden="true"
  >
    <h1 className="text-5xl font-bold text-electric">
      {headlineEn}
    </h1>
  </div>
</section>
```

---

## CSS Variable — `--mx` / `--my`

Posisi mouse disimpan sebagai CSS custom property langsung pada elemen DOM,
**bukan** sebagai React state, untuk menghindari 60 re-render per detik.

```css
/* src/index.css */

/* @property registration untuk smooth transition */
@property --mx {
  syntax: '<percentage>';
  inherits: false;
  initial-value: 50%;
}

@property --my {
  syntax: '<percentage>';
  inherits: false;
  initial-value: 50%;
}

.hero__overlay {
  /* Spotlight mask: lingkaran 280px di posisi mouse */
  -webkit-mask-image: radial-gradient(
    circle 280px at var(--mx) var(--my),
    black 0%,
    transparent 100%
  );
  mask-image: radial-gradient(
    circle 280px at var(--mx) var(--my),
    black 0%,
    transparent 100%
  );
  transition: --mx 0.05s ease-out, --my 0.05s ease-out;
}
```

---

## requestAnimationFrame — Pattern

Mouse event dapat terjadi hingga ratusan kali per detik. Throttle dengan `rAF`:

```jsx
// src/components/organisms/HeroBilingual.jsx
import { useEffect, useRef } from 'react';

function HeroBilingual({ headlineEn, headlineId, ctaLabel, ctaTo }) {
  const heroRef    = useRef(null);
  const overlayRef = useRef(null);
  const rafId      = useRef(null);   // simpan ID di ref, bukan state

  useEffect(() => {
    const hero    = heroRef.current;
    const overlay = overlayRef.current;
    if (!hero || !overlay) return;

    // Fallback: matikan efek di touchscreen atau reduced-motion
    const noHover   = window.matchMedia('(hover: none)').matches;
    const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    if (noHover || reducedMotion) return;

    function handleMove(e) {
      // Cancel frame sebelumnya — hanya satu frame aktif sekaligus
      if (rafId.current) cancelAnimationFrame(rafId.current);

      rafId.current = requestAnimationFrame(() => {
        const rect = hero.getBoundingClientRect();
        const mx = ((e.clientX - rect.left) / rect.width  * 100).toFixed(2) + '%';
        const my = ((e.clientY - rect.top)  / rect.height * 100).toFixed(2) + '%';

        // Set langsung ke DOM — bukan via React state
        overlay.style.setProperty('--mx', mx);
        overlay.style.setProperty('--my', my);
      });
    }

    hero.addEventListener('mousemove', handleMove);

    // WAJIB: cleanup saat unmount
    return () => {
      hero.removeEventListener('mousemove', handleMove);
      if (rafId.current) cancelAnimationFrame(rafId.current);
    };
  }, []); // deps kosong — hanya dipasang sekali saat mount

  return (
    <section ref={heroRef} className="hero relative overflow-hidden bg-navy-950 min-h-screen">
      <div className="hero__base ..."><h1>{headlineId}</h1></div>
      <div ref={overlayRef} className="hero__overlay ..." aria-hidden="true">
        <h1>{headlineEn}</h1>
      </div>
      {/* CTA group */}
    </section>
  );
}

export default HeroBilingual;
```

---

## Fallback Mobile + Reduced Motion

Dua kondisi yang menonaktifkan efek spotlight:

| Kondisi | Media Query | Perilaku |
|---|---|---|
| Touchscreen (tidak ada hover) | `(hover: none)` | Overlay `--mx` / `--my` tetap di 50% 50% |
| Pengguna aktifkan "reduce motion" | `(prefers-reduced-motion: reduce)` | Transisi CSS dimatikan, overlay disembunyikan |

```css
/* Fallback reduced motion */
@media (prefers-reduced-motion: reduce) {
  .hero__overlay { display: none; }
}
```

```css
/* Fallback touch device */
@media (hover: none) {
  .hero__overlay { display: none; }
}
```

Cek di `useEffect` sudah ditangani dengan `matchMedia` sebelum memasang event listener.

---

## Memory & Performance Checklist

| Item | Implementasi |
|---|---|
| `addEventListener mousemove` hanya dipasang saat mount | `useEffect(() => { ... return cleanup }, [])` |
| Listener dihapus saat unmount | `return () => hero.removeEventListener(...)` |
| rAF ID disimpan di `useRef`, bukan `useState` | `const rafId = useRef(null)` |
| `cancelAnimationFrame` dipanggil di cleanup | `if (rafId.current) cancelAnimationFrame(rafId.current)` |
| CSS variable di-set via `el.style.setProperty` | Menghindari re-render React sama sekali |
| `@property` di `index.css` untuk transisi halus | `@property --mx { syntax: '<percentage>'; ... }` |
| Fallback `(hover: none)` | `useEffect` check `matchMedia('(hover: none)').matches` |
| Fallback `prefers-reduced-motion` | `useEffect` check + CSS `@media` |
| `aria-hidden="true"` pada layer overlay | Screen reader tidak membaca duplikat teks |
