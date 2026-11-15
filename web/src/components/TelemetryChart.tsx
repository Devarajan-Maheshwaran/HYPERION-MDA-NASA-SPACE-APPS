import { useEffect, useRef, useState } from 'react';
import { Area, CartesianGrid, ComposedChart, Line, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import type { WorkstationState } from '../lib/types';
import { commsDelay } from '../lib/clinical';
import { num } from '../lib/format';
import { Card, EmptyState } from './ui';

interface ChartPoint {
  t_s: number;
  hr_bpm: number | null;
  residual_bpm: number | null;
  band: [number, number] | null;
}

export function TelemetryChart({ state }: { state: WorkstationState }) {
  const data: ChartPoint[] = state.history.map((point) => ({
    t_s: point.t_s,
    hr_bpm: point.hr_bpm,
    residual_bpm: point.residual_bpm,
    band: point.band_lower !== null && point.band_upper !== null ? [point.band_lower, point.band_upper] : null,
  }));
  const metrics = [
    { label: 'ENMO', value: num(state.overlays.enmo_g, 2), unit: 'g' },
    { label: 'CO₂', value: num(state.overlays.co2_mmhg, 1), unit: 'mmHg' },
    { label: 'Radiation', value: num(state.overlays.proton_mgy_day, 1), unit: 'mGy/d' },
    { label: 'Comms delay', value: commsDelay(state.habitat), unit: '' },
  ];

  return (
    <Card className="overflow-hidden">
      <div className="flex flex-wrap items-center justify-between gap-2 border-b border-line px-5 py-3.5">
        <div>
          <h2 className="text-sm font-semibold">Heart rate, context removed</h2>
          <p className="mt-0.5 text-2xs text-ink-subtle">One chart · raw signal vs exercise/CO₂ residual</p>
        </div>
        <div className="flex items-center gap-4 text-2xs text-ink-subtle">
          <span className="flex items-center gap-1.5"><span className="h-0.5 w-4 bg-ink-subtle" /> Raw HR</span>
          <span className="flex items-center gap-1.5"><span className="h-0.5 w-4 bg-nominal" /> Residual</span>
          <span className="flex items-center gap-1.5"><span className="h-2.5 w-4 rounded-sm bg-nominal/15" /> Demo band</span>
        </div>
      </div>
      {state.telemetry_mode === 'NOT_AVAILABLE' || data.length === 0 ? (
        <EmptyState title="Live telemetry not available" detail="No astronaut wearable is connected. Select a simulated scenario to stress-test the gates; real mode never invents frames." />
      ) : (
        <ChartFrame>
            <ComposedChart data={data} margin={{ top: 6, right: 16, bottom: 0, left: -14 }} accessibilityLayer>
              <CartesianGrid stroke="#E2E8F0" strokeDasharray="3 3" vertical={false} />
              <XAxis dataKey="t_s" tick={{ fill: '#94A3B8', fontSize: 11, fontFamily: 'JetBrains Mono' }} tickLine={false} axisLine={{ stroke: '#E2E8F0' }} tickFormatter={(value: number) => `${value}s`} minTickGap={36} />
              <YAxis tick={{ fill: '#94A3B8', fontSize: 11, fontFamily: 'JetBrains Mono' }} tickLine={false} axisLine={false} width={44} />
              <Tooltip content={<ChartTooltip />} cursor={{ stroke: '#CBD5E1', strokeDasharray: '3 3' }} />
              <Area type="monotone" dataKey="band" stroke="none" fill="#10B981" fillOpacity={0.1} isAnimationActive={false} connectNulls />
              <Line type="monotone" dataKey="hr_bpm" name="Raw HR" stroke="#64748B" strokeWidth={1.6} dot={false} isAnimationActive={false} connectNulls />
              <Line type="monotone" dataKey="residual_bpm" name="Residual" stroke="#10B981" strokeWidth={2} dot={false} isAnimationActive={false} connectNulls />
            </ComposedChart>
        </ChartFrame>
      )}
      <div className="grid grid-cols-2 gap-2 border-t border-line p-3 sm:grid-cols-4">
        {metrics.map((metric) => (
          <div key={metric.label} className="rounded-lg bg-page px-3 py-2">
            <div className="label-micro">{metric.label}</div>
            <div className="num mt-0.5 text-sm font-medium text-ink">{metric.value}{metric.unit ? <span className="ml-1 text-2xs font-normal text-ink-subtle">{metric.unit}</span> : null}</div>
          </div>
        ))}
      </div>
      <p className="border-t border-line px-5 py-2 text-2xs leading-4 text-ink-label">
        Shaded band: demo empirical residual interval. Gate 3 shows the split-conformal upper bound; neither carries a real-astronaut coverage guarantee. Context channels are SIMULATED.
      </p>
    </Card>
  );
}

function ChartFrame({ children }: { children: React.ReactElement }) {
  const ref = useRef<HTMLDivElement | null>(null);
  const [width, setWidth] = useState(0);
  useEffect(() => {
    const node = ref.current;
    if (!node) return;
    const observer = new ResizeObserver((entries) => {
      const next = entries[0]?.contentRect.width ?? 0;
      setWidth(next);
    });
    observer.observe(node);
    setWidth(node.getBoundingClientRect().width);
    return () => observer.disconnect();
  }, []);
  return (
    <div ref={ref} className="h-[240px] px-2 pt-4" aria-label="Raw heart rate and residual chart">
      {width > 0 ? <ResponsiveContainer width="100%" height="100%">{children}</ResponsiveContainer> : null}
    </div>
  );
}

function ChartTooltip({ active, payload, label }: {
  active?: boolean; payload?: Array<{ name?: string; value?: number | string; color?: string }>; label?: number;
}) {
  if (!active || !payload?.length) return null;
  return (
    <div className="rounded-lg border border-line bg-white px-3 py-2 shadow-raised">
      <div className="num text-2xs text-ink-label">T+{label}s</div>
      {payload.filter((item) => item.name === 'Raw HR' || item.name === 'Residual').map((item) => (
        <div key={item.name} className="mt-1 flex items-center gap-2 text-xs">
          <span className="h-1.5 w-1.5 rounded-full" style={{ backgroundColor: item.color }} />
          <span className="text-ink-body">{item.name}</span>
          <span className="num ml-auto font-medium text-ink">{typeof item.value === 'number' ? item.value.toFixed(1) : item.value} bpm</span>
        </div>
      ))}
    </div>
  );
}
