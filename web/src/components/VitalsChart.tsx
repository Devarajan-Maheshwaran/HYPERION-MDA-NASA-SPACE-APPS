import * as React from 'react';
import {
  Area, CartesianGrid, ComposedChart, Legend, Line, ReferenceLine, ResponsiveContainer,
  Tooltip, XAxis, YAxis,
} from 'recharts';
import type { Frame } from '../lib/types';
import { formatValue } from '../lib/status';

interface Point {
  t: number;
  hr: number | null;
  residual: number | null;
  band: [number, number] | null;
  activity: number | null;
}

function toPoints(history: Frame[]): Point[] {
  return history.map((frame) => ({
    t: Math.round(frame.t_s),
    hr: frame.hr_bpm,
    residual: frame.residual_bpm,
    band:
      frame.band_lower !== null && frame.band_upper !== null
        ? [frame.band_lower, frame.band_upper]
        : null,
    activity: frame.activity_norm,
  }));
}

export function VitalsChart({ history }: { history: Frame[] }) {
  const data = React.useMemo(() => toPoints(history), [history]);
  const bandLabel = history[history.length - 1]?.band_label ?? 'demo band (empirical residual quantile)';

  if (!data.length) {
    return (
      <div className="flex h-[280px] items-center justify-center rounded-lg border border-dashed border-ink-600 text-xs text-slate-500">
        No frames yet. Start a scenario in the Ops console to stream data.
      </div>
    );
  }

  return (
    <div className="space-y-2">
      <div className="h-[280px] w-full">
        <ResponsiveContainer width="100%" height="100%">
          <ComposedChart data={data} margin={{ top: 8, right: 12, bottom: 4, left: -8 }}>
            <CartesianGrid stroke="#22304d" strokeDasharray="3 3" />
            <XAxis dataKey="t" stroke="#64748b" tick={{ fontSize: 10 }}
              label={{ value: 'scenario time (s)', position: 'insideBottom', offset: -2, fill: '#64748b', fontSize: 10 }} />
            <YAxis stroke="#64748b" tick={{ fontSize: 10 }} />
            <Tooltip contentStyle={{ background: '#111a2b', border: '1px solid #22304d', fontSize: 11 }}
              labelFormatter={(label) => `t = ${label} s`} />
            <Legend wrapperStyle={{ fontSize: 10 }} />
            <Area dataKey="band" name={bandLabel} stroke="none" fill="#38bdf8" fillOpacity={0.12}
              connectNulls={false} isAnimationActive={false} />
            <ReferenceLine y={0} stroke="#475569" strokeDasharray="4 4" />
            <Line dataKey="hr" name="Raw HR (bpm)" stroke="#fb7185" dot={false} strokeWidth={2}
              connectNulls={false} isAnimationActive={false} />
            <Line dataKey="residual" name="Exercise-adjusted residual (bpm)" stroke="#38bdf8"
              dot={false} strokeWidth={2} connectNulls={false} isAnimationActive={false} />
          </ComposedChart>
        </ResponsiveContainer>
      </div>
      <p className="text-[10px] leading-relaxed text-slate-500">
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
        <ComposedChart data={data} margin={{ top: 4, right: 12, bottom: 4, left: -8 }}>
          <CartesianGrid stroke="#22304d" strokeDasharray="3 3" />
          <XAxis dataKey="t" stroke="#64748b" tick={{ fontSize: 10 }} />
          <YAxis stroke="#64748b" tick={{ fontSize: 10 }} />
          <Tooltip contentStyle={{ background: '#111a2b', border: '1px solid #22304d', fontSize: 11 }} />
          <Line dataKey="activity" name="Activity (personal rest scales)" stroke="#a78bfa"
            dot={false} strokeWidth={2} isAnimationActive={false} connectNulls={false} />
        </ComposedChart>
      </ResponsiveContainer>
    </div>
  );
}

export function FrameStats({ frame }: { frame: Frame | null }) {
  if (!frame) return null;
  return (
    <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
      <MiniStat label="Raw HR" value={`${formatValue(frame.hr_bpm)} bpm`} />
      <MiniStat label="Residual" value={`${formatValue(frame.residual_bpm)} bpm`} />
      <MiniStat label="Activity" value={formatValue(frame.activity_norm, 2)} hint="personal rest scales" />
      <MiniStat label="Kurtosis" value={formatValue(frame.sqi.kurtosis, 2)}
        hint={frame.sqi.calibrated ? 'calibrated' : 'uncalibrated'} />
    </div>
  );
}

function MiniStat({ label, value, hint }: { label: string; value: string; hint?: string }) {
  return (
    <div className="rounded-lg border border-ink-600 bg-ink-900/60 px-3 py-2">
      <div className="text-[10px] font-semibold uppercase tracking-wider text-slate-500">{label}</div>
      <div className="font-mono text-base text-slate-100">{value}</div>
      {hint ? <div className="text-[10px] text-slate-500">{hint}</div> : null}
    </div>
  );
}
