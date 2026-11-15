import * as React from 'react';
import {
  CartesianGrid, ComposedChart, Line, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from 'recharts';
import { Keyboard, MousePointerClick, Radiation, ShieldCheck } from 'lucide-react';
import { api } from '../lib/api';
import { useSession } from '../hooks/useSession';
import type { OrganReading, WorkstationState } from '../lib/types';
import { BodyMap } from '../components/BodyMap';
import { AlertBanner, Badge, Button, Card, CardContent, CardDescription, CardHeader, CardTitle,
  EmptyState, Input, Label, StatusDot, Table, Tabs, TabsContent, Td, Th } from '../components/ui';
import { organTone, stateLabel, stateTone, toneClass } from '../lib/status';
import { missionClock, num, signed } from '../lib/format';
import { cn } from '../lib/utils';

const AXIS = { fontSize: 10, fill: '#6B7280', fontFamily: 'JetBrains Mono' };

export function WorkstationView() {
  const { role, refresh } = useSession();
  const [ws, setWs] = React.useState<WorkstationState | null>(null);
  const [error, setError] = React.useState<string | null>(null);
  const [selected, setSelected] = React.useState<string | null>('heart');
  const [busy, setBusy] = React.useState(false);
  const canControl = role !== 'researcher';

  const load = React.useCallback(async () => {
    try { setWs(await api.state()); setError(null); }
    catch (exc) { setError(exc instanceof Error ? exc.message : String(exc)); }
  }, []);

  React.useEffect(() => {
    void load();
    const timer = setInterval(() => void load(), 1500);
    return () => clearInterval(timer);
  }, [load]);

  const runScenario = async (id: string) => {
    setBusy(true);
    try { setWs(await api.scenario({ scenario_id: id })); await refresh(); }
    catch (exc) { setError(exc instanceof Error ? exc.message : String(exc)); }
    finally { setBusy(false); }
  };
  const setMode = async (mode: string) => {
    setBusy(true);
    try { setWs(await api.scenario({ mode })); await refresh(); }
    catch (exc) { setError(exc instanceof Error ? exc.message : String(exc)); }
    finally { setBusy(false); }
  };
  const setHabitat = async (habitat: string) => {
    try { setWs(await api.scenario({ habitat })); await refresh(); }
    catch (exc) { setError(exc instanceof Error ? exc.message : String(exc)); }
  };

  if (!ws) {
    return <EmptyState title="Loading workstation state" detail={error ?? 'Contacting /api/state…'} />;
  }
  const organ = ws.organs.find((o) => o.system === selected) ?? null;
  const sim = ws.telemetry_mode !== 'REAL_EMPIRICAL';
  const unavailable = ws.telemetry_mode === 'NOT_AVAILABLE';

  return (
    <div className="space-y-3">
      {/* 1. Top avionics bar + provenance */}
      <Card>
        <CardContent className="space-y-2 py-3">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <h1 className="text-lg font-semibold tracking-[-0.01em] text-ink">
              HYPERION-MDA <span className="text-ink-faint">//</span> Onboard Astronaut Health &amp; 3-Stage Clinical Triage Workstation
            </h1>
            <span className="tnum text-xs text-ink-muted">{missionClock(ws.t_s)} · {ws.habitat_label}</span>
          </div>
          <div className="flex flex-wrap items-center gap-1.5">
            {ws.habitat_options.map((h) => (
              <Button key={h.key} size="sm" variant={ws.habitat === h.key ? 'default' : 'outline'}
                disabled={!canControl || busy} onClick={() => void setHabitat(h.key)}>{h.label}</Button>
            ))}
            <span className="mx-1 h-4 w-px bg-hairline" />
            <Button size="sm" variant={ws.data_source_mode === 'REAL_EMPIRICAL' ? 'success' : 'outline'}
              disabled={!canControl || busy} onClick={() => void setMode('REAL_EMPIRICAL')}>🟢 REAL</Button>
            <Button size="sm" variant={sim && !unavailable ? 'default' : 'outline'}
              disabled={!canControl || busy} onClick={() => void setMode('SIMULATED_FALLBACK')}>🟠 SIMULATED</Button>
            {unavailable ? <Badge tone="unknown">TELEMETRY NOT AVAILABLE</Badge> : null}
          </div>
          <div className="flex flex-wrap items-center gap-1.5">
            {ws.demo_scenarios.map((s) => (
              <Button key={s.id} size="sm" variant={ws.scenario_key === s.id ? 'default' : 'outline'}
                disabled={!canControl || busy} onClick={() => void runScenario(s.id)}>{s.label}</Button>
            ))}
          </div>
          <div data-tone={unavailable ? 'unknown' : sim ? 'watch' : 'nominal'} className={cn('rounded-md border px-3 py-2 text-xs font-medium', toneClass(unavailable ? 'unknown' : sim ? 'watch' : 'nominal'))}>
            {unavailable ? '⚪ ' : sim ? '🟠 ' : '🟢 '}{ws.provenance_banner}
          </div>
          {error ? <AlertBanner tone="alert" title="State refresh failed">{error} — treat displayed values as UNKNOWN.</AlertBanner> : null}
        </CardContent>
      </Card>

      {/* 30 / 42 / 28 bento */}
      <div className="grid gap-3 xl:grid-cols-[30fr_42fr_28fr]">
        {/* LEFT */}
        <div className="space-y-3">
          <Card>
            <CardHeader><CardTitle>1 · Clickable 6-system body twin</CardTitle>
              <CardDescription>Demo rule table. Grey = unknown / not available, never healthy.</CardDescription></CardHeader>
            <CardContent><BodyMap organs={ws.organs} selected={selected} onSelect={setSelected} /></CardContent>
          </Card>
          <Card>
            <CardHeader><CardTitle>Selected organ inspector</CardTitle></CardHeader>
            <CardContent><OrganInspector organ={organ} /></CardContent>
          </Card>
        </div>

        {/* CENTER */}
        <div className="min-w-0 space-y-3">
          <Card>
            <CardHeader><CardTitle>2 · Three-stage deterministic trust gate</CardTitle>
              <CardDescription>No neural network or LLM in the decision path.</CardDescription></CardHeader>
            <CardContent><GatePipeline ws={ws} /></CardContent>
          </Card>
          <Card>
            <CardHeader><CardTitle>3 · Live telemetry &amp; residual charts</CardTitle>
              <CardDescription>{ws.overlays.label}</CardDescription></CardHeader>
            <CardContent className="space-y-3">
              <TelemetryCharts ws={ws} />
            </CardContent>
          </Card>
          <Card>
            <CardHeader><CardTitle>NASA-STD-3001 clinical triage decision card</CardTitle>
              <CardDescription>{ws.triage.label}</CardDescription></CardHeader>
            <CardContent><TriageCard ws={ws} /></CardContent>
          </Card>
        </div>

        {/* RIGHT */}
        <div className="space-y-3">
          <Card>
            <CardHeader><CardTitle>4 · Live crew diagnostics</CardTitle>
              <CardDescription>Mouse · camera/image · keyboard. All entries are INJECTED and unverified.</CardDescription></CardHeader>
            <CardContent><DiagnosticsBay ws={ws} onState={setWs} canControl={canControl} /></CardContent>
          </Card>
          <Card>
            <CardHeader><CardTitle>5 · Standard Measures readiness shield</CardTitle></CardHeader>
            <CardContent><ReadinessShield ws={ws} /></CardContent>
          </Card>
        </div>
      </div>

      {/* Bottom bar */}
      <div className="grid gap-3 lg:grid-cols-2">
        <Card>
          <CardHeader><CardTitle>ML training &amp; federated benchmark</CardTitle>
            <CardDescription>{ws.ml_benchmark.provenance}</CardDescription></CardHeader>
          <CardContent><MLPanel ws={ws} /></CardContent>
        </Card>
        <Card>
          <CardHeader><CardTitle>HealthAudit.sol cryptographic audit trail</CardTitle>
            <CardDescription>{ws.audit.contract}</CardDescription></CardHeader>
          <CardContent><AuditPanel ws={ws} /></CardContent>
        </Card>
      </div>
    </div>
  );
}

function OrganInspector({ organ }: { organ: OrganReading | null }) {
  if (!organ) return <p className="text-xs text-ink-faint">Select a system on the body twin.</p>;
  const tau = organ.staleness_tau;
  return (
    <div className="space-y-2 text-xs">
      <div className="flex items-center gap-2">
        <span className="text-sm font-semibold text-ink">{organ.label}</span>
        <Badge tone={organTone(organ.status)}>{organ.status}</Badge>
      </div>
      <p className="text-ink-muted">{organ.hazard}</p>
      <div className="grid grid-cols-2 gap-2">
        <div><div className="microlabel">Value</div><div className="tnum text-ink">{organ.value === null ? 'Not available' : `${num(organ.value)} ${organ.unit}`}</div></div>
        <div><div className="microlabel">Personal baseline z_t</div>
          <div className="tnum text-ink">{organ.z_score === null || organ.z_score === undefined ? 'Not available' : signed(organ.z_score, 2)}</div>
          <div className="text-[10px] text-ink-faint">{organ.baseline_note ?? 'No personal baseline for this indicator.'}</div></div>
      </div>
      <div>
        <div className="microlabel mb-1">Staleness τ = e^(−λΔt)</div>
        <div className="h-1.5 w-full overflow-hidden rounded bg-white/[0.05]">
          <div className="h-full bg-state-info" style={{ width: `${tau === null ? 0 : Math.round(tau * 100)}%` }} />
        </div>
        <div className="tnum mt-0.5 text-[10px] text-ink-faint">{tau === null ? 'Not available' : tau.toFixed(2)} · age {organ.age_hours === null ? '—' : `${num(organ.age_hours)} h`}</div>
      </div>
      <p className="text-[10px] text-ink-faint">{organ.demo_threshold} · {organ.threshold_label}</p>
      <div className="rounded-md border border-hairline bg-base px-2.5 py-2">
        <div className="microlabel">Guided crew action</div>
        <div className="text-ink">{organ.action}</div>
      </div>
    </div>
  );
}

function GatePipeline({ ws }: { ws: WorkstationState }) {
  const frame = ws.frame;
  const g = (n: number) => ws.gates.find((x) => x.gate === n);
  const g1 = g(1), g2 = g(2), g3 = g(3);
  return (
    <div className="space-y-2">
      <div className="grid gap-2 sm:grid-cols-3">
        <GateCard title="Gate 1 · SQI" outcome={g1?.outcome} lines={[
          `Kurtosis: ${num(frame?.sqi.kurtosis, 2)}`, `Slew: ${num(frame?.sqi.slew, 1)}`,
          frame?.sqi.calibrated ? 'Calibrated' : 'Uncalibrated → UNKNOWN']} />
        <GateCard title="Gate 2 · Exercise" outcome={g2?.outcome} lines={[
          'r_HR = HR − f(activity, CO₂)', `Raw HR: ${num(frame?.hr_bpm)} bpm`,
          `ENMO*: ${num(ws.overlays.enmo_g, 2)} g`, `Residual: ${signed(frame?.residual_bpm)} bpm`]} />
        <GateCard title="Gate 3 · Conformal" outcome={g3?.outcome} lines={[
          `U_t: ${num(ws.conformal.upper)} bpm`, `q̂: ${num(ws.conformal.q_hat, 2)} (α=${ws.conformal.alpha})`,
          'σ_epistemic: Not available', `#1 check: ${ws.active_sensing.top?.label ?? '—'}`]} />
      </div>
      {frame?.suppressed ? (
        <div className="rounded-md border border-state-info/30 bg-state-info/10 px-3 py-2 text-xs font-semibold text-state-info">
          🛡️ FALSE ALARM BLOCKED (exercise movement explains high HR) — bounded by hard ceiling + hold timeout.
        </div>
      ) : null}
      {frame?.non_rate_flags.length ? (
        <div className="rounded-md border border-state-alert/30 bg-state-alert/10 px-3 py-2 text-xs text-state-alert">
          Non-rate finding — never suppressed: {frame.non_rate_flags.join(', ')}
        </div>
      ) : null}
      <p className="text-[10px] text-ink-faint">{ws.conformal.label} · {ws.active_sensing.label}</p>
    </div>
  );
}

function GateCard({ title, outcome, lines }: { title: string; outcome?: string; lines: string[] }) {
  const tone = outcome === 'PASS' ? 'nominal' : outcome === 'BLOCK' ? 'info' : outcome === 'HOLD' ? 'watch' : 'unknown';
  return (
    <div data-tone={tone} className={cn('rounded-md border p-2.5', toneClass(tone))}>
      <div className="flex items-center justify-between gap-1">
        <span className="text-[10px] font-semibold uppercase tracking-[0.06em]">{title}</span>
        <span className="tnum text-[11px] font-semibold">{outcome ?? 'UNKNOWN'}</span>
      </div>
      <div className="mt-1 space-y-0.5">
        {lines.map((l) => <div key={l} className="tnum text-[10px] opacity-90">{l}</div>)}
      </div>
    </div>
  );
}

function TelemetryCharts({ ws }: { ws: WorkstationState }) {
  const { role } = useSession();
  const [goesError, setGoesError] = React.useState<string | null>(null);
  const canRefreshGoes = role === 'ops' || role === 'researcher' || role === 'flight-surgeon';
  if (!ws.history.length) return <EmptyState title="No telemetry yet" detail={ws.telemetry_mode === 'NOT_AVAILABLE' ? 'Real mode has no live wearable source. Select a demo scenario for explicitly labelled simulated telemetry.' : 'Select a demo scenario to stream labelled simulated frames.'} />;
  return (
    <>
      <div className="h-[220px] w-full">
        <ResponsiveContainer width="100%" height="100%">
          <ComposedChart data={ws.history} margin={{ top: 6, right: 12, bottom: 0, left: -18 }} accessibilityLayer>
            <CartesianGrid stroke="rgba(255,255,255,0.05)" vertical={false} />
            <XAxis dataKey="t_s" tick={AXIS} tickLine={false} stroke="rgba(255,255,255,0.12)" tickFormatter={(v: number) => `${v}s`} minTickGap={28} />
            <YAxis tick={AXIS} tickLine={false} axisLine={false} stroke="rgba(255,255,255,0.12)" width={40} />
            <Tooltip contentStyle={{ background: '#181B21', border: '1px solid rgba(255,255,255,0.12)', borderRadius: 6, fontSize: 11, fontFamily: 'JetBrains Mono' }} />
            <Line dataKey="hr_bpm" name="Raw HR" stroke="#F85149" strokeWidth={1.5} dot={false} isAnimationActive={false} />
            <Line dataKey="residual_bpm" name="Residual" stroke="#58A6FF" strokeWidth={1.5} dot={false} isAnimationActive={false} />
            <Line dataKey="conformal_upper" name="Demo U_t" stroke="#F59E0B" strokeDasharray="4 3" strokeWidth={1.25} dot={false} isAnimationActive={false} />
          </ComposedChart>
        </ResponsiveContainer>
      </div>
      <div className="h-[140px] w-full">
        <ResponsiveContainer width="100%" height="100%">
          <ComposedChart data={ws.history} margin={{ top: 4, right: 12, bottom: 0, left: -18 }} accessibilityLayer>
            <CartesianGrid stroke="rgba(255,255,255,0.05)" vertical={false} />
            <XAxis dataKey="t_s" tick={AXIS} tickLine={false} stroke="rgba(255,255,255,0.12)" tickFormatter={(v: number) => `${v}s`} minTickGap={28} />
            <YAxis tick={AXIS} tickLine={false} axisLine={false} stroke="rgba(255,255,255,0.12)" width={40} />
            <Tooltip contentStyle={{ background: '#181B21', border: '1px solid rgba(255,255,255,0.12)', borderRadius: 6, fontSize: 11, fontFamily: 'JetBrains Mono' }} />
            <Line dataKey="enmo_g" name="ENMO g (SIM reference)" stroke="#9CA3AC" strokeWidth={1.5} dot={false} isAnimationActive={false} />
            <Line dataKey="co2_mmhg" name="Cabin CO₂ mmHg (SIM)" stroke="#DB6D28" strokeWidth={1.5} dot={false} isAnimationActive={false} />
          </ComposedChart>
        </ResponsiveContainer>
      </div>
      <div className="flex flex-wrap gap-3 text-[10px] text-ink-faint">
        <span>CO₂: <span className="tnum text-ink-secondary">{num(ws.overlays.co2_mmhg)} mmHg</span></span>
        <span>Proton dose: <span className="tnum text-ink-secondary">{ws.overlays.proton_mgy_day === null ? 'Not available' : `${num(ws.overlays.proton_mgy_day)} mGy/d (SIM)`}</span></span>
        <span>GOES: <span className="tnum text-ink-secondary">{ws.sources.goes.available ? 'available' : 'Not available'}</span></span>
        <span>State: <span className="text-ink-secondary">{ws.frame ? stateLabel(ws.frame.state) : '—'}</span></span>
        <Button size="sm" variant="ghost" disabled={!canRefreshGoes}
          onClick={() => void api.refreshGoes().then(() => setGoesError(null)).catch((exc: unknown) => setGoesError(exc instanceof Error ? exc.message : String(exc)))}>
          Refresh GOES
        </Button>
      </div>
      {goesError ? <AlertBanner tone="watch" title="GOES refresh failed">{goesError} — cached/not-available status is unchanged.</AlertBanner> : null}
    </>
  );
}

function TriageCard({ ws }: { ws: WorkstationState }) {
  const tone = ws.triage.tier === 'SURGEON' ? 'alert' : ws.triage.tier === 'CREW' ? 'watch'
    : ws.triage.tier === 'NOMINAL' ? 'nominal' : 'unknown';
  return (
    <div className="space-y-2 text-xs">
      <div className="flex items-center gap-2">
        <Badge tone={tone}>{ws.triage.tier}</Badge>
        <span className="text-ink-secondary">{ws.triage.crew_or_surgeon}</span>
        {ws.frame ? <span className="ml-auto flex items-center gap-1.5"><StatusDot tone={stateTone(ws.frame.state)} />{stateLabel(ws.frame.state)}</span> : null}
      </div>
      <p className="text-ink-muted"><strong className="text-ink">Why:</strong> {ws.triage.why}</p>
      <ol className="list-decimal space-y-1 pl-4 text-ink-secondary">
        {ws.triage.steps.map((s) => <li key={s}>{s}</li>)}
      </ol>
      <div className="flex flex-wrap gap-1.5">
        {ws.triage.actions.map((a) => <span key={a} className="rounded border border-hairline bg-base px-2 py-1 text-[11px] text-ink">{a}</span>)}
      </div>
    </div>
  );
}

function DiagnosticsBay({ ws, onState, canControl }: { ws: WorkstationState; onState: (s: WorkstationState) => void; canControl: boolean }) {
  const [tab, setTab] = React.useState('pvt');
  return (
    <Tabs active={tab} onChange={setTab} label="Crew diagnostics" tabs={[
      { id: 'pvt', label: 'Mouse · PVT' }, { id: 'eye', label: 'Eye scan' }, { id: 'vitals', label: 'Keyboard vitals' },
    ]}>
      <TabsContent value="pvt">{tab === 'pvt' ? <PVTTool onState={onState} canControl={canControl} /> : null}</TabsContent>
      <TabsContent value="eye">{tab === 'eye' ? <UltrasoundTool ws={ws} onState={onState} canControl={canControl} /> : null}</TabsContent>
      <TabsContent value="vitals">{tab === 'vitals' ? <VitalsLogger onState={onState} canControl={canControl} /> : null}</TabsContent>
    </Tabs>
  );
}

const PVT_TRIALS = 5;

function PVTTool({ onState, canControl }: { onState: (s: WorkstationState) => void; canControl: boolean }) {
  const [phase, setPhase] = React.useState<'idle' | 'wait' | 'go' | 'done'>('idle');
  const [left, setLeft] = React.useState(15);
  const [trials, setTrials] = React.useState(0);
  const [error, setError] = React.useState<string | null>(null);
  const samples = React.useRef<number[]>([]);
  const shownAt = React.useRef(0);
  const endAt = React.useRef(0);
  const timeout = React.useRef<ReturnType<typeof setTimeout> | undefined>(undefined);
  const ticker = React.useRef<ReturnType<typeof setInterval> | undefined>(undefined);
  const finished = React.useRef(false);

  const clear = React.useCallback(() => { if (timeout.current) clearTimeout(timeout.current); if (ticker.current) clearInterval(ticker.current); }, []);
  React.useEffect(() => clear, [clear]);

  const finish = React.useCallback(async () => {
    if (finished.current) return;
    finished.current = true; clear(); setPhase('done');
    if (!samples.current.length) { setError('No clicks recorded.'); return; }
    try { onState(await api.examPvt(samples.current)); setError(null); }
    catch (exc) { setError(exc instanceof Error ? exc.message : String(exc)); }
  }, [clear, onState]);

  const schedule = React.useCallback(() => {
    if (performance.now() >= endAt.current || samples.current.length >= PVT_TRIALS) { void finish(); return; }
    setPhase('wait');
    timeout.current = setTimeout(() => { shownAt.current = performance.now(); setPhase('go'); }, 1500 + Math.random() * 2000);
  }, [finish]);

  const start = () => {
    clear(); samples.current = []; finished.current = false; setError(null); setLeft(15); setTrials(0);
    endAt.current = performance.now() + 15000;
    ticker.current = setInterval(() => {
      const l = Math.max(0, Math.ceil((endAt.current - performance.now()) / 1000));
      setLeft(l); if (l <= 0) void finish();
    }, 200);
    schedule();
  };
  const click = () => {
    if (phase !== 'go' || finished.current) return;
    samples.current.push(performance.now() - shownAt.current);
    setTrials(samples.current.length);
    if (samples.current.length >= PVT_TRIALS) void finish();
    else if (performance.now() < endAt.current) schedule();
    else void finish();
  };

  return (
    <div className="space-y-2">
      <button type="button" disabled={!canControl || phase === 'idle' || phase === 'done'} onClick={click}
        className={cn('tnum flex h-24 w-full items-center justify-center rounded-md border text-sm font-semibold transition-colors',
          phase === 'go' ? 'border-state-alert bg-state-alert text-base' : 'border-dashed border-hairline bg-base text-ink-faint')}>
        {phase === 'go' ? 'CLICK NOW' : phase === 'wait' ? `Wait… ${left}s` : phase === 'done' ? 'Submitted' : '15 s · 5-trial click PVT'}
      </button>
      <div className="flex items-center gap-2">
        <Button size="sm" disabled={!canControl || phase === 'wait' || phase === 'go'} onClick={start}>
          <MousePointerClick size={12} strokeWidth={1.75} /> {phase === 'done' ? 'Run again' : 'Start'}
        </Button>
        <span className="tnum text-[10px] text-ink-faint">{trials}/{PVT_TRIALS} trials · random 1.5–3.5 s · resets τ_PVT = 1.0</span>
      </div>
      {error ? <AlertBanner tone="alert" title="PVT not logged">{error}</AlertBanner> : null}
    </div>
  );
}

function UltrasoundTool({ ws, onState, canControl }: { ws: WorkstationState; onState: (s: WorkstationState) => void; canControl: boolean }) {
  const canvasRef = React.useRef<HTMLCanvasElement>(null);
  const imageRef = React.useRef<HTMLImageElement | null>(null);
  const objectUrlRef = React.useRef<string | null>(null);
  const [points, setPoints] = React.useState<Array<{ x: number; y: number }>>([]);
  const [scale, setScale] = React.useState('20');
  const [error, setError] = React.useState<string | null>(null);
  const [custom, setCustom] = React.useState(false);

  const draw = React.useCallback((caliper?: { x1: number; y1: number; x2: number; y2: number }) => {
    const ctx = canvasRef.current?.getContext('2d');
    if (!ctx || !canvasRef.current) return;
    const { width: w, height: h } = canvasRef.current;
    ctx.fillStyle = '#0B0C0E'; ctx.fillRect(0, 0, w, h);
    if (custom && imageRef.current) {
      ctx.drawImage(imageRef.current, 0, 0, w, h);
    } else {
      // Synthetic B-mode fan — NOT a patient image.
      const grad = ctx.createRadialGradient(w / 2, 20, 10, w / 2, 20, h);
      grad.addColorStop(0, '#2A2F38'); grad.addColorStop(1, '#0B0C0E');
      ctx.fillStyle = grad; ctx.beginPath(); ctx.moveTo(w / 2, 10); ctx.arc(w / 2, 10, h - 10, 0.25 * Math.PI, 0.75 * Math.PI); ctx.fill();
      ctx.strokeStyle = '#6E7681'; ctx.lineWidth = 2;
      ctx.beginPath(); ctx.ellipse(w / 2, h * 0.42, w * 0.22, h * 0.2, 0, 0, Math.PI * 2); ctx.stroke();
      ctx.fillStyle = '#181B21'; ctx.fillRect(w / 2 - 14, h * 0.6, 28, h * 0.3);
    }
    const line = caliper ?? (points.length === 2 ? { x1: points[0]!.x, y1: points[0]!.y, x2: points[1]!.x, y2: points[1]!.y } : null);
    if (line) {
      ctx.strokeStyle = '#F59E0B'; ctx.lineWidth = 2;
      ctx.beginPath(); ctx.moveTo(line.x1, line.y1); ctx.lineTo(line.x2, line.y2); ctx.stroke();
      ctx.fillStyle = '#F59E0B';
      for (const p of [ { x: line.x1, y: line.y1 }, { x: line.x2, y: line.y2 } ]) {
        ctx.beginPath(); ctx.arc(p.x, p.y, 3, 0, Math.PI * 2); ctx.fill();
      }
    }
    ctx.fillStyle = '#9CA3AC'; ctx.font = '10px JetBrains Mono';
    ctx.fillText(custom ? 'UPLOADED IMAGE — manual caliper — not a diagnosis' : 'SAMPLE — 3 mm behind globe — not a diagnosis', 8, h - 8);
  }, [points, custom]);

  React.useEffect(() => { draw(custom ? undefined : ws.caliper); }, [draw, ws.caliper, custom]);
  React.useEffect(() => () => { if (objectUrlRef.current) URL.revokeObjectURL(objectUrlRef.current); }, []);

  const sample = async (kind: 'nominal' | 'sans') => {
    imageRef.current = null; setCustom(false); setPoints([]);
    try { onState(await api.examUltrasound({ sample: kind })); setError(null); }
    catch (exc) { setError(exc instanceof Error ? exc.message : String(exc)); }
  };
  const onCanvasClick = (e: React.MouseEvent<HTMLCanvasElement>) => {
    if (!custom || !canvasRef.current) return;
    const rect = e.currentTarget.getBoundingClientRect();
    const p = {
      x: (e.clientX - rect.left) * (canvasRef.current.width / rect.width),
      y: (e.clientY - rect.top) * (canvasRef.current.height / rect.height),
    };
    setPoints((prev) => prev.length >= 2 ? [p] : [...prev, p]);
  };
  const submitCustom = async () => {
    if (points.length !== 2) { setError('Place two caliper points on the image.'); return; }
    const pxPerMm = Number(scale);
    if (!Number.isFinite(pxPerMm) || pxPerMm <= 0) { setError('Enter a positive px/mm scale from the image metadata.'); return; }
    try {
      onState(await api.examUltrasound({ px_per_mm: pxPerMm, x1: points[0]!.x, y1: points[0]!.y, x2: points[1]!.x, y2: points[1]!.y }));
      setError(null);
    } catch (exc) { setError(exc instanceof Error ? exc.message : String(exc)); }
  };
  const upload = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]; if (!file || !canvasRef.current) return;
    if (objectUrlRef.current) URL.revokeObjectURL(objectUrlRef.current);
    const url = URL.createObjectURL(file); objectUrlRef.current = url;
    const img = new Image();
    img.onload = () => {
      imageRef.current = img; setCustom(true); setPoints([]); setError(null);
    };
    img.onerror = () => setError('Could not read that image file.');
    img.src = url;
  };

  return (
    <div className="space-y-2">
      <canvas ref={canvasRef} width={280} height={200} onClick={onCanvasClick}
        className="w-full cursor-crosshair rounded-md border border-hairline" />
      <div className="flex flex-wrap gap-1.5">
        <Button size="sm" variant="outline" disabled={!canControl} onClick={() => void sample('nominal')}>Sample 1 · 4.6 mm</Button>
        <Button size="sm" variant="outline" disabled={!canControl} onClick={() => void sample('sans')}>Sample 2 · 6.1 mm</Button>
      </div>
      <div className="flex items-center gap-2">
        <Label htmlFor="scale" className="shrink-0">px/mm</Label>
        <Input id="scale" className="h-7 w-20" value={scale} onChange={(e) => setScale(e.target.value)} />
        <input type="file" accept="image/*" onChange={upload} disabled={!canControl} className="text-[10px] text-ink-faint" />
        <Button size="sm" disabled={!canControl || !custom} onClick={() => void submitCustom()}>Submit caliper</Button>
      </div>
      {ws.caliper ? <p className="tnum text-[10px] text-ink-faint">ONSD {num(ws.caliper.onsd_mm)} mm · resets τ_ONSD = 1.0 · {ws.caliper.note}</p> : null}
      {error ? <AlertBanner tone="alert" title="Caliper not logged">{error}</AlertBanner> : null}
    </div>
  );
}

