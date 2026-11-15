import * as React from 'react';
import { motion } from 'motion/react';
import { Play, RefreshCw, Square } from 'lucide-react';
import { api } from '../lib/api';
import { useSession } from '../hooks/useSession';
import type { AuditEntry, LaneInfo, ScenarioInfo } from '../lib/types';
import { AlertBanner, Badge, Button, Card, CardContent, CardDescription, CardHeader,
  CardTitle, EmptyState, StatusDot, Table, Td, Th } from '../components/ui';
import { formatTime, shortHash } from '../lib/utils';
import { laneExplanation } from '../lib/status';
import { zoneContainer, zoneItem } from '../lib/motion';
import { missionClock, num } from '../lib/format';

export function OpsConsole() {
  const { role, subjects, startScenario, stopScenario, running, refresh, frame } = useSession();
  const [lanes, setLanes] = React.useState<LaneInfo[]>([]);
  const [scenarios, setScenarios] = React.useState<ScenarioInfo[]>([]);
  const [audit, setAudit] = React.useState<AuditEntry[]>([]);
  const [verify, setVerify] = React.useState<{ ok: boolean; entries: number; reason: string } | null>(null);
  const [error, setError] = React.useState<string | null>(null);
  const [busy, setBusy] = React.useState<string | null>(null);

  const isOps = role === 'ops';
  const canRun = role === 'crew' || role === 'ops' || role === 'flight-surgeon';

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
    <motion.div variants={zoneContainer} initial="hidden" animate="show" className="space-y-3">
      {error ? <AlertBanner tone="alert" title="Ops action failed">{error}</AlertBanner> : null}
      {!isOps ? (
        <AlertBanner tone="watch" title="Calibration is read-only for this role">
          Calibration needs the Ops role. Scenario control is available to Crew, Flight surgeon and Ops.
        </AlertBanner>
      ) : null}

      <div className="grid gap-3 lg:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
        <motion.div variants={zoneItem}>
          <Card className="h-full">
            <CardHeader>
              <CardTitle>Data lanes</CardTitle>
              <CardDescription>Unavailable lanes report the real reason. Nothing is substituted or fabricated.</CardDescription>
            </CardHeader>
            <CardContent className="space-y-1.5">
              {lanes.map((lane) => (
                <div key={lane.lane} className="rounded-md border border-hairline bg-base p-2.5">
                  <div className="flex items-center justify-between gap-2">
                    <span className="tnum text-xs font-semibold text-ink">{lane.lane}</span>
                    <span className="flex items-center gap-1.5">
                      <StatusDot tone={lane.available ? 'nominal' : 'unknown'} />
                      <Badge tone={lane.available ? 'nominal' : 'unknown'}>
                        {lane.available ? 'Available' : 'Not available'}
                      </Badge>
                    </span>
                  </div>
                  <p className="mt-1 text-[11px] leading-snug text-ink-muted">{lane.detail}</p>
                  <p className="mt-0.5 text-[10px] text-ink-faint">{lane.provenance}</p>
                </div>
              ))}
            </CardContent>
          </Card>
        </motion.div>

        <motion.div variants={zoneItem}>
          <Card className="h-full">
            <CardHeader>
              <CardTitle>Per-person calibration</CardTitle>
              <CardDescription>
                Gate 1 and Gate 2 return UNKNOWN until a calibration exists. Calibration here is built
                from a SIMULATED resting window and is a demo calibration, not a clinical one.
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-1.5">
              {subjects.map((subject) => (
                <div key={subject.subject_id} className="rounded-md border border-hairline bg-base p-2.5">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="tnum text-xs font-semibold text-ink">{subject.subject_id}</span>
                    <Badge tone={subject.calibration.calibrated ? 'info' : 'unknown'}>
                      {subject.calibration.calibrated ? 'Calibrated (demo)' : 'Uncalibrated'}
                    </Badge>
                    <div className="ml-auto flex gap-1.5">
                      <Button size="sm" variant="outline" disabled={!isOps || busy === subject.subject_id}
                        onClick={() => void calibrate(subject.subject_id)}>Calibrate</Button>
                      <Button size="sm" variant="ghost" disabled={!isOps || busy === subject.subject_id}
                        onClick={() => void uncalibrate(subject.subject_id)}>Clear</Button>
                    </div>
                  </div>
                  {subject.calibration.calibrated ? (
                    <p className="tnum mt-1 text-[10px] text-ink-faint">
                      rest HR {num(subject.calibration.rest_hr_median)} ± {num(subject.calibration.rest_hr_scale, 2)} bpm · n={subject.calibration.n_windows}
                    </p>
                  ) : (
                    <p className="mt-1 text-[10px] text-ink-faint">All gates UNKNOWN for this person.</p>
                  )}
                </div>
              ))}
            </CardContent>
          </Card>
        </motion.div>
      </div>

      <motion.div variants={zoneItem}>
        <Card>
          <CardHeader className="flex-row flex-wrap items-center justify-between gap-2">
            <div>
              <CardTitle>Scenario runner</CardTitle>
              <CardDescription>
                Deterministic, labelled test conditions — including the cases that must alert. Gates are
                never tuned to make a scenario pass.
              </CardDescription>
            </div>
            <div className="flex items-center gap-2">
              {running ? <Badge tone="info">Running · {missionClock(frame?.t_s ?? 0)}</Badge> : null}
              <Button variant="outline" size="sm" onClick={() => void stopScenario()} disabled={!running || !canRun}>
                <Square size={11} strokeWidth={1.75} /> Stop
              </Button>
            </div>
          </CardHeader>
          <CardContent className="p-0">
            <div className="overflow-auto">
              <Table>
                <thead>
                  <tr><Th>Scenario</Th><Th>Lane</Th><Th className="text-right">Duration</Th><Th>Expected</Th><Th className="text-right">Action</Th></tr>
                </thead>
                <tbody>
                  {scenarios.map((scenario) => (
                    <tr key={scenario.scenario_id} className="transition-colors hover:bg-white/[0.02]">
                      <Td className="font-sans">
                        <div className="text-xs font-medium text-ink">{scenario.label}</div>
                        <div className="mt-0.5 max-w-[320px] whitespace-normal text-[10px] text-ink-faint">{scenario.purpose}</div>
                      </Td>
                      <Td><Badge tone={scenario.lane === 'INJECTED' ? 'watch' : 'unknown'}>{scenario.lane}</Badge></Td>
                      <Td className="text-right">{scenario.duration_s}s</Td>
                      <Td className="max-w-[360px] whitespace-normal font-sans text-[11px]">{scenario.expected}</Td>
                      <Td className="text-right">
                        <Button size="sm" variant="outline" disabled={!canRun}
                          onClick={() => void startScenario(scenario.scenario_id)}>
                          <Play size={11} strokeWidth={1.75} /> Run
                        </Button>
                      </Td>
                    </tr>
                  ))}
                </tbody>
              </Table>
            </div>
            <p className="border-t border-hairline px-4 py-2 text-[10px] text-ink-faint">
              {laneExplanation('SIMULATED')} {laneExplanation('INJECTED')}
            </p>
          </CardContent>
        </Card>
      </motion.div>

      <motion.div variants={zoneItem}>
        <Card>
          <CardHeader className="flex-row flex-wrap items-center justify-between gap-2">
            <div>
              <CardTitle>Audit chain</CardTitle>
              <CardDescription>
                Append-only local SHA-256 hash chain. Tamper-evident, not tamper-proof, and not a
                blockchain. No raw measurements are stored.
              </CardDescription>
            </div>
            <div className="flex items-center gap-2">
              {verify ? (
                <Badge tone={verify.ok ? 'nominal' : 'alert'}>
                  {verify.ok ? `Chain intact · ${verify.entries} entries` : `Broken · ${verify.reason}`}
                </Badge>
              ) : null}
              <Button variant="outline" size="sm" onClick={() => void load()}>
                <RefreshCw size={12} strokeWidth={1.75} /> Verify
              </Button>
            </div>
          </CardHeader>
          <CardContent className="p-0">
            {audit.length === 0 ? (
              <div className="p-4"><EmptyState title="No audit entries visible for this role" /></div>
            ) : (
              <div className="max-h-[360px] overflow-auto">
                <Table>
                  <thead><tr><Th>#</Th><Th>Time</Th><Th>Event</Th><Th>Role</Th><Th>Subject</Th><Th>Lane</Th><Th>Hash</Th></tr></thead>
                  <tbody>
                    {[...audit].reverse().map((entry) => (
                      <tr key={entry.seq} className="transition-colors hover:bg-white/[0.02]">
                        <Td>{entry.seq}</Td>
                        <Td>{formatTime(entry.ts)}</Td>
                        <Td>{entry.event}</Td>
                        <Td className="font-sans">{entry.role}</Td>
                        <Td>{entry.subject_id}</Td>
                        <Td className="text-[10px] uppercase">{entry.lane}</Td>
                        <Td className="text-[10px]">{shortHash(entry.sha256)}</Td>
                      </tr>
                    ))}
                  </tbody>
                </Table>
              </div>
            )}
          </CardContent>
        </Card>
      </motion.div>
    </motion.div>
  );
}
