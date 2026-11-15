import type { KeyboardEvent } from 'react';
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
  nominal: '#3FB950',
  watch: '#DB6D28',
  alert: '#F85149',
  unknown: '#6E7681',
  info: '#58A6FF',
};

export function BodyMap({
  organs, selected, onSelect,
}: {
  organs: OrganReading[];
  selected: string | null;
  onSelect: (system: string) => void;
}) {
  const onKey = (event: KeyboardEvent<SVGGElement>, system: string) => {
    if (event.key === 'Enter' || event.key === ' ') {
      event.preventDefault();
      onSelect(system);
    }
  };

  return (
    <div className="flex flex-col gap-3 sm:flex-row">
      <svg viewBox="0 0 200 420" className="h-[300px] w-[150px] shrink-0" role="group"
        aria-label="Clickable body map showing demo organ status">
        <g fill="none" stroke="rgba(255,255,255,0.12)" strokeWidth="1.5">
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
            <g key={organ.system} role="button" tabIndex={0} aria-pressed={isSelected}
              aria-label={`${organ.label}: ${organ.status}`}
              className="cursor-pointer focus-visible:outline-none"
              onClick={() => onSelect(organ.system)} onKeyDown={(event) => onKey(event, organ.system)}>
              <circle cx={pos.x} cy={pos.y} r={isSelected ? 14 : 11}
                fill={FILL[tone]} fillOpacity={isSelected ? 0.85 : 0.45}
                stroke={isSelected ? '#F59E0B' : FILL[tone]} strokeWidth={isSelected ? 2 : 1.25} />
              <title>{`${organ.label}: ${organ.status}`}</title>
            </g>
          );
        })}
      </svg>

      <div className="grid flex-1 content-start gap-1.5">
        {organs.map((organ) => {
          const tone = organTone(organ.status);
          return (
            <button key={organ.system} type="button" onClick={() => onSelect(organ.system)}
              aria-pressed={selected === organ.system}
              className={cn(
                'flex items-center justify-between gap-2 rounded-md border px-2.5 py-2 text-left transition-colors duration-150',
                selected === organ.system
                  ? 'border-accent/40 bg-accent-dim'
                  : 'border-hairline bg-base hover:bg-white/[0.03]',
              )}>
              <div className="min-w-0">
                <div className="truncate text-xs font-semibold text-ink">{organ.label}</div>
                <div className="truncate text-[10px] text-ink-faint">{organ.indicator}</div>
              </div>
              <span data-tone={tone} className={cn(
                'tnum shrink-0 rounded border px-1.5 py-0.5 text-[10px] font-medium uppercase tracking-[0.06em]',
                toneClass(tone),
              )}>
                {organ.status === 'NOT_AVAILABLE' ? 'N/A' : organ.status}
              </span>
            </button>
          );
        })}
        <p className="mt-1 text-[10px] leading-relaxed text-ink-faint">
          Grey means unknown or not available — never healthy. Status comes from a demo rule table
          applied to crew-entered checks, not from a validated clinical model.
        </p>
      </div>
    </div>
  );
}

export function OrganDetail({ organ }: { organ: OrganReading | null }) {
  if (!organ) {
    return <p className="text-xs text-ink-faint">Select a system on the body map to see its evidence.</p>;
  }
  return (
    <div className="space-y-3">
      <div className="flex items-center gap-2">
        <h4 className="text-sm font-semibold text-ink">{organ.label}</h4>
        <Badge tone={organTone(organ.status)}>{organ.status}</Badge>
      </div>
      <dl className="grid gap-1.5 text-xs">
        <Row label="Indicator" value={organ.indicator} />
        <Row label="Spaceflight hazard" value={organ.hazard} />
        <Row label="Demo threshold" value={organ.demo_threshold} />
        <Row label="Staleness τ" value={organ.staleness_tau === null ? 'Not available' : organ.staleness_tau.toFixed(2)} />
        <Row label="Age" value={organ.age_hours === null ? 'Not available' : `${organ.age_hours.toFixed(1)} h`} />
        <Row label="Evidence" value={organ.evidence} />
      </dl>
      <div className="rounded-md border border-hairline bg-base px-3 py-2">
        <div className="microlabel">Guided action</div>
        <div className="mt-0.5 text-sm font-medium text-ink">{organ.action}</div>
      </div>
      <p className="text-[10px] text-ink-faint">{organ.threshold_label}</p>
    </div>
  );
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex gap-2 border-b border-hairline/50 pb-1">
      <dt className="w-28 shrink-0 text-ink-faint">{label}</dt>
      <dd className="tnum flex-1 text-ink-secondary">{value}</dd>
    </div>
  );
}
