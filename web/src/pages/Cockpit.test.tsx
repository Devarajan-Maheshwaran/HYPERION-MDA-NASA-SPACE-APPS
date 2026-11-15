// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { WorkstationPage } from './WorkstationPage';
import { WorkstationProvider } from '../state/WorkstationProvider';
import { api } from '../lib/api';
import type { WorkstationState } from '../lib/types';
import {
  acknowledgedState, deliveredState, escalatedState, exerciseState,
  makeState, replayState, sansState,
} from '../test/fixtures';
import { expectNoConsoleErrors } from '../test/console';

vi.mock('../lib/api', async () => {
  const actual = await vi.importActual<typeof import('../lib/api')>('../lib/api');
  return {
    ...actual,
    api: {
      ...actual.api,
      state: vi.fn(), scenario: vi.fn(), transport: vi.fn(), resetCase: vi.fn(),
      setBlackout: vi.fn(), acknowledgePacket: vi.fn(), lab: vi.fn(),
      examUltrasound: vi.fn(),
    },
  };
});

const mocked = vi.mocked(api);
let current: WorkstationState;

beforeEach(() => {
  current = makeState();
  mocked.state.mockImplementation(async () => current);
  mocked.scenario.mockImplementation(async (payload) => {
    if (payload.replay_participant) current = replayState();
    else if (payload.scenario_id === 'sans-stale-eye') current = sansState();
    else if (payload.scenario_id === 'eva-ared-exercise') current = exerciseState();
    else if (payload.scenario_id === 'spe-radiation') current = escalatedState();
    else if (payload.habitat) current = { ...current, habitat: payload.habitat as WorkstationState['habitat'] };
    return current;
  });
  mocked.transport.mockImplementation(async (action, dtS) => {
    if (action === 'pause') current = { ...current, running: false };
    else if (action === 'play') current = { ...current, running: true };
    else if (action === 'step') current = { ...current, t_s: current.t_s + (dtS ?? 10) };
    return current;
  });
  mocked.resetCase.mockImplementation(async () => { current = makeState(); return current; });
  mocked.setBlackout.mockImplementation(async (blackout) => {
    current = { ...current, comms: { ...current.comms!, blackout } };
    return { ...current, packets: current.comms!.packets, blackout };
  });
  mocked.acknowledgePacket.mockImplementation(async () => {
    current = acknowledgedState();
    return { ...current, receipt: current.comms!.packets[0]!.receipt! };
  });
  mocked.lab.mockResolvedValue({
    lane: 'LAB DATA', provenance: 'NASA OSDR OSD-575', generated_at: '2026-11-14T12:00:00.000Z',
    disclaimer: 'demo', available: true, detail: 'verified', sha256: 'c'.repeat(64),
    rows: [{ sample: 'FL-1', group: 'flight', mass_mg: 12.4 }, { sample: 'GC-1', group: 'ground', mass_mg: 14.1 }],
  });
  mocked.examUltrasound.mockImplementation(async () => { current = makeState(); return current; });
});

afterEach(() => { cleanup(); vi.clearAllMocks(); });

async function renderCockpit() {
  const assertQuiet = expectNoConsoleErrors();
  render(<MemoryRouter><WorkstationProvider><WorkstationPage /></WorkstationProvider></MemoryRouter>);
  await screen.findByRole('heading', { name: 'Assess. Verify. Act.' });
  return assertQuiet;
}

