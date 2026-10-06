import { memo } from 'react';

function Footer() {
  return (
    <footer className="border-t border-[var(--border-light)] py-8">
      <div className="max-w-7xl mx-auto px-6 flex flex-col sm:flex-row items-center justify-between gap-4">
        <p className="text-sm text-[var(--color-text-mute)]">
          © 2026 Tilas. All rights reserved.
        </p>
        <nav className="flex items-center gap-6" aria-label="Footer links">
          <a
            href="https://github.com"
            className="text-sm text-[var(--color-text-mute)] hover:text-ink transition-colors"
            target="_blank"
            rel="noreferrer"
          >
            GitHub
          </a>
          <a
            href="/docs"
            className="text-sm text-[var(--color-text-mute)] hover:text-ink transition-colors"
          >
            Docs
          </a>
          <a
            href="/license"
            className="text-sm text-[var(--color-text-mute)] hover:text-ink transition-colors"
          >
            License
          </a>
        </nav>
      </div>
    </footer>
  );
}

export default memo(Footer);
