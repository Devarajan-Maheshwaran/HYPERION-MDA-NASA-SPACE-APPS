import { ArrowRight, ShieldCheck } from 'lucide-react';
import type { GateVerdict, WorkstationState } from '../lib/types';
import { gateTone } from '../lib/clinical';
import { num } from '../lib/format';
import { Badge, Button } from './ui';
import { cn } from '../lib/utils';

const GATE_META = [
  { gate: 1, title: 'Signal quality', subtitle: 'Is this sensor window trustworthy?' },
  { gate: 2, title: 'Exertion residualizer', subtitle: 'Does movement explain the heart rate?' },
  { gate: 3, title: 'Uncertainty & freshness', subtitle: 'Should a crew check happen before escalation?' },
] as const;

export function GatePipeline({ state, revision, onOpenCheck }: {
  state: WorkstationState; revision: number; onOpenCheck: () => void;
}) {
  const gate2 = state.gates.find((gate) => gate.gate === 2);
  const blocked = gate2?.outcome === 'BLOCK';

  return (
    <section aria-label="Three-stage deterministic safety gate">
      <div className="mb-3 flex items-center justify-between">
        <h2 className="text-md font-semibold">3-Stage Deterministic Safety Gate</h2>
        <span className="label-micro">No LLM in the decision path</span>
      </div>
      <ol className="space-y-2">
        {GATE_META.map((meta, index) => {
          const gate = state.gates.find((item) => item.gate === meta.gate);
          return (
            <li key={`${meta.gate}-${revision}`} className={cn('rounded-xl border border-line bg-white', 'animate-gate-sweep')} style={{ animationDelay: `${index * 450}ms`, animationFillMode: 'both' }}>
              <GateRow meta={meta} gate={gate} state={state} />
              {meta.gate === 2 && blocked ? (
                <div className="mx-4 mb-4 flex items-start gap-2 rounded-lg border border-watch/25 bg-watch-soft px-3 py-2.5 text-watch-text">
                  <ShieldCheck size={16} className="mt-0.5 shrink-0" aria-hidden />
                  <p className="text-xs font-semibold leading-5">
                    FALSE ALARM BLOCKED — High HR (<span className="num">{num(state.frame?.hr_bpm, 0)} bpm</span>) matches <span className="num">{num(state.overlays.enmo_g, 2)}g</span> Exercise Load
                  </p>
                </div>
              ) : null}
              {meta.gate === 3 ? (
                <div className="mx-4 mb-4 flex flex-wrap items-center justify-between gap-3 rounded-lg bg-page px-3 py-2.5">
                  <span className="num text-xs text-ink-body">U_t = ŷ + q̂₁₋α · demo quantile, no coverage guarantee</span>
                  <Button variant="secondary" size="sm" onClick={onOpenCheck}>
                    Open Recommended Crew Check <ArrowRight size={13} aria-hidden />
                  </Button>
                </div>
              ) : null}
            </li>
          );
        })}
      </ol>
    </section>
  );
}

function GateRow({ meta, gate, state }: {
  meta: (typeof GATE_META)[number]; gate: GateVerdict | undefined; state: WorkstationState;
}) {
  const tone = gateTone(gate);
  return (
    <div className="flex items-start gap-3 px-4 py-3.5">
      <span className="num mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-full border border-line bg-page text-xs font-medium text-ink">
        {meta.gate}
      </span>
      <div className="min-w-0 flex-1">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <h3 className="text-sm font-semibold">{meta.title}</h3>
          <Badge tone={tone}>{gate?.outcome ?? 'UNKNOWN'}</Badge>
        </div>
        <p className="mt-0.5 text-xs text-ink-subtle">{meta.subtitle}</p>
        <p className="mt-1.5 text-xs leading-5 text-ink-body">{gate?.reason ?? 'No telemetry frame is available.'}</p>
        <GateEvidence gate={meta.gate} evidence={gate?.evidence ?? {}} state={state} />
      </div>
    </div>
  );
}

function GateEvidence({ gate, evidence, state }: {
  gate: 1 | 2 | 3; evidence: Record<string, unknown>; state: WorkstationState;
}) {
  if (gate === 1) {
    return (
      <div className="num mt-2 flex flex-wrap gap-x-4 gap-y-1 text-2xs text-ink-subtle">
        <span>kurtosis <b className="font-medium text-ink">{num(asNumber(evidence['kurtosis']), 2)}</b></span>
        <span>slew <b className="font-medium text-ink">{num(asNumber(evidence['slew']), 1)}</b></span>
        <span>calibrated <b className="font-medium text-ink">{evidence['calibrated'] ? 'yes' : 'no'}</b></span>
      </div>
    );
  }
  if (gate === 2) {
    return (
      <div className="mt-2 rounded-md border border-line bg-page px-2.5 py-2">
        <div className="num text-xs text-ink">r_HR = HR − f(ENMO, CO₂)</div>
        <div className="num mt-1 flex flex-wrap gap-x-4 gap-y-1 text-2xs text-ink-subtle">
          <span>HR {num(asNumber(evidence['hr_bpm']), 0)} bpm</span>
          <span>residual {num(asNumber(evidence['residual_bpm']), 1)} bpm</span>
          <span>activity {num(asNumber(evidence['activity_norm']), 2)} × rest scale</span>
        </div>
        <p className="mt-1 text-2xs leading-4 text-ink-label">The gate uses per-person normalized activity, not raw ENMO grams.</p>
      </div>
    );
  }
  return (
    <div className="num mt-2 flex flex-wrap gap-x-4 gap-y-1 text-2xs text-ink-subtle">
      <span>ŷ {num(state.conformal.prediction, 1)} bpm</span>
      <span>q̂ {num(state.conformal.q_hat, 2)}</span>
      <span>U_t {num(state.conformal.upper, 1)} bpm</span>
      <span>τ_min {num(asNumber(evidence['min_tau']), 2)}</span>
    </div>
  );
}

function asNumber(value: unknown): number | null {
  return typeof value === 'number' && Number.isFinite(value) ? value : null;
}
