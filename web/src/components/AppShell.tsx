import * as React from 'react';
import { NavLink, useLocation } from 'react-router-dom';
import { motion } from 'motion/react';
import { Menu } from 'lucide-react';
import { useSession } from '../hooks/useSession';
import { DISCLAIMER } from '../lib/types';
import { laneExplanation } from '../lib/status';
import { cn } from '../lib/utils';
import { Rail, NAV_ITEMS } from './layout/Rail';
import { Topbar, type Timeframe } from './layout/Topbar';
import { CommandPalette } from './layout/CommandPalette';

export { LaneBadge } from './layout/Topbar';

interface ShellContextValue {
  timeframe: Timeframe;
  setTimeframe: (value: Timeframe) => void;
  openPalette: () => void;
}

const ShellContext = React.createContext<ShellContextValue>({
  timeframe: '2m',
  setTimeframe: () => undefined,
  openPalette: () => undefined,
});

export function useShell(): ShellContextValue {
  return React.useContext(ShellContext);
}

const COLLAPSE_KEY = 'hyperion.rail.collapsed';

export function AppShell({ children }: { children: React.ReactNode }) {
  const { frame, error, role, startScenario, running } = useSession();
  const [collapsed, setCollapsed] = React.useState(() => {
    try { return localStorage.getItem(COLLAPSE_KEY) === '1'; } catch { return false; }
  });
  const [paletteOpen, setPaletteOpen] = React.useState(false);
  const [mobileNav, setMobileNav] = React.useState(false);
  const [timeframe, setTimeframe] = React.useState<Timeframe>('2m');
  const location = useLocation();

  React.useEffect(() => { setMobileNav(false); }, [location.pathname]);
  React.useEffect(() => {
    try { localStorage.setItem(COLLAPSE_KEY, collapsed ? '1' : '0'); } catch { /* private mode */ }
  }, [collapsed]);

  // ⌘K / Ctrl-K opens the palette from anywhere.
  React.useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === 'k') {
        event.preventDefault();
        setPaletteOpen((value) => !value);
      }
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, []);

  const primary = React.useCallback(() => {
    if (role === 'researcher') return;
    void startScenario(frame?.scenario_id ?? 'exercise-false-alarm');
  }, [frame?.scenario_id, role, startScenario]);

  const items = NAV_ITEMS.filter((item) => item.roles.includes(role));
  const shellValue = React.useMemo(() => ({ timeframe, setTimeframe, openPalette: () => setPaletteOpen(true) }), [timeframe]);

  return (
    <ShellContext.Provider value={shellValue}>
      <div className="flex h-screen overflow-hidden bg-base">
        <Rail collapsed={collapsed} onToggle={() => setCollapsed((value) => !value)} />

        <div className="flex min-w-0 flex-1 flex-col">
          <Topbar
            timeframe={timeframe}
            onTimeframe={setTimeframe}
            onOpenPalette={() => setPaletteOpen(true)}
            onPrimary={primary}
          />

          {/* mobile nav */}
          <div className="flex items-center gap-2 border-b border-hairline bg-surface px-3 py-1.5 md:hidden">
            <button type="button" onClick={() => setMobileNav((v) => !v)} aria-label="Toggle navigation"
              aria-expanded={mobileNav} className="text-ink-muted">
              <Menu size={15} strokeWidth={1.75} />
            </button>
            <span className="text-xs text-ink-muted">{items.length} views</span>
            <button type="button" onClick={() => setPaletteOpen(true)}
              className="ml-auto text-xs text-ink-faint hover:text-ink-secondary">⌘K</button>
          </div>
          {mobileNav ? (
            <div className="grid grid-cols-2 gap-1 border-b border-hairline bg-surface p-2 md:hidden">
              {items.map((item) => (
                <NavLink key={item.to} to={item.to}
                  className={({ isActive }) => cn('rounded-md px-2 py-1.5 text-xs',
                    isActive ? 'bg-white/[0.06] text-ink' : 'text-ink-secondary')}>
                  {item.label}
                </NavLink>
              ))}
            </div>
          ) : null}

          {/* honesty strip: lane provenance is always stated, never buried */}
          <div className="flex shrink-0 items-center gap-2 border-b border-hairline bg-surface-2/60 px-3 py-1">
            <span className="microlabel shrink-0">Provenance</span>
            <span className="truncate text-[11px] text-ink-muted">{laneExplanation(frame?.lane ?? 'NONE')}</span>
            {running ? <span className="tnum ml-auto shrink-0 text-[10px] text-accent">STREAMING</span> : null}
          </div>

          {error ? (
            <div role="alert" className="shrink-0 border-b border-state-alert/30 bg-state-alert/10 px-3 py-1.5 text-xs text-state-alert">
              API error: {error} — displayed values are not refreshed and must be treated as UNKNOWN.
            </div>
          ) : null}

          <motion.main
            key={location.pathname}
            initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ duration: 0.18 }}
            className="min-h-0 flex-1 overflow-y-auto"
          >
            <div className="p-3 lg:p-4">{children}</div>
          </motion.main>

          <footer className="shrink-0 border-t border-hairline bg-surface px-3 py-1.5">
            <div className="flex flex-wrap items-center justify-between gap-x-4 gap-y-1">
              <span className="text-[11px] font-medium text-ink-secondary">{DISCLAIMER}</span>
              <span className="tnum hidden text-[10px] text-ink-faint lg:inline">
                deterministic gates · no neural model or LLM in the decision path · demo-grade roles · local hash-chain audit
              </span>
            </div>
          </footer>
        </div>

        <CommandPalette open={paletteOpen} onOpenChange={setPaletteOpen} />
      </div>
    </ShellContext.Provider>
  );
}
