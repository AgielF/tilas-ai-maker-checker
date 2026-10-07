import { memo, useState } from 'react';
import Button from '../atoms/Button';
import FileUploader from '../molecules/FileUploader';

const DOCUMENTS = [
  { key: 'poFile', title: 'Purchase Order', required: true },
  { key: 'grFile', title: 'Goods Receipt', required: true },
  { key: 'invoiceFile', title: 'Invoice', required: true },
  { key: 'taxInvoiceFile', title: 'Faktur Pajak', required: false },
];

const FILE_UPLOADER_PROPS = {
  accept: ".pdf,.xlsx,.xls,application/pdf,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet,application/vnd.ms-excel",
  acceptExtensions: [".pdf", ".xlsx", ".xls"],
  acceptLabel: "PDF atau Excel",
  dropzoneText: "Drag & drop PDF atau Excel atau klik untuk pilih",
  sizeText: "PDF atau Excel · maks. 10 MB",
  errorInvalidFormat: "File harus berformat PDF atau Excel.",
};

function DocumentUploadGroup({ title, required, file, error, onFile, onRemove, onError, disabled }) {
  return (
    <section className="flex flex-col gap-3 border border-[var(--border-dark)] bg-surface p-4">
      <div className="flex items-center justify-between gap-2">
        <h3 className="text-sm font-semibold uppercase tracking-wider text-ink">{title}</h3>
        <span className={[
          'text-[10px] font-semibold uppercase tracking-wider',
          required ? 'text-sev-high' : 'text-[var(--color-text-mute)]',
        ].join(' ')}>
          {required ? 'Wajib (PDF/Excel)' : 'Opsional (PDF/Excel)'}
        </span>
      </div>
      <FileUploader
        file={file}
        onFile={onFile}
        onRemove={onRemove}
        onError={onError}
        disabled={disabled}
        error={error}
        {...FILE_UPLOADER_PROPS}
      />
    </section>
  );
}

function CheckerUploadPanel({ onSubmit, loading = false, error: submitError = null }) {
  const [poFile, setPoFile] = useState(null);
  const [grFile, setGrFile] = useState(null);
  const [invoiceFile, setInvoiceFile] = useState(null);
  const [taxInvoiceFile, setTaxInvoiceFile] = useState(null);
  const [fileErrors, setFileErrors] = useState({});
  const [hasL2, setHasL2] = useState(false);
  const [hasDocs, setHasDocs] = useState(true);
  const fileValues = { poFile, grFile, invoiceFile, taxInvoiceFile };
  const fileSetters = {
    poFile: setPoFile,
    grFile: setGrFile,
    invoiceFile: setInvoiceFile,
    taxInvoiceFile: setTaxInvoiceFile,
  };
  const hasRequiredFiles = Boolean(poFile && grFile && invoiceFile);

  const setFile = (key, file) => {
    fileSetters[key](file);
    setFileErrors((current) => ({ ...current, [key]: '' }));
  };

  const removeFile = (key) => {
    fileSetters[key](null);
    setFileErrors((current) => ({ ...current, [key]: '' }));
  };

  const setFileError = (key, message) => {
    setFileErrors((current) => ({ ...current, [key]: message }));
  };

  const submit = (event) => {
    event.preventDefault();
    if (!hasRequiredFiles || loading) return;
    onSubmit(
      { poFile, grFile, invoiceFile, taxInvoiceFile },
      { hasLevel2Approval: hasL2, hasCompleteDocs: hasDocs },
    );
  };

  return (
    <form onSubmit={submit} className="flex flex-col gap-5 border border-[var(--border-dark)] bg-surface p-5">
      <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
        {DOCUMENTS.map(({ key, title, required }) => (
          <DocumentUploadGroup
            key={key}
            title={title}
            required={required}
            file={fileValues[key]}
            error={fileErrors[key]}
            onFile={(file) => setFile(key, file)}
            onRemove={() => removeFile(key)}
            onError={(message) => setFileError(key, message)}
            disabled={loading}
          />
        ))}
      </div>

      <div className="flex flex-col gap-3 sm:flex-row sm:flex-wrap sm:items-center">
        <label className="flex cursor-pointer items-center gap-2 text-sm text-[var(--color-text-inv)]">
          <input
            type="checkbox"
            checked={hasL2}
            onChange={(event) => setHasL2(event.target.checked)}
            disabled={loading}
            className="h-4 w-4 accent-electric"
          />
          Has Level 2 Approval
        </label>
        <label className="flex cursor-pointer items-center gap-2 text-sm text-[var(--color-text-inv)]">
          <input
            type="checkbox"
            checked={hasDocs}
            onChange={(event) => setHasDocs(event.target.checked)}
            disabled={loading}
            className="h-4 w-4 accent-electric"
          />
          Has Complete Docs
        </label>
        <Button
          type="submit"
          variant="primary"
          size="md"
          loading={loading}
          disabled={!hasRequiredFiles || loading}
          className="sm:ml-auto"
        >
          Run 4-Way Checker
        </Button>
      </div>

      {!hasRequiredFiles && (
        <p className="text-xs text-[var(--color-text-inv-mute)]">
          Unggah PO, Goods Receipt, dan Invoice (PDF atau Excel) untuk melanjutkan. Faktur Pajak bersifat opsional.
        </p>
      )}
      {submitError && (
        <p role="alert" className="border border-sev-critical/30 bg-sev-critical/5 px-4 py-3 text-sm text-sev-critical">
          {submitError.message ?? String(submitError)}
        </p>
      )}
    </form>
  );
}

export default memo(CheckerUploadPanel);
