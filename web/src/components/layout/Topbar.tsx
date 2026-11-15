import { useLocation, useNavigate } from 'react-router-dom';
import { ChevronRight, Command, Play, Search } from 'lucide-react';
import { useSession } from '../../hooks/useSession';
import { Button, Kbd, Segmented, Select } from '../ui';
import { cn } from '../../lib/utils';
import { laneExplanation, laneTone, stateLabel, stateTone } from '../../lib/status';
import { StatusDot } from '../ui';
import type { Habitat, Role } from '../../lib/types';
import { NAV_ITEMS } from './Rail';

export type Timeframe = '30s' | '2m' | '5m' | 'all';

export const TIMEFRAME_OPTIONS: Array<{ id: Timeframe; label: string }> = [
  { id: '30s', label: '30s' },
  { id: '2m', label: '2m' },
  { id: '5m', label: '5m' },
  { id: 'all', label: 'All' },
];

export const TIMEFRAME_SECONDS: Record<Timeframe, number> = {
  '30s': 30, '2m': 120, '5m': 300, all: Number.POSITIVE_INFINITY,
};

export function LaneBadge({ className }: { className?: string }) {
  const { frame } = useSession();
  const lane = frame?.lane ?? 'NONE';
  return (
    <span
      title={laneExplanation(lane)}
      data-lane={lane}
      className={cn(
        'tnum inline-flex shrink-0 items-center gap-1.5 rounded border px-1.5 py-[2px] text-[10px] font-medium uppercase tracking-[0.06em]',
        laneTone(lane),
        className,
      )}
    >
      {lane}
    </span>
  );
}

const ROLE_LABEL: Record<Role, string> = {
  crew: 'Crew', 'flight-surgeon': 'Flight surgeon', ops: 'Operations', researcher: 'Researcher',
};

export function Topbar({
  timeframe, onTimeframe, onOpenPalette, onPrimary,
}: {
  timeframe: Timeframe;
  onTimeframe: (value: Timeframe) => void;
  onOpenPalette: () => void;
  onPrimary: () => void;
}) {
  const location = useLocation();
  const navigate = useNavigate();
  const { frame, connected, running, role, changeRole, habitat, changeHabitat, session } = useSession();
  const current = NAV_ITEMS.find((item) => item.to === location.pathname);

  return (
    <header className="sticky top-0 z-30 flex h-[52px] shrink-0 items-center gap-3 border-b border-hairline bg-surface/95 px-3 backdrop-blur">
      {/* breadcrumb */}
      <nav aria-label="Breadcrumb" className="flex min-w-0 items-center gap-1.5">
        <button
          type="button"
          onClick={() => navigate('/overview')}
          className="shrink-0 text-sm font-medium text-ink-muted transition-colors hover:text-ink"
        >
          HYPERION
        </button>
        <ChevronRight size={13} strokeWidth={1.75} className="shrink-0 text-ink-faint" />
        <span className="truncate text-sm font-semibold text-ink">{current?.label ?? 'Workstation'}</span>
      </nav>

      <LaneBadge className="hidden lg:inline-flex" />
      {frame ? (
        <span data-tone={stateTone(frame.state)} className="hidden items-center gap-1.5 xl:inline-flex">
          <StatusDot tone={stateTone(frame.state)} pulse={running} />
          <span className="text-xs text-ink-secondary">{stateLabel(frame.state)}</span>
        </span>
      ) : null}

      {/* command trigger */}
      <button
        type="button"
        onClick={onOpenPalette}
        className="ml-auto hidden h-7 min-w-[190px] items-center gap-2 rounded-md border border-hairline bg-base px-2.5
                   text-ink-faint transition-colors hover:border-hairline-strong hover:text-ink-secondary sm:flex"
      >
        <Search size={13} strokeWidth={1.75} />
        <span className="flex-1 text-left text-xs">Commands…</span>
        <Kbd><Command size={9} strokeWidth={2} className="inline" />K</Kbd>
      </button>

      <div className="hidden md:block">
        <Segmented
          options={TIMEFRAME_OPTIONS}
          value={timeframe}
          onChange={onTimeframe}
          layoutId="topbar-timeframe"
        />
      </div>

      <Select
        aria-label="Habitat"
        value={habitat}
        className="hidden xl:block"
        onChange={(event) => void changeHabitat(event.target.value as Habitat)}
      >
        {(session?.habitats ?? []).map((item) => <option key={item} value={item}>{item}</option>)}
      </Select>

      <Select aria-label="Demo role" value={role} onChange={(event) => void changeRole(event.target.value as Role)}>
        {(Object.keys(ROLE_LABEL) as Role[]).map((item) => (
          <option key={item} value={item}>{ROLE_LABEL[item]}</option>
        ))}
      </Select>

      <span
        title={connected ? 'Server-sent events connected' : 'Stream disconnected — values are stale'}
        className="hidden items-center gap-1.5 sm:flex"
      >
        <StatusDot tone={connected ? 'nominal' : 'unknown'} pulse={connected && running} />
        <span className="tnum text-[10px] uppercase tracking-[0.06em] text-ink-faint">
          {connected ? 'live' : 'offline'}
        </span>
      </span>

      <Button size="sm" onClick={onPrimary} className="shrink-0" disabled={role === 'researcher'}
        title={role === 'researcher' ? 'Researcher role is read-only' : undefined}>
        <Play size={12} strokeWidth={1.75} />
        <span className="hidden sm:inline">{running ? 'Restart scenario' : 'Run scenario'}</span>
      </Button>
    </header>
  );
}
