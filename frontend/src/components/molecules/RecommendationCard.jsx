import { memo } from 'react';
import Badge from '../atoms/Badge';
import Button from '../atoms/Button';
import Icon from '../atoms/Icon';

// ── Formatters ────────────────────────────────────────────────────────────────

const _idrFormatter = new Intl.NumberFormat('id-ID', {
  style: 'currency',
  currency: 'IDR',
  maximumFractionDigits: 0,
});

/** Returns formatted Rupiah string, or null if value is not a finite number. */
const fmtIDR = (v) => (typeof v === 'number' && isFinite(v) ? _idrFormatter.format(v) : null);

/** Returns "+X.X%" / "-X.X%" string, or null if value is not a finite number. */
const fmtPct = (v) =>
  typeof v === 'number' && isFinite(v)
    ? `${v > 0 ? '+' : ''}${v.toFixed(1)}%`
    : null;

/** True when a value is present and is not the "Data tidak tersedia" sentinel. */
const isAvailable = (v) =>
  v !== null && v !== undefined && v !== 'Data tidak tersedia' && v !== '';

// ── Badge helpers ─────────────────────────────────────────────────────────────

const REKOMENDASI_VARIANT = {
  SETUJU:    'success',
  NEGOSIASI: 'warning',
  TOLAK:     'critical',
};

const STATUS_VARIANT = {
  WAJAR:        'success',
  PERHATIAN:    'warning',
  'TIDAK WAJAR': 'critical',
};

function RekomendasiBadge({ value }) {
  if (!isAvailable(value)) return null;
  const variant = REKOMENDASI_VARIANT[value] ?? 'muted';
  return <Badge variant={variant}>{value}</Badge>;
}

function StatusBadge({ value }) {
  if (!isAvailable(value)) return <span className="text-[var(--color-text-mute)]">—</span>;
  const variant = STATUS_VARIANT[value] ?? 'muted';
  return <Badge variant={variant}>{value}</Badge>;
}

// ── Sub-sections ──────────────────────────────────────────────────────────────

/** Math check banner — CRITICAL/WARNING (alert), INFO (informational) */
function MathCheckBanner({ kesimpulan }) {
  if (!kesimpulan) return null;
  const status = kesimpulan.math_check_status;
  if (status !== 'CRITICAL' && status !== 'WARNING' && status !== 'INFO') return null;

  const isCritical = status === 'CRITICAL';
  const isWarning = status === 'WARNING';
  const isInfo = status === 'INFO';

  const tone = isCritical
    ? { bg: 'bg-sev-critical/5', border: 'border-sev-critical', text: 'text-sev-critical' }
    : isWarning
    ? { bg: 'bg-amber/5', border: 'border-amber', text: 'text-amber' }
    : { bg: 'bg-electric/5', border: 'border-electric', text: 'text-electric' };

  const title = isCritical
    ? 'Inkonsistensi Matematis Terdeteksi'
    : isWarning
    ? 'Peringatan Inkonsistensi'
    : 'Catatan Selisih Total';

  const iconName = 'alert-triangle';

  return (
    <div
      className={[
        'flex items-start gap-3 p-4 border-l-4 rounded-r',
        tone.bg,
        tone.border,
      ].join(' ')}
      role={isInfo ? 'note' : 'alert'}
    >
      <span className={`mt-0.5 flex-shrink-0 ${tone.text}`}>
        <Icon name={iconName} size={18} strokeWidth={2} />
      </span>
      <div className="flex flex-col gap-0.5">
        <span className={`text-sm font-semibold leading-tight ${tone.text}`}>
          {title}
        </span>
        {kesimpulan.math_check_note && (
          <span className="text-xs text-[var(--color-text-inv-mute)] leading-relaxed">
            {kesimpulan.math_check_note}
          </span>
        )}
      </div>
    </div>
  );
}

