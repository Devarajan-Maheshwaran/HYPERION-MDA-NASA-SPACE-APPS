// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { App } from './App';
import { api } from './lib/api';
import { makeState } from './test/fixtures';
import { expectNoConsoleErrors } from './test/console';

vi.mock('./lib/api', async () => {
  const actual = await vi.importActual<typeof import('./lib/api')>('./lib/api');
  return { ...actual, api: { ...actual.api, state: vi.fn(), scenario: vi.fn() } };
});

afterEach(() => { cleanup(); vi.clearAllMocks(); });

describe('three-view application shell', () => {
  it('boots directly into the live Crew Workstation, never a blank chart', async () => {
    const assertQuiet = expectNoConsoleErrors();
    vi.mocked(api.state).mockResolvedValue(makeState());
    render(<MemoryRouter initialEntries={['/']}><App /></MemoryRouter>);
    await screen.findByRole('heading', { name: 'Assess. Verify. Act.' });
    expect(screen.getAllByLabelText('Raw heart rate and residual chart')).toHaveLength(1);
    expect(screen.getByRole('navigation', { name: 'Primary' })).toBeTruthy();
    assertQuiet();
  });

  it('keeps Overview and Docs reachable and exposes the provenance popover', async () => {
    const assertQuiet = expectNoConsoleErrors();
    vi.mocked(api.state).mockResolvedValue(makeState());
    vi.mocked(api.scenario).mockResolvedValue(makeState({ data_source_mode: 'REAL_EMPIRICAL', telemetry_mode: 'NOT_AVAILABLE', frame: null, history: [], gates: [] }));
    render(<MemoryRouter initialEntries={['/overview']}><App /></MemoryRouter>);

    await screen.findByRole('heading', { level: 1, name: /Helping astronauts/ });
    expect(screen.getByRole('navigation', { name: 'Primary' })).toBeTruthy();

    fireEvent.click(screen.getByRole('link', { name: /01.*Crew Workstation/ }));
    await screen.findByRole('heading', { name: 'Assess. Verify. Act.' });

    fireEvent.click(screen.getByRole('link', { name: /03.*ML Architecture & Docs/ }));
    await screen.findByText('Requested benchmarks');

    fireEvent.click(screen.getByRole('button', { name: 'Data provenance and source mode' }));
    await screen.findByText('Data provenance');
    fireEvent.click(screen.getByRole('button', { name: /Real Empirical Data/ }));
    await waitFor(() => expect(vi.mocked(api.scenario)).toHaveBeenCalledWith({ mode: 'REAL_EMPIRICAL' }));
    assertQuiet();
  });
});
