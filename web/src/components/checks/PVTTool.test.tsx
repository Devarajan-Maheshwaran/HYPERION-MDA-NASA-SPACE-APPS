// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { act, cleanup, fireEvent, render, screen } from '@testing-library/react';
import { PVTTool } from './PVTTool';
import { WorkstationProvider } from '../../state/WorkstationProvider';
import { api } from '../../lib/api';
import { makeState } from '../../test/fixtures';
import { expectNoConsoleErrors } from '../../test/console';

vi.mock('../../lib/api', async () => {
  const actual = await vi.importActual<typeof import('../../lib/api')>('../../lib/api');
  return { ...actual, api: { ...actual.api, state: vi.fn(), examPvt: vi.fn() } };
});

const mocked = vi.mocked(api);
const onSaved = vi.fn();
let clock = 1000;

beforeEach(() => {
  vi.useFakeTimers();
  vi.spyOn(Math, 'random').mockReturnValue(0);
  clock = 1000;
  vi.spyOn(performance, 'now').mockImplementation(() => clock);
  mocked.state.mockResolvedValue(makeState());
  mocked.examPvt.mockResolvedValue(makeState({ readiness: { ...makeState().readiness, freshness_tau_avg: 1 } }));
});

afterEach(() => {
  cleanup();
  vi.useRealTimers();
  vi.restoreAllMocks();
  onSaved.mockClear();
});

async function renderTool() {
  const assertQuiet = expectNoConsoleErrors();
  render(<WorkstationProvider><PVTTool onSaved={onSaved} /></WorkstationProvider>);
  await act(async () => { await Promise.resolve(); });
  return assertQuiet;
}

describe('PVT crew check', () => {
  it('discards early clicks and records five performance.now reaction times', async () => {
    const assertQuiet = await renderTool();
    fireEvent.click(screen.getByRole('button', { name: 'Start reaction test' }));
    fireEvent.click(screen.getByRole('button', { name: 'Wait for reaction target' }));
    expect(screen.getByText(/Too early/)).toBeTruthy();
    expect(mocked.examPvt).not.toHaveBeenCalled();

    fireEvent.click(screen.getByRole('button', { name: 'Start reaction test' }));
    for (let trial = 0; trial < 5; trial += 1) {
      clock = 1000 + trial * 1000;
      await act(async () => { vi.advanceTimersByTime(1200); });
      clock += 280 + trial * 10;
      fireEvent.click(screen.getByRole('button', { name: 'Click reaction target now' }));
    }
    await act(async () => { await vi.advanceTimersByTimeAsync(1); });
    expect(mocked.examPvt).toHaveBeenCalledTimes(1);
    const samples = mocked.examPvt.mock.calls[0]![0];
    expect(samples).toEqual([280, 290, 300, 310, 320]);
    expect(onSaved).toHaveBeenCalledTimes(1);
    assertQuiet();
  });
});
