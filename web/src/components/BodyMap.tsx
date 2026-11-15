import type { OrganReading } from '../lib/types';
import { organTone, toneClass } from '../lib/status';
import { cn } from '../lib/utils';
import { Badge } from './ui';

// Positions on a neutral 200x420 outline. Display only: no risk model, no scores.
const POSITION: Record<string, { x: number; y: number }> = {
  'head-eyes': { x: 100, y: 42 },
  brain: { x: 132, y: 26 },
  'chest-immune': { x: 100, y: 122 },
  heart: { x: 82, y: 138 },
  metabolic: { x: 100, y: 186 },
  bones: { x: 100, y: 280 },
};

const FILL: Record<string, string> = {
  nominal: '#22c55e',
  watch: '#f59e0b',
  alert: '#ef4444',
  unknown: '#64748b',
  info: '#38bdf8',
};

export function BodyMap({
  organs,
  selected,
  onSelect,
}: {
  organs: OrganReading[];
  selected: string | null;
  onSelect: (system: string) => void;
}) {
  return (
    <div className="flex flex-col gap-3 sm:flex-row">
      <svg viewBox="0 0 200 420" className="h-[340px] w-[170px] shrink-0" role="img"
        aria-label="Clickable body map showing demo organ status">
        {/* Neutral outline, deliberately not anatomical detail */}
        <g fill="none" stroke="#334155" strokeWidth="2">
          <circle cx="100" cy="42" r="26" />
          <path d="M100 68 L100 200" />
          <path d="M64 96 L136 96" />
          <path d="M64 96 L52 178" />
          <path d="M136 96 L148 178" />
          <path d="M72 100 L72 200 L128 200 L128 100 Z" />
          <path d="M84 200 L78 330 L70 396" />
          <path d="M116 200 L122 330 L130 396" />
        </g>
        {organs.map((organ) => {
          const pos = POSITION[organ.system];
          if (!pos) return null;
          const tone = organTone(organ.status);
          const isSelected = selected === organ.system;
          return (
            <g key={organ.system} className="cursor-pointer" onClick={() => onSelect(organ.system)}>
              <circle cx={pos.x} cy={pos.y} r={isSelected ? 15 : 12}
                fill={FILL[tone]} fillOpacity={isSelected ? 0.9 : 0.55}
                stroke={isSelected ? '#e2e8f0' : FILL[tone]} strokeWidth={isSelected ? 2.5 : 1.5} />
              <title>{`${organ.label}: ${organ.status}`}</title>
            </g>
          );
        })}
      </svg>

      <div className="grid flex-1 gap-1.5">
        {organs.map((organ) => {
          const tone = organTone(organ.status);
          return (
            <button key={organ.system} type="button" onClick={() => onSelect(organ.system)}
              className={cn(
                'flex items-center justify-between gap-2 rounded-lg border px-3 py-2 text-left transition-colors',
                selected === organ.system ? 'border-slate-400 bg-ink-700' : 'border-ink-600 bg-ink-900/50 hover:bg-ink-700/60',
              )}>
              <div className="min-w-0">
                <div className="truncate text-xs font-semibold text-slate-100">{organ.label}</div>
                <div className="truncate text-[10px] text-slate-500">{organ.indicator}</div>
              </div>
              <span className={cn('shrink-0 rounded border px-1.5 py-0.5 text-[10px] font-bold uppercase',
                toneClass(tone))}>
                {organ.status === 'NOT_AVAILABLE' ? 'N/A' : organ.status}
              </span>
            </button>
          );
        })}
        <p className="mt-1 text-[10px] leading-relaxed text-slate-500">
          Grey means unknown or not available — never healthy. Status comes from a demo rule table
          applied to crew-entered checks, not from a validated clinical model.
        </p>
      </div>
    </div>
  );
}

export function OrganDetail({ organ }: { organ: OrganReading | null }) {
  if (!organ) {
    return <p className="text-xs text-slate-500">Select a system on the body map to see its evidence.</p>;
  }
  return (
    <div className="space-y-2">
      <div className="flex items-center gap-2">
        <h4 className="text-sm font-semibold text-slate-100">{organ.label}</h4>
        <Badge tone={organTone(organ.status)}>{organ.status}</Badge>
      </div>
      <dl className="grid gap-1.5 text-xs">
        <Row label="Indicator" value={organ.indicator} />
        <Row label="Spaceflight hazard" value={organ.hazard} />
        <Row label="Demo threshold" value={organ.demo_threshold} />
        <Row label=" staleness τ" value={organ.staleness_tau === null ? 'Not available' : organ.staleness_tau.toFixed(2)} />
        <Row label="Age" value={organ.age_hours === null ? 'Not available' : `${organ.age_hours.toFixed(1)} h`} />
        <Row label="Evidence" value={organ.evidence} />
      </dl>
      <div className="rounded-lg border border-sky-500/40 bg-sky-500/10 px-3 py-2">
        <div className="text-[10px] font-semibold uppercase tracking-wider text-sky-300">Guided action</div>
        <div className="text-sm font-medium text-slate-100">{organ.action}</div>
      </div>
      <p className="text-[10px] text-slate-500">{organ.threshold_label}</p>
    </div>
  );
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex gap-2">
      <dt className="w-28 shrink-0 capitalize text-slate-500">{label.trim()}</dt>
      <dd className="flex-1 text-slate-300">{value}</dd>
    </div>
  );
}
