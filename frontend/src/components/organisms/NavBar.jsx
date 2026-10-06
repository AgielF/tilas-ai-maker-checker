import { Link } from 'react-router-dom';
import NavLink from '../molecules/NavLink';

const NAV_LINKS = [
  { to: '/#features',      label: 'Product',  dimmed: false },
  { to: '/#how-it-works',  label: 'Research', dimmed: false },
  { to: '/checker',        label: 'Checker',  dimmed: false },
  { to: '/about',          label: 'Docs',     dimmed: true  },
];

function NavBar({ activePath = '' }) {
  return (
    <header
      className="sticky top-0 z-50 h-16 bg-canvas/80 backdrop-blur-md border-b border-[var(--border-light)]"
    >
      <div className="max-w-7xl mx-auto px-6 h-full flex items-center justify-between gap-8">
        {/* Logo */}
        <Link
          to="/"
          className="flex items-center gap-2 text-navy no-underline"
          aria-label="Tilas — home"
        >
          <span className="text-xl font-black tracking-tight text-navy leading-none">
            Tilas
          </span>
          <span
            className="w-2 h-2 rounded-full bg-electric flex-shrink-0"
            aria-hidden="true"
          />
        </Link>

        {/* Nav links */}
        <nav className="hidden md:flex items-center gap-1" aria-label="Main navigation">
          {NAV_LINKS.map(({ to, label, dimmed }) => (
            dimmed ? (
              <span
                key={to}
                className="text-sm font-medium px-3 py-2 text-[var(--color-text-mute)] opacity-60 cursor-default"
                title="Coming soon"
              >
                {label}
              </span>
            ) : (
              <NavLink
                key={to}
                to={to}
                active={activePath === to}
              >
                {label}
              </NavLink>
            )
          ))}
        </nav>

      </div>
    </header>
  );
}

export default NavBar;
