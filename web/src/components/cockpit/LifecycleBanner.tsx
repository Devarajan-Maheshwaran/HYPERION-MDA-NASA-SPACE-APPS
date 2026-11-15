import { AlertTriangle, CheckCircle2, Radio, Stethoscope } from 'lucide-react';
import type { Lifecycle, LifecycleStage, StageTone } from '../../lib/types';
import { missionClock } from '../../lib/format';
import { cn } from '../../lib/utils';

const ORDER: Array<{ stage: LifecycleStage; code: string; short: string }> = [
  { stage: 'S0_NOMINAL', code: 'S0', short: 'Nominal' },
  { stage: 'S1_EXERTION_COMPENSATED', code: 'S1', short: 'Exertion' },
  { stage: 'S2_ACTIVE_SENSING_HOLD', code: 'S2', short: 'Sensing hold' },
  { stage: 'S3_CREW_COUNTERMEASURE', code: 'S3', short: 'Crew action' },
  { stage: 'S4_SURGEON_ESCALATED', code: 'S4', short: 'Surgeon' },
];

/** S0 emerald · S1 teal · S2 amber · S3 orange · S4 rose. Colour is the only place
 *  these hues appear outside the organ badges, and every stage is also named in text. */
const TONE_CLASS: Record<StageTone, { chip: string; bar: string; text: string }> = {
  nominal: { chip: 'border-nominal/25 bg-nominal-soft', bar: 'bg-nominal', text: 'text-nominal-text' },
  teal: { chip: 'border-teal-300 bg-teal-50', bar: 'bg-teal-500', text: 'text-teal-800' },
  watch: { chip: 'border-watch/25 bg-watch-soft', bar: 'bg-watch', text: 'text-watch-text' },
  orange: { chip: 'border-orange-300 bg-orange-50', bar: 'bg-orange-500', text: 'text-orange-800' },
  critical: { chip: 'border-critical/25 bg-critical-soft', bar: 'bg-critical', text: 'text-critical-text' },
};

const ACTIVE_TONE: Record<string, StageTone> = {
  S0_NOMINAL: 'nominal',
  S1_EXERTION_COMPENSATED: 'teal',
  S2_ACTIVE_SENSING_HOLD: 'watch',
  S3_CREW_COUNTERMEASURE: 'orange',
  S4_SURGEON_ESCALATED: 'critical',
  S4_SURGEON_ACKNOWLEDGED: 'critical',
};

export function LifecycleBanner({ lifecycle }: { lifecycle: Lifecycle }) {
  const tone = TONE_CLASS[lifecycle.tone] ?? TONE_CLASS.nominal;
  const acknowledged = lifecycle.acknowledged;
  const activeIndex = ORDER.findIndex((item) => item.stage === lifecycle.stage
    || (acknowledged && item.stage === 'S4_SURGEON_ESCALATED'));

  return (
    <section aria-label="Mission health lifecycle" aria-live="polite"
             className={cn('rounded-xl border px-4 py-3', tone.chip)}>
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div className="min-w-0">
          <div className="flex items-center gap-2">
            {lifecycle.action_required ? <AlertTriangle size={15} className={tone.text} aria-hidden />
              : acknowledged ? <CheckCircle2 size={15} className={tone.text} aria-hidden />
              : lifecycle.stage === 'S4_SURGEON_ESCALATED' ? <Radio size={15} className={tone.text} aria-hidden />
              : <Stethoscope size={15} className={tone.text} aria-hidden />}
            <h2 className={cn('text-sm font-bold tracking-wide', tone.text)}>{lifecycle.label}</h2>
          </div>
          <p className="mt-1 text-xs leading-5 text-ink-body">{lifecycle.reason}</p>
        </div>
        <span className="num shrink-0 rounded-md border border-line bg-white/70 px-2 py-1 text-2xs text-ink-subtle">
          since {missionClock(lifecycle.since_mission_t_s)}
        </span>
      </div>

      <ol className="mt-3 flex items-center gap-1" aria-label="S0 to S4 progression">
        {ORDER.map((item, index) => {
          const active = index === activeIndex;
          const itemTone = TONE_CLASS[ACTIVE_TONE[item.stage] ?? 'nominal'];
          return (
            <li key={item.stage} className="flex min-w-0 flex-1 items-center gap-1">
              <div className="min-w-0 flex-1">
                <div className={cn('h-1.5 rounded-full', active ? itemTone.bar : 'bg-white/70')} />
                <div className={cn('num mt-1 truncate text-2xs', active ? cn('font-bold', itemTone.text) : 'text-ink-label')}>
                  {item.code} <span className="hidden sm:inline">{item.short}</span>
                </div>
              </div>
            </li>
          );
        })}
      </ol>

      <div className="mt-2 flex flex-wrap items-center gap-2 border-t border-white/60 pt-2">
        {acknowledged ? (
          <span className="num rounded-full border border-line bg-white px-2 py-0.5 text-2xs font-semibold text-ink">
            S4_SURGEON_ACKNOWLEDGED
          </span>
        ) : null}
        {lifecycle.action_required ? (
          <span className="num rounded-full border border-watch/40 bg-white px-2 py-0.5 text-2xs font-bold text-watch-text animate-pulse">
            ACTION REQUIRED TO RESOLVE S2 HOLD
          </span>
        ) : null}
        <span className="text-2xs leading-4 text-ink-label">{lifecycle.routing_label}</span>
      </div>
    </section>
  );
}
