import { useState } from 'react';
import { Link } from 'react-router-dom';
import { Activity, ArrowRight, BookOpen, BrainCircuit, Database, Gauge, ShieldCheck, Stethoscope } from 'lucide-react';
import { Badge, Card } from '../components/ui';
import { cn } from '../lib/utils';

const PROBLEMS = [
  {
    icon: Gauge,
    problem: 'Generic thresholds miss the individual',
    solution: 'Personal baselines, not population averages',
    body: 'Microgravity shifts fluids, CO₂ exposure and insulin sensitivity. A reading that looks abnormal on Earth may be normal for this astronaut.',
    formula: 'z = (x − μ₀) / σ₀',
    tags: ['SANS', 'CO₂', 'Insulin drift'],
  },
  {
    icon: Activity,
    problem: 'Exercise creates false alarms',
    solution: 'Subtract the workload before alerting',
    body: 'Two hours of daily exercise can drive heart rate to 148 bpm. An ENMO-aware residualizer asks whether the rate is explained by movement.',
    formula: 'r_HR = HR − f(ENMO, CO₂)',
    tags: ['2 h/day', '148 bpm', 'ENMO residualizer'],
  },
  {
    icon: BrainCircuit,
    problem: 'Wearables are fast; manual checks go stale',
    solution: 'Ask for the right two-minute check',
    body: 'Continuous signals and episodic exams age at different rates. A freshness weight decays old evidence and requests the highest-value crew check.',
    formula: 'τ = e^(−λΔt)',
    tags: ['Wearable + episodic fusion', '2-min check'],
  },
];

const STEPS = [
  {
    icon: Database,
    title: 'Tri-Stream Real Data',
    subtitle: 'OSD-575 · GOES · WESAD',
    summary: 'Three empirical lanes are kept separate and labelled: NASA OSD-575 lab records, NOAA GOES proton flux, and WESAD/PhysioNet wearable research data. When a lane is unavailable the system says so, and live stress-testing uses an explicitly simulated fallback.',
  },
  {
    icon: BrainCircuit,
    title: '12K-param PyTorch + DP-FL',
    subtitle: 'LayerNorm · Flower · Opacus',
    summary: 'The proposed HyperionCoreNet is a small LayerNorm network trained across four silos with federated averaging and DP-SGD. That neural and privacy stack is a design specification in this prototype; the live decision path is the deterministic gate engine, and unimplemented benchmarks are labelled.',
  },
  {
    icon: ShieldCheck,
    title: '3-Stage Safety Gate',
    subtitle: 'Quality · Exertion · Freshness',
    summary: 'Gate 1 checks sensor quality, Gate 2 blocks exercise-explained heart-rate alarms, and Gate 3 holds a ground alarm when stale manual context should be refreshed first. Hard ceilings, non-rate findings and hold timeouts can never be hidden by the exercise filter.',
  },
  {
    icon: Stethoscope,
    title: 'NASA-STD-3001 Triage & Log',
    subtitle: 'Crew action · SHA-256 audit',
    summary: 'The workstation maps findings to nominal, crew-check, onboard-countermeasure or flight-surgeon escalation using demo rules referenced to NASA/CSA evidence. Events are written to a local SHA-256 hash chain with no raw measurements; no EVM transaction or blockchain exists.',
  },
];

