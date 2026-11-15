import * as React from 'react';
import { useNavigate } from 'react-router-dom';
import { Command } from 'cmdk';
import { ArrowRight, Play, Search, ShieldCheck, Square, UserRound } from 'lucide-react';
import { api } from '../../lib/api';
import { useSession } from '../../hooks/useSession';
import { DialogShell, Kbd } from '../ui';
import { NAV_ITEMS } from './Rail';
import type { Role, ScenarioInfo } from '../../lib/types';

const ROLES: Role[] = ['crew', 'flight-surgeon', 'ops', 'researcher'];
const ROLE_LABEL: Record<Role, string> = {
  crew: 'Crew', 'flight-surgeon': 'Flight surgeon', ops: 'Operations', researcher: 'Researcher',
};

export function CommandPalette({ open, onOpenChange }: { open: boolean; onOpenChange: (v: boolean) => void }) {
  const navigate = useNavigate();
  const { role, subjects, startScenario, changeRole, changeSubject, stopScenario, refresh } = useSession();
  const [scenarios, setScenarios] = React.useState<ScenarioInfo[]>([]);
  const [scenarioError, setScenarioError] = React.useState<string | null>(null);
  const canControl = role !== 'researcher';

  React.useEffect(() => {
    if (!open) return;
    let cancelled = false;
    setScenarioError(null);
    void api.scenarios().then(
      (result) => { if (!cancelled) setScenarios(result.scenarios); },
      (exc: unknown) => {
        if (!cancelled) {
          setScenarios([]);
          setScenarioError(exc instanceof Error ? exc.message : String(exc));
        }
      },
    );
    return () => { cancelled = true; };
  }, [open]);

  const run = (action: () => void | Promise<unknown>) => {
    onOpenChange(false);
    void action();
  };

  const items = NAV_ITEMS.filter((item) => item.roles.includes(role));

  return (
    <DialogShell open={open} onOpenChange={onOpenChange} title="Command palette" variant="palette" hideHeader>
      <Command label="Command palette"
        className="[&_[cmdk-group-heading]]:microlabel [&_[cmdk-group-heading]]:px-3 [&_[cmdk-group-heading]]:pb-1 [&_[cmdk-group-heading]]:pt-2">
        <div className="flex items-center gap-2 border-b border-hairline px-3">
          <Search size={14} strokeWidth={1.75} className="shrink-0 text-ink-faint" />
          <Command.Input autoFocus placeholder="Search commands, scenarios, subjects…"
            className="h-11 w-full bg-transparent text-sm text-ink placeholder:text-ink-faint focus:outline-none" />
          <Kbd>esc</Kbd>
        </div>
        <Command.List className="max-h-[340px] overflow-y-auto p-1.5">
          <Command.Empty className="px-3 py-6 text-center text-xs text-ink-faint">No matching command.</Command.Empty>

          <Command.Group heading="Navigate">
            {items.map((item) => (
              <Row key={item.to} onSelect={() => run(() => navigate(item.to))} value={`navigate ${item.label}`}>
                <item.icon size={14} strokeWidth={1.75} className="text-ink-muted" />
                <span className="flex-1">{item.label}</span>
                <Kbd>{item.shortcut}</Kbd>
              </Row>
            ))}
          </Command.Group>

          {canControl ? (
            <Command.Group heading="Run scenario · simulated / injected">
              {scenarioError ? (
                <div role="alert" className="px-3 py-2 text-xs text-state-alert">
                  Scenarios unavailable — {scenarioError}. Nothing was started.
                </div>
              ) : scenarios.map((scenario) => (
                <Row key={scenario.scenario_id} value={`scenario ${scenario.label} ${scenario.scenario_id}`}
                  onSelect={() => run(() => startScenario(scenario.scenario_id))}>
                  <Play size={14} strokeWidth={1.75} className="text-ink-muted" />
                  <span className="flex-1">{scenario.label}</span>
                  <span className="tnum text-[10px] text-ink-faint">{scenario.lane}</span>
                </Row>
              ))}
              <Row value="stop stream" onSelect={() => run(stopScenario)}>
                <Square size={14} strokeWidth={1.75} className="text-ink-muted" />
                <span className="flex-1">Stop the active stream</span>
              </Row>
            </Command.Group>
          ) : null}

          <Command.Group heading="Switch subject">
            {subjects.map((subject) => (
              <Row key={subject.subject_id} value={`subject ${subject.subject_id} ${subject.label}`}
                onSelect={() => run(() => changeSubject(subject.subject_id))}>
                <UserRound size={14} strokeWidth={1.75} className="text-ink-muted" />
                <span className="tnum flex-1">{subject.subject_id}</span>
                <span className="text-[10px] text-ink-faint">
                  {subject.calibration.calibrated ? 'calibrated' : 'uncalibrated'}
                </span>
              </Row>
            ))}
          </Command.Group>

          <Command.Group heading="Demo role · not authentication">
            {ROLES.map((item) => (
              <Row key={item} value={`role ${item} ${ROLE_LABEL[item]}`} onSelect={() => run(() => changeRole(item))}>
                <ShieldCheck size={14} strokeWidth={1.75} className="text-ink-muted" />
                <span className="flex-1">{ROLE_LABEL[item]}</span>
                {item === role ? <span className="tnum text-[10px] text-accent">ACTIVE</span> : null}
              </Row>
            ))}
            <Row value="refresh session" onSelect={() => run(refresh)}>
              <ArrowRight size={14} strokeWidth={1.75} className="text-ink-muted" />
              <span className="flex-1">Refresh session state</span>
            </Row>
          </Command.Group>
        </Command.List>
      </Command>
    </DialogShell>
  );
}

function Row({ children, onSelect, value }: { children: React.ReactNode; onSelect: () => void; value: string }) {
  return (
    <Command.Item value={value} onSelect={onSelect}
      className="flex cursor-pointer items-center gap-2.5 rounded-md px-3 py-2 text-sm text-ink-secondary
                 aria-selected:bg-white/[0.06] aria-selected:text-ink">
      {children}
    </Command.Item>
  );
}
