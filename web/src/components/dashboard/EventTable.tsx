import * as React from 'react';
import { motion } from 'motion/react';
import { ArrowUpRight, Copy, Filter } from 'lucide-react';
import { useSession } from '../../hooks/useSession';
import { useShell } from '../AppShell';
import { TIMEFRAME_SECONDS } from '../layout/Topbar';
import { Badge, Button, Drawer, EmptyState, Segmented, StatusDot, Table, Td, Th } from '../ui';
import { missionClock, num, signed } from '../../lib/format';
import { outcomeTone, stateLabel, stateTone } from '../../lib/status';
import type { Frame, GateVerdict } from '../../lib/types';
import { cn } from '../../lib/utils';
import { SPRING } from '../../lib/motion';

type DensityFilter = 'all' | 'suppressed' | 'alerts';

const FILTERS: Array<{ id: DensityFilter; label: string }> = [
  { id: 'all', label: 'All frames' },
  { id: 'suppressed', label: 'Suppressed' },
  { id: 'alerts', label: 'Alerts' },
];

export function EventTable() {
  const { history } = useSession();
  const { timeframe } = useShell();
  const [filter, setFilter] = React.useState<DensityFilter>('all');
  const [selected, setSelected] = React.useState<Frame | null>(null);
  const [copied, setCopied] = React.useState(false);

  const rows = React.useMemo(() => {
    const cutoff = Number.isFinite(TIMEFRAME_SECONDS[timeframe])
      ? (history[history.length - 1]?.t_s ?? 0) - TIMEFRAME_SECONDS[timeframe]
      : Number.NEGATIVE_INFINITY;
    return history
      .filter((frame) => frame.t_s >= cutoff)
      .filter((frame) => filter === 'all'
        || (filter === 'suppressed' && frame.suppressed)
        || (filter === 'alerts' && frame.state === 'SURGEON_ALERT'))
      .slice()
      .reverse();
  }, [history, timeframe, filter]);

  const copyRow = async (frame: Frame) => {
    try {
      await navigator.clipboard.writeText(JSON.stringify(frame, null, 2));
      setCopied(true);
      setTimeout(() => setCopied(false), 1400);
    } catch {
      setCopied(false);
    }
  };

  return (
    <section className="flex flex-col rounded-xl border border-hairline bg-surface">
      <header className="flex flex-wrap items-center justify-between gap-2 border-b border-hairline px-4 py-2.5">
        <div className="flex items-center gap-2">
          <Filter size={13} strokeWidth={1.75} className="text-ink-faint" />
          <h2 className="text-sm font-semibold text-ink">Gate verdict log</h2>
          <span className="tnum text-[10px] text-ink-faint">{rows.length} rows</span>
        </div>
        <div className="flex items-center gap-2">
          {copied ? <span className="tnum text-[10px] text-state-ok">COPIED</span> : null}
          <Segmented options={FILTERS} value={filter} onChange={setFilter} layoutId="event-table-filter" />
        </div>
      </header>

      {rows.length === 0 ? (
        <div className="p-4">
          <EmptyState title="No frames match this filter"
            detail="The log records every evaluated frame with its three gate verdicts. Run a scenario to populate it." />
        </div>
      ) : (
        <div className="max-h-[340px] overflow-auto">
          <Table>
            <thead>
              <tr>
                <Th className="w-[92px]">Mission t</Th>
                <Th className="w-[80px] text-right">HR bpm</Th>
                <Th className="w-[92px] text-right">Residual</Th>
                <Th className="w-[86px] text-right">Activity</Th>
                <Th className="w-[56px] text-center">G1</Th>
                <Th className="w-[56px] text-center">G2</Th>
                <Th className="w-[56px] text-center">G3</Th>
                <Th>State</Th>
                <Th className="w-[120px]">Lane</Th>
                <Th className="w-[76px] text-right">Actions</Th>
              </tr>
            </thead>
            <tbody>
              {rows.map((frame) => (
                <motion.tr
                  key={`${frame.scenario_id}-${frame.t_s}`}
                  layout="position"
                  transition={SPRING}
                  onClick={() => setSelected(frame)}
                  className="group cursor-pointer transition-colors hover:bg-white/[0.025]"
                >
                  <Td className="text-ink">{missionClock(frame.t_s)}</Td>
                  <Td className={cn('text-right', frame.hr_bpm !== null && frame.hr_bpm >= 180 ? 'text-state-alert' : 'text-ink')}>
                    {num(frame.hr_bpm)}
                  </Td>
                  <Td className="text-right">{signed(frame.residual_bpm)}</Td>
                  <Td className="text-right">{num(frame.activity_norm, 2)}</Td>
                  {frame.gates.map((gate) => (
                    <Td key={gate.gate} className="text-center">
                      <GateCell gate={gate} />
                    </Td>
                  ))}
                  <Td>
                    <span className="flex items-center gap-1.5">
                      <StatusDot tone={stateTone(frame.state)} />
                      <span className="font-sans text-[11px] text-ink-secondary">{stateLabel(frame.state)}</span>
                    </span>
                  </Td>
                  <Td className="text-[10px] uppercase tracking-[0.04em] text-ink-faint">{frame.lane}</Td>
                  <Td className="text-right">
                    <span className="flex items-center justify-end gap-0.5 opacity-0 transition-opacity group-hover:opacity-100 focus-within:opacity-100">
                      <Button size="sm" variant="ghost" className="h-5 px-1"
                        onClick={(event) => { event.stopPropagation(); void copyRow(frame); }}
                        aria-label="Copy frame JSON">
                        <Copy size={11} strokeWidth={1.75} />
                      </Button>
                      <Button size="sm" variant="ghost" className="h-5 px-1"
                        onClick={(event) => { event.stopPropagation(); setSelected(frame); }}
                        aria-label="Open frame detail">
                        <ArrowUpRight size={11} strokeWidth={1.75} />
                      </Button>
                    </span>
                  </Td>
                </motion.tr>
              ))}
            </tbody>
          </Table>
        </div>
      )}

      <Drawer
        open={selected !== null}
        title={selected ? `Frame ${missionClock(selected.t_s)}` : 'Frame'}
        subtitle={selected ? `${selected.subject_id} · ${selected.lane} · ${selected.habitat}` : undefined}
        onClose={() => setSelected(null)}
      >
        {selected ? <FrameDetail frame={selected} /> : null}
      </Drawer>
    </section>
  );
}