describe('astronaut-in-seat cockpit', () => {
  it('shows the ticking clock, transport controls and stream health in one strip', async () => {
    const assertQuiet = await renderCockpit();
    const strip = screen.getByRole('region', { name: 'Mission clock and transport' });
    expect(within(strip).getByText('LIVE 1.0 Hz')).toBeTruthy();
    expect(within(strip).getByLabelText('Mission elapsed time').textContent).toBe('T+0002s');
    expect(within(strip).getByRole('button', { name: 'Pause mission clock' })).toBeTruthy();
    expect(within(strip).getByRole('button', { name: 'Step forward 10 seconds' })).toBeTruthy();
    expect(within(strip).getByRole('button', { name: 'Reset case to nominal' })).toBeTruthy();
    assertQuiet();
  });

  it('pauses, steps ten seconds and resets the case through the API', async () => {
    const assertQuiet = await renderCockpit();
    fireEvent.click(screen.getByRole('button', { name: 'Pause mission clock' }));
    await waitFor(() => expect(mocked.transport).toHaveBeenCalledWith('pause'));
    await screen.findByText('PAUSED');

    fireEvent.click(screen.getByRole('button', { name: 'Step forward 10 seconds' }));
    await waitFor(() => expect(mocked.transport).toHaveBeenCalledWith('step', 10));
    await waitFor(() => expect(screen.getByLabelText('Mission elapsed time').textContent).toBe('T+0012s'));

    fireEvent.click(screen.getByRole('button', { name: 'Reset case to nominal' }));
    await waitFor(() => expect(mocked.resetCase).toHaveBeenCalledTimes(1));
    await screen.findByText(/Case reset to nominal monitoring/);
    assertQuiet();
  });

  it('renders the S0-S4 lifecycle progression and the demo routing disclaimer', async () => {
    const assertQuiet = await renderCockpit();
    const banner = screen.getByRole('region', { name: 'Mission health lifecycle' });
    expect(within(banner).getByText('S0 · NOMINAL MONITORING')).toBeTruthy();
    for (const code of ['S0', 'S1', 'S2', 'S3', 'S4']) {
      expect(within(banner).getAllByText(new RegExp(`^${code}`)).length).toBeGreaterThan(0);
    }
    expect(within(banner).getByText(/DEMO routing table/)).toBeTruthy();
    assertQuiet();
  });

  it('pulses amber and auto-focuses the ultrasound when an S2 hold needs an exam', async () => {
    current = sansState();
    const assertQuiet = await renderCockpit();
    expect(screen.getAllByText('ACTION REQUIRED TO RESOLVE S2 HOLD').length).toBeGreaterThan(0);
    const bay = screen.getByRole('tablist', { name: 'Crew instruments' });
    expect(within(bay).getByRole('tab', { name: /Eye ONSD/ }).getAttribute('aria-selected')).toBe('true');
    // The instrument itself is mounted exactly once, in the always-visible bay.
    expect(screen.getAllByRole('button', { name: 'Save eye measurement' })).toHaveLength(1);
    assertQuiet();
  });

  it('keeps all three instruments visible without opening a tab', async () => {
    const assertQuiet = await renderCockpit();
    const bay = screen.getByRole('tablist', { name: 'Crew instruments' });
    for (const name of [/^PVT/, /Eye ONSD/, /^Vitals/]) {
      expect(within(bay).getByRole('tab', { name })).toBeTruthy();
    }
    fireEvent.click(within(bay).getByRole('tab', { name: /^Vitals/ }));
    expect(screen.getByLabelText(/Systolic/)).toBeTruthy();
    assertQuiet();
  });

  it('switches to the recorded non-astronaut replay lane and labels it', async () => {
    const assertQuiet = await renderCockpit();
    fireEvent.change(screen.getByLabelText('Recorded human replay participant, not astronauts'), { target: { value: 's1' } });
    await waitFor(() => expect(mocked.scenario).toHaveBeenCalledWith({ replay_participant: 's1' }));
    await screen.findByText('RECORDED HUMAN REPLAY · NON-ASTRONAUT');
    expect(screen.getByText(/streaming s1/)).toBeTruthy();
    assertQuiet();
  });

  it('toggles the rover blackout through the comms endpoint', async () => {
    const assertQuiet = await renderCockpit();
    fireEvent.click(screen.getByLabelText('Rover blackout'));
    await waitFor(() => expect(mocked.setBlackout).toHaveBeenCalledWith(true));
    await screen.findByText(/Rover blackout engaged/);
    assertQuiet();
  });
});

