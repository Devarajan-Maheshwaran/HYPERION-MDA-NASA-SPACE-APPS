import { Activity, Eye, HeartPulse } from 'lucide-react';
import type { WorkstationState } from '../../lib/types';
import { freshnessPercent } from '../../lib/clinical';
import { num } from '../../lib/format';
import { PVTTool } from '../checks/PVTTool';
import { UltrasoundTool } from '../checks/UltrasoundTool';
import { VitalsTool } from '../checks/VitalsTool';
import type { CrewTool } from '../checks/CrewChecks';
import { Badge, Card, Gauge } from '../ui';
import { cn } from '../../lib/utils';

const TOOLS: Array<{ id: CrewTool; label: string; detail: string; icon: typeof Activity }> = [
  { id: 'pvt', label: 'PVT', detail: '5 clicks · ~15 s', icon: Activity },
  { id: 'ultrasound', label: 'Eye ONSD', detail: 'Caliper · ~2 min', icon: Eye },
  { id: 'vitals', label: 'Vitals', detail: 'Keyboard · ~1 min', icon: HeartPulse },
];

/** Always visible: the astronaut in the seat must never hunt for the tool that
 *  resolves the current hold. When S2 is active the recommended tool auto-focuses
 *  and the bay pulses amber until the exam is submitted. */
export function InstrumentBay({ state, activeTool, onSelectTool, onSaved }: {
  state: WorkstationState; activeTool: CrewTool; onSelectTool: (tool: CrewTool) => void; onSaved: () => void;
}) {
  const actionRequired = state.lifecycle?.action_required ?? false;
  const recommended = state.lifecycle?.requested_exam === 'ultrasound'
    ? 'ultrasound'
    : state.active_sensing.top?.exam === 'onsd' ? 'ultrasound'
      : state.active_sensing.top?.exam === 'pvt' ? 'pvt' : 'vitals';
  const freshness = freshnessPercent(state.readiness.freshness_tau_avg);

  return (
    <Card className={cn('overflow-hidden', actionRequired && 'ring-2 ring-watch/60')}>
      <div className={cn('border-b px-4 py-3', actionRequired ? 'border-watch/30 bg-watch-soft' : 'border-line')}>
        <div className="flex items-center justify-between gap-2">
          <span className="label-micro">Instrument bay · always on</span>
          <Badge tone={actionRequired ? 'watch' : 'neutral'}>τ̄ {num(state.readiness.freshness_tau_avg, 2)}</Badge>
        </div>
        {actionRequired ? (
          <p className="num mt-1.5 text-2xs font-bold text-watch-text animate-pulse" role="alert">
            ACTION REQUIRED TO RESOLVE S2 HOLD
          </p>
        ) : (
          <p className="mt-1 text-2xs leading-4 text-ink-subtle">
            Recommended next: {state.active_sensing.top?.label ?? 'no exam pending'}
          </p>
        )}
        <div className="mt-2">
          <Gauge value={freshness} tone={freshness !== null && freshness < 50 ? 'watch' : 'nominal'} label="Average evidence freshness" />
        </div>
      </div>

      <div className="grid grid-cols-3 gap-1.5 p-2" role="tablist" aria-label="Crew instruments">
        {TOOLS.map((tool) => {
          const Icon = tool.icon;
          const selected = activeTool === tool.id;
          const urgent = actionRequired && recommended === tool.id;
          return (
            <button
              key={tool.id}
              type="button"
              role="tab"
              aria-selected={selected}
              onClick={() => onSelectTool(tool.id)}
              className={cn(
                'rounded-lg border px-2 py-2.5 text-left transition-colors',
                selected ? 'border-primary bg-page' : 'border-line bg-white hover:border-line-strong',
                urgent && !selected && 'border-watch bg-watch-soft animate-pulse',
              )}
            >
              <Icon size={14} className={selected ? 'text-ink' : 'text-ink-subtle'} aria-hidden />
              <div className="mt-1 text-2xs font-bold text-ink">{tool.label}</div>
              <div className="text-2xs leading-4 text-ink-label">{tool.detail}</div>
            </button>
          );
        })}
      </div>

      <div role="tabpanel" className="border-t border-line p-3">
        {activeTool === 'pvt' ? <PVTTool onSaved={onSaved} /> : null}
        {activeTool === 'ultrasound' ? <UltrasoundTool onSaved={onSaved} /> : null}
        {activeTool === 'vitals' ? <VitalsTool onSaved={onSaved} /> : null}
      </div>
    </Card>
  );
}
