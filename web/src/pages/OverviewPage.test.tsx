// @vitest-environment jsdom
import { afterEach, describe, expect, it } from 'vitest';
import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { OverviewPage } from './OverviewPage';

afterEach(cleanup);

function renderOverview() {
  return render(<MemoryRouter><OverviewPage /></MemoryRouter>);
}

describe('Overview landing page', () => {
  it('explains the mission problem and links to the two product views', () => {
    renderOverview();
    expect(screen.getByRole('heading', { level: 1 }).textContent).toContain('filter out exercise false alarms');
    expect(screen.getByRole('link', { name: /Launch Live Crew Workstation/ }).getAttribute('href')).toBe('/');
    expect(screen.getByRole('link', { name: /Read ML & System Docs/ }).getAttribute('href')).toBe('/docs');
    expect(screen.getByText('z = (x − μ₀) / σ₀')).toBeTruthy();
    expect(screen.getByText('τ = e^(−λΔt)')).toBeTruthy();
  });

  it('reveals a two-sentence architecture summary on demand', () => {
    renderOverview();
    const gate = screen.getByRole('tab', { name: /3-Stage Safety Gate/ });
    fireEvent.click(gate);
    expect(gate.getAttribute('aria-selected')).toBe('true');
    expect(screen.getByRole('tabpanel').textContent).toContain('Hard ceilings');
    const data = screen.getByRole('tab', { name: /Tri-Stream Real Data/ });
    fireEvent.click(data);
    expect(screen.getByRole('tabpanel').textContent).toContain('explicitly simulated fallback');
  });
});
