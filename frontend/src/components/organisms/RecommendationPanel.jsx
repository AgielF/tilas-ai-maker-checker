import { memo } from 'react';
import LoadingSteps from '../molecules/LoadingSteps';
import RecommendationCard from '../molecules/RecommendationCard';
import Button from '../atoms/Button';
import Icon from '../atoms/Icon';

/**
 * RecommendationPanel — Maker page content area.
 * Handles 4 states via the `state` prop.
 *
 * Props:
 *   state      {'idle'|'loading'|'error'|'success'}
 *   result     {Object}   RecommendationResponse (state=success)
 *   error      {string}   error message (state=error)
 *   onCancel   {Function} called when Cancel is clicked during loading
 *   onRetry    {Function} called when Retry is clicked on error
 *   onValidate {Function} called when "Validate this price" is clicked
 *   mode       {'penawaran'|'bon'} maker mode — affects result rendering
 */
function RecommendationPanel({ state = 'idle', result, error, onCancel, onRetry, onValidate, mode = 'penawaran' }) {
  if (state === 'loading') {
    return (
      <section className="border border-[var(--border-light)]">
        <LoadingSteps currentStep={0} onCancel={onCancel} />
      </section>
    );
  }

  if (state === 'error') {
    return (
      <section className="border border-sev-critical/30 bg-sev-critical/5 p-6 flex flex-col gap-4">
        <div className="flex items-start gap-3">
          <span className="text-sev-critical mt-0.5 shrink-0">
            <Icon name="x-circle" size={18} />
          </span>
          <p className="text-sm text-sev-critical leading-relaxed">
            {error ?? 'Terjadi kesalahan. Silakan coba lagi.'}
          </p>
        </div>
        {onRetry && (
          <Button variant="ghost" size="sm" className="self-start" onClick={onRetry}>
            Retry
          </Button>
        )}
      </section>
    );
  }

  if (state === 'success' && result) {
    return (
      <RecommendationCard result={result} onValidate={onValidate} mode={mode} />
    );
  }

  // idle (default)
  return (
    <section className="border border-[var(--border-light)] flex flex-col items-center justify-center gap-3 py-16 px-6 text-center">
      <span className="text-[var(--color-text-mute)]">
        <Icon name="search" size={36} strokeWidth={1.5} />
      </span>
      <p className="text-sm text-[var(--color-text-mute)]">
        Masukkan nama item untuk memulai
      </p>
    </section>
  );
}

export default memo(RecommendationPanel);
