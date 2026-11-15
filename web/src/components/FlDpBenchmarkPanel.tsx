import { useEffect, useState } from 'react';
import { FlaskConical, ShieldAlert } from 'lucide-react';
import { api } from '../lib/api';
import type { FlDpBenchmark } from '../lib/types';
import { compactHash, num } from '../lib/format';
import { Badge, Card, CardHeader } from './ui';

/** Every number here is read from artifacts/fl_dp_benchmark_results.json via the API.
 *  Nothing is estimated, interpolated or defaulted in the browser. */
export function FlDpBenchmarkPanel() {
  const [benchmark, setBenchmark] = useState<FlDpBenchmark | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    void api.flDpBenchmark()
      .then((payload) => { if (!cancelled) setBenchmark(payload.benchmark); })
      .catch((cause: unknown) => {
        if (!cancelled) setError(cause instanceof Error ? cause.message : 'Benchmark endpoint unavailable.');
      });
    return () => { cancelled = true; };
  }, []);

  if (error) {
    return (
      <Card className="mt-4">
        <CardHeader eyebrow="Measured federated benchmark" title="Federated / DP-SGD results"
                    description="The benchmark endpoint could not be reached." />
        <p className="px-5 py-4 text-sm text-critical-text">{error}</p>
      </Card>
    );
  }
  if (!benchmark) {
    return (
      <Card className="mt-4">
        <CardHeader eyebrow="Measured federated benchmark" title="Federated / DP-SGD results"
                    description="Loading the committed artifact…" />
      </Card>
    );
  }
  const results = benchmark.results;
  if (!benchmark.available || !results) {
    return (
      <Card className="mt-4">
        <CardHeader eyebrow="Measured federated benchmark" title="Federated / DP-SGD results"
                    description="No artifact is committed, so no value is shown." />
        <p className="px-5 py-4 text-sm text-ink-body">{benchmark.detail}</p>
      </Card>
    );
  }

  const config = results.config as { rounds?: number; local_steps?: number; n_clients?: number; clip_norm?: number; noise_multiplier?: number; client_fraction?: number };
  const crossCheck = results.accuracy.frozen_m6_cross_check;

  return (
    <Card className="mt-4">
      <CardHeader
        eyebrow="Measured · committed artifact · reproducible"
        title="Federated / DP-SGD benchmark"
        description={`${results.dataset.n_windows} windows · ${results.dataset.n_features} features · ${results.dataset.participants.length} participants · leave-one-participant-out. ${results.scope}`}
        action={<Badge tone="nominal">MEASURED</Badge>}
      />

      <div className="flex flex-wrap items-center gap-2 border-b border-line bg-page px-5 py-2.5">
        <span className="num text-2xs text-ink-subtle">{benchmark.path ?? 'artifacts/fl_dp_benchmark_results.json'}</span>
        <span className="num text-2xs text-ink-label">sha256 {compactHash(benchmark.sha256 ?? '')}</span>
        <span className="num ml-auto text-2xs text-ink-label">
          {config.n_clients ?? '—'} clients · C={num(config.client_fraction, 1)} · {config.rounds ?? '—'} rounds × {config.local_steps ?? '—'} steps
        </span>
      </div>

      <div className="overflow-x-auto">
        <table className="w-full min-w-[720px] text-left text-sm">
          <caption className="sr-only">Measured mean absolute error by training regime with participant bootstrap confidence intervals</caption>
          <thead className="border-b border-line bg-page text-2xs uppercase tracking-wide text-ink-label">
            <tr>
              <th className="px-5 py-3 font-semibold">Training regime</th>
              <th className="px-4 py-3 font-semibold">MAE (bpm)</th>
              <th className="px-4 py-3 font-semibold">95% participant CI</th>
              <th className="px-4 py-3 font-semibold">Δ vs centralized</th>
              <th className="px-5 py-3 font-semibold">Window-level ε at δ=1e−5</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-line">
            {results.accuracy.table.map((row) => (
              <tr key={row.regime}>
                <td className="px-5 py-2.5">
                  <div className="font-medium text-ink">{row.label}</div>
                  <div className="num text-2xs text-ink-label">{row.regime}</div>
                </td>
                <td className="num px-4 py-2.5 font-medium text-ink">{num(row.mae_bpm.mean, 2)}</td>
                <td className="num px-4 py-2.5 text-ink-subtle">[{num(row.mae_bpm.ci_low, 2)}, {num(row.mae_bpm.ci_high, 2)}]</td>
                <td className="num px-4 py-2.5 text-ink-subtle">
                  {row.mae_bpm.gap_vs_centralized_bpm > 0 ? '+' : ''}{num(row.mae_bpm.gap_vs_centralized_bpm, 2)}
                </td>
                <td className="num px-5 py-2.5 text-ink">
                  {row.window_level_epsilon
                    ? `≤ ${num(row.window_level_epsilon.max_over_folds, 2)}`
                    : <span className="text-ink-label">no noise applied</span>}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="flex items-start gap-2 border-t border-line bg-watch-soft px-5 py-3">
        <ShieldAlert size={15} className="mt-0.5 shrink-0 text-watch-text" aria-hidden />
        <div className="text-2xs leading-4 text-watch-text">
          <b className="font-bold">Threat model: {results.threat_model.level}-level, not participant-level.</b>{' '}
          {results.threat_model.guarantee_covers}. Neighbouring datasets differ by one 8 s window.
          <ul className="mt-1 list-disc space-y-0.5 pl-4">
            {results.threat_model.not_covered.map((item) => <li key={item}>{item}</li>)}
          </ul>
        </div>
      </div>

      {crossCheck ? (
        <p className="border-t border-line px-5 py-2 text-2xs leading-4 text-ink-subtle">
          Cross-check: the training-mean row reproduces the frozen M6 A0 aggregate
          (<span className="num">{num(crossCheck.measured_mae_bpm, 3)}</span> bpm vs{' '}
          <span className="num">{num(crossCheck.expected_mae_bpm, 3)}</span> bpm) —{' '}
          <b className={crossCheck.matches ? 'text-nominal-text' : 'text-critical-text'}>
            {crossCheck.matches ? 'match' : 'MISMATCH'}
          </b>. This confirms the data join and the LOPO splits are the frozen protocol.
        </p>
      ) : null}

      <div className="border-t border-line px-5 py-4">
        <h3 className="text-sm font-semibold text-ink">Privacy / utility sweep</h3>
        <p className="mt-0.5 text-2xs text-ink-subtle">Same rounds, steps, clipping and splits; only the Gaussian noise multiplier changes.</p>
        <div className="mt-2 overflow-x-auto">
          <table className="w-full min-w-[420px] text-left text-sm">
            <thead className="border-b border-line text-2xs uppercase tracking-wide text-ink-label">
              <tr><th className="py-2 pr-4 font-semibold">σ</th><th className="py-2 pr-4 font-semibold">MAE (bpm)</th><th className="py-2 font-semibold">Worst-case window ε</th></tr>
            </thead>
            <tbody className="divide-y divide-line">
              {results.dp_privacy_utility.sweep.map((row) => (
                <tr key={row.noise_multiplier} className={row.is_default_operating_point ? 'bg-primary-blue-soft' : undefined}>
                  <td className="num py-2 pr-4 text-ink">
                    {num(row.noise_multiplier, 1)}{row.is_default_operating_point ? <span className="ml-1.5 text-2xs text-ink-subtle">operating point</span> : null}
                  </td>
                  <td className="num py-2 pr-4 text-ink">{num(row.mae_bpm.mean, 2)}</td>
                  <td className="num py-2 text-ink">≤ {num(row.window_level_epsilon_worst_case, 2)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      <div className="border-t border-line px-5 py-4">
        <h3 className="text-sm font-semibold text-ink">Byzantine fault injection · 5 seeds · 1 of 4 clients</h3>
        <div className="mt-2 overflow-x-auto">
          <table className="w-full min-w-[520px] text-left text-sm">
            <thead className="border-b border-line text-2xs uppercase tracking-wide text-ink-label">
              <tr><th className="py-2 pr-4 font-semibold">Fault</th><th className="py-2 pr-4 font-semibold">Aggregator</th><th className="py-2 pr-4 font-semibold">MAE (bpm)</th><th className="py-2 pr-4 font-semibold">± SD over seeds</th><th className="py-2 font-semibold">Outcome</th></tr>
            </thead>
            <tbody className="divide-y divide-line">
              {results.robustness.runs.map((row) => (
                <tr key={`${row.fault}-${row.aggregator}`}>
                  <td className="num py-2 pr-4 text-ink">{row.fault}</td>
                  <td className="num py-2 pr-4 text-ink">{row.aggregator}</td>
                  <td className="num py-2 pr-4 text-ink">{row.mae_bpm_mean_over_seeds === null ? '—' : num(row.mae_bpm_mean_over_seeds, 2)}</td>
                  <td className="num py-2 pr-4 text-ink-subtle">{num(row.mae_bpm_sd_over_seeds, 2)}</td>
                  <td className="py-2"><Badge tone={row.outcome === 'CONVERGED' ? 'nominal' : 'critical'}>{row.outcome}</Badge></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <ul className="mt-2 space-y-1">
          {results.robustness.comparison.map((row) => (
            <li key={row.fault} className="text-2xs leading-4 text-ink-subtle">
              <b className="num font-semibold text-ink">{row.fault}</b>: {row.finding ?? 'measured, see table'}
            </li>
          ))}
        </ul>
      </div>

      <div className="flex items-start gap-2 border-t border-line bg-page px-5 py-3">
        <FlaskConical size={15} className="mt-0.5 shrink-0 text-ink-subtle" aria-hidden />
        <ul className="space-y-1 text-2xs leading-4 text-ink-subtle">
          {results.limitations.map((item) => <li key={item}>{item}</li>)}
        </ul>
      </div>
      <p className="num border-t border-line px-5 py-2 text-2xs text-ink-label">
        Reproduce: python3 scripts/run_fl_dp_benchmark.py · verify: --verify · accountant: exact integer-order SGM RDP
      </p>
    </Card>
  );
}
