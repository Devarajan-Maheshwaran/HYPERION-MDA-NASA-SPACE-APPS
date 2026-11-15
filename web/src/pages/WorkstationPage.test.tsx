// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { WorkstationPage } from './WorkstationPage';
import { WorkstationProvider } from '../state/WorkstationProvider';
import { api } from '../lib/api';
import type { WorkstationState } from '../lib/types';
import { exerciseState, makeState, sansState } from '../test/fixtures';
import { expectNoConsoleErrors } from '../test/console';

vi.mock('../lib/api', async () => {
  const actual = await vi.importActual<typeof import('../lib/api')>('../lib/api');
  return {
    ...actual,
    api: {
      ...actual.api,
      state: vi.fn(),
      scenario: vi.fn(),
      examPvt: vi.fn(),
      examUltrasound: vi.fn(),
      examVitals: vi.fn(),
    },
  };
});

const mocked = vi.mocked(api);
let current: WorkstationState;

beforeEach(() => {
  current = makeState();
  mocked.state.mockImplementation(async () => current);
  mocked.scenario.mockImplementation(async (payload) => {
    if (payload.scenario_id === 'eva-ared-exercise') current = exerciseState();
    else if (payload.scenario_id === 'sans-stale-eye') current = sansState();
    else if (payload.scenario_id) current = makeState({ scenario_key: payload.scenario_id });
    else if (payload.habitat) current = { ...current, habitat: payload.habitat as WorkstationState['habitat'] };
    return current;
  });
  mocked.examPvt.mockImplementation(async () => { current = { ...current, readiness: { ...current.readiness, freshness_tau_avg: 1 } }; return current; });
  mocked.examUltrasound.mockImplementation(async () => { current = { ...current, caliper: { x1: 0, y1: 0, x2: 122, y2: 0, px_per_mm: 20, onsd_mm: 6.1, retrobulbar_mm: 3, note: 'demo' } }; return current; });
  mocked.examVitals.mockImplementation(async () => { current = { ...current, readiness: { ...current.readiness, freshness_tau_avg: 1 } }; return current; });
});

afterEach(() => { cleanup(); vi.clearAllMocks(); });

async function renderWorkstation() {
  const assertQuiet = expectNoConsoleErrors();
  render(<MemoryRouter><WorkstationProvider><WorkstationPage /></WorkstationProvider></MemoryRouter>);
  await screen.findByRole('heading', { name: 'Assess. Verify. Act.' });
  return assertQuiet;
}

describe('Crew Workstation', () => {
  it('renders the simulation banner, six organs, three gates and exactly one chart', async () => {
    const assertQuiet = await renderWorkstation();
    expect(screen.getByText('SIMULATED SCENARIO FALLBACK ACTIVE')).toBeTruthy();
    expect(screen.getByRole('img', { name: /Medical illustration/ })).toBeTruthy();
    for (const label of ['Head & Eyes', 'Heart & Vessels', 'Chest & Immune', 'Metabolic & Gut', 'Bones & Muscles', 'Brain & Sleep']) {
      expect(screen.getByRole('button', { name: `${label}: NOMINAL` })).toBeTruthy();
    }
    expect(screen.getByText('Signal quality')).toBeTruthy();
    expect(screen.getByText('Exertion residualizer')).toBeTruthy();
    expect(screen.getByText('Uncertainty & freshness')).toBeTruthy();
    expect(screen.getAllByLabelText('Raw heart rate and residual chart')).toHaveLength(1);
    assertQuiet();
  });

  it('selects every organ and shows its measurement and demo threshold', async () => {
    const assertQuiet = await renderWorkstation();
    for (const organ of current.organs) {
      fireEvent.click(screen.getByRole('button', { name: `${organ.label}: NOMINAL` }));
      const detail = screen.getByRole('heading', { name: organ.label }).closest('.card-surface') as HTMLElement;
      expect(within(detail).getByText('DEMO threshold')).toBeTruthy();
      expect(within(detail).getByText(organ.status)).toBeTruthy();
    }
    assertQuiet();
  });

  it('switches all five scenarios and replays the exercise false-alarm block', async () => {
    const assertQuiet = await renderWorkstation();
    const labels = ['Nominal Rest', 'Exercise Bout Blocks False Alarm', 'High CO₂ + SANS Eye Risk', 'Solar Radiation Spike', 'Blood Sugar & Sleep Drift'];
    for (const [index, label] of labels.entries()) {
      fireEvent.click(screen.getByRole('button', { name: new RegExp(label.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')) }));
      await waitFor(() => expect(mocked.scenario).toHaveBeenCalledTimes(index + 1));
    }
    expect(mocked.scenario).toHaveBeenCalledWith({ scenario_id: 'glycemic-circadian' });
    fireEvent.click(screen.getByRole('button', { name: /Exercise Bout Blocks False Alarm/ }));
    await screen.findByText(/FALSE ALARM BLOCKED/);
    expect(screen.getAllByText(/148 bpm/).length).toBeGreaterThan(0);
    expect(screen.getByText(/0.31g/)).toBeTruthy();
    assertQuiet();
  });

  it('opens the recommended ultrasound from Gate 3 and returns to the gate after saving', async () => {
    current = sansState();
    const assertQuiet = await renderWorkstation();
    fireEvent.click(screen.getByRole('button', { name: /Open Recommended Crew Check/ }));
    expect(screen.getByRole('tab', { name: /^Eye ultrasound/ }).getAttribute('aria-selected')).toBe('true');
    fireEvent.click(screen.getByRole('button', { name: 'Sample · 6.1 mm' }));
    fireEvent.click(screen.getByRole('button', { name: 'Save eye measurement' }));
    await waitFor(() => expect(mocked.examUltrasound).toHaveBeenCalledWith({ sample: 'sans' }));
    await screen.findByText('3-Stage Deterministic Safety Gate');
    assertQuiet();
  });

  it('submits keyboard vitals and returns to the safety gate', async () => {
    const assertQuiet = await renderWorkstation();
    fireEvent.click(screen.getByRole('tab', { name: /B · Crew checks/ }));
    fireEvent.click(screen.getByRole('tab', { name: /^Crew vitals/ }));
    fireEvent.change(screen.getByLabelText(/Systolic/), { target: { value: '122' } });
    fireEvent.change(screen.getByLabelText(/Diastolic/), { target: { value: '78' } });
    fireEvent.change(screen.getByLabelText(/Glucose/), { target: { value: '92' } });
    fireEvent.click(screen.getByRole('button', { name: 'Save vitals & re-run gates' }));
    await waitFor(() => expect(mocked.examVitals).toHaveBeenCalledWith({ bp_sys: 122, bp_dia: 78, glucose_mgdl: 92 }));
    await screen.findByText('3-Stage Deterministic Safety Gate');
    assertQuiet();
  });

  it('requires both blood-pressure values before posting', async () => {
    const assertQuiet = await renderWorkstation();
    fireEvent.click(screen.getByRole('tab', { name: /B · Crew checks/ }));
    fireEvent.click(screen.getByRole('tab', { name: /^Crew vitals/ }));
    fireEvent.change(screen.getByLabelText(/Systolic/), { target: { value: '122' } });
    fireEvent.click(screen.getByRole('button', { name: 'Save vitals & re-run gates' }));
    expect(await screen.findByText('Enter systolic and diastolic blood pressure together.')).toBeTruthy();
    expect(mocked.examVitals).not.toHaveBeenCalled();
    assertQuiet();
  });
});