function VitalsLogger({ onState, canControl }: { onState: (s: WorkstationState) => void; canControl: boolean }) {
  const [form, setForm] = React.useState({ bp_sys: '', bp_dia: '', glucose_mgdl: '', temp_c: '', sleep_hrs: '', water_ml: '', ared_min: '', mood_score: '' });
  const [error, setError] = React.useState<string | null>(null);
  const [busy, setBusy] = React.useState(false);
  const set = (k: keyof typeof form) => (e: React.ChangeEvent<HTMLInputElement>) => setForm({ ...form, [k]: e.target.value });
  const submit = async (e: React.FormEvent) => {
    e.preventDefault(); setBusy(true);
    const payload: Record<string, unknown> = {};
    for (const [k, v] of Object.entries(form)) if (v !== '') payload[k] = Number(v);
    try { onState(await api.examVitals(payload)); setError(null); setForm({ bp_sys: '', bp_dia: '', glucose_mgdl: '', temp_c: '', sleep_hrs: '', water_ml: '', ared_min: '', mood_score: '' }); }
    catch (exc) { setError(exc instanceof Error ? exc.message : String(exc)); }
    finally { setBusy(false); }
  };
  const fields: Array<[keyof typeof form, string]> = [
    ['bp_sys', 'BP sys (mmHg)'], ['bp_dia', 'BP dia (mmHg)'], ['glucose_mgdl', 'Glucose (mg/dL)'],
    ['temp_c', 'Temp (°C)'], ['sleep_hrs', 'Sleep (h)'], ['water_ml', 'Water (mL)'],
    ['ared_min', 'ARED (min)'], ['mood_score', 'Mood (1–10)'],
  ];
  return (
    <form onSubmit={submit} className="space-y-2">
      <div className="grid grid-cols-2 gap-2">
        {fields.map(([k, label]) => (
          <div key={k} className="grid gap-1">
            <Label htmlFor={k}>{label}</Label>
            <Input id={k} type="number" step="any" inputMode="decimal" value={form[k]} onChange={set(k)} disabled={!canControl} />
          </div>
        ))}
      </div>
      <Button type="submit" size="sm" disabled={!canControl || busy}>
        <Keyboard size={12} strokeWidth={1.75} /> {busy ? 'Logging…' : 'Log crew vitals & re-run 3-stage trust gate'}
      </Button>
      {error ? <AlertBanner tone="alert" title="Could not log">{error}</AlertBanner> : null}
    </form>
  );
}

