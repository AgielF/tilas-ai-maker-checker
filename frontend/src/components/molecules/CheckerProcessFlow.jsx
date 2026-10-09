import { memo } from 'react';
import Icon from '../atoms/Icon';

const STEPS = [
  { icon: 'file-text',      label: 'Upload 4 Dok.', desc: 'PO, GR, Invoice, FP' },
  { icon: 'shield',         label: 'Ekstraksi AI',  desc: 'LLM baca dokumen' },
  { icon: 'check',          label: '4-Way Match',   desc: 'PO ↔ GR ↔ Inv\nQty ±2%, amount ±1%' },
  { icon: 'search',         label: 'Validasi SOP',  desc: 'L2 > 100jt, faktur pajak\nsplit PO, duplikat invoice' },
  { icon: 'alert-triangle', label: 'Risk Report',   desc: 'Skor 0-100, 6 label\nsitasi + action plan' },
];

function CheckerProcessFlow() {
  return (
    <section className="border border-[var(--border-dark)] bg-surface p-5">
      <div className="flex flex-col gap-4">
        <span className="text-xs text-[var(--color-text-inv-mute)] uppercase tracking-wider">
          Alur Proses Checker
        </span>
        <div className="flex items-start justify-between w-full gap-2">
          {STEPS.map((step, i) => (
            <div key={step.label} className="flex items-start flex-1 min-w-0">
              <div className="flex flex-col items-center gap-2 flex-1 min-w-0">
                <span className="flex items-center justify-center w-14 h-14 rounded-full border border-electric/40 bg-electric/10 text-electric shrink-0">
                  <Icon name={step.icon} size={22} />
                </span>
                <span className="text-sm font-semibold text-[var(--color-text-inv)] text-center leading-tight">
                  {step.label}
                </span>
                <span className="text-xs text-[var(--color-text-inv-mute)] text-center leading-snug whitespace-pre-line">
                  {step.desc}
                </span>
              </div>
              {i < STEPS.length - 1 && (
                <span className="flex items-center text-[var(--color-text-inv-mute)] shrink-0 px-1 mt-6">
                  <Icon name="arrow-right" size={18} />
                </span>
              )}
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}

export default memo(CheckerProcessFlow);
