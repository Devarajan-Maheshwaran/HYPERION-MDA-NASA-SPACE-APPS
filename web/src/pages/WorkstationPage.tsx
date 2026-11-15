import { useEffect, useState } from 'react';
import { CheckCircle2, FlaskConical, X } from 'lucide-react';
import { BodyMap } from '../components/BodyMap';
import { OrganDetail } from '../components/OrganDetail';
import { GatePipeline } from '../components/GatePipeline';
import { TelemetryChart } from '../components/TelemetryChart';
import { TriageCard } from '../components/TriageCard';
import { CrewChecks, type CrewTool } from '../components/checks/CrewChecks';
import { ControlStrip } from '../components/cockpit/ControlStrip';
import { LifecycleBanner } from '../components/cockpit/LifecycleBanner';
import { GateStrip } from '../components/cockpit/GateStrip';
import { InstrumentBay } from '../components/cockpit/InstrumentBay';
import { CommsOutbox } from '../components/cockpit/CommsOutbox';
import { ProvenancePanel } from '../components/cockpit/ProvenancePanel';
import { Badge, Tabs } from '../components/ui';
import { recommendedTool } from '../lib/clinical';
import { useWorkstation } from '../state/WorkstationProvider';
import { cn } from '../lib/utils';

export function WorkstationPage() {
  const { state, revision, notice, dismissNotice } = useWorkstation();
  const [selectedOrgan, setSelectedOrgan] = useState('head-eyes');
  const [tab, setTab] = useState<'gate' | 'checks'>('gate');
  const [tool, setTool] = useState<CrewTool>('pvt');

  const scenarioKey = state?.scenario_key;
  const requestedExam = state?.lifecycle?.requested_exam;
  const actionRequired = state?.lifecycle?.action_required ?? false;

  useEffect(() => {
    if (state) setTool(recommendedTool(state));
    // Re-focus the instrument only when the case changes, not on every 1 Hz tick.
  }, [scenarioKey]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    // An S2 hold auto-focuses the exam that resolves it. The astronaut never hunts for it.
    if (actionRequired && requestedExam === 'ultrasound') setTool('ultrasound');
  }, [actionRequired, requestedExam]);

  if (!state) return null;
  const organ = state.organs.find((item) => item.system === selectedOrgan) ?? state.organs[0];
  const simulated = state.data_source_mode === 'SIMULATED_FALLBACK';
  const recorded = state.telemetry_mode === 'RECORDED_REPLAY';

  const openCheck = () => {
    setTool(recommendedTool(state));
    setTab('checks');
  };

  return (
    <div className="mx-auto max-w-content px-4 py-5 sm:px-6">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <div className="label-micro">Live crew workstation</div>
          <h1 className="mt-0.5 text-3xl">Assess. Verify. Act.</h1>
        </div>
        <div className="flex items-center gap-2">
          <Badge tone="neutral">{state.subject_id}</Badge>
          <Badge tone={state.audit.verification.ok ? 'nominal' : 'critical'}>
            audit {state.audit.verification.ok ? 'chain intact' : 'BROKEN'}
          </Badge>
        </div>
      </div>

      <div className="mt-4">
        <ControlStrip state={state} />
      </div>

      <div className={cn(
        'mt-3 flex items-start gap-3 rounded-xl border px-4 py-2.5',
        simulated ? 'border-watch/25 bg-watch-soft text-watch-text'
          : recorded ? 'border-primary-blue/25 bg-primary-blue-soft text-ink-body'
            : 'border-line bg-white text-ink-body',
      )} role="status">
        <FlaskConical size={16} className="mt-0.5 shrink-0" aria-hidden />
        <div className="min-w-0">
          <div className="text-xs font-bold tracking-wide">
            {simulated ? 'SIMULATED SCENARIO FALLBACK ACTIVE'
              : recorded ? 'RECORDED HUMAN REPLAY · NON-ASTRONAUT'
                : state.telemetry_mode === 'NOT_AVAILABLE' ? 'REAL-SOURCE MODE · LIVE TELEMETRY NOT AVAILABLE'
                  : 'REAL EMPIRICAL TELEMETRY'}
          </div>
          <p className="mt-0.5 text-2xs leading-4">
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

      {/* 3 / 5 / 4 cockpit: body + focused organ · lifecycle + gates + chart · instruments + comms */}
      <div className="mt-4 grid items-start gap-4 xl:grid-cols-12">
        <div className="space-y-3 xl:col-span-3">
          <div className="card-surface p-3">
            <div className="mb-1.5 flex items-center justify-between px-1">
              <span className="label-micro">Organ systems</span>
              <Badge tone="neutral">{state.organs.length}</Badge>
            </div>
            <BodyMap organs={state.organs} selected={selectedOrgan} onSelect={setSelectedOrgan} />
          </div>
          {organ ? <OrganDetail organ={organ} /> : null}
          <ProvenancePanel state={state} />
        </div>

        <div className="min-w-0 space-y-3 xl:col-span-5">
          {state.lifecycle ? <LifecycleBanner lifecycle={state.lifecycle} /> : null}
          <GateStrip gates={state.gates} revision={revision} />
          <TelemetryChart state={state} />
          <Tabs
            label="Workstation panels"
            active={tab}
            onChange={(id) => setTab(id === 'checks' ? 'checks' : 'gate')}
            className="w-full"
            items={[
              { id: 'gate', label: 'A · Safety gate & triage' },
              { id: 'checks', label: 'B · Crew checks', badge: state.triage.tier === 'CREW' ? <Badge tone="watch">1</Badge> : undefined },
            ]}
          />
          <div role="tabpanel" className="space-y-3">
            {tab === 'gate' ? (
              <>
                <GatePipeline state={state} revision={revision} onOpenCheck={openCheck} />
                <TriageCard triage={state.triage} onOpenCheck={openCheck} />
              </>
            ) : (
              <CrewChecks state={state} activeTool={tool} onSelectTool={setTool}
                          onSaved={() => setTab('gate')} renderPanel={false} />
            )}
          </div>
        </div>

        <div className="space-y-3 xl:col-span-4">
          <InstrumentBay state={state} activeTool={tool} onSelectTool={setTool} onSaved={() => setTab('gate')} />
          {state.comms ? <CommsOutbox comms={state.comms} /> : null}
        </div>
      </div>
    </div>
  );
}