function ReadinessShield({ ws }: { ws: WorkstationState }) {
  const f = ws.readiness.freshness_tau_avg;
  return (
    <div className="space-y-2">
      <div className="flex items-center gap-2">
        <ShieldCheck size={16} strokeWidth={1.75} className="text-accent" />
        <span className="tnum text-sm text-ink">{ws.readiness.streak_days} d streak</span>
        <span className="ml-auto tnum text-xs text-ink-muted">τ̄ {f === null ? '—' : `${Math.round(f * 100)}%`}</span>
      </div>
      <div className="h-1.5 w-full overflow-hidden rounded bg-white/[0.05]">
        <div className="h-full bg-accent" style={{ width: `${f === null ? 0 : Math.round(f * 100)}%` }} />
      </div>
      <div className="flex flex-wrap gap-1.5">
        {ws.readiness.badges.map((b) => (
          <span key={b.id} className={cn('rounded border px-2 py-0.5 text-[10px]', b.unlocked ? 'border-accent/40 bg-accent-dim text-accent' : 'border-hairline text-ink-faint')}>
            {b.unlocked ? '🛡️' : '🔒'} {b.label}
          </span>
        ))}
      </div>
      <p className="text-[10px] text-ink-faint">{ws.readiness.note} Badges are demo engagement only.</p>
    </div>
  );
}

