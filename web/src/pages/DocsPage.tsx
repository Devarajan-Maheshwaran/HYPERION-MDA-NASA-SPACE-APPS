import { ExternalLink, ShieldCheck } from 'lucide-react';
import { Badge, Card, CardHeader } from '../components/ui';
import { FlDpBenchmarkPanel } from '../components/FlDpBenchmarkPanel';
import { useWorkstation } from '../state/WorkstationProvider';
import { num } from '../lib/format';

const REFERENCES = [
  { label: 'NASA-STD-3001 · Human Spaceflight Standards', url: 'https://www.nasa.gov/ochmo/human-spaceflight-and-aviation-standards/', note: 'Agency crew-health standard framework; this prototype is not a compliance claim.' },
  { label: 'NASA HRP · Evidence Reports', url: 'https://humanresearchroadmap.nasa.gov/evidence/', note: 'Human Research Program evidence book for spaceflight health risks.' },
  { label: 'NASA HRP · Risk of SANS', url: 'https://humanresearchroadmap.nasa.gov/evidence/reports/SANS.pdf', note: 'Spaceflight Associated Neuro-ocular Syndrome evidence report.' },
  { label: 'NASA HRP · Cardiovascular Adaptations', url: 'https://humanresearchroadmap.nasa.gov/evidence/reports/Cardio%20Risk%20EB%202022%20FINAL_4-3-2023.pdf', note: 'Cardiovascular adaptations contributing to adverse mission performance and health outcomes.' },
  { label: 'CSA · The Vascular series', url: 'https://www.asc-csa.gc.ca/eng/sciences/vascular.asp', note: 'Canadian Space Agency research on arterial stiffness, insulin resistance and bone calcium.' },
];

const THRESHOLDS = [
  { organ: 'Head & Eyes', indicator: 'ONSD / cabin CO₂', rule: 'ONSD ≥ 5.8 mm OR CO₂ ≥ 4.0 mmHg', validity: 'ONSD 72 h', ref: 'SANS evidence report' },
  { organ: 'Heart & Vessels', indicator: 'BP / heart rate', rule: 'BP ≥ 140/90 mmHg OR HR > 115 bpm', validity: 'BP 4 h', ref: 'Cardiovascular + CSA Vascular' },
  { organ: 'Chest & Immune', indicator: 'Temperature / proton dose', rule: 'Temp ≥ 38.0 °C OR proton > 2.0 mGy/day', validity: 'Temperature 4 h', ref: 'HRP evidence book' },
  { organ: 'Metabolic & Gut', indicator: 'Fasting glucose', rule: '100–125 mg/dL WATCH · ≥ 126 mg/dL ALERT', validity: 'Glucose 8 h', ref: 'CSA Vascular' },
  { organ: 'Bones & Muscles', indicator: 'Water / ARED log', rule: 'Water < 1400 mL OR ARED < 20 min', validity: 'Countermeasure log', ref: 'HRP evidence book' },
  { organ: 'Brain & Sleep', indicator: 'Sleep / PVT', rule: 'Sleep < 4.5 h OR PVT median > 350 ms', validity: 'Sleep 24 h · PVT 12 h', ref: 'HRP evidence book' },
];

const BENCHMARKS = [
  { model: 'Local-Only', status: 'MEASURED (HR MAE)' },
  { model: 'Centralized', status: 'MEASURED (HR MAE)' },
  { model: 'Federated + Cosine-Median', status: 'MEASURED + SIMULATED_TOY_FEDAVG' },
  { model: 'Federated + DP-SGD', status: 'MEASURED (window-level ε)' },
];

