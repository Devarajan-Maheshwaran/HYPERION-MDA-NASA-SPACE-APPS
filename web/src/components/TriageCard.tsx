import { ArrowRight } from 'lucide-react';
import type { WorkstationState } from '../lib/types';
import { TRIAGE_LABELS, triageTone } from '../lib/clinical';
import { Badge, Button, Card } from './ui';

export function TriageCard({ triage, onOpenCheck }: {
  triage: WorkstationState['triage']; onOpenCheck: () => void;
}) {
  const tone = triageTone(triage.tier);
  return (
    <Card className="p-5" aria-live="polite">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <span className="label-micro">Grounded triage</span>
        <Badge tone={tone}>{triage.crew_or_surgeon}</Badge>
      </div>
      <h2 className="mt-2 text-xl font-semibold">{TRIAGE_LABELS[triage.tier]}</h2>
      <p className="mt-2 text-sm leading-6 text-ink-body">{triage.why}</p>
      <ol className="mt-4 space-y-2">
        {triage.steps.map((step, index) => (
          <li key={step} className="flex items-start gap-2.5 text-sm text-ink-body">
            <span className="num mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-neutral-soft text-2xs text-ink-subtle">{index + 1}</span>
            <span>{step}</span>
          </li>
        ))}
      </ol>
      <div className="mt-4 flex flex-wrap items-center gap-2 border-t border-line pt-4">
        {triage.actions.map((action) => <Badge key={action} tone="neutral">{action}</Badge>)}
        {triage.tier === 'CREW' || triage.tier === 'WATCH' ? (
          <Button size="sm" variant="secondary" className="ml-auto" onClick={onOpenCheck}>
            Open crew check <ArrowRight size={13} aria-hidden />
          </Button>
        ) : null}
      </div>
      <p className="mt-3 text-2xs leading-4 text-ink-label">{triage.label}</p>
    </Card>
  );
}
