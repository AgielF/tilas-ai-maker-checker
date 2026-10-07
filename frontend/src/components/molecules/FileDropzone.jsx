import { memo, useRef, useState, useCallback } from 'react';
import Icon from '../atoms/Icon';

/**
 * FileDropzone — drag-and-drop / click-to-pick file input.
 * Props:
 *   onFile              {(File) => void}     called when a valid file is picked
 *   onError             {(string) => void}   called when validation fails
 *   accept              {string}             MIME types (default 'application/pdf,.pdf')
 *   acceptExtensions    {string[]}           allowed extensions (default ['.pdf'])
 *   acceptLabel         {string}             label for display (default 'PDF')
 *   maxSizeMB           {number}             max allowed size in MB (default 10)
 *   disabled            {boolean}
 *   dropzoneText        {string}             custom dropzone text
 *   sizeText            {string}             custom size text
 *   errorInvalidFormat  {string}             error message for invalid format
 */
function FileDropzone({
  onFile,
  onError,
  accept = 'application/pdf,.pdf',
  acceptExtensions = ['.pdf'],
  acceptLabel = 'PDF',
  maxSizeMB = 10,
  disabled = false,
  dropzoneText,
  sizeText,
  errorInvalidFormat = 'File harus berformat PDF.',
}) {
  const inputRef = useRef(null);
  const [dragOver, setDragOver] = useState(false);

  const validate = useCallback(
    (file) => {
      // Check file extension
      const ext = file.name.toLowerCase().substring(file.name.lastIndexOf('.'));
      if (!acceptExtensions.includes(ext)) {
        onError(errorInvalidFormat);
        return false;
      }
      // Check MIME type (if accept is specified)
      if (accept && !accept.split(',').some((a) => file.type === a.trim() || (a.trim().endsWith('/*') && file.type.startsWith(a.trim().slice(0, -1))))) {
        onError(errorInvalidFormat);
        return false;
      }
      if (file.size > maxSizeMB * 1024 * 1024) {
        onError(`Ukuran file melebihi batas ${maxSizeMB} MB.`);
        return false;
      }
      return true;
    },
    [acceptExtensions, accept, maxSizeMB, onError, errorInvalidFormat]
  );

  const handleFile = useCallback(
    (file) => {
      if (!file) return;
      if (validate(file)) onFile(file);
    },
    [validate, onFile]
  );

  const handleClick = () => {
    if (!disabled) inputRef.current?.click();
  };

  const handleChange = (e) => {
    handleFile(e.target.files?.[0]);
    // reset so the same file can be re-selected after removal
    e.target.value = '';
  };

  const handleDragOver = (e) => {
    e.preventDefault();
    if (!disabled) setDragOver(true);
  };

  const handleDragLeave = () => setDragOver(false);

  const handleDrop = (e) => {
    e.preventDefault();
    setDragOver(false);
    if (disabled) return;
    handleFile(e.dataTransfer.files?.[0]);
  };

  const displayText = dropzoneText || `Drag & drop ${acceptLabel} atau `;
  const clickText = 'klik untuk pilih';
  const displaySizeText = sizeText || `${acceptLabel} · maks. ${maxSizeMB} MB`;

  return (
    <div
      role="button"
      tabIndex={disabled ? -1 : 0}
      aria-label={`Upload ${acceptLabel}`}
      onClick={handleClick}
      onKeyDown={(e) => (e.key === 'Enter' || e.key === ' ') && handleClick()}
      onDragOver={handleDragOver}
      onDragLeave={handleDragLeave}
      onDrop={handleDrop}
      className={[
        'flex flex-col items-center justify-center gap-3 px-6 py-10',
        'border-2 border-dashed rounded-md transition-colors',
        'cursor-pointer select-none',
        dragOver
          ? 'border-electric bg-electric/10 text-electric'
          : disabled
          ? 'border-[var(--border-light)] text-[var(--color-text-mute)] opacity-50 cursor-not-allowed'
          : 'border-[var(--border-dark)] text-[var(--color-text-inv-mute)] hover:border-electric hover:text-electric',
      ].join(' ')}
    >
      <Icon name="upload-cloud" size={32} strokeWidth={1.5} />
      <p className="text-sm text-center leading-relaxed">
        {displayText}
        <span className="text-electric font-medium">{clickText}</span>
      </p>
      <p className="text-xs text-[var(--color-text-mute)]">
        {displaySizeText}
      </p>

      <input
        ref={inputRef}
        type="file"
        accept={accept}
        className="sr-only"
        tabIndex={-1}
        onChange={handleChange}
        disabled={disabled}
      />
    </div>
  );
}

export default memo(FileDropzone);
