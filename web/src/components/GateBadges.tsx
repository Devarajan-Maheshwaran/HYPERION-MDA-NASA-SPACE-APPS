import * as React from 'react';
import type { Frame, GateVerdict } from '../lib/types';
import { outcomeTone, toneClass } from '../lib/status';
import { cn } from '../lib/utils';
import { Badge } from './ui';

const GATE_TITLE: Record<1 | 2 | 3, string> = {
  1: 'Sensor quality',
  2: 'Exercise filter',
  3: 'Uncertainty / staleness',
};

const GATE_RULE: Record<1 | 2 | 3, string> = {
  1: 'Quarantines a window outside this person’s calibrated sensor envelope. Ships uncalibrated: UNKNOWN, never a silent pass.',
  2: 'Blocks a rate alarm only when movement explains it, below the hard ceiling, with no non-rate finding, and within the hold limit.',
  3: 'Holds a ground alarm when a stale manual exam, not the signal, drives the risk — and asks for the fastest crew check.',
};

export function GateBadges({ frame }: { frame: Frame | null }) {
  const [open, setOpen] = React.useState<1 | 2 | 3 | null>(null);
  if (!frame) {
    return (
      <div className="rounded-lg border border-dashed border-ink-600 px-3 py-6 text-center text-xs text-slate-500">
        No gate verdicts yet — no data loaded.
      </div>
    );
  }
  const active = frame.gates.find((gate) => gate.gate === open) ?? null;

  return (
    <div className="space-y-2">
      <div className="grid gap-2 sm:grid-cols-3">
        {frame.gates.map((gate) => (
          <button key={gate.gate} type="button" onClick={() => setOpen(open === gate.gate ? null : gate.gate)}
            className={cn('rounded-lg border p-2.5 text-left transition-colors',
              toneClass(outcomeTone(gate.outcome)),
              open === gate.gate ? 'ring-1 ring-slate-300' : 'hover:brightness-125')}>
            <div className="flex items-center justify-between gap-1">
              <span className="text-[10px] font-bold uppercase tracking-widest">Gate {gate.gate}</span>
              <span className="text-[11px] font-bold">{gate.outcome}</span>
            </div>
            <div className="mt-0.5 text-[11px] font-medium text-slate-200">{GATE_TITLE[gate.gate]}</div>
            <div className="mt-1 line-clamp-2 text-[10px] leading-tight opacity-80">{gate.reason}</div>
          </button>
        ))}
      </div>

      {frame.suppressed ? (
        <div className="rounded-lg border border-sky-500/40 bg-sky-500/10 px-3 py-2 text-xs text-sky-200">
          <strong>Gate 2 blocked an exercise false alarm.</strong> {frame.suppression_reason}
          <div className="mt-0.5 text-[10px] text-sky-300/80">
            Suppression is bounded by a hard HR ceiling and a hold timeout, and never applies to a non-rate finding.
          </div>
        </div>
      ) : null}

      {frame.non_rate_flags.length ? (
        <div className="rounded-lg border border-alert/50 bg-alert/10 px-3 py-2 text-xs text-alert">
          <strong>Non-rate finding — never suppressed:</strong> {frame.non_rate_flags.join(', ')}
        </div>
      ) : null}

      {active ? <GateEvidence gate={active} /> : null}
    </div>
  );
}

function GateEvidence({ gate }: { gate: GateVerdict }) {
  return (
    <div className="rounded-lg border border-ink-600 bg-ink-900/70 p-3">
      <div className="mb-1 flex items-center gap-2">
        <Badge tone={outcomeTone(gate.outcome)}>Gate {gate.gate} · {gate.outcome}</Badge>
        <span className="text-xs text-slate-400">{GATE_TITLE[gate.gate]}</span>
      </div>
      <p className="mb-2 text-[11px] leading-relaxed text-slate-400">{GATE_RULE[gate.gate]}</p>
      <dl className="grid gap-1 sm:grid-cols-2">
        {Object.entries(gate.evidence).map(([key, value]) => (
          <div key={key} className="flex justify-between gap-2 border-b border-ink-700 py-0.5 text-[11px]">
            <dt className="text-slate-500">{key}</dt>
            <dd className="font-mono text-slate-200">{render(value)}</dd>
          </div>
        ))}
      </dl>
    </div>
  );
}

function render(value: unknown): string {
  if (value === null || value === undefined) return 'Not available';
  if (typeof value === 'number') return Number.isInteger(value) ? String(value) : value.toFixed(3);
  if (typeof value === 'boolean') return value ? 'true' : 'false';
  if (Array.isArray(value)) return value.length ? value.join(', ') : 'none';
  return String(value);
}
