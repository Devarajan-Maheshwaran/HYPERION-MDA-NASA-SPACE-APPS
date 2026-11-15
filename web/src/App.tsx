import { useEffect } from 'react';
import { Navigate, Route, Routes, useLocation } from 'react-router-dom';
import { AnimatePresence, motion } from 'motion/react';
import { Header } from './components/Header';
import { ErrorNotice, PageSkeleton } from './components/ui';
import { OverviewPage } from './pages/OverviewPage';
import { WorkstationPage } from './pages/WorkstationPage';
import { DocsPage } from './pages/DocsPage';
import { WorkstationProvider, useWorkstation } from './state/WorkstationProvider';
import { DISCLAIMER } from './lib/types';

export function App() {
  return (
    <WorkstationProvider>
      <Shell />
    </WorkstationProvider>
  );
}

function Shell() {
  const location = useLocation();
  const { loading, state, error, reload } = useWorkstation();

  useEffect(() => {
    window.scrollTo({ top: 0, behavior: 'instant' });
  }, [location.pathname]);

  return (
    <div className="flex min-h-screen flex-col bg-page">
      <Header />
      <main className="flex-1">
        {error ? (
          <div className="mx-auto max-w-content px-4 pt-4 sm:px-6">
            <ErrorNotice title="Workstation API unavailable" onRetry={() => void reload()}>{error}</ErrorNotice>
          </div>
        ) : null}
        {loading ? <PageSkeleton /> : (
          <AnimatePresence mode="wait" initial={false}>
            <motion.div
              key={location.pathname}
              initial={{ opacity: 0, y: 6 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: 6 }}
              transition={{ duration: 0.28, ease: [0.16, 1, 0.3, 1] }}
            >
              <Routes location={location}>
                <Route path="/" element={<OverviewPage />} />
                <Route path="/workstation" element={state ? <WorkstationPage /> : <Unavailable />} />
                <Route path="/docs" element={<DocsPage />} />
                <Route path="*" element={<Navigate to="/" replace />} />
              </Routes>
            </motion.div>
          </AnimatePresence>
        )}
      </main>
      <footer className="border-t border-line bg-white">
        <div className="mx-auto flex max-w-content flex-col gap-2 px-4 py-4 text-2xs text-ink-label sm:flex-row sm:items-center sm:justify-between sm:px-6">
          <span>HYPERION-MDA · NASA Space Apps research prototype</span>
          <span>{DISCLAIMER}</span>
        </div>
      </footer>
    </div>
  );
}

function Unavailable() {
  return (
    <div className="mx-auto max-w-content px-6 py-16 text-center">
      <h1 className="text-2xl">Workstation state unavailable</h1>
      <p className="mt-2 text-sm text-ink-body">The API did not return a state snapshot. Use Retry above once the backend is running.</p>
    </div>
  );
}