/** 2-column hero stats row */
function HeroStats({ kesimpulan, items = [], mode = 'penawaran' }) {
  // BON mode: no vendor, no price — show item inventory stats instead.
  if (mode === 'bon') {
    const totalItems = items.length;
    const withoutMarket = items.filter((it) => it.harga_pasar_rata == null).length;
    const withMarket = totalItems - withoutMarket;

    return (
      <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
        <div className="flex flex-col gap-0.5 border border-[var(--border-dark)] p-4">
          <span className="text-xs text-[var(--color-text-inv-mute)] uppercase tracking-wider">
            Total Item
          </span>
          <span className="font-mono tabular-nums text-2xl font-bold text-[var(--color-text-inv)]">
            {totalItems}
          </span>
        </div>
        <div className="flex flex-col gap-0.5 border border-[var(--border-dark)] p-4">
          <span className="text-xs text-[var(--color-text-inv-mute)] uppercase tracking-wider">
            Sudah Ada Harga Pasar
          </span>
          <span className="font-mono tabular-nums text-2xl font-bold text-emerald">
            {withMarket}
          </span>
        </div>
        <div className="flex flex-col gap-0.5 border border-[var(--border-dark)] p-4">
          <span className="text-xs text-[var(--color-text-inv-mute)] uppercase tracking-wider">
            Belum Ada Harga Pasar
          </span>
          <span
            className={`font-mono tabular-nums text-2xl font-bold ${
              withoutMarket > 0 ? 'text-amber' : 'text-emerald'
            }`}
          >
            {withoutMarket}
          </span>
        </div>
      </div>
    );
  }

  // Penawaran mode: original behavior
  if (!kesimpulan) return null;

  const totalFormatted = fmtIDR(kesimpulan.total_penawaran);
  const hematFormatted = fmtIDR(kesimpulan.estimasi_penghematan);
  const skor            = kesimpulan.skor_vendor;

  return (
    <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
      {/* Total Penawaran */}
      <div className="flex flex-col gap-0.5 border border-[var(--border-dark)] p-4">
        <span className="text-xs text-[var(--color-text-inv-mute)] uppercase tracking-wider">
          Total Penawaran
        </span>
        {totalFormatted ? (
          <span className="font-mono tabular-nums text-2xl font-bold text-[var(--color-text-inv)]">
            {totalFormatted}
          </span>
        ) : (
          <span className="text-sm italic text-[var(--color-text-inv-mute)]">Belum tersedia</span>
        )}
      </div>

      {/* Estimasi Penghematan */}
      <div className="flex flex-col gap-0.5 border border-[var(--border-dark)] p-4">
        <span className="text-xs text-[var(--color-text-inv-mute)] uppercase tracking-wider">
          Estimasi Penghematan
        </span>
        {hematFormatted ? (
          <span className="font-mono tabular-nums text-2xl font-bold text-emerald">
            {hematFormatted}
          </span>
        ) : (
          <span className="text-sm italic text-[var(--color-text-inv-mute)]">Belum tersedia</span>
        )}
      </div>

      {/* Skor vendor */}
      <div className="flex flex-col gap-0.5 border border-[var(--border-dark)] p-4">
        <span className="text-xs text-[var(--color-text-inv-mute)] uppercase tracking-wider">
          Skor Vendor
        </span>
        {typeof skor === 'number' && isFinite(skor) ? (
          <span
            className={`font-mono tabular-nums text-2xl font-bold ${
              skor >= 80
                ? 'text-emerald'
                : skor >= 50
                ? 'text-amber'
                : 'text-sev-critical'
            }`}
          >
            {skor}/100
          </span>
        ) : (
          <span className="text-sm italic text-[var(--color-text-inv-mute)]">Belum tersedia</span>
        )}
      </div>
    </div>
  );
}

