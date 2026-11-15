import * as React from 'react';
import {
  Area, CartesianGrid, ComposedChart, Line, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from 'recharts';
import { motion } from 'motion/react';
import { useSession } from '../../hooks/useSession';
import { useShell } from '../AppShell';
import { TIMEFRAME_OPTIONS, TIMEFRAME_SECONDS } from '../layout/Topbar';
import { InlineMetric, Segmented, Skeleton, StatusDot } from '../ui';
import { missionClock, num, signed } from '../../lib/format';
import { stateLabel, stateTone } from '../../lib/status';
import type { Frame } from '../../lib/types';
import { cn } from '../../lib/utils';

interface Point {
  t: number;
  hr: number | null;
  residual: number | null;
  band: [number, number] | null;
  activity: number | null;
  suppressed: boolean;
  state: string;
}

function toPoints(history: Frame[], windowSeconds: number): Point[] {
  const cutoff = Number.isFinite(windowSeconds)
    ? (history[history.length - 1]?.t_s ?? 0) - windowSeconds
    : Number.NEGATIVE_INFINITY;
  return history.filter((f) => f.t_s >= cutoff).map((frame) => ({
    t: Math.round(frame.t_s),
    hr: frame.hr_bpm,
    residual: frame.residual_bpm,
    band: frame.band_lower !== null && frame.band_upper !== null
      ? [frame.band_lower, frame.band_upper] : null,
    activity: frame.activity_norm,
    suppressed: frame.suppressed,
    state: frame.state,
  }));
}

/** Crosshair tooltip: hairline panel, tabular figures, no drop shadow. */
function CrosshairTooltip({ active, payload, label }: {
  active?: boolean;
  payload?: Array<{ payload?: Point }>;
  label?: number | string;
}) {
  if (!active || !payload?.length) return null;
  const point = payload[0]?.payload;
  if (!point) return null;
  return (
    <div className="pointer-events-none min-w-[168px] rounded-md border border-hairline-strong bg-surface-2/95 px-2.5 py-2 backdrop-blur">
      <div className="tnum mb-1.5 flex items-center justify-between gap-3 border-b border-hairline pb-1.5">
        <span className="text-[10px] text-ink-faint">{missionClock(Number(label))}</span>
        {point.suppressed ? <span className="text-[10px] text-state-info">G2 BLOCK</span> : null}
      </div>
      <dl className="space-y-1">
        <Row label="Raw HR" value={`${num(point.hr)} bpm`} colour="#F85149" />
        <Row label="Residual" value={`${signed(point.residual)} bpm`} colour="#58A6FF" />
        <Row label="Activity" value={`${num(point.activity, 2)} ×rest`} colour="#9CA3AC" />
      </dl>
    </div>
  );
}

function Row({ label, value, colour }: { label: string; value: string; colour: string }) {
  return (
    <div className="flex items-center justify-between gap-3">
      <dt className="flex items-center gap-1.5 text-[10px] text-ink-muted">
        <span className="inline-block h-[2px] w-2.5 rounded-full" style={{ background: colour }} />
        {label}
      </dt>
      <dd className="tnum text-[11px] text-ink">{value}</dd>
    </div>
  );
}

export function TelemetryCanvas() {
  const { history, frame, running, loading } = useSession();
  const { timeframe, setTimeframe } = useShell();
  const data = React.useMemo(() => toPoints(history, TIMEFRAME_SECONDS[timeframe]), [history, timeframe]);
  const suppressedCount = data.filter((point) => point.suppressed).length;

  return (
    <section className="flex h-full flex-col rounded-xl border border-hairline bg-surface">
      {/* Metrics live in the chart header, not in floating boxes. */}
      <header className="flex flex-wrap items-start justify-between gap-3 border-b border-hairline px-4 py-3">
        <div className="flex flex-wrap items-end gap-4">
          <InlineMetric label="Heart rate" value={num(frame?.hr_bpm)} unit="bpm"
            tone={frame?.state === 'SURGEON_ALERT' ? 'alert' : undefined} />
          <InlineMetric label="Workload residual" value={signed(frame?.residual_bpm)} unit="bpm" />
          <InlineMetric label="Activity" value={num(frame?.activity_norm, 2)} unit="×rest" />
          <InlineMetric label="Kurtosis" value={num(frame?.sqi.kurtosis, 2)}
            unit={frame?.sqi.calibrated ? 'cal' : 'uncal'} />
        </div>
        <div className="flex flex-col items-end gap-1">
          <span className="flex items-center gap-1.5">
            <StatusDot tone={frame ? stateTone(frame.state) : 'unknown'} pulse={running} />
            <span className="text-xs font-medium text-ink">{frame ? stateLabel(frame.state) : 'No data'}</span>
          </span>
          <span className="tnum text-[10px] text-ink-faint">
            {frame ? missionClock(frame.t_s) : 'T+----s'} · {data.length} samples
          </span>
          <Segmented className="md:hidden" options={TIMEFRAME_OPTIONS} value={timeframe}
            onChange={setTimeframe} layoutId="canvas-timeframe-mobile" />
        </div>
      </header>

      <div className="relative min-h-[260px] flex-1 px-1 py-3">
        {loading ? (
          <div className="space-y-2 p-3">
            <Skeleton className="h-[180px] w-full" />
            <Skeleton className="h-3 w-1/3" />
          </div>
        ) : data.length === 0 ? (
          <div className="flex h-full min-h-[240px] flex-col items-center justify-center gap-1.5">
            <span className="text-sm text-ink-secondary">No telemetry in this window</span>
            <span className="max-w-xs text-center text-xs text-ink-faint">
              Run a scenario from the command palette or the primary action. Nothing is plotted until frames arrive.
            </span>
          </div>
        ) : (
          <ResponsiveContainer width="100%" height="100%">
            <ComposedChart data={data} margin={{ top: 6, right: 14, bottom: 0, left: -18 }} accessibilityLayer>
              <CartesianGrid stroke="rgba(255,255,255,0.05)" strokeDasharray="0" vertical={false} />
              <XAxis dataKey="t" stroke="rgba(255,255,255,0.12)" tickLine={false}
                tick={{ fontSize: 10, fill: '#6B7280', fontFamily: 'JetBrains Mono' }}
                tickFormatter={(value: number) => `${value}s`} minTickGap={28} />
              <YAxis stroke="rgba(255,255,255,0.12)" tickLine={false} axisLine={false}
                tick={{ fontSize: 10, fill: '#6B7280', fontFamily: 'JetBrains Mono' }} width={44} />
              <Area dataKey="band" stroke="none" fill="#58A6FF" fillOpacity={0.07}
                isAnimationActive={false} connectNulls={false} />
              <ReferenceLine y={0} stroke="rgba(255,255,255,0.14)" strokeDasharray="3 3" />
              {/* Custom crosshair: vertical hairline + instrument tooltip. */}
              <Tooltip
                content={<CrosshairTooltip />}
                cursor={{ stroke: 'rgba(255,255,255,0.22)', strokeWidth: 1, strokeDasharray: '3 3' }}
                isAnimationActive={false}
              />
              <Line dataKey="hr" stroke="#F85149" strokeWidth={1.5} dot={false}
                isAnimationActive={false} connectNulls={false} activeDot={{ r: 3, strokeWidth: 0, fill: '#F85149' }} />
              <Line dataKey="residual" stroke="#58A6FF" strokeWidth={1.5} dot={false}
                isAnimationActive={false} connectNulls={false} activeDot={{ r: 3, strokeWidth: 0, fill: '#58A6FF' }} />
            </ComposedChart>
          </ResponsiveContainer>
        )}
      </div>

      <footer className="flex flex-wrap items-center gap-x-4 gap-y-1 border-t border-hairline px-4 py-2">
        <Legend colour="#F85149" label="Raw HR" />
        <Legend colour="#58A6FF" label="Exercise-adjusted residual" />
        <Legend colour="rgba(88,166,255,0.25)" label="Demo residual band" />
        {suppressedCount > 0 ? (
          <motion.span initial={{ opacity: 0 }} animate={{ opacity: 1 }}
            className="tnum ml-auto text-[10px] text-state-info">
            {suppressedCount} frames suppressed by Gate 2
          </motion.span>
        ) : null}
      </footer>
      <p className="border-t border-hairline px-4 py-2 text-[10px] leading-relaxed text-ink-faint">
        Band is an empirical quantile of this person&apos;s calibrated resting residual — descriptive, not a
        conformal interval, and carries no coverage guarantee. Activity is per-person rest scales, not ENMO in g.
      </p>
    </section>
  );
}

function Legend({ colour, label }: { colour: string; label: string }) {
  return (
    <span className="flex items-center gap-1.5">
      <span className={cn('inline-block h-[2px] w-3 rounded-full')} style={{ background: colour }} />
      <span className="text-[10px] text-ink-muted">{label}</span>
    </span>
  );
}
