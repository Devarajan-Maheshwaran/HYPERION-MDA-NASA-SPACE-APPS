import * as React from 'react';
import {
  Area, CartesianGrid, ComposedChart, Line, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from 'recharts';
import type { Frame } from '../lib/types';
import { formatValue } from '../lib/status';
import { InlineMetric } from './ui';
import { missionClock, num, signed } from '../lib/format';

interface Point {
  t: number;
  hr: number | null;
  residual: number | null;
  band: [number, number] | null;
  activity: number | null;
}

const AXIS_TICK = { fontSize: 10, fill: '#6B7280', fontFamily: 'JetBrains Mono' };
const GRID = 'rgba(255,255,255,0.05)';
const CURSOR = { stroke: 'rgba(255,255,255,0.22)', strokeWidth: 1, strokeDasharray: '3 3' };

function toPoints(history: Frame[]): Point[] {
  return history.map((frame) => ({
    t: Math.round(frame.t_s),
    hr: frame.hr_bpm,
    residual: frame.residual_bpm,
    band: frame.band_lower !== null && frame.band_upper !== null ? [frame.band_lower, frame.band_upper] : null,
    activity: frame.activity_norm,
  }));
}

function InstrumentTooltip({ active, payload, label }: {
  active?: boolean;
  payload?: Array<{ dataKey?: string; value?: number | [number, number]; payload?: Point }>;
  label?: number | string;
}) {
  if (!active || !payload?.length) return null;
  const point = payload[0]?.payload;
  if (!point) return null;
  return (
    <div className="tnum min-w-[160px] rounded-md border border-hairline-strong bg-surface-2/95 px-2.5 py-2 text-[11px] backdrop-blur">
      <div className="mb-1 border-b border-hairline pb-1 text-[10px] text-ink-faint">{missionClock(Number(label))}</div>
      <div className="flex justify-between gap-3"><span className="text-ink-muted">Raw HR</span><span className="text-ink">{num(point.hr)} bpm</span></div>
      <div className="flex justify-between gap-3"><span className="text-ink-muted">Residual</span><span className="text-ink">{signed(point.residual)} bpm</span></div>
      <div className="flex justify-between gap-3"><span className="text-ink-muted">Activity</span><span className="text-ink">{num(point.activity, 2)} ×rest</span></div>
    </div>
  );
}

export function VitalsChart({ history }: { history: Frame[] }) {
  const data = React.useMemo(() => toPoints(history), [history]);
  const bandLabel = history[history.length - 1]?.band_label ?? 'demo band (empirical residual quantile)';

  if (!data.length) {
    return (
      <div className="flex h-[280px] items-center justify-center rounded-lg border border-dashed border-hairline text-xs text-ink-faint">
        No frames yet. Run a scenario to stream data.
      </div>
    );
  }

  return (
    <div className="space-y-2">
      <div className="h-[280px] w-full">
        <ResponsiveContainer width="100%" height="100%">
          <ComposedChart data={data} margin={{ top: 8, right: 12, bottom: 4, left: -18 }} accessibilityLayer>
            <CartesianGrid stroke={GRID} vertical={false} />
            <XAxis dataKey="t" stroke="rgba(255,255,255,0.12)" tickLine={false} tick={AXIS_TICK}
              tickFormatter={(value: number) => `${value}s`} minTickGap={28} />
            <YAxis stroke="rgba(255,255,255,0.12)" tickLine={false} axisLine={false} tick={AXIS_TICK} width={44} />
            <Tooltip content={<InstrumentTooltip />} cursor={CURSOR} isAnimationActive={false} />
            <Area dataKey="band" name={bandLabel} stroke="none" fill="#58A6FF" fillOpacity={0.07}
              connectNulls={false} isAnimationActive={false} />
            <ReferenceLine y={0} stroke="rgba(255,255,255,0.14)" strokeDasharray="3 3" />
            <Line dataKey="hr" name="Raw HR (bpm)" stroke="#F85149" dot={false} strokeWidth={1.5}
              connectNulls={false} isAnimationActive={false} activeDot={{ r: 3, strokeWidth: 0 }} />
            <Line dataKey="residual" name="Exercise-adjusted residual (bpm)" stroke="#58A6FF"
              dot={false} strokeWidth={1.5} connectNulls={false} isAnimationActive={false} activeDot={{ r: 3, strokeWidth: 0 }} />
          </ComposedChart>
        </ResponsiveContainer>
      </div>
      <div className="flex flex-wrap items-center gap-x-4 gap-y-1">
        <Legend colour="#F85149" label="Raw HR" />
        <Legend colour="#58A6FF" label="Exercise-adjusted residual" />
        <Legend colour="rgba(88,166,255,0.25)" label="Demo residual band" />
      </div>
      <p className="text-[10px] leading-relaxed text-ink-faint">
        The shaded band is an empirical quantile of this person&apos;s calibrated resting residual.
        It is a descriptive demo band, <strong>not</strong> a conformal prediction interval and carries
        no coverage guarantee. Residual is observed minus a saturating per-person workload expectation.
      </p>
    </div>
  );
}

export function ActivityChart({ history }: { history: Frame[] }) {
  const data = React.useMemo(() => toPoints(history), [history]);
  if (!data.length) return null;
  return (
    <div className="h-[140px] w-full">
      <ResponsiveContainer width="100%" height="100%">
        <ComposedChart data={data} margin={{ top: 4, right: 12, bottom: 4, left: -18 }} accessibilityLayer>
          <CartesianGrid stroke={GRID} vertical={false} />
          <XAxis dataKey="t" stroke="rgba(255,255,255,0.12)" tickLine={false} tick={AXIS_TICK}
            tickFormatter={(value: number) => `${value}s`} minTickGap={28} />
          <YAxis stroke="rgba(255,255,255,0.12)" tickLine={false} axisLine={false} tick={AXIS_TICK} width={44} />
          <Tooltip content={<InstrumentTooltip />} cursor={CURSOR} isAnimationActive={false} />
          <Line dataKey="activity" name="Activity (personal rest scales)" stroke="#9CA3AC"
            dot={false} strokeWidth={1.5} isAnimationActive={false} connectNulls={false} activeDot={{ r: 3, strokeWidth: 0 }} />
        </ComposedChart>
      </ResponsiveContainer>
    </div>
  );
}

export function FrameStats({ frame }: { frame: Frame | null }) {
  if (!frame) return null;
  return (
    <div className="flex flex-wrap items-end gap-4 border-b border-hairline pb-3">
      <InlineMetric label="Raw HR" value={formatValue(frame.hr_bpm)} unit="bpm" />
      <InlineMetric label="Residual" value={formatValue(frame.residual_bpm)} unit="bpm" />
      <InlineMetric label="Activity" value={formatValue(frame.activity_norm, 2)} unit="×rest" />
      <InlineMetric label="Kurtosis" value={formatValue(frame.sqi.kurtosis, 2)}
        unit={frame.sqi.calibrated ? 'cal' : 'uncal'} />
    </div>
  );
}

function Legend({ colour, label }: { colour: string; label: string }) {
  return (
    <span className="flex items-center gap-1.5">
      <span className="inline-block h-[2px] w-3 rounded-full" style={{ background: colour }} />
      <span className="text-[10px] text-ink-muted">{label}</span>
    </span>
  );
}