/** Horizontal-scroll items table */
function ItemsTable({ items, kesimpulan, mode = 'penawaran' }) {
  const isBon = mode === 'bon';
  if (!items || items.length === 0) {
    return (
      <div className="border border-[var(--border-dark)] flex flex-col items-center justify-center gap-2 py-10 px-6 text-center">
        <span className="text-[var(--color-text-inv-mute)]">
          <Icon name="file-text" size={28} strokeWidth={1.5} />
        </span>
        <p className="text-sm text-[var(--color-text-inv-mute)]">
          Tidak ada item terdeteksi dari dokumen
        </p>
      </div>
    );
  }

  return (
    <div className="overflow-x-auto border border-[var(--border-dark)]">
      <table className="w-full text-sm min-w-[640px]">
        <thead>
          <tr className="border-b border-[var(--border-dark)] bg-surface">
            {[
              'Item',
              'Qty',
              ...(isBon ? [] : ['Harga Vendor', 'Total']),
              isBon ? 'Harga Pasar / Satuan' : 'Harga Pasar',
              ...(isBon ? ['Estimasi Total'] : []),
              ...(isBon ? [] : ['Selisih', 'Status']),
              'Rekomendasi',
            ].map((h) => (
              <th
                key={h}
                className={[
                  'px-4 py-2 text-xs font-medium uppercase tracking-wider text-[var(--color-text-inv-mute)]',
                  h === 'Item' ? 'text-left' : 'text-right',
                  h === 'Status' || h === 'Rekomendasi' ? 'text-center' : '',
                  (h === 'Qty' || h === 'Total') ? 'hidden md:table-cell' : '',
                ].join(' ')}
              >
                {h}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {items.map((item, idx) => {
            const hargaVendor = fmtIDR(item.harga_vendor);
            const hargaPasar  = fmtIDR(item.harga_pasar_rata);
            const selisih     = fmtPct(item.selisih_persen);
            const selisihNum  = typeof item.selisih_persen === 'number' ? item.selisih_persen : null;

            return (
              <tr
                key={idx}
                className="border-b border-[var(--border-dark)] last:border-0 hover:bg-surface/60 transition-colors"
              >
                {/* Item name */}
                <td className="px-4 py-3 font-medium text-[var(--color-text-inv)] max-w-[200px]">
                  <div className="truncate" title={item.nama_item}>
                    {item.nama_item || '—'}
                  </div>
                  {/* Sumber links per item */}
                  {Array.isArray(item.sumber) && (
                    <div className="flex flex-wrap gap-1.5 mt-1">
                      {item.sumber
                        .filter((s) => typeof s === 'string' && s.startsWith('http'))
                        .map((url, si) => (
                          <a
                            key={si}
                            href={url}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="inline-flex items-center gap-1 text-[10px] text-electric hover:underline"
                          >
                            <Icon name="external-link" size={10} />
                            Sumber {si + 1}
                          </a>
                        ))}
                    </div>
                  )}
                </td>

                {/* Qty */}
                <td className="hidden md:table-cell px-4 py-3 text-right font-mono tabular-nums text-[var(--color-text-inv)]">
                  {isAvailable(item.qty) && isAvailable(item.satuan) ? `${item.qty} ${item.satuan}` : '—'}
                </td>

                {!isBon && (
                  <>
                    {/* Harga vendor */}
                    <td className="px-4 py-3 text-right font-mono tabular-nums text-[var(--color-text-inv)]">
                      {hargaVendor ?? '—'}
                    </td>

                    {/* Total */}
                    <td className="hidden md:table-cell px-4 py-3 text-right font-mono tabular-nums text-[var(--color-text-inv)]">
                      {fmtIDR(item.total_price_vendor) ?? '—'}
                    </td>
                  </>
                )}

                {/* Harga pasar */}
                <td className="px-4 py-3 text-right font-mono tabular-nums text-[var(--color-text-inv-mute)]">
                  {hargaPasar ? hargaPasar : <span className="italic">—</span>}
                </td>

                {/* Estimasi total (BON only) */}
                {isBon && (
                  <td className="px-4 py-3 text-right font-mono tabular-nums text-[var(--color-text-inv)]">
                    {typeof item.qty === 'number' && item.qty > 0 && typeof item.harga_pasar_rata === 'number'
                      ? fmtIDR(item.qty * item.harga_pasar_rata)
                      : <span className="italic">—</span>}
                  </td>
                )}

                {!isBon && (
                  <>
                    {/* Selisih */}
                    <td
                      className={[
                        'px-4 py-3 text-right font-mono tabular-nums text-sm',
                        selisihNum === null
                          ? 'text-[var(--color-text-inv-mute)]'
                          : selisihNum > 0
                          ? 'text-sev-high'
                          : 'text-emerald',
                      ].join(' ')}
                    >
                      {selisih ?? '—'}
                    </td>

                    {/* Status */}
                    <td className="px-4 py-3 text-center">
                      <StatusBadge value={item.status} />
                    </td>
                  </>
                )}

                {/* Rekomendasi */}
                <td className="px-4 py-3 text-center">
                  <RekomendasiBadge value={item.rekomendasi} />
                </td>
              </tr>
            );
          })}
        </tbody>
        <tfoot className="border-t-2 border-[var(--border-dark)] bg-surface">
          {isBon ? (
            (() => {
              const priced = items.filter(
                (it) => typeof it.qty === 'number' && it.qty > 0 && typeof it.harga_pasar_rata === 'number',
              );
              const totalEstimasi = priced.reduce(
                (sum, it) => sum + it.qty * it.harga_pasar_rata, 0,
              );
              return (
                <>
                  <tr>
                    <td colSpan={4} className="px-4 py-3 text-right font-bold text-[var(--color-text-inv)]">
                      Total Estimasi Pengadaan
                    </td>
                    <td className="px-4 py-3 text-right font-mono tabular-nums font-bold text-[var(--color-text-inv)]">
                      {fmtIDR(totalEstimasi) ?? '—'}
                    </td>
                  </tr>
                  <tr>
                    <td colSpan={5} className="px-4 py-2 text-right italic text-xs text-[var(--color-text-inv-mute)]">
                      Berdasarkan {priced.length} dari {items.length} item yang punya harga pasar
                    </td>
                  </tr>
                </>
              );
            })()
          ) : (
            <tr>
              <td colSpan={1} className="px-4 py-3 text-right font-bold text-[var(--color-text-inv)] md:hidden">
                TOTAL
              </td>
              <td colSpan={3} className="hidden md:table-cell px-4 py-3 text-right font-bold text-[var(--color-text-inv)]">
                TOTAL
              </td>
              <td className="px-4 py-3 text-right font-mono tabular-nums font-bold text-[var(--color-text-inv)]">
                {fmtIDR(kesimpulan?.total_penawaran) ?? '—'}
              </td>
              <td colSpan={4} className="hidden md:table-cell px-4 py-3"></td>
              <td colSpan={3} className="md:hidden px-4 py-3"></td>
            </tr>
          )}
        </tfoot>
      </table>
    </div>
  );
}

/** Sumber fallback notice — shown only when ALL sources are unavailable */
function SumberNotice({ items }) {
  if (!Array.isArray(items) || items.length === 0) return null;

  const allSources = items.flatMap((item) =>
    Array.isArray(item.sumber) ? item.sumber : []
  );
  const hasValidUrl = allSources.some(
    (s) => typeof s === 'string' && s.startsWith('http')
  );

  if (hasValidUrl) return null;

  return (
    <p className="text-xs italic text-[var(--color-text-inv-mute)]">
      Tidak ada sumber harga pembanding tersedia
    </p>
  );
}

// ── Main component ────────────────────────────────────────────────────────────

/**
 * RecommendationCard — renders a full Maker Agent recommendation result.
 *
 * Props:
 *   result     {Object}    RecommendationResponse from /recommend-with-file
 *   onValidate {Function}  called when "Validate this price" is clicked
 */
function RecommendationCard({ result = {}, onValidate, mode = 'penawaran' }) {
  const vendorName        = result.vendor_name;
  const vendorContact     = result.vendor_contact;
  const vendorAddress     = result.vendor_address;
  const items             = result.items ?? [];
  const kesimpulan        = result.kesimpulan ?? null;
  const ringkasanAlasan   = kesimpulan?.ringkasan_alasan ?? '';
  const rekomendasiVendor = kesimpulan?.rekomendasi_vendor ?? null;

  return (
    <article className="flex flex-col gap-6 border border-[var(--border-dark)] bg-surface p-6">

      {/* ── 1. HEADER ────────────────────────────────────────────────────── */}
      <div className="flex flex-col gap-2">
        <span className="text-xs text-[var(--color-text-inv-mute)] uppercase tracking-wider">
          {mode === 'bon' ? 'Rekomendasi BON Permintaan' : 'Harga yang Direkomendasikan'}
        </span>
        <div className="flex flex-col gap-1">
          <div className="flex items-start justify-between gap-4 flex-wrap">
            <h2 className="text-2xl font-semibold text-[var(--color-text-inv)] leading-tight">
              {mode === 'bon'
                ? 'Belum Ada Vendor'
                : (isAvailable(vendorName) ? vendorName : '—')}
            </h2>
            {mode === 'bon' ? (
              <span className="px-3 py-1 text-xs uppercase tracking-wider border border-electric text-electric">
                Cari Supplier
              </span>
            ) : (
              isAvailable(rekomendasiVendor) && (
                <RekomendasiBadge value={rekomendasiVendor} />
              )
            )}
          </div>
          {(isAvailable(vendorContact) || isAvailable(vendorAddress)) && (
            <div className="flex flex-col gap-1 mt-1">
              {isAvailable(vendorContact) && (
                <div className="flex items-center gap-2 text-sm text-[var(--color-text-inv-mute)]">
                  <Icon name="mail" size={14} />
                  <span>{vendorContact}</span>
                </div>
              )}
              {isAvailable(vendorAddress) && (
                <div className="flex items-center gap-2 text-sm text-[var(--color-text-inv-mute)]">
                  <Icon name="map-pin" size={14} />
                  <span>{vendorAddress}</span>
                </div>
              )}
            </div>
          )}
        </div>
      </div>

      {/* ── 2. MATH CHECK BANNER ───────────────────────────────────────── */}
      <MathCheckBanner kesimpulan={kesimpulan} />

      {/* ── 3. HERO STATS ────────────────────────────────────────────────── */}
      <HeroStats kesimpulan={kesimpulan} items={items} mode={mode} />

      {/* ── 3. TABLE ITEMS ───────────────────────────────────────────────── */}
      <div className="flex flex-col gap-2">
        <span className="text-xs text-[var(--color-text-inv-mute)] uppercase tracking-wider">
          Detail Item
        </span>
        <ItemsTable items={items} kesimpulan={kesimpulan} mode={mode} />
        <SumberNotice items={items} />
      </div>

      {/* ── 5. RINGKASAN ─────────────────────────────────────────────────── */}
      {ringkasanAlasan && (
        <div className="flex flex-col gap-1.5 border-t border-[var(--border-dark)] pt-4">
          <span className="text-xs text-[var(--color-text-inv-mute)] uppercase tracking-wider">
            Ringkasan
          </span>
          <p className="text-sm text-[var(--color-text-inv)] leading-relaxed">
            {ringkasanAlasan}
          </p>
        </div>
      )}

      {/* ── 6. ACTIONS ───────────────────────────────────────────────────── */}
      {onValidate && mode !== 'bon' && (
        <div className="flex justify-start border-t border-[var(--border-dark)] pt-4">
          <Button variant="primary" size="sm" onClick={onValidate}>
            Validate this price
          </Button>
        </div>
      )}
    </article>
  );
}

export default memo(RecommendationCard);