function MLPanel({ ws }: { ws: WorkstationState }) {
  const ml = ws.ml_benchmark;
  return (
    <div className="space-y-2 text-xs">
      <Table>
        <thead><tr><Th>Requested benchmark</Th><Th>Status</Th><Th className="text-right">Metric</Th></tr></thead>
        <tbody>
          {ml.requested_benchmarks.map((r) => (
            <tr key={r.model}><Td className="font-sans">{r.model}</Td>
              <Td><Badge tone={r.status === 'SIMULATED_TOY_FEDAVG' ? 'info' : 'unknown'}>{r.status}</Badge></Td>
              <Td className="text-right">{r.metric ?? 'Not available'}</Td></tr>
          ))}
        </tbody>
      </Table>
      <Table>
        <thead><tr><Th>Measured M6 HR model</Th><Th className="text-right">MAE (bpm)</Th><Th className="text-right">95% CI</Th></tr></thead>
        <tbody>
          {ml.measured_m6_hr.map((r) => (
            <tr key={r.model}><Td>{r.model}</Td><Td className="text-right">{num(r.mae_bpm, 2)}</Td>
              <Td className="text-right">{r.ci_low === null ? '—' : `[${num(r.ci_low, 2)}, ${num(r.ci_high, 2)}]`}</Td></tr>
          ))}
        </tbody>
      </Table>
      <div className="rounded-md border border-hairline bg-base p-2.5">
        <div className="microlabel mb-1">Not implemented — shown honestly, not fabricated</div>
        <ul className="list-disc space-y-0.5 pl-4 text-[11px] text-ink-muted">
          {ml.not_implemented.map((n) => <li key={n}>{n}</li>)}
        </ul>
      </div>
      <div className="flex flex-wrap items-center gap-2 text-[11px]">
        <Radiation size={13} strokeWidth={1.75} className="text-ink-faint" />
        <span className="text-ink-muted">{ml.fl_simulation.label}</span>
        <Badge tone={ml.cosine_median_demo.caught ? 'nominal' : 'watch'}>
          cosine-median {ml.cosine_median_demo.caught ? 'caught silo-2 bit-flip (SIM)' : 'no flip caught'}
        </Badge>
      </div>
    </div>
  );
}

