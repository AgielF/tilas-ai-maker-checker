import { memo } from 'react';
import Icon from '../atoms/Icon';

const STEPS = [
  { icon: 'file-text',   label: 'Upload',        desc: 'PDF / Excel' },
  { icon: 'shield',      label: 'Ekstraksi AI',  desc: 'LLM baca dokumen' },
  { icon: 'search',      label: 'Cari Harga',    desc: 'Serper marketplace' },
  { icon: 'dollar-sign', label: 'Analisis',      desc: 'Bandingkan harga' },
  { icon: 'check',       label: 'Rekomendasi',   desc: 'Hasil + sitasi' },
];

function MakerProcessFlow() {
  return (
    <section className="border border-[var(--border-dark)] bg-surface p-5">
      <div className="flex flex-col gap-4">
        <span className="text-xs text-[var(--color-text-inv-mute)] uppercase tracking-wider">
          Alur Proses Maker
        </span>
        <div className="flex items-center justify-between w-full gap-2">
          {STEPS.map((step, i) => (
            <div key={step.label} className="flex items-center flex-1 min-w-0">
              <div className="flex flex-col items-center gap-2 flex-1 min-w-0">
                <span className="flex items-center justify-center w-14 h-14 rounded-full border border-electric/40 bg-electric/10 text-electric shrink-0">
                  <Icon name={step.icon} size={22} />
                </span>
                <span className="text-sm font-semibold text-[var(--color-text-inv)] text-center leading-tight">
                  {step.label}
                </span>
                <span className="text-xs text-[var(--color-text-inv-mute)] text-center leading-tight">
                  {step.desc}
                </span>
              </div>
              {i < STEPS.length - 1 && (
                <span className="flex items-center text-[var(--color-text-inv-mute)] shrink-0 px-1">
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

export default memo(MakerProcessFlow);
