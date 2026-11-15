import * as React from 'react';
import { api } from '../lib/api';
import { useSession } from '../hooks/useSession';
import type { AuditEntry, LaneInfo, ScenarioInfo } from '../lib/types';
import { AlertBanner, Badge, Button, Card, CardContent, CardDescription, CardHeader,
  CardTitle, EmptyState, Table, Td, Th } from '../components/ui';
import { formatTime, shortHash } from '../lib/utils';
import { laneExplanation } from '../lib/status';

export function OpsConsole() {
  const { role, subjects, startScenario, stopScenario, running, refresh, frame } = useSession();
  const [lanes, setLanes] = React.useState<LaneInfo[]>([]);
  const [scenarios, setScenarios] = React.useState<ScenarioInfo[]>([]);
  const [audit, setAudit] = React.useState<AuditEntry[]>([]);
  const [verify, setVerify] = React.useState<{ ok: boolean; entries: number; reason: string } | null>(null);
  const [error, setError] = React.useState<string | null>(null);
  const [busy, setBusy] = React.useState<string | null>(null);

  const isOps = role === 'ops';

  const load = React.useCallback(async () => {
    try {
      setLanes((await api.lanes()).lanes);
      setScenarios((await api.scenarios()).scenarios);
      setVerify(await api.verifyAudit());
      setError(null);
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : String(exc));
    }
    try {
      setAudit((await api.audit()).entries);
    } catch {
      setAudit([]);
    }
  }, []);

  React.useEffect(() => {
    void load();
    const timer = setInterval(() => void load(), 5000);
    return () => clearInterval(timer);
  }, [load]);

  const calibrate = async (id: string) => {
    setBusy(id);
    try {
      await api.calibrate(id);
      await refresh();
      await load();
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : String(exc));
    } finally {
      setBusy(null);
    }
  };

  const uncalibrate = async (id: string) => {
    setBusy(id);
    try {
      await api.uncalibrate(id);
      await refresh();
      await load();
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : String(exc));
    } finally {
      setBusy(null);
    }
  };

  return (
    <div className="space-y-4">
      {error ? <AlertBanner tone="alert" title="Ops action failed">{error}</AlertBanner> : null}
      {!isOps ? (
        <AlertBanner tone="watch" title="Read-only for this role">
          Calibration and scenario control need the Ops role. Use the role selector in the header.
        </AlertBanner>
      ) : null}

      <div className="grid gap-4 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>Data lanes</CardTitle>
            <CardDescription>
              Unavailable lanes report the real reason. Nothing is substituted or fabricated.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-2">
            {lanes.map((lane) => (
              <div key={lane.lane} className="rounded-lg border border-ink-600 bg-ink-900/60 p-2.5">
                <div className="flex items-center justify-between gap-2">
                  <span className="text-xs font-semibold text-slate-100">{lane.lane}</span>
                  <Badge tone={lane.available ? 'nominal' : 'unknown'}>
                    {lane.available ? 'Available' : 'Not available'}
                  </Badge>
                </div>
                <p className="mt-1 text-[11px] text-slate-400">{lane.detail}</p>
                <p className="mt-0.5 text-[10px] text-slate-500">{lane.provenance}</p>
              </div>
            ))}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Per-person calibration</CardTitle>
            <CardDescription>
              Gate 1 and Gate 2 return UNKNOWN until a calibration exists. Calibration here is built
              from a SIMULATED resting window and is a demo calibration, not a clinical one.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-2">
            {subjects.map((subject) => (
              <div key={subject.subject_id} className="rounded-lg border border-ink-600 bg-ink-900/60 p-2.5">
                <div className="flex flex-wrap items-center gap-2">
                  <span className="text-xs font-semibold text-slate-100">{subject.subject_id}</span>
                  <Badge tone={subject.calibration.calibrated ? 'info' : 'unknown'}>
                    {subject.calibration.calibrated ? 'Calibrated (demo)' : 'Uncalibrated'}
                  </Badge>
                  <div className="ml-auto flex gap-1.5">
                    <Button size="sm" disabled={!isOps || busy === subject.subject_id}
                      onClick={() => void calibrate(subject.subject_id)}>Calibrate</Button>
                    <Button size="sm" variant="outline" disabled={!isOps || busy === subject.subject_id}
                      onClick={() => void uncalibrate(subject.subject_id)}>Clear</Button>
                  </div>
                </div>
                {subject.calibration.calibrated ? (
                  <p className="mt-1 font-mono text-[10px] text-slate-500">
                    rest HR {subject.calibration.rest_hr_median?.toFixed(1)} ±{' '}
                    {subject.calibration.rest_hr_scale?.toFixed(2)} bpm · n={subject.calibration.n_windows}
                  </p>
                ) : (
                  <p className="mt-1 text-[10px] text-slate-500">All gates UNKNOWN for this person.</p>
                )}
              </div>
            ))}
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader className="flex-row items-center justify-between">
          <div>
            <CardTitle>Scenario runner</CardTitle>
            <CardDescription>
              Deterministic, labelled test conditions — including the cases that must alert. Gates are
              never tuned to make a scenario pass.
            </CardDescription>
          </div>
          <div className="flex items-center gap-2">
            {running ? <Badge tone="info">Running · t={frame?.t_s.toFixed(0) ?? 0}s</Badge> : null}
            <Button variant="outline" size="sm" onClick={() => void stopScenario()} disabled={!running}>Stop</Button>
          </div>
        </CardHeader>
        <CardContent>
          <div className="grid gap-2 md:grid-cols-2 xl:grid-cols-3">
            {scenarios.map((scenario) => (
              <div key={scenario.scenario_id} className="rounded-lg border border-ink-600 bg-ink-900/60 p-3">
                <div className="flex items-center justify-between gap-2">
                  <span className="text-xs font-semibold text-slate-100">{scenario.label}</span>
                  <Badge tone={scenario.lane === 'INJECTED' ? 'alert' : 'info'}>{scenario.lane}</Badge>
                </div>
                <p className="mt-1 text-[11px] text-slate-400">{scenario.purpose}</p>
                <p className="mt-1 text-[10px] text-slate-500"><strong>Expected:</strong> {scenario.expected}</p>
                <Button size="sm" className="mt-2 w-full" disabled={!isOps && role !== 'crew' && role !== 'flight-surgeon'}
                  onClick={() => void startScenario(scenario.scenario_id)}>
                  Run scenario
                </Button>
              </div>
            ))}
          </div>
          <p className="mt-2 text-[10px] text-slate-500">
            {laneExplanation('SIMULATED')} {laneExplanation('INJECTED')}
          </p>
        </CardContent>
      </Card>

      <Card>
        <CardHeader className="flex-row items-center justify-between">
          <div>
            <CardTitle>Audit chain</CardTitle>
            <CardDescription>
              Append-only local SHA-256 hash chain. Tamper-evident, not tamper-proof, and not a
              blockchain. No raw measurements are stored.
            </CardDescription>
          </div>
          {verify ? (
            <Badge tone={verify.ok ? 'nominal' : 'alert'}>
              {verify.ok ? `Chain intact · ${verify.entries} entries` : `Broken · ${verify.reason}`}
            </Badge>
          ) : null}
        </CardHeader>
        <CardContent>
          {audit.length === 0 ? (
            <EmptyState title="No audit entries visible for this role" />
          ) : (
            <div className="max-h-[360px] overflow-auto">
              <Table>
                <thead><tr><Th>#</Th><Th>Time</Th><Th>Event</Th><Th>Role</Th><Th>Subject</Th><Th>Lane</Th><Th>Hash</Th></tr></thead>
                <tbody>
                  {[...audit].reverse().map((entry) => (
                    <tr key={entry.seq}>
                      <Td>{entry.seq}</Td>
                      <Td>{formatTime(entry.ts)}</Td>
                      <Td className="font-mono">{entry.event}</Td>
                      <Td>{entry.role}</Td>
                      <Td>{entry.subject_id}</Td>
                      <Td>{entry.lane}</Td>
                      <Td className="font-mono text-[10px]">{shortHash(entry.sha256)}</Td>
                    </tr>
                  ))}
                </tbody>
              </Table>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
