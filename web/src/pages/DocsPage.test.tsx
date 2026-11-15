// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, render, screen } from '@testing-library/react';
import { DocsPage } from './DocsPage';
import { WorkstationProvider } from '../state/WorkstationProvider';
import { api } from '../lib/api';
import { makeState } from '../test/fixtures';
import { expectNoConsoleErrors } from '../test/console';

vi.mock('../lib/api', async () => {
  const actual = await vi.importActual<typeof import('../lib/api')>('../lib/api');
  return { ...actual, api: { ...actual.api, state: vi.fn() } };
});

afterEach(() => { cleanup(); vi.clearAllMocks(); });

describe('ML Architecture & Docs', () => {
  it('labels unmeasured benchmarks and keeps the audit explicitly off-chain', async () => {
    const assertQuiet = expectNoConsoleErrors();
    vi.mocked(api.state).mockResolvedValue(makeState());
    render(<WorkstationProvider><DocsPage /></WorkstationProvider>);
    await screen.findByText('Requested benchmarks');
    expect(screen.getAllByText('NOT_IMPLEMENTED').length).toBeGreaterThan(2);
    expect(screen.getAllByText('SIMULATED_TOY_FEDAVG').length).toBeGreaterThan(0);
    expect(screen.getByText('Zero Raw Private Health Data Stored On-Chain')).toBeTruthy();
    expect(screen.getByText(/no chain exists/)).toBeTruthy();
    expect(screen.getByText('— no EVM tx')).toBeTruthy();
    expect(screen.getByText('24.18 bpm')).toBeTruthy();
    expect(screen.getAllByRole('link').length).toBeGreaterThanOrEqual(5);
    assertQuiet();
  });
});
