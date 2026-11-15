import { Check, Circle } from 'lucide-react';
import type { WorkstationState } from '../../lib/types';
import { freshnessPercent } from '../../lib/clinical';
import { num } from '../../lib/format';
import { Badge, Card, Gauge } from '../ui';
import { PVTTool } from './PVTTool';
import { UltrasoundTool } from './UltrasoundTool';
import { VitalsTool } from './VitalsTool';

export type CrewTool = 'pvt' | 'ultrasound' | 'vitals';

export function CrewChecks({ state, activeTool, onSelectTool, onSaved }: {
  state: WorkstationState; activeTool: CrewTool; onSelectTool: (tool: CrewTool) => void; onSaved: () => void;
}) {
  const freshness = freshnessPercent(state.readiness.freshness_tau_avg);
  const freshCount = state.organs.filter((organ) => organ.staleness_tau !== null && organ.staleness_tau >= 0.5).length;
  const staleCount = state.organs.length - freshCount;
  const top = state.active_sensing.top;
  const tools: Array<{ id: CrewTool; label: string; detail: string }> = [
    { id: 'pvt', label: 'Reaction test', detail: '5 clicks · ~15 s' },
    { id: 'ultrasound', label: 'Eye ultrasound', detail: 'ONSD caliper · ~2 min' },
    { id: 'vitals', label: 'Crew vitals', detail: 'Keyboard log · ~1 min' },
  ];

  return (
    <div className="space-y-4">
      <Card className="p-5">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <div className="label-micro">Evidence readiness · not a clinical score</div>
            <div className="mt-1 flex items-baseline gap-2">
              <span className="num text-3xl font-medium text-ink">{freshness === null ? '—' : `${freshness}%`}</span>
              <span className="text-sm text-ink-subtle">average freshness</span>
            </div>
          </div>
          <div className="text-right text-xs text-ink-subtle">
            <div><span className="num font-medium text-ink">{state.readiness.streak_days}</span> day streak · <span className="num">{state.readiness.days_logged}</span> logged</div>
            <div className="mt-1"><span className="num text-nominal-text">{freshCount}</span> fresh · <span className="num text-watch-text">{staleCount}</span> stale / unknown</div>
          </div>
        </div>
        <div className="mt-3"><Gauge value={freshness} tone={freshness !== null && freshness < 50 ? 'watch' : 'nominal'} label="Average evidence freshness" /></div>
        <div className="mt-3 flex flex-wrap items-center gap-2">
          {top ? <Badge tone="watch">Recommended: {top.label}</Badge> : null}
          <span className="text-2xs text-ink-label">{state.readiness.note}</span>
        </div>
        <p className="mt-2 text-2xs leading-4 text-ink-subtle">{state.active_sensing.label}</p>
      </Card>

      <div className="grid grid-cols-3 gap-2" role="tablist" aria-label="Crew check tools">
        {tools.map((tool) => (
          <button
            key={tool.id}
            type="button"
            role="tab"
            aria-selected={activeTool === tool.id}
            onClick={() => onSelectTool(tool.id)}
            className={`rounded-xl border px-3 py-3 text-left transition-colors ${activeTool === tool.id ? 'border-primary bg-white shadow-card' : 'border-line bg-white hover:border-line-strong'}`}
          >
            <div className="flex items-center justify-between gap-1">
              <span className="text-xs font-semibold text-ink sm:text-sm">{tool.label}</span>
              {activeTool === tool.id ? <Check size={13} aria-hidden /> : <Circle size={11} className="text-ink-label" aria-hidden />}
            </div>
            <span className="mt-1 block text-2xs text-ink-subtle">{tool.detail}</span>
          </button>
        ))}
      </div>

      <div role="tabpanel">
        {activeTool === 'pvt' ? <PVTTool onSaved={onSaved} /> : null}
        {activeTool === 'ultrasound' ? <UltrasoundTool onSaved={onSaved} /> : null}
        {activeTool === 'vitals' ? <VitalsTool onSaved={onSaved} /> : null}
      </div>
      <p className="px-1 text-2xs leading-4 text-ink-label">
        Current mean τ̄ = <span className="num">{num(state.readiness.freshness_tau_avg, 3)}</span>. Only submitted indicators are refreshed; this prototype does not claim that every organ becomes 100% fresh after one tool.
      </p>
    </div>
  );
}
