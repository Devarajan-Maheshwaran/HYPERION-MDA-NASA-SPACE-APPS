import { useEffect, useState } from 'react';
import { CheckCircle2, FlaskConical, X } from 'lucide-react';
import { BodyMap } from '../components/BodyMap';
import { OrganDetail } from '../components/OrganDetail';
import { GatePipeline } from '../components/GatePipeline';
import { TelemetryChart } from '../components/TelemetryChart';
import { TriageCard } from '../components/TriageCard';
import { CrewChecks, type CrewTool } from '../components/checks/CrewChecks';
import { Badge, Button, Card, Tabs } from '../components/ui';
import { HABITATS, SCENARIOS, recommendedTool } from '../lib/clinical';
import { useWorkstation } from '../state/WorkstationProvider';
import { cn } from '../lib/utils';

export function WorkstationPage() {
  const { state, busy, revision, notice, dismissNotice, selectScenario, selectHabitat } = useWorkstation();
  const [selectedOrgan, setSelectedOrgan] = useState('head-eyes');
  const [tab, setTab] = useState<'gate' | 'checks'>('gate');
  const [tool, setTool] = useState<CrewTool>('pvt');

  useEffect(() => {
    if (state) setTool(recommendedTool(state));
  }, [state?.scenario_key]); // Recommend the right tool when the scenario changes, not on every poll.

  if (!state) return null;
  const organ = state.organs.find((item) => item.system === selectedOrgan) ?? state.organs[0];
  const simulated = state.data_source_mode === 'SIMULATED_FALLBACK';

  const openCheck = () => {
    setTool(recommendedTool(state));
    setTab('checks');
  };
  const saved = () => {
    setTab('gate');
  };

  return (
    <div className="mx-auto max-w-content px-4 py-6 sm:px-6">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <div className="label-micro">Live crew workstation</div>
          <h1 className="mt-1 text-3xl">Assess. Verify. Act.</h1>
          <p className="mt-1 text-sm text-ink-body">Six organ systems, three deterministic gates, and the next useful crew check.</p>
        </div>
        <div className="flex items-center gap-2 text-xs text-ink-subtle">
          <span className={cn('h-2 w-2 rounded-full', state.running ? 'bg-nominal' : 'bg-neutral')} aria-hidden />
          {state.running ? 'Scenario engine running' : 'Stream stopped'}
          <span className="num rounded-md border border-line bg-white px-2 py-1 text-2xs">{state.subject_id}</span>
        </div>
      </div>

      <section className="mt-5" aria-label="Mission habitat">
        <div className="label-micro mb-2">Habitat</div>
        <div className="flex flex-wrap gap-2">
          {HABITATS.map((habitat) => (
            <button
              key={habitat.key}
              type="button"
              disabled={busy}
              aria-pressed={state.habitat === habitat.key}
              onClick={() => void selectHabitat(habitat.key)}
              className={cn(
                'rounded-full border px-3.5 py-1.5 text-xs font-medium transition-colors disabled:opacity-60',
                state.habitat === habitat.key ? 'border-primary bg-primary text-white' : 'border-line bg-white text-ink-body hover:border-line-strong',
              )}
            >
              {habitat.label}
            </button>
          ))}
        </div>
      </section>

      <section className="mt-4" aria-label="Stress-test scenarios">
        <div className="label-micro mb-2">Scenario</div>
        <div className="flex flex-wrap gap-2">
          {SCENARIOS.map((scenario, index) => (
            <Button
              key={scenario.id}
              variant={state.scenario_key === scenario.id ? 'primary' : 'secondary'}
              size="sm"
              disabled={busy}
              aria-pressed={state.scenario_key === scenario.id}
              onClick={() => void selectScenario(scenario.id)}
              className="h-9"
            >
              <span className="num text-2xs opacity-60">{String(index + 1).padStart(2, '0')}</span>
              {scenario.label}
            </Button>
          ))}
        </div>
      </section>

      <div className={cn(
        'mt-4 flex items-start gap-3 rounded-xl border px-4 py-3',
        simulated ? 'border-watch/25 bg-watch-soft text-watch-text' : 'border-line bg-white text-ink-body',
      )} role="status">
        <FlaskConical size={17} className="mt-0.5 shrink-0" aria-hidden />
        <div>
          <div className="text-xs font-bold tracking-wide">
            {simulated ? 'SIMULATED SCENARIO FALLBACK ACTIVE' : state.telemetry_mode === 'NOT_AVAILABLE' ? 'REAL-SOURCE MODE · LIVE TELEMETRY NOT AVAILABLE' : 'REAL EMPIRICAL TELEMETRY'}
          </div>
          <p className="mt-0.5 text-xs leading-5">
            {simulated
              ? 'Physics-guided physiological scenario used for live stress-testing. Explicitly labeled non-flight simulation.'
              : state.provenance_banner}
          </p>
        </div>
      </div>

      {notice ? (
        <div className="mt-3 flex items-center gap-2 rounded-lg border border-nominal/20 bg-nominal-soft px-3 py-2 text-xs text-nominal-text" role="status">
          <CheckCircle2 size={15} aria-hidden />
          <span className="flex-1">{notice}</span>
          <button type="button" onClick={dismissNotice} aria-label="Dismiss notification" className="rounded p-1 hover:bg-nominal/10"><X size={13} aria-hidden /></button>
        </div>
      ) : null}

      <div className="mt-6 grid items-start gap-5 lg:grid-cols-[2fr_3fr]">
        <div className="space-y-4">
          <Card className="p-4">
            <div className="mb-2 flex items-center justify-between px-1">
              <span className="label-micro">Organ systems</span>
              <Badge tone="neutral">{state.organs.length} systems</Badge>
            </div>
            <BodyMap organs={state.organs} selected={selectedOrgan} onSelect={setSelectedOrgan} />
          </Card>
          {organ ? <OrganDetail organ={organ} /> : null}
        </div>

        <div className="min-w-0">
          <Tabs
            label="Workstation panels"
            active={tab}
            onChange={(id) => setTab(id === 'checks' ? 'checks' : 'gate')}
            className="mb-4 w-full"
            items={[
              { id: 'gate', label: 'A · Safety gate & triage' },
              { id: 'checks', label: 'B · Crew checks', badge: state.triage.tier === 'CREW' ? <Badge tone="watch">1</Badge> : undefined },
            ]}
          />
          <div role="tabpanel" className="space-y-4">
            {tab === 'gate' ? (
              <>
                <GatePipeline state={state} revision={revision} onOpenCheck={openCheck} />
                <TelemetryChart state={state} />
                <TriageCard triage={state.triage} onOpenCheck={openCheck} />
              </>
            ) : (
              <CrewChecks state={state} activeTool={tool} onSelectTool={setTool} onSaved={saved} />
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
