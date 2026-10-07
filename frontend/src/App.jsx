import { lazy, Suspense } from 'react';
import { BrowserRouter, Routes, Route } from 'react-router-dom';
import Spinner from './components/atoms/Spinner';

// Landing is NOT lazy — must render instantly as the entry point
import LandingPage from './pages/LandingPage';

// ─── Lazy-loaded active pages ────────────────────────────────────────────────
const NotFoundPage   = lazy(() => import('./pages/NotFoundPage'));
const CheckerPage    = lazy(() => import('./pages/CheckerPage'));
const RiskReportPage = lazy(() => import('./pages/RiskReportPage'));
const MakerPage      = lazy(() => import('./pages/MakerPage'));
const BonsPage       = lazy(() => import('./pages/BonsPage'));
const BonDetailPage  = lazy(() => import('./pages/BonDetailPage'));
const ComingSoonPage = lazy(() => import('./pages/ComingSoonPage'));

// ─── Suspense fallback ───────────────────────────────────────────────────────
function LoadingScreen() {
  return (
    <div className="min-h-screen bg-ink flex items-center justify-center">
      <Spinner size="lg" />
    </div>
  );
}

// ─── App ─────────────────────────────────────────────────────────────────────
export default function App() {
  return (
    <BrowserRouter>
      <Suspense fallback={<LoadingScreen />}>
        <Routes>
          {/* Active routes */}
          <Route path="/"                    element={<LandingPage />} />
          <Route path="/checker"             element={<CheckerPage />} />
          <Route path="/checker/risk-report" element={<RiskReportPage />} />
          <Route path="/bons"                element={<BonsPage />} />
          <Route path="/bons/:id"            element={<BonDetailPage />} />

          {/* Coming Soon routes */}
          <Route path="/dashboard" element={
            <ComingSoonPage
              title="Dashboard"
              description="Ringkasan KPI, aktivitas vendor, dan temuan audit terbaru. Sedang dikerjakan untuk versi berikutnya."
              eta="Est. 1–2 minggu"
            />
          } />
          <Route path="/maker" element={<MakerPage />} />
          <Route path="/maker/validate" element={
            <ComingSoonPage
              title="Price Validation"
              description="Cross-validate harga item dari quote vendor. Bagian dari modul Maker Agent."
              eta="Est. 1 minggu"
            />
          } />
          <Route path="/vendors" element={
            <ComingSoonPage
              title="Vendor Management"
              description="Kelola master data vendor dan quote."
              eta="Est. 2 minggu"
            />
          } />
          <Route path="/findings" element={
            <ComingSoonPage
              title="Audit Findings"
              description="Lihat semua temuan audit dan riwayat pemeriksaan."
              eta="Est. 1 minggu"
            />
          } />
          <Route path="/about" element={
            <ComingSoonPage
              title="About Tilas"
              description="Dokumentasi arsitektur, tech stack, dan roadmap."
              eta="Est. 3 hari"
            />
          } />

          <Route path="*" element={<NotFoundPage />} />
        </Routes>
      </Suspense>
    </BrowserRouter>
  );
}
