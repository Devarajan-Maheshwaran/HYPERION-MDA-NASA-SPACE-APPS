import * as React from 'react';
import { api } from '../lib/api';
import { useSession } from '../hooks/useSession';
import type { ManualCheck } from '../lib/types';
import { AlertBanner, Badge, Button, Card, CardContent, CardDescription, CardHeader,
  CardTitle, EmptyState, Input, Label, Select, Stat, Table, Td, Th } from '../components/ui';
import { formatTime } from '../lib/utils';

type Kind = ManualCheck['kind'];

const KIND_UNIT: Record<Kind, string> = {
  bp: 'mmHg', glucose: 'mg/dL', temperature: 'degC', sleep: 'h', mood: '1-10',
  onsd: 'mm', pvt: 'ms',
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

  const canPost = role === 'crew' || role === 'flight-surgeon';

  const load = React.useCallback(async () => {
    try {
      const data = await api.manual(subjectId);
      setChecks(data.checks);
      setError(null);
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : String(exc));
    }
  }, [subjectId]);

  React.useEffect(() => { void load(); }, [load]);

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
    <div className="grid gap-4 lg:grid-cols-2">
      <div className="space-y-4">
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
                  <Select id="kind" value={kind} onChange={(event) => setKind(event.target.value as Kind)}>
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
                        onChange={(event) => setSystolic(event.target.value)} placeholder="120" />
                    </div>
                    <div className="grid gap-1.5">
                      <Label htmlFor="dia">Diastolic (mmHg)</Label>
                      <Input id="dia" type="number" inputMode="decimal" required value={diastolic}
                        onChange={(event) => setDiastolic(event.target.value)} placeholder="80" />
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

        <PVTTest />
      </div>

      <Card>
        <CardHeader className="flex-row items-center justify-between">
          <div>
            <CardTitle>Check history · {subjectId}</CardTitle>
            <CardDescription>Stale entries make the related organ status UNKNOWN, never nominal.</CardDescription>
          </div>
          <Button variant="outline" size="sm" onClick={() => void load()}>Refresh</Button>
        </CardHeader>
        <CardContent>
          {checks.length === 0 ? (
            <EmptyState title="No checks logged" detail="Manual checks are hours or days apart; staleness is tracked per check." />
          ) : (
            <div className="max-h-[520px] overflow-auto">
              <Table>
                <thead><tr><Th>Time</Th><Th>Check</Th><Th>Value</Th><Th>Lane</Th></tr></thead>
                <tbody>
                  {[...checks].reverse().map((check, index) => (
                    <tr key={`${check.recorded_at}-${index}`}>
                      <Td>{formatTime(check.recorded_at)}</Td>
                      <Td>{KIND_LABEL[check.kind]}</Td>
                      <Td className="font-mono">
                        {check.kind === 'bp'
                          ? `${check.systolic ?? '—'}/${check.diastolic ?? '—'} ${check.unit}`
                          : `${check.value ?? '—'} ${check.unit}`}
                      </Td>
                      <Td><Badge tone="info">{check.lane}</Badge></Td>
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

const PVT_DURATION_MS = 15000;

function PVTTest() {
  const { subjectId, role } = useSession();
  const [phase, setPhase] = React.useState<'idle' | 'waiting' | 'stimulus' | 'done'>('idle');
  const [times, setTimes] = React.useState<number[]>([]);
  const [remaining, setRemaining] = React.useState(15);
  const [result, setResult] = React.useState<{ median: number; lapses: number; n: number } | null>(null);
  const [error, setError] = React.useState<string | null>(null);
  const shownAt = React.useRef<number>(0);
  const timeout = React.useRef<ReturnType<typeof setTimeout> | undefined>(undefined);
  const ticker = React.useRef<ReturnType<typeof setInterval> | undefined>(undefined);
  const endAt = React.useRef<number>(0);
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

  const finish = React.useCallback(async (collected: number[]) => {
    clearTimers();
    setPhase('done');
    if (!collected.length) {
      setError('No clicks recorded — the test needs at least one response.');
      return;
    }
    try {
      const response = await api.pvt(subjectId, collected);
      setResult({ median: response.median_ms, lapses: response.lapses_over_350ms, n: response.n });
      setError(null);
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : String(exc));
    }
  }, [clearTimers, subjectId]);

  const start = () => {
    setTimes([]);
    setResult(null);
    setError(null);
    setRemaining(15);
    endAt.current = performance.now() + PVT_DURATION_MS;
    ticker.current = setInterval(() => {
      const left = Math.max(0, Math.ceil((endAt.current - performance.now()) / 1000));
      setRemaining(left);
      if (left <= 0) {
        setTimes((current) => { void finish(current); return current; });
      }
    }, 200);
    scheduleStimulus();
  };

  const click = () => {
    if (phase !== 'stimulus') return;
    const elapsed = performance.now() - shownAt.current;
    setTimes((current) => [...current, elapsed]);
    if (performance.now() < endAt.current) scheduleStimulus();
    else void finish([...times, elapsed]);
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
              className={`flex h-32 w-full items-center justify-center rounded-lg border text-lg font-bold transition-colors ${
                phase === 'stimulus'
                  ? 'border-nominal bg-nominal text-ink-900'
                  : phase === 'waiting'
                    ? 'border-ink-600 bg-ink-900 text-slate-500'
                    : 'border-dashed border-ink-600 bg-ink-900 text-slate-500'
              }`}>
              {phase === 'stimulus' ? 'CLICK NOW' : phase === 'waiting' ? `Wait… ${remaining}s left` :
                phase === 'done' ? 'Test complete' : 'Press Start to begin'}
            </button>
            <div className="flex items-center gap-2">
              <Button onClick={start} disabled={phase === 'waiting' || phase === 'stimulus'}>
                {phase === 'done' ? 'Run again' : 'Start'}
              </Button>
              <span className="text-xs text-slate-500">{times.length} responses recorded</span>
            </div>
            {result ? (
              <div className="grid grid-cols-3 gap-2">
                <Stat label="Median" value={`${result.median.toFixed(0)} ms`} />
                <Stat label="Responses" value={result.n} />
                <Stat label="> 350 ms" value={result.lapses} hint="deck's demo indicator" />
              </div>
            ) : null}
            {error ? <AlertBanner tone="alert" title="Test not logged">{error}</AlertBanner> : null}
          </>
        )}
      </CardContent>
    </Card>
  );
}