export function DocsPage() {
  const { state } = useWorkstation();
  const ml = state?.ml_benchmark;
  const audit = state?.audit;
  const entries = audit?.entries.slice(-12).reverse() ?? [];

  return (
    <div className="mx-auto max-w-content px-4 py-10 sm:px-6">
      <div className="max-w-prose">
        <div className="label-micro">ML architecture & documentation</div>
        <h1 className="mt-2 text-3xl">Small models, explicit evidence, no hidden claims.</h1>
        <p className="mt-3 text-md leading-6 text-ink-body">
          The live decision path is a deterministic safety gate. Neural, federated and privacy components are shown as design specifications unless the API reports a measured result.
        </p>
      </div>

      <section className="mt-8" aria-labelledby="spec-title">
        <h2 id="spec-title" className="sr-only">Model specifications</h2>
        <div className="grid gap-4 md:grid-cols-2">
          <SpecCard index="01" title="Classical baselines" status="NOT_IMPLEMENTED">
            <p>scikit-learn Logistic Regression and Random Forest (<span className="num">100</span> trees, <span className="num">max_depth=8</span>) with participant-ID group splits.</p>
            <p className="mt-2 text-ink-subtle">The committed M6 baseline uses numpy/scipy ridge/logistic models, not these sklearn estimators. Measured M6 heart-rate rows are listed below.</p>
          </SpecCard>
          <SpecCard index="02" title="Exertion residualizer" status="DEMO CONTEXT MODEL">
            <p>Design: Huber/Ridge regression removes workload-driven heart rate before alerting.</p>
            <div className="num mt-2 rounded-md bg-page px-2.5 py-2 text-xs">r_HR = HR − f(ENMO, CO₂)</div>
            <p className="mt-2 text-ink-subtle">Implemented live: a transparent saturating per-person context model, not a fitted Huber/Ridge model. Activity is normalized to personal rest scales.</p>
          </SpecCard>
          <SpecCard index="03" title="HyperionCoreNet" status="NOT_IMPLEMENTED">
            <p><span className="num">~12K</span> parameters · <span className="num">42</span> inputs (<span className="num">18</span> raw + <span className="num">18</span> z + <span className="num">6</span> τ).</p>
            <div className="num mt-2 space-y-1 rounded-md bg-page px-2.5 py-2 text-2xs leading-4">
              <div>Linear(42,64) → LayerNorm → GELU → Dropout(0.25)</div>
              <div>2 × residual LayerNorm block 64→64</div>
              <div>Linear(64,6) → Sigmoid</div>
            </div>
            <p className="mt-2 text-ink-subtle">Small-cohort overfitting resistance; LayerNorm avoids BatchNorm population statistics and plays better with DP-SGD noise.</p>
          </SpecCard>
          <SpecCard index="04" title="Federated & private training" status="SIMULATED_TOY_FEDAVG">
            <p>Design: Flower across <span className="num">4</span> silos + Opacus DP-SGD + cosine-median robust aggregation.</p>
            <div className="num mt-2 rounded-md bg-page px-2.5 py-2 text-xs">s_k = cos(Δw_k, Δw_med) &lt; 0 → reject</div>
            <p className="mt-2 text-ink-subtle">
              Two things are shown, kept apart: (1) the in-process toy FedAvg ({ml?.fl_simulation.rounds ?? '—'} rounds) that drives the SIMULATED_TOY_FEDAVG audit blocks, with no privacy guarantee; and (2) the measured participant-separated benchmark below, which does report a window-level ε from an exact RDP accountant. Flower and Opacus are still not used.
            </p>
          </SpecCard>
        </div>
      </section>

      <section className="mt-10" aria-labelledby="benchmark-title">
        <Card>
          <CardHeader eyebrow="Evaluation plan" title="Requested benchmarks" description="The four training regimes are now measured for heart-rate MAE and window-level ε (table below). Macro-F1, AUROC and Brier are classification metrics for a classifier that does not exist here, so they stay dashes rather than invented numbers." />
          <div className="overflow-x-auto">
            <table className="w-full min-w-[720px] text-left text-sm">
              <thead className="border-b border-line bg-page text-2xs uppercase tracking-wide text-ink-label">
                <tr><th className="px-5 py-3 font-semibold">Configuration</th><th className="px-4 py-3 font-semibold">Macro-F1</th><th className="px-4 py-3 font-semibold">AUROC</th><th className="px-4 py-3 font-semibold">Brier</th><th className="px-4 py-3 font-semibold">ε at δ=1e−5</th><th className="px-5 py-3 font-semibold">Provenance</th></tr>
              </thead>
              <tbody className="divide-y divide-line">
                {BENCHMARKS.map((row) => (
                  <tr key={row.model}>
                    <td className="px-5 py-3 font-medium text-ink">{row.model}</td>
                    <td className="num px-4 py-3 text-ink-label">—</td><td className="num px-4 py-3 text-ink-label">—</td><td className="num px-4 py-3 text-ink-label">—</td><td className="num px-4 py-3 text-ink-label">—</td>
                    <td className="px-5 py-3"><Badge tone={row.status.startsWith('MEASURED') ? 'nominal' : 'watch'}>{row.status}</Badge></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>

        <FlDpBenchmarkPanel />

        <Card className="mt-4">
          <CardHeader eyebrow="Measured offline result" title="M6 heart-rate baselines" description="Leave-one-participant-out results on non-astronaut PhysioNet recordings (ODC-By 1.0). These are measured MAE values, not the requested classification benchmarks above." />
          <div className="overflow-x-auto">
            <table className="w-full min-w-[520px] text-left text-sm">
              <thead className="border-b border-line bg-page text-2xs uppercase tracking-wide text-ink-label"><tr><th className="px-5 py-3 font-semibold">Model</th><th className="px-4 py-3 font-semibold">MAE</th><th className="px-4 py-3 font-semibold">CI low</th><th className="px-4 py-3 font-semibold">CI high</th><th className="px-5 py-3 font-semibold">Provenance</th></tr></thead>
              <tbody className="divide-y divide-line">
                {(ml?.measured_m6_hr ?? []).map((row) => (
                  <tr key={row.model}>
                    <td className="num px-5 py-2.5 font-medium text-ink">{row.model}</td>
                    <td className="num px-4 py-2.5 text-ink">{num(row.mae_bpm, 2)} bpm</td>
                    <td className="num px-4 py-2.5 text-ink-subtle">{num(row.ci_low, 2)}</td>
                    <td className="num px-4 py-2.5 text-ink-subtle">{num(row.ci_high, 2)}</td>
                    <td className="px-5 py-2.5 text-2xs text-ink-subtle">RECORDED-NON-ASTRONAUT</td>
                  </tr>
                ))}
                {!ml?.measured_m6_hr.length ? <tr><td colSpan={5} className="px-5 py-6 text-sm text-ink-subtle">Measured M6 results are not available from the API.</td></tr> : null}
              </tbody>
            </table>
          </div>
        </Card>
      </section>

      <section className="mt-10" aria-labelledby="threshold-title">
        <Card>
          <CardHeader eyebrow="Clinical reference map" title="Six-organ demo thresholds" description="These are prototype demo rules mapped to NASA/CSA evidence topics. They are not official NASA-STD-3001 limits and this prototype does not claim compliance." />
          <div className="overflow-x-auto">
            <table className="w-full min-w-[820px] text-left text-sm">
              <thead className="border-b border-line bg-page text-2xs uppercase tracking-wide text-ink-label"><tr><th className="px-5 py-3 font-semibold">Organ system</th><th className="px-4 py-3 font-semibold">Indicator</th><th className="px-4 py-3 font-semibold">Demo rule</th><th className="px-4 py-3 font-semibold">Validity window</th><th className="px-5 py-3 font-semibold">Evidence topic</th></tr></thead>
              <tbody className="divide-y divide-line">
                {THRESHOLDS.map((row) => (
                  <tr key={row.organ}>
                    <td className="px-5 py-3 font-medium text-ink">{row.organ}</td>
                    <td className="px-4 py-3 text-ink-body">{row.indicator}</td>
                    <td className="num px-4 py-3 text-xs text-ink">{row.rule}</td>
                    <td className="num px-4 py-3 text-xs text-ink-subtle">{row.validity}</td>
                    <td className="px-5 py-3 text-xs text-ink-subtle">{row.ref}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <div className="border-t border-line px-5 py-4">
            <div className="label-micro mb-2">Official references</div>
            <ul className="grid gap-2 md:grid-cols-2">
              {REFERENCES.map((ref) => (
                <li key={ref.url}>
                  <a href={ref.url} target="_blank" rel="noreferrer" className="inline-flex items-center gap-1.5 text-sm font-medium text-primary-blue hover:underline">
                    {ref.label}<ExternalLink size={12} aria-hidden />
                  </a>
                  <p className="text-2xs leading-4 text-ink-subtle">{ref.note}</p>
                </li>
              ))}
            </ul>
          </div>
        </Card>
      </section>

      <section className="mt-10" aria-labelledby="audit-title">
        <Card>
          <CardHeader
            eyebrow="Tamper-evident local ledger"
            title="SHA-256 audit ledger"
            description="Latest events from the local hash chain. Block numbers are sequence numbers; there is no EVM transaction and no deployed contract."
            action={audit ? <Badge tone={audit.verification.ok ? 'nominal' : 'critical'}>{audit.verification.ok ? 'Chain intact' : 'Chain mismatch'} · {audit.verification.entries}</Badge> : undefined}
          />
          <div className="flex flex-wrap items-center gap-2 border-b border-line bg-page px-5 py-3">
            <Badge tone="neutral"><ShieldCheck size={12} aria-hidden /> Zero Raw Private Health Data Stored On-Chain</Badge>
            <span className="text-2xs text-ink-subtle">Clarification: a local SHA-256 hash chain exists; no blockchain or EVM deployment exists. This badge describes the local ledger’s measurement-free payload policy.</span>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full min-w-[900px] text-left text-sm">
              <thead className="border-b border-line bg-page text-2xs uppercase tracking-wide text-ink-label"><tr><th className="px-5 py-3 font-semibold">Block #</th><th className="px-4 py-3 font-semibold">Tx Hash</th><th className="px-4 py-3 font-semibold">Payload SHA-256</th><th className="px-4 py-3 font-semibold">Event Type</th><th className="px-5 py-3 font-semibold">Timestamp</th></tr></thead>
              <tbody className="divide-y divide-line">
                {entries.map((entry) => (
                  <tr key={entry.seq}>
                    <td className="num px-5 py-2.5 text-ink">{entry.seq}</td>
                    <td className="px-4 py-2.5 text-2xs text-ink-label">— no EVM tx</td>
                    <td className="num max-w-[260px] break-all px-4 py-2.5 text-2xs text-ink-subtle" title={entry.sha256}>{entry.sha256}</td>
                    <td className="px-4 py-2.5 text-xs font-medium text-ink">{entry.event}</td>
                    <td className="num px-5 py-2.5 text-2xs text-ink-subtle">{entry.ts}</td>
                  </tr>
                ))}
                {!entries.length ? <tr><td colSpan={5} className="px-5 py-6 text-sm text-ink-subtle">Audit entries are not available from the API.</td></tr> : null}
              </tbody>
            </table>
          </div>
          <p className="border-t border-line px-5 py-3 text-2xs leading-4 text-ink-label">{audit?.contract ?? 'HealthAudit.sol reference only — NOT deployed, NOT on-chain.'} Acknowledgement notes are hashed; raw measurements are never stored.</p>
        </Card>
      </section>
    </div>
  );
}

function SpecCard({ index, title, status, children }: {
  index: string; title: string; status: string; children: React.ReactNode;
}) {
  return (
    <Card className="p-5">
      <div className="flex items-start justify-between gap-3">
        <div className="flex items-center gap-3">
          <span className="num flex h-8 w-8 items-center justify-center rounded-lg border border-line bg-page text-xs text-ink-subtle">{index}</span>
          <h3 className="text-lg font-semibold">{title}</h3>
        </div>
        <Badge tone={status.includes('SIMULATED') || status.includes('DEMO') ? 'watch' : 'neutral'}>{status}</Badge>
      </div>
      <div className="mt-4 text-sm leading-6 text-ink-body">{children}</div>
    </Card>
  );
}
