import { useEffect, useCallback } from 'react';
import { useLocation, useSearchParams } from 'react-router-dom';
import WorkbenchTemplate from '../components/templates/WorkbenchTemplate';
import NavBar from '../components/organisms/NavBar';
import FindingList from '../components/organisms/FindingList';
import Button from '../components/atoms/Button';
import Badge from '../components/atoms/Badge';
import Icon from '../components/atoms/Icon';
import { useRiskReport } from '../hooks/useApi';
import { SAMPLE_TRANSACTION_ID, SAMPLE_DOCS } from '../lib/constants';

const DEFAULT_RECOMMENDATIONS = [
  'Investigasi approval untuk selisih harga',
  'Konfirmasi ke vendor mengenai kuantitas',
  'Flag vendor untuk review berkala',
];

const SEV_COLORS = { critical: 'bg-sev-critical', high: 'bg-sev-high', medium: 'bg-sev-medium', low: 'bg-sev-low' };
const SEV_TEXT   = { critical: 'text-sev-critical', high: 'text-sev-high', medium: 'text-sev-medium', low: 'text-sev-low' };

// Backend returns severity as uppercase — map to lowercase for SeverityBadge + RiskGauge
const SEV_SCORE_MAP = { CRITICAL: 90, HIGH: 72, MEDIUM: 45, LOW: 20, WARN: 55 };

const fmtTs = (iso) => {
  try { return new Date(iso).toLocaleString('id-ID', { dateStyle: 'medium', timeStyle: 'short' }); }
  catch { return iso; }
};

// Map API finding shape → FindingList shape
// Preserve the audit evidence fields and fraud indication for FindingList.
function mapFinding(f) {
  return {
    id:             f.id,
    transaction_id: f.po_number ?? f.transaction_id,
    severity:       (f.severity ?? '').toLowerCase(),
    message:        f.description ?? f.sop_reference ?? '—',
    indication_label: f.indication_label ?? 'UNKNOWN',
    evidence_url: f.evidence_url ?? null,
    sop_clause_citation: f.sop_clause_citation ?? null,
    evidence_type: f.evidence_type ?? '',
    created_at:     f.created_at,
  };
}

// Derive breakdown counts from findings array
function deriveBreakdown(findings) {
  const counts = { critical: 0, high: 0, medium: 0, low: 0 };
  for (const f of findings ?? []) {
    const key = (f.severity ?? '').toLowerCase();
    if (key in counts) counts[key]++;
  }
  return counts;
}

function RiskGauge({ severity }) {
  const score = SEV_SCORE_MAP[(severity ?? '').toUpperCase()] ?? 50;
  const pct   = Math.min(100, Math.max(0, score));
  const color = pct >= 70 ? 'bg-sev-high' : pct >= 40 ? 'bg-sev-medium' : 'bg-sev-low';
  return (
    <div className="border border-[var(--border-dark)] bg-surface p-6 flex flex-col gap-3">
      <span className="text-xs font-semibold uppercase tracking-wider text-[var(--color-text-inv-mute)]">Risk Score</span>
      <div className="flex items-end gap-3">
        <span className="font-mono tabular-nums text-5xl font-black text-[var(--color-text-inv)]">{score}</span>
        <span className="text-[var(--color-text-inv-mute)] text-sm pb-1">/ 100</span>
      </div>
      <div className="h-2 w-full bg-surface-2 rounded-full overflow-hidden">
        <div className={`h-full rounded-full ${color}`} style={{ width: `${pct}%` }} />
      </div>
    </div>
  );
}

function SeverityBreakdown({ counts }) {
  const total = Object.values(counts).reduce((s, v) => s + v, 0) || 1;
  return (
    <div className="border border-[var(--border-dark)] bg-surface p-6 flex flex-col gap-4">
      <span className="text-xs font-semibold uppercase tracking-wider text-[var(--color-text-inv-mute)]">Severity Breakdown</span>
      {Object.entries(counts).map(([sev, count]) => (
        <div key={sev} className="flex items-center gap-3">
          <span className={`w-16 text-xs font-semibold uppercase ${SEV_TEXT[sev] ?? 'text-[var(--color-text-inv-mute)]'}`}>{sev}</span>
          <div className="flex-1 h-2 bg-surface-2 rounded-full overflow-hidden">
            <div className={`h-full rounded-full ${SEV_COLORS[sev] ?? 'bg-electric'}`} style={{ width: `${(count / total) * 100}%` }} />
          </div>
          <span className="w-4 text-right text-xs font-mono tabular-nums text-[var(--color-text-inv-mute)]">{count}</span>
        </div>
      ))}
    </div>
  );
}

function StatusBadge({ status }) {
  const map = {
    PASS: { variant: 'success', label: 'PASS' },
    WARN: { variant: 'warning', label: 'WARN' },
    FAIL: { variant: 'critical', label: 'FAIL' },
  };
  const { variant, label } = map[(status ?? '').toUpperCase()] ?? { variant: 'muted', label: status ?? '—' };
  return <Badge variant={variant}>{label}</Badge>;
}

function ExecutiveSummaryCard({ summary }) {
  if (!summary?.trim()) return null;

  return (
    <section className="border-l-4 border-electric bg-surface/30 p-6">
      <div className="mb-3 flex items-center gap-2 text-electric">
        <Icon name="alert-triangle" size={18} />
        <h3 className="text-xs font-semibold uppercase tracking-wider">
          Ringkasan Eksekutif
        </h3>
      </div>
      <p className="text-base leading-relaxed text-[var(--color-text-inv)]">{summary}</p>
    </section>
  );
}

