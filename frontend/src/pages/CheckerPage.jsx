import { useState, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import WorkbenchTemplate from '../components/templates/WorkbenchTemplate';
import NavBar from '../components/organisms/NavBar';
import PageHeader from '../components/organisms/PageHeader';
import MatchGrid from '../components/organisms/MatchGrid';
import CheckerInputForm from '../components/organisms/CheckerInputForm';
import CheckerUploadPanel from '../components/organisms/CheckerUploadPanel';
import TabSwitch from '../components/molecules/TabSwitch';
import Button from '../components/atoms/Button';
import Icon from '../components/atoms/Icon';
import { useMatchThreeWay, useRiskReportFromFiles } from '../hooks/useApi';
import { SAMPLE_TRANSACTION_ID, SAMPLE_DOCS } from '../lib/constants';

const formatMoney = (amount, currency = 'IDR') => new Intl.NumberFormat('id-ID', {
  style: 'currency',
  currency,
  maximumFractionDigits: 0,
}).format(amount);

function cloneSampleDocs() {
  return {
    po: { ...SAMPLE_DOCS.po },
    gr: { ...SAMPLE_DOCS.gr },
    invoice: { ...SAMPLE_DOCS.invoice },
  };
}

function normalizeDocument(document) {
  const normalized = {
    ...document,
    quantity: Number(document.quantity || 0),
    amount: Number(document.amount || 0),
  };

  for (const field of ['dpp_amount', 'ppn_amount']) {
    normalized[field] = document[field] === '' || document[field] == null
      ? null
      : Number(document[field]);
  }

  return normalized;
}

function normalizeDocs(docs) {
  return {
    po: normalizeDocument(docs.po),
    gr: normalizeDocument(docs.gr),
    invoice: normalizeDocument(docs.invoice),
  };
}

function VerdictBanner({ matched, discrepancies }) {
  if (matched) {
    return (
      <div className="flex items-center gap-3 px-4 py-3 border border-emerald/30 bg-emerald/10">
        <span className="text-emerald shrink-0"><Icon name="check" size={16} /></span>
        <span className="text-sm font-semibold uppercase tracking-wider text-emerald">Matched</span>
      </div>
    );
  }
  return (
    <div className="flex flex-col gap-2 px-4 py-3 border border-amber/30 bg-amber/10">
      <div className="flex items-center gap-3">
        <span className="text-amber shrink-0"><Icon name="alert-triangle" size={16} /></span>
        <span className="text-sm font-semibold uppercase tracking-wider text-amber">Discrepancy</span>
      </div>
      {discrepancies?.length > 0 && (
        <ul className="flex flex-col gap-1 pl-7">
          {discrepancies.map((d, i) => (
            <li key={i} className="text-sm text-[var(--color-text-inv-mute)]">· {d}</li>
          ))}
        </ul>
      )}
    </div>
  );
}

function DeltaTable({ po, gr, invoice }) {
  const currency = po?.currency ?? 'IDR';
  const delta = po != null && invoice != null ? invoice - po : null;
  return (
    <div className="border border-[var(--border-dark)] overflow-hidden">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-[var(--border-dark)] bg-surface">
            {['Field', 'PO', 'GR', 'Invoice', 'Delta'].map((h) => (
              <th key={h} className={`${h === 'Field' ? 'text-left' : 'text-right'} px-4 py-2 text-xs font-medium uppercase tracking-wider text-[var(--color-text-inv-mute)]`}>{h}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          <tr className="border-b border-[var(--border-dark)] last:border-0 bg-amber/5">
            <td className="px-4 py-2 font-medium text-amber uppercase text-xs tracking-wider">DPP</td>
            <td className="px-4 py-2 text-right font-mono tabular-nums text-[var(--color-text-inv)]">{po != null ? formatMoney(po, currency) : '—'}</td>
            <td className="px-4 py-2 text-right font-mono tabular-nums text-[var(--color-text-inv-mute)]">{gr != null ? formatMoney(gr, currency) : '—'}</td>
            <td className="px-4 py-2 text-right font-mono tabular-nums text-amber">{invoice != null ? formatMoney(invoice, currency) : '—'}</td>
            <td className="px-4 py-2 text-right font-mono tabular-nums text-sev-high">{delta != null ? (delta >= 0 ? '+' : '') + formatMoney(delta, currency) : '—'}</td>
          </tr>
        </tbody>
      </table>
    </div>
  );
}

export default function CheckerPage() {
  const [txId, setTxId] = useState(SAMPLE_TRANSACTION_ID);
  const [activeTab, setActiveTab] = useState('upload');
  const [docs, setDocs] = useState(cloneSampleDocs);
  const [hasL2, setHasL2] = useState(false);
  const [hasDocs, setHasDocs] = useState(true);
  const navigate = useNavigate();
  const {
    data,
    error,
    loading: matchLoading,
    run,
    reset: resetMatch,
  } = useMatchThreeWay();
  const {
    loading: uploadLoading,
    error: uploadError,
    submit: submitFiles,
    reset: resetUpload,
  } = useRiskReportFromFiles();
  const loading = matchLoading || uploadLoading;

  const handleRun = useCallback(() => {
    run(txId.trim() || SAMPLE_TRANSACTION_ID, normalizeDocs(docs)).catch(() => {});
  }, [docs, run, txId]);

  const resetSamples = useCallback(() => {
    setDocs(cloneSampleDocs());
    setHasL2(false);
    setHasDocs(true);
  }, []);

  const handleTabChange = useCallback((nextTab) => {
    setActiveTab(nextTab);
    resetMatch();
    resetUpload();
  }, [resetMatch, resetUpload]);

  const handleUploadSubmit = useCallback(async (files, options) => {
    try {
      const report = await submitFiles(
        txId.trim() || SAMPLE_TRANSACTION_ID,
        files,
        options,
      );
      if (report) {
        navigate(
          `/checker/risk-report?tx=${encodeURIComponent(txId.trim() || SAMPLE_TRANSACTION_ID)}`,
          { state: { reportData: report } },
        );
      }
    } catch {
      // The upload hook stores and exposes the error for the panel.
    }
  }, [navigate, submitFiles, txId]);

  const activeTx = txId.trim() || SAMPLE_TRANSACTION_ID;
  const displayedDocs = {
    po: docs.po,
    gr: docs.gr,
    invoice: docs.invoice,
  };
  const differences = (data?.discrepancies ?? []).map((discrepancy) => {
    if (/quantity/i.test(discrepancy)) return 'quantity';
    if (/dpp/i.test(discrepancy)) return 'dpp_amount';
    if (/amount/i.test(discrepancy)) return 'amount';
    return null;
  }).filter(Boolean);

  return (
    <WorkbenchTemplate
      navbar={<NavBar activePath="/checker" />}
      header={<PageHeader title="Checker Agent" />}
      inputZone={
        <div className="flex flex-col gap-4">
          <label className="flex flex-col gap-1 text-sm font-medium text-[var(--color-text-inv-mute)]">
            Transaction ID
            <input
              type="text"
              value={txId}
              onChange={(e) => setTxId(e.target.value)}
              placeholder="Masukkan transaction ID…"
              className="w-full rounded-md border border-[var(--border-dark)] bg-surface px-4 py-2 text-sm text-ink placeholder:text-[var(--color-text-mute)] focus:outline-none focus:ring-2 focus:ring-electric/50"
            />
          </label>
          <TabSwitch
            tabs={[
              { id: 'upload', label: 'Upload PDF/Excel' },
              { id: 'manual', label: 'Input Manual' },
            ]}
            activeId={activeTab}
            onChange={handleTabChange}
          />
          <div
            id={`checker-panel-${activeTab}`}
            role="tabpanel"
            aria-labelledby={`checker-tab-${activeTab}`}
          >
            {activeTab === 'upload' ? (
              <CheckerUploadPanel
                onSubmit={handleUploadSubmit}
                loading={uploadLoading}
                error={uploadError}
              />
            ) : (
              <CheckerInputForm
                value={docs}
                onChange={setDocs}
                onSubmit={handleRun}
                loading={matchLoading}
                hasL2={hasL2}
                hasDocs={hasDocs}
                onHasL2Change={setHasL2}
                onHasDocsChange={setHasDocs}
                onReset={resetSamples}
              />
            )}
          </div>
        </div>
      }
      resultZone={
        loading ? (
          <div className="flex items-center justify-center gap-3 py-12 text-[var(--color-text-inv-mute)]">
            <span className="inline-block w-5 h-5 rounded-full border-2 border-electric border-r-transparent animate-spin" />
            <span className="text-sm">Menjalankan checker…</span>
          </div>
        ) : error ? (
          <div className="flex items-start gap-3 border border-sev-critical/30 bg-sev-critical/5 px-4 py-4">
            <span className="text-sev-critical shrink-0 mt-0.5"><Icon name="x-circle" size={16} /></span>
            <div className="flex flex-col gap-2">
              <p className="text-sm text-sev-critical">{String(error)}</p>
              <Button variant="ghost" size="sm" className="self-start" onClick={handleRun}>
                Retry
              </Button>
            </div>
          </div>
        ) : data ? (
          <div className="flex flex-col gap-4">
            <VerdictBanner matched={data.matched} discrepancies={data.discrepancies} />
            <MatchGrid
              po={displayedDocs.po}
              gr={displayedDocs.gr}
              invoice={displayedDocs.invoice}
              differences={data.matched ? [] : differences}
              status={data.matched ? 'matched' : 'discrepancy'}
            />
            <DeltaTable
              po={docs.po.amount}
              gr={docs.gr.amount}
              invoice={docs.invoice.dpp_amount || docs.invoice.amount}
            />
            <div className="flex justify-end pt-2">
              <Button
                variant="primary"
                size="lg"
                onClick={() => navigate(
                  `/checker/risk-report?tx=${encodeURIComponent(activeTx)}`,
                  { state: { docs: normalizeDocs(docs), hasL2, hasDocs } },
                )}
              >
                Generate Risk Report
              </Button>
            </div>
          </div>
        ) : null
      }
    />
  );
}
