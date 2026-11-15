import * as React from 'react';
import { AnimatePresence, motion } from 'motion/react';
import type { Frame, GateVerdict } from '../lib/types';
import { outcomeTone, toneClass } from '../lib/status';
import { cn } from '../lib/utils';
import { Badge } from './ui';
import { EASE_CRISP, pressable } from '../lib/motion';

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
      <div className="rounded-lg border border-dashed border-hairline px-3 py-6 text-center text-xs text-ink-faint">
        No gate verdicts yet — no data loaded.
      </div>
    );
  }
  const active = frame.gates.find((gate) => gate.gate === open) ?? null;

  return (
    <div className="space-y-2">
      <div className="grid gap-2 sm:grid-cols-3">
        {frame.gates.map((gate) => {
          const isOpen = open === gate.gate;
          return (
            <motion.button key={gate.gate} type="button" {...pressable}
              data-tone={outcomeTone(gate.outcome)}
              aria-expanded={isOpen}
              onClick={() => setOpen(isOpen ? null : gate.gate)}
              className={cn(
                'rounded-md border p-2.5 text-left transition-colors duration-150',
                toneClass(outcomeTone(gate.outcome)),
                isOpen ? 'ring-1 ring-accent/50' : 'hover:brightness-110',
              )}>
              <div className="flex items-center justify-between gap-1">
                <span className="tnum text-[10px] font-semibold uppercase tracking-[0.08em]">Gate {gate.gate}</span>
                <span className="tnum text-[11px] font-semibold">{gate.outcome}</span>
              </div>
              <div className="mt-0.5 text-[11px] font-medium text-ink">{GATE_TITLE[gate.gate]}</div>
              <div className="mt-1 line-clamp-2 text-[10px] leading-tight opacity-80">{gate.reason}</div>
            </motion.button>
          );
        })}
      </div>

      {frame.suppressed ? (
        <div className="rounded-md border border-state-info/30 bg-state-info/10 px-3 py-2 text-xs text-state-info">
          <strong>Gate 2 blocked an exercise false alarm.</strong> {frame.suppression_reason}
          <div className="mt-0.5 text-[10px] opacity-80">
            Suppression is bounded by a hard HR ceiling and a hold timeout, and never applies to a non-rate finding.
          </div>
        </div>
      ) : null}

      {frame.non_rate_flags.length ? (
        <div className="rounded-md border border-state-alert/30 bg-state-alert/10 px-3 py-2 text-xs text-state-alert">
          <strong>Non-rate finding — never suppressed:</strong> {frame.non_rate_flags.join(', ')}
        </div>
      ) : null}

      <AnimatePresence initial={false}>
        {active ? (
          <motion.div key={active.gate}
            initial={{ height: 0, opacity: 0 }} animate={{ height: 'auto', opacity: 1 }}
            exit={{ height: 0, opacity: 0 }} transition={{ duration: 0.2, ease: EASE_CRISP }}
            className="overflow-hidden">
            <GateEvidence gate={active} />
          </motion.div>
        ) : null}
      </AnimatePresence>
    </div>
  );
}

function GateEvidence({ gate }: { gate: GateVerdict }) {
  return (
    <div className="rounded-md border border-hairline bg-base p-3">
      <div className="mb-1 flex items-center gap-2">
        <Badge tone={outcomeTone(gate.outcome)}>Gate {gate.gate} · {gate.outcome}</Badge>
        <span className="text-xs text-ink-muted">{GATE_TITLE[gate.gate]}</span>
      </div>
      <p className="mb-2 text-[11px] leading-relaxed text-ink-muted">{GATE_RULE[gate.gate]}</p>
      <dl className="grid gap-1 sm:grid-cols-2">
        {Object.entries(gate.evidence).map(([key, value]) => (
          <div key={key} className="flex justify-between gap-2 border-b border-hairline/50 py-0.5 text-[11px]">
            <dt className="text-ink-faint">{key}</dt>
            <dd className="tnum text-ink-secondary">{render(value)}</dd>
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