function AuditPanel({ ws }: { ws: WorkstationState }) {
  return (
    <div className="space-y-2">
      <div className="flex flex-wrap items-center gap-2">
        <Badge tone={ws.audit.verification.ok ? 'nominal' : 'alert'}>
          {ws.audit.verification.ok ? `Chain intact · ${ws.audit.verification.entries}` : ws.audit.verification.reason}
        </Badge>
        <span className="tnum text-[10px] text-state-ok">ZERO RAW PRIVATE HEALTH DATA ON-CHAIN</span>
      </div>
      <p className="text-[10px] text-ink-faint">{ws.audit.contract}. Local SHA-256 hash chain only; no EVM transaction exists.</p>
      <div className="max-h-[220px] overflow-auto">
        <Table>
          <thead><tr><Th>Block #</Th><Th>Event</Th><Th>Lane</Th><Th>Tx hash</Th><Th>SHA-256</Th></tr></thead>
          <tbody>
            {[...ws.audit.entries].reverse().map((e) => (
              <tr key={e.seq}><Td>{e.seq}</Td><Td className="font-sans">{e.event}</Td><Td className="text-[10px]">{e.lane}</Td>
                <Td className="text-[10px] text-ink-faint">— no EVM tx</Td>
                <Td className="text-[10px]" title={e.sha256}>{e.sha256.slice(0, 10)}…{e.sha256.slice(-4)}</Td></tr>
            ))}
          </tbody>
        </Table>
      </div>
    </div>
  );
}