export function OverviewPage() {
  const [activeStep, setActiveStep] = useState(0);
  const selected = STEPS[activeStep] ?? STEPS[0]!;

  return (
    <div className="mx-auto max-w-content px-4 pb-16 sm:px-6">
      <section className="mx-auto max-w-[880px] pb-14 pt-14 text-center sm:pt-20">
        <div className="label-micro">Onboard Autonomous Medical Decision Support</div>
        <h1 className="mx-auto mt-4 max-w-[820px] text-[28px] font-semibold leading-[1.18] tracking-[-0.03em] text-ink sm:text-hero">
          Helping astronauts assess their own health, filter out exercise false alarms, and know when to call Earth.
        </h1>
        <p className="mx-auto mt-5 max-w-prose text-lg text-ink-body">
          A medical question on Mars can wait 20 minutes for an answer, and Earth communication cutoffs can fail entirely.
          HYPERION-MDA fuses wearable and episodic evidence behind a 3-Stage Deterministic Safety Gate so crews can act onboard with confidence.
        </p>
        <div className="mt-8 flex flex-col items-center justify-center gap-3 sm:flex-row">
          <Link
            to="/workstation"
            className="inline-flex h-12 items-center gap-2 rounded-lg bg-primary px-5 text-md font-medium text-white transition-colors hover:bg-primary-hover"
          >
            Launch Live Crew Workstation <ArrowRight size={16} aria-hidden />
          </Link>
          <Link
            to="/docs"
            className="inline-flex h-12 items-center gap-2 rounded-lg border border-line bg-white px-5 text-md font-medium text-ink transition-colors hover:border-line-strong hover:bg-page"
          >
            <BookOpen size={16} aria-hidden /> Read ML & System Docs
          </Link>
        </div>
        <div className="mt-6 flex flex-wrap items-center justify-center gap-2">
          <Badge tone="neutral">Research prototype</Badge>
          <Badge tone="neutral">Demo thresholds · not clinically validated</Badge>
          <Badge tone="watch">Simulated fallback explicitly labeled</Badge>
        </div>
      </section>

      <section aria-labelledby="problems-title">
        <div className="mb-5 flex items-end justify-between">
          <div>
            <div className="label-micro">Why onboard autonomy</div>
            <h2 id="problems-title" className="mt-1 text-2xl">Three failure modes, one deterministic answer</h2>
          </div>
        </div>
        <div className="grid gap-4 lg:grid-cols-3">
          {PROBLEMS.map((item) => (
            <Card key={item.problem} className="flex flex-col p-5">
              <div className="flex h-9 w-9 items-center justify-center rounded-lg border border-line bg-page text-ink">
                <item.icon size={17} strokeWidth={1.8} aria-hidden />
              </div>
              <div className="mt-4 text-xs font-medium text-ink-subtle">{item.problem}</div>
              <h3 className="mt-1 text-lg font-semibold">{item.solution}</h3>
              <p className="mt-2 flex-1 text-sm leading-6 text-ink-body">{item.body}</p>
              <div className="num mt-4 rounded-lg border border-line bg-page px-3 py-2 text-sm text-ink">{item.formula}</div>
              <div className="mt-3 flex flex-wrap gap-1.5">
                {item.tags.map((tag) => <span key={tag} className="rounded-full bg-neutral-soft px-2 py-0.5 text-2xs text-ink-subtle">{tag}</span>)}
              </div>
            </Card>
          ))}
        </div>
      </section>

      <section aria-labelledby="architecture-title" className="mt-14">
        <div className="mb-5">
          <div className="label-micro">System architecture</div>
          <h2 id="architecture-title" className="mt-1 text-2xl">From raw evidence to a grounded crew action</h2>
          <p className="mt-1 text-sm text-ink-body">Select a stage to see what it does—and what is still a design specification.</p>
        </div>
        <Card className="overflow-hidden">
          <div className="grid divide-y divide-line md:grid-cols-4 md:divide-x md:divide-y-0" role="tablist" aria-label="Architecture stages">
            {STEPS.map((step, index) => (
              <button
                key={step.title}
                type="button"
                role="tab"
                aria-selected={activeStep === index}
                onClick={() => setActiveStep(index)}
                className={cn(
                  'relative flex items-start gap-3 px-5 py-5 text-left transition-colors',
                  activeStep === index ? 'bg-page' : 'bg-white hover:bg-page/60',
                )}
              >
                <span className={cn(
                  'num flex h-7 w-7 shrink-0 items-center justify-center rounded-full border text-xs font-medium',
                  activeStep === index ? 'border-primary bg-primary text-white' : 'border-line bg-white text-ink-subtle',
                )}>{index + 1}</span>
                <span>
                  <span className="block text-sm font-semibold text-ink">{step.title}</span>
                  <span className="mt-1 block text-2xs text-ink-subtle">{step.subtitle}</span>
                </span>
                {activeStep === index ? <span className="absolute inset-x-0 bottom-0 h-0.5 bg-primary-blue" /> : null}
              </button>
            ))}
          </div>
          <div className="flex items-start gap-4 border-t border-line bg-white px-5 py-5" role="tabpanel">
            <selected.icon size={20} className="mt-0.5 shrink-0 text-ink-subtle" aria-hidden />
            <div>
              <h3 className="text-sm font-semibold">{selected.title}</h3>
              <p className="mt-1 max-w-4xl text-sm leading-6 text-ink-body">{selected.summary}</p>
            </div>
          </div>
        </Card>
      </section>
    </div>
  );
}
