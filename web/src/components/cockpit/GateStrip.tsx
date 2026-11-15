import type { GateVerdict } from '../../lib/types';
import { gateTone } from '../../lib/clinical';
import { Badge } from '../ui';
import { cn } from '../../lib/utils';

const META = [
  { gate: 1, title: 'Quality' },
  { gate: 2, title: 'Exertion' },
  { gate: 3, title: 'Freshness' },
] as const;

/** Compact always-visible strip. The full reasoning stays in GatePipeline below it. */
export function GateStrip({ gates, revision }: { gates: GateVerdict[]; revision: number }) {
  return (
    <section aria-label="Live three-gate strip" className="grid grid-cols-3 gap-2">
      {META.map((meta, index) => {
        const gate = gates.find((item) => item.gate === meta.gate);
        const tone = gateTone(gate);
        return (
          <div key={`${meta.gate}-${revision}`}
               className={cn('rounded-lg border bg-white px-3 py-2.5 animate-gate-sweep')}
               style={{ animationDelay: `${index * 120}ms`, animationFillMode: 'both',
                        borderColor: tone === 'nominal' ? '#A7F3D0' : tone === 'watch' ? '#FDE68A' : '#E2E8F0' }}>
            <div className="flex items-center justify-between gap-1">
              <span className="num text-2xs font-bold text-ink-label">G{meta.gate}</span>
              <Badge tone={tone}>{gate?.outcome ?? 'UNKNOWN'}</Badge>
            </div>
            <div className="mt-1 truncate text-2xs font-semibold text-ink" title={meta.title}>{meta.title}</div>
            <p className="mt-0.5 line-clamp-2 text-2xs leading-4 text-ink-subtle">{gate?.reason ?? 'No frame.'}</p>
          </div>
        );
      })}
    </section>
  );
}
