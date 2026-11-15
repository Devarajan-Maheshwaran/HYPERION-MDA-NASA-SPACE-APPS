import { ArrowUpRight } from 'lucide-react';
import type { OrganReading } from '../lib/types';
import { freshnessPercent, organSummary, organTone } from '../lib/clinical';
import { num, signed } from '../lib/format';
import { Badge, Card, Gauge, MetricTile } from './ui';

export function OrganDetail({ organ }: { organ: OrganReading }) {
  const tone = organTone(organ.status);
  const freshness = freshnessPercent(organ.staleness_tau);
  const surgeon = organ.status === 'ALERT';

  return (
    <Card className="p-5" aria-live="polite">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h2 className="text-lg font-semibold">{organ.label}</h2>
        <Badge tone={tone}>{organ.status}</Badge>
      </div>
      <div className="mt-2">
        <Badge tone="neutral">{organ.hazard}</Badge>
      </div>
      <p className="mt-3 text-sm leading-6 text-ink-body">{organSummary(organ)}</p>

      <div className="mt-4 grid grid-cols-3 gap-2">
        <MetricTile label="Measurement" value={num(organ.value)} unit={organ.unit} detail={<span className="num">{organ.indicator}</span>} />
        <MetricTile label="Personal z" value={signed(organ.z_score)} detail={organ.z_score === null || organ.z_score === undefined ? 'No baseline' : 'vs rest baseline'} />
        <div className="rounded-lg border border-line bg-page px-3 py-3">
          <div className="label-micro">Freshness τ</div>
          <div className="num mt-1.5 text-lg font-medium text-ink">{freshness === null ? '—' : `${freshness}%`}</div>
          <div className="mt-2"><Gauge value={freshness} tone={freshness !== null && freshness < 50 ? 'watch' : 'neutral'} label={`${organ.label} freshness`} /></div>
          <div className="num mt-1 text-2xs text-ink-subtle">{organ.age_hours === null ? 'No timestamp' : `${num(organ.age_hours)} h old`}</div>
        </div>
      </div>

      <div className="mt-4 rounded-lg border border-line bg-page p-3">
        <div className="flex items-center justify-between gap-2">
          <span className="label-micro">Clinical action · demo rule</span>
          <span className="inline-flex items-center gap-1 text-2xs font-medium text-ink-subtle">
            {surgeon ? 'Flight surgeon' : 'Crew self-care'} <ArrowUpRight size={12} aria-hidden />
          </span>
        </div>
        <p className="num mt-1.5 text-xs leading-5 text-ink">{organ.demo_threshold}</p>
        <p className="mt-1 text-2xs text-ink-label">{organ.threshold_label}</p>
        <div className="mt-2 border-t border-line pt-2 text-sm font-medium text-ink">{organ.action}</div>
        <p className="mt-1 text-2xs leading-4 text-ink-subtle">{organ.evidence}</p>
      </div>
    </Card>
  );
}
