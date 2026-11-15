import * as React from 'react';
import { NavLink, useLocation } from 'react-router-dom';
import { useSession } from '../hooks/useSession';
import { Badge, Select } from './ui';
import { cn } from '../lib/utils';
import { DISCLAIMER, type Habitat, type Role } from '../lib/types';
import { laneExplanation, laneTone, stateLabel, stateTone } from '../lib/status';

const ROLE_LABEL: Record<Role, string> = {
  crew: 'Crew',
  'flight-surgeon': 'Flight surgeon',
  ops: 'Ops / engineering',
  researcher: 'Researcher',
};

const NAV: Array<{ to: string; label: string; roles: Role[] }> = [
  { to: '/crew', label: 'Crew console', roles: ['crew', 'flight-surgeon', 'ops'] },
  { to: '/crew/checks', label: 'Crew checks', roles: ['crew', 'flight-surgeon'] },
  { to: '/surgeon', label: 'Surgeon queue', roles: ['flight-surgeon', 'ops'] },
  { to: '/ops', label: 'Ops console', roles: ['ops', 'flight-surgeon'] },
  { to: '/research', label: 'Research', roles: ['researcher', 'flight-surgeon', 'ops'] },
];

export function LaneBadge({ className }: { className?: string }) {
  const { frame } = useSession();
  const lane = frame?.lane ?? 'NONE';
  return (
    <span
      title={laneExplanation(lane)}
      className={cn(
        'inline-flex items-center gap-1.5 rounded-md border px-2.5 py-1 text-[11px] font-bold uppercase tracking-widest',
        laneTone(lane),
        className,
      )}
    >
      <span aria-hidden className="text-[8px]">●</span>
      {lane}
    </span>
  );
}

export function AppShell({ children }: { children: React.ReactNode }) {
  const { role, changeRole, subjectId, changeSubject, subjects, habitat, changeHabitat,
    session, frame, connected, running, error } = useSession();
  const location = useLocation();
  const visibleNav = NAV.filter((item) => item.roles.includes(role));

  return (
    <div className="flex min-h-screen flex-col bg-ink-900 text-slate-200">
      <header className="sticky top-0 z-30 border-b border-ink-600 bg-ink-800/95 backdrop-blur">
        <div className="mx-auto flex max-w-[1600px] flex-wrap items-center gap-3 px-4 py-2.5">
          <div className="flex items-center gap-2">
            <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-sky-600 font-bold text-white">H</div>
            <div>
              <div className="text-sm font-bold tracking-wide text-slate-100">HYPERION-MDA</div>
              <div className="text-[10px] uppercase tracking-widest text-slate-500">Crew health workstation</div>
            </div>
          </div>

          <LaneBadge />

          {frame ? (
            <Badge tone={stateTone(frame.state)}>{stateLabel(frame.state)}</Badge>
          ) : (
            <Badge tone="unknown">No data loaded</Badge>
          )}

          <div className="ml-auto flex flex-wrap items-center gap-2">
            <span className={cn('flex items-center gap-1 text-[10px] uppercase tracking-wider',
              connected ? 'text-nominal' : 'text-slate-500')}>
              <span aria-hidden>●</span>{connected ? 'SSE live' : 'SSE offline'}
            </span>
            {running ? <Badge tone="info">Streaming</Badge> : null}
            <Select aria-label="Habitat" value={habitat}
              onChange={(event) => void changeHabitat(event.target.value as Habitat)}>
              {(session?.habitats ?? []).map((item) => <option key={item} value={item}>{item}</option>)}
            </Select>
            <Select aria-label="Subject" value={subjectId}
              onChange={(event) => void changeSubject(event.target.value)}>
              {subjects.map((subject) => (
                <option key={subject.subject_id} value={subject.subject_id}>
                  {subject.subject_id}{subject.calibration.calibrated ? '' : ' (uncalibrated)'}
                </option>
              ))}
            </Select>
            <Select aria-label="Role" value={role}
              onChange={(event) => void changeRole(event.target.value as Role)}>
              {(Object.keys(ROLE_LABEL) as Role[]).map((item) => (
                <option key={item} value={item}>{ROLE_LABEL[item]}</option>
              ))}
            </Select>
          </div>
        </div>

        <nav className="mx-auto flex max-w-[1600px] flex-wrap gap-1 px-4 pb-2">
          {visibleNav.map((item) => (
            <NavLink key={item.to} to={item.to}
              className={({ isActive }) => cn(
                'rounded-lg px-3 py-1.5 text-xs font-medium transition-colors',
                isActive || location.pathname === item.to
                  ? 'bg-ink-700 text-slate-100'
                  : 'text-slate-400 hover:bg-ink-700/60 hover:text-slate-200',
              )}>
              {item.label}
            </NavLink>
          ))}
        </nav>
      </header>

      <div className="border-b border-ink-700 bg-watch/10 px-4 py-1.5 text-center text-[11px] text-watch">
        Research prototype · demo-grade role switcher, not authentication · {laneExplanation(frame?.lane ?? 'NONE')}
      </div>

      {error ? (
        <div className="border-b border-alert/40 bg-alert/10 px-4 py-2 text-center text-xs text-alert">
          API error: {error} — values below are not refreshed and must be treated as UNKNOWN.
        </div>
      ) : null}

      <main className="mx-auto w-full max-w-[1600px] flex-1 px-4 py-4">{children}</main>

      <footer className="sticky bottom-0 z-20 border-t border-ink-600 bg-ink-800/95 px-4 py-2 backdrop-blur">
        <div className="mx-auto flex max-w-[1600px] flex-wrap items-center justify-between gap-2 text-[11px]">
          <span className="font-semibold text-slate-300">{DISCLAIMER}</span>
          <span className="text-slate-500">
            No neural model or LLM in the decision path · gates are deterministic · audit is a local hash chain, not a blockchain
          </span>
        </div>
      </footer>
    </div>
  );
}
