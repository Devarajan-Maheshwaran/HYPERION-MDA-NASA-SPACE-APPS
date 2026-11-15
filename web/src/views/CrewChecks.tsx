import * as React from 'react';
import { motion } from 'motion/react';
import { RefreshCw } from 'lucide-react';
import { api } from '../lib/api';
import { useSession } from '../hooks/useSession';
import type { ManualCheck } from '../lib/types';
import { AlertBanner, Badge, Button, Card, CardContent, CardDescription, CardHeader,
  CardTitle, EmptyState, InlineMetric, Input, Label, Select, Table, Td, Th } from '../components/ui';
import { formatTime } from '../lib/utils';
import { zoneContainer, zoneItem } from '../lib/motion';

type Kind = ManualCheck['kind'];

const KIND_UNIT: Record<Kind, string> = {
  bp: 'mmHg', glucose: 'mg/dL', temperature: 'degC', sleep: 'h', mood: '1-10', onsd: 'mm', pvt: 'ms',
};

const KIND_LABEL: Record<Kind, string> = {
  bp: 'Cuff blood pressure', glucose: 'Fingerstick glucose', temperature: 'Oral temperature',
  sleep: 'Sleep duration', mood: 'Mood score', onsd: 'Optic nerve sheath diameter (ONSD)',
  pvt: 'Reaction test (PVT)',
};

