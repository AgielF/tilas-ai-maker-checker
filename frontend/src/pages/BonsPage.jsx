import { useState, useCallback, useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import WorkbenchTemplate from '../components/templates/WorkbenchTemplate';
import NavBar from '../components/organisms/NavBar';
import PageHeader from '../components/organisms/PageHeader';
import FileUploader from '../components/molecules/FileUploader';
import TabSwitch from '../components/molecules/TabSwitch';
import Button from '../components/atoms/Button';
import Table from '../components/atoms/Table';
import Badge from '../components/atoms/Badge';
import EmptyState from '../components/molecules/EmptyState';
import { useParseBons, useListDocuments } from '../hooks/useApi';

const DIVISIONS = ['PPIC', 'PURCHASING', 'PACKING', 'PACK', 'SAMPLE', 'OFFICE'];

function DivisionBadge({ division }) {
  if (!division) return <span className="text-[var(--color-text-inv-mute)]">—</span>;
  const colors = {
    PPIC: 'bg-cyan-500/20 text-cyan-400 border border-cyan-500/40',
    PURCHASING: 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/40',
    PACKING: 'bg-amber-500/20 text-amber-400 border border-amber-500/40',
    PACK: 'bg-amber-500/20 text-amber-400 border border-amber-500/40',
    SAMPLE: 'bg-fuchsia-500/20 text-fuchsia-400 border border-fuchsia-500/40',
    OFFICE: 'bg-slate-500/20 text-slate-400 border border-slate-500/40',
  };
  const style = colors[division] || 'bg-electric/20 text-electric border border-electric/40';
  return (
    <span className={`text-xs px-2 py-0.5 rounded-full font-medium border ${style}`}>
      {division}
    </span>
  );
}

function DocumentRow({ doc, onClick }) {
  // Debug: log the doc structure
  if (process.env.NODE_ENV === 'development') {
    console.log('DocumentRow doc:', doc);
  }
  
  return (
    <tr
      onClick={() => onClick(doc.id)}
      className="cursor-pointer border-b border-[var(--border-dark)] last:border-0 hover:bg-surface/50 transition-colors"
    >
      <td className="px-4 py-3 font-mono tabular-nums text-[var(--color-text-inv)]">
        {doc.doc_number || doc.docNumber || doc.bon_number || doc.bonNumber || '—'}
      </td>
      <td className="px-4 py-3 text-[var(--color-text-inv)]">
        {doc.doc_date || doc.docDate ? new Date(doc.doc_date || doc.docDate).toLocaleDateString('id-ID', {
          day: '2-digit',
          month: '2-digit',
          year: 'numeric',
          hour: '2-digit',
          minute: '2-digit',
        }) : '—'}
      </td>
      <td className="px-4 py-3">
        <DivisionBadge division={doc.division} />
      </td>
      <td className="px-4 py-3 font-mono tabular-nums text-right text-[var(--color-text-inv)]">
        {doc.item_count || doc.itemCount || doc.items?.length || 0}
      </td>
      <td className="px-4 py-3 text-[var(--color-text-inv-mute)] truncate max-w-xs">
        {doc.source_file || doc.sourceFile || '—'}
      </td>
    </tr>
  );
}

export default function BonsPage() {
  const navigate = useNavigate();
  const [activeTab, setActiveTab] = useState('upload');
  const [selectedFile, setSelectedFile] = useState(null);
  const [fileError, setFileError] = useState('');
  const [divisionFilter, setDivisionFilter] = useState('');

  const { loading: parseLoading, error: parseError, submit: submitParse } = useParseBons();
  const listParams = useMemo(
    () => (divisionFilter ? { division: divisionFilter } : {}),
    [divisionFilter]
  )
  const { data: documents, loading: listLoading, error: listError, refetch: refetchList } = useListDocuments(
    listParams
  );

  const handleFileSelect = useCallback((file) => {
    setSelectedFile(file);
    setFileError('');
  }, []);

  const handleFileRemove = useCallback(() => {
    setSelectedFile(null);
  }, []);

  const handleFileError = useCallback((error) => {
    setFileError(error);
  }, []);

  const handleParse = useCallback(async () => {
    if (!selectedFile) {
      setFileError('Silakan pilih file Excel terlebih dahulu.');
      return;
    }
    try {
      await submitParse(selectedFile);
      // On success, switch to Archive tab and refetch list
      setActiveTab('archive');
      setSelectedFile(null);
      refetchList();
    } catch {
      // Error is handled by hook
    }
  }, [selectedFile, submitParse, refetchList]);

  const handleRowClick = useCallback((docId) => {
    navigate(`/bons/${docId}`);
  }, [navigate]);

  const handleDivisionChange = useCallback((division) => {
    setDivisionFilter(division === '' ? '' : division);
  }, []);

  // On initial mount, fetch the document list
  // (useListDocuments already fetches on mount with default params)

  return (
    <WorkbenchTemplate
      navbar={<NavBar activePath="/bons" />}
      header={
        <PageHeader
          title="Bon Permintaan"
          subtitle="Upload Excel Bon Permintaan atau lihat arsip dokumen"
          badge={{ label: 'Parser', variant: 'electric' }}
        />
      }
      inputZone={
        <div className="flex flex-col gap-4">
          <TabSwitch
            tabs={[
              { id: 'upload', label: 'Upload Baru' },
              { id: 'archive', label: 'Arsip' },
            ]}
            activeId={activeTab}
            onChange={setActiveTab}
          />
          <div
            id={`bons-panel-${activeTab}`}
            role="tabpanel"
            aria-labelledby={`bons-tab-${activeTab}`}
          >
            {activeTab === 'upload' ? (
              <UploadTab
                selectedFile={selectedFile}
                onFileSelect={handleFileSelect}
                onFileRemove={handleFileRemove}
                onFileError={handleFileError}
                fileError={fileError}
                loading={parseLoading}
                error={parseError}
                onParse={handleParse}
                disabled={parseLoading}
              />
            ) : (
              <ArchiveTab
                documents={documents}
                loading={listLoading}
                error={listError}
                divisionFilter={divisionFilter}
                onDivisionChange={handleDivisionChange}
                onRowClick={handleRowClick}
              />
            )}
          </div>
        </div>
      }
    />
  );
}

// ── Tab: Upload Baru ─────────────────────────────────────────────────────────

function UploadTab({
  selectedFile,
  onFileSelect,
  onFileRemove,
  onFileError,
  fileError,
  loading,
  error,
  onParse,
  disabled,
}) {
  return (
    <div className="flex flex-col gap-4 max-w-2xl">
      <div className="rounded-md border border-[var(--border-dark)] bg-surface p-6">
        <p className="text-sm text-[var(--color-text-inv-mute)] mb-4">
          Unggah file Excel (.xlsx, .xls) Bon Permintaan. File akan diparse dan
          disimpan ke arsip otomatis.
        </p>
        <FileUploader
          file={selectedFile}
          onFile={onFileSelect}
          onRemove={onFileRemove}
          onError={onFileError}
          disabled={disabled}
          error={fileError || error}
          accept=".xlsx,.xls,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet,application/vnd.ms-excel"
          acceptExtensions={[".xlsx", ".xls"]}
          acceptLabel="Excel"
          dropzoneText="Drag & drop Excel atau klik untuk pilih"
          sizeText="Excel (.xlsx, .xls) · maks. 10 MB"
          errorInvalidFormat="File harus berformat Excel (.xlsx, .xls)."
        />
      </div>

      <div className="flex justify-end">
        <Button
          variant="primary"
          size="lg"
          onClick={onParse}
          disabled={disabled || !selectedFile}
        >
          {loading ? (
            <>
              <span className="inline-block w-4 h-4 rounded-full border-2 border-white/50 border-r-transparent animate-spin mr-2" />
              Memproses…
            </>
          ) : (
            'Parse & Simpan'
          )}
        </Button>
      </div>

      {error && (
        <div className="flex items-start gap-3 border border-sev-critical/30 bg-sev-critical/5 px-4 py-4 text-sev-critical">
          <span className="text-sm">{String(error)}</span>
        </div>
      )}
    </div>
  );
}

// ── Tab: Archive ──────────────────────────────────────────────────────────────

function ArchiveTab({
  documents,
  loading,
  error,
  divisionFilter,
  onDivisionChange,
  onRowClick,
}) {
  if (loading) {
    return (
      <div className="flex items-center justify-center gap-3 py-12 text-[var(--color-text-inv-mute)]">
        <span className="inline-block w-5 h-5 rounded-full border-2 border-electric border-r-transparent animate-spin" />
        <span className="text-sm">Memuat arsip…</span>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex items-start gap-3 border border-sev-critical/30 bg-sev-critical/5 px-4 py-4 text-sev-critical">
        <span className="text-sm">{String(error)}</span>
      </div>
    );
  }

  if (!documents || documents.length === 0) {
    return (
      <EmptyState
        label="Belum ada dokumen"
        description={divisionFilter
          ? `Tidak ada BON untuk division "${divisionFilter}".`
          : 'Upload file Excel di tab "Upload Baru" untuk memulai.'}
      />
    );
  }

  return (
    <div className="flex flex-col gap-4">
      {/* Filter Division */}
      <div className="flex flex-wrap items-center gap-3">
        <span className="text-sm text-[var(--color-text-inv-mute)] shrink-0">Filter Division:</span>
        <div className="flex flex-wrap gap-2">
          <button
            onClick={() => onDivisionChange('')}
            className={`px-3 py-1.5 rounded-full text-sm font-medium transition-colors ${
              !divisionFilter
                ? 'bg-electric text-white'
                : 'border border-[var(--border-dark)] text-[var(--color-text-inv-mute)] hover:border-electric hover:text-electric'
            }`}
          >
            Semua
          </button>
          {DIVISIONS.map((d) => (
            <button
              key={d}
              onClick={() => onDivisionChange(d)}
              className={`px-3 py-1.5 rounded-full text-sm font-medium transition-colors ${
                divisionFilter === d
                  ? 'bg-electric text-white'
                  : 'border border-[var(--border-dark)] text-[var(--color-text-inv-mute)] hover:border-electric hover:text-electric'
              }`}
            >
              {d}
            </button>
          ))}
        </div>
      </div>

      {/* Table */}
      <div className="rounded-md border border-[var(--border-dark)] overflow-hidden">
        <Table className="bg-canvas">
          <thead>
            <tr className="border-b border-[var(--border-dark)] bg-surface/80">
              {['BON#', 'Tanggal', 'Division', 'Items', 'File'].map((h) => (
                <th
                  key={h}
                  className={`${h === 'BON#' ? 'text-left' : 'text-right'} px-4 py-3 text-xs font-semibold uppercase tracking-wider text-[var(--color-text-inv)]`}
                >
                  {h}
                </th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-[var(--border-dark)]">
            {documents.map((doc) => (
              <DocumentRow key={doc.id} doc={doc} onClick={onRowClick} />
            ))}
          </tbody>
        </Table>
      </div>
    </div>
  );
}