function PatternAnalysisSection({ patterns = [] }) {
  if (!patterns.length) return null;

  return (
    <section className="flex flex-col gap-3 border border-[var(--border-dark)] bg-surface p-6">
      <h3 className="text-xs font-semibold uppercase tracking-wider text-[var(--color-text-inv-mute)]">
        Pola Terdeteksi
      </h3>
      <ul className="flex flex-col gap-3">
        {patterns.map((pattern, index) => (
          <li key={`${pattern}-${index}`} className="flex items-start gap-3 text-sm leading-relaxed text-[var(--color-text-inv)]">
            <span className="mt-2 h-1.5 w-1.5 shrink-0 rounded-full bg-electric" aria-hidden="true" />
            <span>{pattern}</span>
          </li>
        ))}
      </ul>
    </section>
  );
}

export default function RiskReportPage() {
  const [searchParams] = useSearchParams();
  const location = useLocation();
  const txId = searchParams.get('tx') ?? SAMPLE_TRANSACTION_ID;
  const { data, error, loading, run } = useRiskReport();
  const uploadedReport = location.state?.reportData ?? null;
  const reportDocs = location.state?.docs ?? SAMPLE_DOCS;
  const reportHasL2 = location.state?.hasL2 ?? false;
  const reportHasDocs = location.state?.hasDocs ?? true;

  const doRun = useCallback(() => {
    run(txId, {
      ...reportDocs,
      has_level2_approval: reportHasL2,
      has_complete_docs: reportHasDocs,
    }).catch(() => {});
  }, [reportDocs, reportHasDocs, reportHasL2, run, txId]);

  // Auto-run on mount + when txId changes
  useEffect(() => {
    if (!uploadedReport) doRun();
  }, [doRun, uploadedReport]);

  const report = uploadedReport ?? data;
  const findings   = (report?.findings ?? []).map(mapFinding);
  const breakdown  = deriveBreakdown(report?.findings);
  const reportTime = report?.findings?.[0]?.created_at ?? '';
  const narrativeRecommendations = report?.narrative?.dynamic_recommendations;
  const recommendedActions = Array.isArray(narrativeRecommendations)
    && narrativeRecommendations.some((action) => action?.trim())
    ? narrativeRecommendations.filter((action) => action?.trim())
    : DEFAULT_RECOMMENDATIONS;

  return (
    <WorkbenchTemplate
      navbar={<NavBar activePath="/checker/risk-report" />}
      header={
        <div className="flex items-start justify-between gap-4 border-b border-[var(--border-light)] pb-6 mb-8">
          <div className="flex flex-col gap-1">
            <h2 className="text-3xl md:text-4xl font-semibold tracking-tight text-[var(--color-text-inv)]">
              Risk Report
            </h2>
            <p className="text-sm text-[var(--color-text-inv-mute)]">
              Transaction: <span className="font-mono">{txId}</span>
              {report && <><span className="mx-2">·</span>{fmtTs(reportTime)}</>}
            </p>
          </div>
          <div className="flex items-center gap-2 shrink-0 mt-1">
            {report && <StatusBadge status={report.overall_status} />}
          </div>
        </div>
      }
      inputZone={null}
      resultZone={
        loading ? (
          <div className="flex items-center justify-center gap-3 py-16 text-[var(--color-text-inv-mute)]">
            <span className="inline-block w-5 h-5 rounded-full border-2 border-electric border-r-transparent animate-spin" />
            <span className="text-sm">Membuat laporan risiko…</span>
          </div>
        ) : error ? (
          <div className="flex items-start gap-3 border border-sev-critical/30 bg-sev-critical/5 px-4 py-4">
            <span className="text-sev-critical shrink-0 mt-0.5"><Icon name="x-circle" size={16} /></span>
            <div className="flex flex-col gap-2">
              <p className="text-sm text-sev-critical">{String(error)}</p>
              <Button variant="ghost" size="sm" className="self-start" onClick={doRun}>
                Retry
              </Button>
            </div>
          </div>
        ) : report ? (
          <div className="flex flex-col gap-6">
            {/* Row 1: Gauge + Breakdown */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <RiskGauge severity={report.severity} />
              <SeverityBreakdown counts={breakdown} />
            </div>

            {/* Row 2: Summary */}
            {report.recommendation && (
              <div className="border border-amber/30 bg-amber/10 px-5 py-4">
                <p className="text-sm font-semibold text-amber">{report.recommendation}</p>
              </div>
            )}

            <ExecutiveSummaryCard summary={report.narrative?.executive_summary} />

            <PatternAnalysisSection patterns={report.narrative?.pattern_analysis} />

            {/* Findings */}
            <section className="flex flex-col gap-3">
              <h3 className="text-sm font-semibold uppercase tracking-wider text-[var(--color-text-inv-mute)]">
                Temuan
              </h3>
              <FindingList items={findings} />
            </section>

            {/* Recommended Actions */}
            <section className="flex flex-col gap-3 border border-[var(--border-dark)] bg-surface p-6">
              <h3 className="text-sm font-semibold uppercase tracking-wider text-[var(--color-text-inv-mute)]">
                Recommended Actions
              </h3>
              <ul className="flex flex-col gap-2">
                {recommendedActions.map((action, index) => (
                  <li key={`${action}-${index}`} className="flex items-start gap-2 text-sm text-[var(--color-text-inv)]">
                    <span className="text-electric mt-0.5 shrink-0">→</span>
                    {action}
                  </li>
                ))}
              </ul>
            </section>
          </div>
        ) : null
      }
    />
  );
}
