// @vitest-environment jsdom
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, render, screen } from '@testing-library/react';
import { DocsPage } from './DocsPage';
import { WorkstationProvider } from '../state/WorkstationProvider';
import { api } from '../lib/api';
import { makeState } from '../test/fixtures';
import type { FlDpBenchmark } from '../lib/types';
import { expectNoConsoleErrors } from '../test/console';

vi.mock('../lib/api', async () => {
  const actual = await vi.importActual<typeof import('../lib/api')>('../lib/api');
  return { ...actual, api: { ...actual.api, state: vi.fn(), flDpBenchmark: vi.fn() } };
});

// Read the committed artifact itself, so this test proves the UI shows measured numbers
// rather than a hand-written fixture that could drift from the benchmark.
// vitest runs with cwd = web/, so resolve from there rather than import.meta.url
// (which jsdom rewrites to an http URL).
const artifactPath = resolve(process.cwd(), '../artifacts/fl_dp_benchmark_results.json');
const artifact = JSON.parse(readFileSync(artifactPath, 'utf-8')) as NonNullable<FlDpBenchmark['results']>;

function mockBenchmark(): void {
  vi.mocked(api.state).mockResolvedValue(makeState());
  vi.mocked(api.flDpBenchmark).mockResolvedValue({
    lane: 'RECORDED-NON-ASTRONAUT', provenance: 'committed artifact',
    generated_at: '2026-11-14T12:00:00.000Z', disclaimer: 'demo',
    benchmark: {
      available: true, detail: 'measured', sha256: 'd'.repeat(64),
      path: 'artifacts/fl_dp_benchmark_results.json', results: artifact,
    },
  });
}

afterEach(() => { cleanup(); vi.clearAllMocks(); });

describe('ML Architecture & Docs', () => {
  it('labels unmeasured specs and keeps the audit explicitly off-chain', async () => {
    const assertQuiet = expectNoConsoleErrors();
    mockBenchmark();
    render(<WorkstationProvider><DocsPage /></WorkstationProvider>);
    await screen.findByText('Requested benchmarks');
    // The sklearn estimators and HyperionCoreNet are still genuinely unimplemented.
    expect(screen.getAllByText('NOT_IMPLEMENTED').length).toBeGreaterThan(1);
    expect(screen.getAllByText(/SIMULATED_TOY_FEDAVG/).length).toBeGreaterThan(0);
    expect(screen.getByText('Zero Raw Private Health Data Stored On-Chain')).toBeTruthy();
    expect(screen.getByText(/no chain exists/)).toBeTruthy();
    expect(screen.getByText('— no EVM tx')).toBeTruthy();
    expect(screen.getByText('24.18 bpm')).toBeTruthy();
    expect(screen.getAllByRole('link').length).toBeGreaterThanOrEqual(5);
    assertQuiet();
  });

  it('renders the measured federated table straight from the committed artifact', async () => {
    const assertQuiet = expectNoConsoleErrors();
    mockBenchmark();
    render(<WorkstationProvider><DocsPage /></WorkstationProvider>);
    await screen.findByText('Federated / DP-SGD benchmark');

    for (const row of artifact.accuracy.table) {
      expect(screen.getByText(row.regime)).toBeTruthy();
      expect(screen.getAllByText(row.mae_bpm.mean.toFixed(2)).length).toBeGreaterThan(0);
    }
    // The threat model must be on screen, not buried in the JSON.
    expect(screen.getByText(/WINDOW-level, not participant-level/)).toBeTruthy();
    expect(screen.getByText(/reproduces the frozen M6 A0 aggregate/)).toBeTruthy();
    expect(screen.getByText('Privacy / utility sweep')).toBeTruthy();
    expect(screen.getByText(/Byzantine fault injection · 5 seeds · 1 of 4 clients/)).toBeTruthy();
    expect(screen.getAllByText('DIVERGED').length).toBeGreaterThan(0);
    expect(screen.getByText(/python3 scripts\/run_fl_dp_benchmark\.py/)).toBeTruthy();
    assertQuiet();
  });
});