describe('store-and-forward surgeon loop', () => {
  it('shows the queued-to-acknowledged flow and the in-transit countdown', async () => {
    current = escalatedState();
    const assertQuiet = await renderCockpit();
    const outbox = screen.getByText('Store-and-forward outbox').closest('.card-surface') as HTMLElement;
    expect(within(outbox).getByText(/IN TRANSIT/)).toBeTruthy();
    expect(within(outbox).getByText('pkt-abcdefgh')).toBeTruthy();
    expect(within(outbox).getByText('LINK UP')).toBeTruthy();
    fireEvent.click(within(outbox).getByRole('button', { name: 'Read SBAR packet' }));
    expect(within(outbox).getByText('Situation')).toBeTruthy();
    expect(within(outbox).getAllByText(/S4 escalation for demo-crew-1/).length).toBeGreaterThan(0);
    assertQuiet();
  });

  it('refuses to send an empty directive and acknowledges a delivered packet', async () => {
    current = deliveredState();
    const assertQuiet = await renderCockpit();
    const send = screen.getByRole('button', { name: /Acknowledge & send directive/ });
    expect(send).toHaveProperty('disabled', true);
    fireEvent.change(screen.getByLabelText(/Act as Flight Surgeon/), { target: { value: 'Recheck ONSD in 30 minutes.' } });
    expect(send).toHaveProperty('disabled', false);
    fireEvent.click(send);
    await waitFor(() => expect(mocked.acknowledgePacket).toHaveBeenCalledWith('pkt-abcdefgh', 'Recheck ONSD in 30 minutes.'));
    await screen.findByText('S4_SURGEON_ACKNOWLEDGED');
    expect(screen.getByText(/Receipt rcpt-abcdefgh/)).toBeTruthy();
    assertQuiet();
  });

  it('renders the acknowledgement receipt hash without claiming a blockchain', async () => {
    current = acknowledgedState();
    const assertQuiet = await renderCockpit();
    expect(screen.getByText('S4_SURGEON_ACKNOWLEDGED')).toBeTruthy();
    expect(screen.getByText(/sha256 bbbbbbbb/)).toBeTruthy();
    expect(screen.queryByRole('button', { name: /Acknowledge & send directive/ })).toBeNull();
    assertQuiet();
  });
});

describe('provenance lanes stay separate and honest', () => {
  it('labels GOES as pfu with a cache age and an explicit not-dose note', async () => {
    const assertQuiet = await renderCockpit();
    expect(screen.getByText('NOAA GOES proton flux')).toBeTruthy();
    expect(screen.getByText('pfu')).toBeTruthy();
    expect(screen.getByText(/NOT absorbed tissue dose in mGy\/day/)).toBeTruthy();
    expect(screen.getByText(/cache age/)).toBeTruthy();
    assertQuiet();
  });

  it('opens the OSD-575 drawer and shows verified rows with their manifest hash', async () => {
    const assertQuiet = await renderCockpit();
    fireEvent.click(screen.getByRole('button', { name: /OSD-575 pre\/post lab/ }));
    await waitFor(() => expect(mocked.lab).toHaveBeenCalledTimes(1));
    await screen.findByText('2 VERIFIED ROWS');
    expect(screen.getByText('FL-1')).toBeTruthy();
    expect(screen.getByText(/sha256 cccccccccccccccc/)).toBeTruthy();
    expect(screen.getByText(/not an environmental sensor/)).toBeTruthy();
    assertQuiet();
  });

  it('never labels the recorded replay lane as astronaut data', async () => {
    current = replayState();
    const assertQuiet = await renderCockpit();
    expect(screen.getByText(/RECORDED · NON-ASTRONAUT · terrestrial exercise/)).toBeTruthy();
    expect(screen.getByText(/3332/)).toBeTruthy();
    assertQuiet();
  });
});
