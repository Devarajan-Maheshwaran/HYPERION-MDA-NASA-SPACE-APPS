import { NavLink } from 'react-router-dom';
import * as Popover from '@radix-ui/react-popover';
import { Check, ChevronDown, Database, FlaskConical, Radio, ShieldCheck } from 'lucide-react';
import { useWorkstation } from '../state/WorkstationProvider';
import { Badge, Button } from './ui';
import { cn } from '../lib/utils';

const NAV = [
  { to: '/', index: '01', label: 'Crew Workstation' },
  { to: '/overview', index: '02', label: 'Overview' },
  { to: '/docs', index: '03', label: 'ML Architecture & Docs' },
];

export function Header() {
  const { state, busy, selectMode } = useWorkstation();
  const simulated = state?.data_source_mode !== 'REAL_EMPIRICAL';
  const telemetryUnavailable = state?.telemetry_mode === 'NOT_AVAILABLE';

  return (
    <header className="sticky top-0 z-40 h-16 border-b border-line bg-white/95 backdrop-blur">
      <div className="mx-auto flex h-full max-w-content items-center justify-between gap-4 px-4 sm:px-6">
        <NavLink to="/" className="flex shrink-0 items-center gap-3" aria-label="HYPERION-MDA overview">
          <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-primary text-white">
            <ShieldCheck size={17} strokeWidth={1.8} aria-hidden />
          </span>
          <span className="hidden text-sm font-bold tracking-tight text-ink sm:block">HYPERION-MDA</span>
          <span className="hidden rounded-full border border-line bg-page px-2.5 py-1 text-2xs font-medium text-ink-subtle xl:block">
            NASA Space Apps · Crew Health
          </span>
        </NavLink>

        <nav aria-label="Primary" className="flex h-10 items-center rounded-lg border border-line bg-page p-1">
          {NAV.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.to === '/'}
              className={({ isActive }) => cn(
                'flex h-8 items-center gap-1.5 rounded-md px-2.5 text-xs font-medium transition-colors sm:px-3.5 sm:text-sm',
                isActive ? 'bg-white text-ink shadow-card' : 'text-ink-subtle hover:text-ink',
              )}
            >
              <span className="num hidden text-2xs text-ink-label lg:inline">{item.index}.</span>
              <span className="hidden md:inline">{item.label}</span>
              <span className="md:hidden">{item.index === '01' ? 'Workstation' : item.index === '02' ? 'Overview' : 'Docs'}</span>
            </NavLink>
          ))}
        </nav>

        <Popover.Root>
          <Popover.Trigger asChild>
            <button
              type="button"
              className={cn(
                'flex h-9 shrink-0 items-center gap-2 rounded-full border px-3 text-xs font-medium transition-colors',
                simulated
                  ? 'border-watch/25 bg-watch-soft text-watch-text hover:border-watch/50'
                  : 'border-nominal/25 bg-nominal-soft text-nominal-text hover:border-nominal/50',
              )}
              aria-label="Data provenance and source mode"
            >
              <span aria-hidden>{simulated ? '◐' : '●'}</span>
              <span className="hidden lg:inline">
                {simulated ? 'Simulated Scenario Fallback' : telemetryUnavailable ? 'Real Sources · Telemetry N/A' : 'Real Empirical Data'}
              </span>
              <span className="lg:hidden">{simulated ? 'Simulated' : 'Real sources'}</span>
              <ChevronDown size={13} aria-hidden />
            </button>
          </Popover.Trigger>
          <Popover.Portal>
            <Popover.Content
              align="end"
              sideOffset={10}
              className="z-50 w-[360px] rounded-xl border border-line bg-white p-4 shadow-popover outline-none"
            >
              <div className="flex items-center justify-between">
                <h2 className="text-sm font-semibold">Data provenance</h2>
                <Badge tone={simulated ? 'watch' : 'nominal'}>{simulated ? 'Explicitly labeled' : 'Real-source mode'}</Badge>
              </div>
              <p className="mt-2 text-xs leading-5 text-ink-body">
                {simulated
                  ? 'Physics-guided physiological scenarios are used for live stress-testing. They are not flight data.'
                  : 'Real empirical sources are listed below. No live astronaut wearable is connected; telemetry is never invented.'}
              </p>

              <div className="mt-4 space-y-2">
                <SourceRow icon={<Database size={14} />} label="NASA OSD-575 lab lane" available={state?.sources.lab.available} detail={state?.sources.lab.detail} />
                <SourceRow icon={<Radio size={14} />} label="NOAA GOES proton lane" available={state?.sources.goes.available} detail={state?.sources.goes.detail ?? 'Cached or live integral proton flux; no dose conversion.'} />
                <SourceRow icon={<FlaskConical size={14} />} label="WESAD / PhysioNet wearable lane" available={state?.sources.wearable.available} detail={state?.sources.wearable.detail} />
              </div>

              <div className="mt-4 grid gap-2 border-t border-line pt-4">
                <Button
                  variant={!simulated ? 'primary' : 'secondary'}
                  size="sm"
                  busy={busy}
                  onClick={() => void selectMode('REAL_EMPIRICAL')}
                  className="justify-between"
                >
                  <span>● Real Empirical Data</span>
                  {!simulated ? <Check size={14} aria-hidden /> : null}
                </Button>
                <Button
                  variant={simulated ? 'primary' : 'secondary'}
                  size="sm"
                  busy={busy}
                  onClick={() => void selectMode('SIMULATED_FALLBACK')}
                  className="justify-between"
                >
                  <span>◐ Simulated Scenario Fallback</span>
                  {simulated ? <Check size={14} aria-hidden /> : null}
                </Button>
              </div>
              <p className="mt-3 text-2xs leading-4 text-ink-label">
                OSD-575 / GOES / WESAD · Demo thresholds, not clinically validated. Not a medical device.
              </p>
              <Popover.Arrow className="fill-white" />
            </Popover.Content>
          </Popover.Portal>
        </Popover.Root>
      </div>
    </header>
  );
}

function SourceRow({ icon, label, available, detail }: {
  icon: React.ReactNode; label: string; available: boolean | undefined; detail: string | undefined;
}) {
  return (
    <div className="rounded-lg border border-line bg-page px-3 py-2.5">
      <div className="flex items-center justify-between gap-2">
        <span className="flex items-center gap-2 text-xs font-medium text-ink">{icon}{label}</span>
        <Badge tone={available ? 'nominal' : 'neutral'}>{available ? 'Available' : 'Not available'}</Badge>
      </div>
      {detail ? <p className="mt-1 line-clamp-2 text-2xs leading-4 text-ink-subtle">{detail}</p> : null}
    </div>
  );
}