function GateCell({ gate }: { gate: GateVerdict }) {
  const short = gate.outcome === 'PASS' ? 'PASS' : gate.outcome === 'BLOCK' ? 'BLOCK'
    : gate.outcome === 'HOLD' ? 'HOLD' : 'UNKN';
  return (
    <span data-tone={outcomeTone(gate.outcome)}
      className={cn('tnum inline-block rounded border px-1 py-[1px] text-[9px] font-medium',
        gate.outcome === 'PASS' ? 'border-state-ok/25 bg-state-ok/10 text-state-ok'
          : gate.outcome === 'BLOCK' ? 'border-state-info/30 bg-state-info/10 text-state-info'
          : gate.outcome === 'HOLD' ? 'border-state-watch/25 bg-state-watch/10 text-state-watch'
          : 'border-hairline bg-white/[0.03] text-ink-muted')}>
      {short}
    </span>
  );
}

function FrameDetail({ frame }: { frame: Frame }) {
  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-2">
        <Badge tone={stateTone(frame.state)}>{stateLabel(frame.state)}</Badge>
        <Badge tone="unknown">{frame.lane}</Badge>
        {frame.suppressed ? <Badge tone="info">G2 SUPPRESSED</Badge> : null}
      </div>

      {frame.non_rate_flags.length ? (
        <div className="rounded-md border border-state-alert/30 bg-state-alert/10 px-3 py-2 text-xs text-state-alert">
          Non-rate finding — never suppressed: {frame.non_rate_flags.join(', ')}
        </div>
      ) : null}

      <dl className="grid grid-cols-2 gap-x-4 gap-y-2">
        <Field label="Raw HR" value={`${num(frame.hr_bpm)} bpm`} />
        <Field label="Residual" value={`${signed(frame.residual_bpm)} bpm`} />
        <Field label="Activity" value={`${num(frame.activity_norm, 3)} ×rest`} />
        <Field label="HR status" value={frame.hr_status} />
        <Field label="Kurtosis" value={num(frame.sqi.kurtosis, 3)} />
        <Field label="Slew" value={num(frame.sqi.slew, 2)} />
        <Field label="Band lower" value={num(frame.band_lower)} />
        <Field label="Band upper" value={num(frame.band_upper)} />
      </dl>

      <div className="space-y-2">
        <div className="microlabel">Gate evidence</div>
        {frame.gates.map((gate) => (
          <div key={gate.gate} className="rounded-md border border-hairline bg-base p-2.5">
            <div className="mb-1.5 flex items-center justify-between gap-2">
              <span className="text-xs font-medium text-ink">Gate {gate.gate}</span>
              <GateCell gate={gate} />
            </div>
            <p className="mb-2 text-[11px] leading-snug text-ink-muted">{gate.reason}</p>
            <dl className="space-y-0.5">
              {Object.entries(gate.evidence).map(([key, value]) => (
                <div key={key} className="flex justify-between gap-3 border-b border-hairline/50 py-0.5">
                  <dt className="text-[10px] text-ink-faint">{key}</dt>
                  <dd className="tnum text-[10px] text-ink-secondary">{renderEvidence(value)}</dd>
                </div>
              ))}
            </dl>
          </div>
        ))}
      </div>

      <div>
        <div className="microlabel mb-1.5">Permitted actions</div>
        <div className="flex flex-wrap gap-1.5">
          {frame.actions.map((action) => (
            <span key={action} className="rounded border border-hairline bg-white/[0.03] px-2 py-1 text-[11px] text-ink-secondary">
              {action}
            </span>
          ))}
        </div>
        <p className="mt-2 text-[10px] leading-relaxed text-ink-faint">
          Action text is restricted to four non-treatment strings. No fluid, salt, medication or therapy
          advice is issued by this prototype.
        </p>
      </div>
    </div>
  );
}

function Field({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <dt className="microlabel">{label}</dt>
      <dd className="tnum mt-0.5 text-xs text-ink">{value}</dd>
    </div>
  );
}

function renderEvidence(value: unknown): string {
  if (value === null || value === undefined) return 'Not available';
  if (typeof value === 'number') return Number.isInteger(value) ? String(value) : value.toFixed(3);
  if (typeof value === 'boolean') return value ? 'true' : 'false';
  if (Array.isArray(value)) return value.length ? value.join(', ') : 'none';
  return String(value);
}