export function CrewChecks() {
  const { subjectId, role } = useSession();
  const [kind, setKind] = React.useState<Kind>('bp');
  const [systolic, setSystolic] = React.useState('');
  const [diastolic, setDiastolic] = React.useState('');
  const [value, setValue] = React.useState('');
  const [checks, setChecks] = React.useState<ManualCheck[]>([]);
  const [message, setMessage] = React.useState<string | null>(null);
  const [error, setError] = React.useState<string | null>(null);
  const [busy, setBusy] = React.useState(false);
  const [loading, setLoading] = React.useState(true);

  const canPost = role === 'crew' || role === 'flight-surgeon';

  const load = React.useCallback(async () => {
    try {
      const data = await api.manual(subjectId);
      setChecks(data.checks);
      setError(null);
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : String(exc));
      setChecks([]);
    } finally {
      setLoading(false);
    }
  }, [subjectId]);

  React.useEffect(() => { setLoading(true); void load(); }, [load]);

  const submit = async (event: React.FormEvent) => {
    event.preventDefault();
    setBusy(true);
    setMessage(null);
    try {
      const payload: Partial<ManualCheck> = {
        subject_id: subjectId, kind, unit: KIND_UNIT[kind],
        systolic: kind === 'bp' ? Number(systolic) : null,
        diastolic: kind === 'bp' ? Number(diastolic) : null,
        value: kind === 'bp' ? null : Number(value),
      };
      await api.postManual(payload);
      setMessage(`${KIND_LABEL[kind]} logged for ${subjectId}.`);
      setSystolic(''); setDiastolic(''); setValue('');
      await load();
    } catch (exc) {
      setMessage(null);
      setError(exc instanceof Error ? exc.message : String(exc));
    } finally {
      setBusy(false);
    }
  };

  return (
    <motion.div variants={zoneContainer} initial="hidden" animate="show"
      className="grid gap-3 lg:grid-cols-[minmax(300px,380px)_minmax(0,1fr)]">
      <div className="space-y-3">
        <motion.div variants={zoneItem}>
          <Card>
            <CardHeader>
              <CardTitle>Log a manual check</CardTitle>
              <CardDescription>
                Crew-entered values are labelled INJECTED and unverified. They drive the demo organ
                rule table and the staleness timer, nothing else.
              </CardDescription>
            </CardHeader>
            <CardContent>
              {!canPost ? (
                <EmptyState title="Not available for this role" detail="Switch to Crew or Flight surgeon to log a check." />
              ) : (
                <form onSubmit={submit} className="space-y-3">
                  <div className="grid gap-1.5">
                    <Label htmlFor="kind">Check type</Label>
                    <Select id="kind" className="h-8 w-full" value={kind} onChange={(event) => setKind(event.target.value as Kind)}>
                      {(Object.keys(KIND_LABEL) as Kind[]).filter((k) => k !== 'pvt').map((item) => (
                        <option key={item} value={item}>{KIND_LABEL[item]}</option>
                      ))}
                    </Select>
                  </div>
                  {kind === 'bp' ? (
                    <div className="grid grid-cols-2 gap-2">
                      <div className="grid gap-1.5">
                        <Label htmlFor="sys">Systolic (mmHg)</Label>
                        <Input id="sys" type="number" inputMode="decimal" required value={systolic}
                          onChange={(event) => setSystolic(event.target.value)} placeholder="122" />
                      </div>
                      <div className="grid gap-1.5">
                        <Label htmlFor="dia">Diastolic (mmHg)</Label>
                        <Input id="dia" type="number" inputMode="decimal" required value={diastolic}
                          onChange={(event) => setDiastolic(event.target.value)} placeholder="78" />
                      </div>
                    </div>
                  ) : (
                    <div className="grid gap-1.5">
                      <Label htmlFor="val">Value ({KIND_UNIT[kind]})</Label>
                      <Input id="val" type="number" step="any" inputMode="decimal" required value={value}
                        onChange={(event) => setValue(event.target.value)} />
                    </div>
                  )}
                  <Button type="submit" disabled={busy}>{busy ? 'Logging…' : 'Log check'}</Button>
                  {message ? <AlertBanner tone="info" title="Logged">{message}</AlertBanner> : null}
                  {error ? <AlertBanner tone="alert" title="Could not log">{error}</AlertBanner> : null}
                </form>
              )}
            </CardContent>
          </Card>
        </motion.div>

        <motion.div variants={zoneItem}><PVTTest /></motion.div>
      </div>

      <motion.div variants={zoneItem} className="min-w-0">
        <Card className="flex h-full flex-col">
          <CardHeader className="flex-row items-center justify-between gap-2">
            <div>
              <CardTitle>Check history · <span className="tnum">{subjectId}</span></CardTitle>
              <CardDescription>Stale entries make the related organ status UNKNOWN, never nominal.</CardDescription>
            </div>
            <Button variant="outline" size="sm" onClick={() => void load()}>
              <RefreshCw size={12} strokeWidth={1.75} /> Refresh
            </Button>
          </CardHeader>
          <CardContent className="min-h-0 flex-1 p-0">
            {loading ? (
              <div className="p-4 text-xs text-ink-faint">Loading checks…</div>
            ) : error ? (
              <div className="p-4"><AlertBanner tone="alert" title="Check history unavailable">{error} — treat as UNKNOWN.</AlertBanner></div>
            ) : checks.length === 0 ? (
              <div className="p-4">
                <EmptyState title="No checks logged" detail="Manual checks are hours or days apart; staleness is tracked per check." />
              </div>
            ) : (
              <div className="max-h-[640px] overflow-auto">
                <Table>
                  <thead><tr><Th>Time</Th><Th>Check</Th><Th className="text-right">Value</Th><Th>Lane</Th></tr></thead>
                  <tbody>
                    {[...checks].reverse().map((check, index) => (
                      <tr key={`${check.recorded_at}-${index}`} className="transition-colors hover:bg-white/[0.02]">
                        <Td>{formatTime(check.recorded_at)}</Td>
                        <Td className="font-sans text-ink">{KIND_LABEL[check.kind]}</Td>
                        <Td className="text-right text-ink">
                          {check.kind === 'bp'
                            ? `${check.systolic ?? '—'}/${check.diastolic ?? '—'} ${check.unit}`
                            : `${check.value ?? '—'} ${check.unit}`}
                        </Td>
                        <Td><Badge tone="watch">{check.lane}</Badge></Td>
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

const PVT_DURATION_MS = 15000;

function PVTTest() {
  const { subjectId, role } = useSession();
  const [phase, setPhase] = React.useState<'idle' | 'waiting' | 'stimulus' | 'done'>('idle');
  const [times, setTimes] = React.useState<number[]>([]);
  const [remaining, setRemaining] = React.useState(15);
  const [result, setResult] = React.useState<{ median: number; lapses: number; n: number } | null>(null);
  const [error, setError] = React.useState<string | null>(null);
  const shownAt = React.useRef(0);
  const timeout = React.useRef<ReturnType<typeof setTimeout> | undefined>(undefined);
  const ticker = React.useRef<ReturnType<typeof setInterval> | undefined>(undefined);
  const endAt = React.useRef(0);
  const collected = React.useRef<number[]>([]);
  const finished = React.useRef(false);
  const canRun = role === 'crew' || role === 'flight-surgeon';

  const clearTimers = React.useCallback(() => {
    if (timeout.current) clearTimeout(timeout.current);
    if (ticker.current) clearInterval(ticker.current);
  }, []);

  React.useEffect(() => clearTimers, [clearTimers]);

  const scheduleStimulus = React.useCallback(() => {
    setPhase('waiting');
    const delay = 1200 + Math.random() * 2300;
    timeout.current = setTimeout(() => {
      shownAt.current = performance.now();
      setPhase('stimulus');
    }, delay);
  }, []);

  const finish = React.useCallback(async (samples: number[]) => {
    if (finished.current) return;
    finished.current = true;
    clearTimers();
    setPhase('done');
    if (!samples.length) {
      setError('No clicks recorded — the test needs at least one response.');
      return;
    }
    try {
      const response = await api.pvt(subjectId, samples);
      setResult({ median: response.median_ms, lapses: response.lapses_over_350ms, n: response.n });
      setError(null);
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : String(exc));
    }
  }, [clearTimers, subjectId]);

  const start = () => {
    clearTimers();
    collected.current = [];
    finished.current = false;
    setTimes([]);
    setResult(null);
    setError(null);
    setRemaining(15);
    endAt.current = performance.now() + PVT_DURATION_MS;
    ticker.current = setInterval(() => {
      const left = Math.max(0, Math.ceil((endAt.current - performance.now()) / 1000));
      setRemaining(left);
      if (left <= 0) void finish(collected.current);
    }, 200);
    scheduleStimulus();
  };

  const click = () => {
    if (phase !== 'stimulus' || finished.current) return;
    const elapsed = performance.now() - shownAt.current;
    collected.current = [...collected.current, elapsed];
    setTimes(collected.current);
    if (performance.now() < endAt.current) scheduleStimulus();
    else void finish(collected.current);
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle>15-second reaction test (PVT)</CardTitle>
        <CardDescription>
          Click as soon as the panel turns bright. Median reaction time is logged as a crew check.
          A demo reaction test, not a validated cognitive assessment.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-3">
        {!canRun ? (
          <EmptyState title="Not available for this role" detail="Switch to Crew or Flight surgeon." />
        ) : (
          <>
            <button type="button" onClick={phase === 'stimulus' ? click : undefined}
              disabled={phase === 'idle' || phase === 'done'}
              className={`tnum flex h-28 w-full items-center justify-center rounded-md border text-base font-semibold transition-colors duration-150 ${
                phase === 'stimulus'
                  ? 'border-accent bg-accent text-base'
                  : 'border-dashed border-hairline bg-base text-ink-faint'
              }`}>
              {phase === 'stimulus' ? 'CLICK NOW' : phase === 'waiting' ? `Wait… ${remaining}s left` :
                phase === 'done' ? 'Test complete' : 'Press Start to begin'}
            </button>
            <div className="flex items-center gap-2">
              <Button onClick={start} disabled={phase === 'waiting' || phase === 'stimulus'}>
                {phase === 'done' ? 'Run again' : 'Start'}
              </Button>
              <span className="tnum text-xs text-ink-faint">{times.length} responses recorded</span>
            </div>
            {result ? (
              <div className="flex flex-wrap items-end gap-4 border-t border-hairline pt-3">
                <InlineMetric label="Median" value={result.median.toFixed(0)} unit="ms" />
                <InlineMetric label="Responses" value={String(result.n)} />
                <InlineMetric label="> 350 ms" value={String(result.lapses)} />
              </div>
            ) : null}
            {error ? <AlertBanner tone="alert" title="Test not logged">{error}</AlertBanner> : null}
          </>
        )}
      </CardContent>
    </Card>
  );
}
