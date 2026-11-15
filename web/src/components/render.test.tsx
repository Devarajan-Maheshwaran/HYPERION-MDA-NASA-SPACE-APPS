// @vitest-environment jsdom
//
// Mounts the real components in a DOM and asserts the honesty rules survive rendering.
// This is not a pixel/browser test: no browser binary is available in this environment.

import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, render, screen } from '@testing-library/react';
import { GateBadges } from './GateBadges';
import { BodyMap, OrganDetail } from './BodyMap';
import type { Frame, OrganReading } from '../lib/types';

afterEach(cleanup);

const frame: Frame = {
  t_s: 42, lane: 'SIMULATED', subject_id: 'demo-crew-1', habitat: 'Space Station (0g)',
  hr_bpm: 147.2, hr_status: 'OK', activity_norm: 128.4,
  activity_unit: 'per-person rest scale (dimensionless)',
  sqi: { kurtosis: 3.1, slew: 42, calibrated: true },
  gates: [
    { gate: 1, outcome: 'PASS', reason: 'within calibrated sensor envelope', evidence: { kurtosis: 3.1 } },
    { gate: 2, outcome: 'BLOCK', reason: "rate explained by this person's activity scale", evidence: { hold_s: 12 } },
    { gate: 3, outcome: 'PASS', reason: 'no rate alarm to hold', evidence: {} },
  ],
  residual_bpm: -1.7, band_upper: 2.3, band_lower: -5.7,
  band_label: 'demo band (empirical residual quantile)',
  state: 'CONTEXT_COMPENSATED', suppressed: true,
  suppression_reason: "rate explained by this person's activity scale",
  non_rate_flags: [], actions: ['Rest and recheck'], scenario_id: 'exercise-false-alarm',
};

const organ: OrganReading = {
  system: 'heart', label: 'Heart & Vessels', status: 'UNKNOWN', indicator: 'bp is stale',
  value: 130, unit: 'mmHg', demo_threshold: 'Rest BP >= 140/90 mmHg (deck claim)',
  threshold_label: 'DEMO THRESHOLD — not a validated clinical limit',
  hazard: 'Gravity shift + radiation (CSA vascular)', staleness_tau: 0.2, age_hours: 11,
  action: 'Repeat measurement', evidence: 'Last bp is 11.0 h old (validity 4 h).',
};

describe('GateBadges rendering', () => {
  it('shows all three gate verdicts', () => {
    render(<GateBadges frame={frame} />);
    expect(screen.getByText('Gate 1')).toBeTruthy();
    expect(screen.getByText('Gate 2')).toBeTruthy();
    expect(screen.getByText('Gate 3')).toBeTruthy();
    expect(screen.getByText('BLOCK')).toBeTruthy();
  });

  it('announces a blocked exercise false alarm', () => {
    render(<GateBadges frame={frame} />);
    expect(screen.getByText(/Gate 2 blocked an exercise false alarm/)).toBeTruthy();
  });

  it('states plainly when there is no data', () => {
    render(<GateBadges frame={null} />);
    expect(screen.getByText(/No gate verdicts yet/)).toBeTruthy();
  });

  it('surfaces a non-rate finding as never suppressed', () => {
    render(<GateBadges frame={{ ...frame, non_rate_flags: ['irregular rhythm (injected)'], state: 'SURGEON_ALERT', suppressed: false }} />);
    expect(screen.getByText(/Non-rate finding — never suppressed/)).toBeTruthy();
  });

  it('does not colour an UNKNOWN gate as passing', () => {
    const unknown: Frame = {
      ...frame, suppressed: false, suppression_reason: null,
      gates: frame.gates.map((g) => ({ ...g, outcome: 'UNKNOWN' as const, reason: 'not calibrated for this person' })),
    };
    const { container } = render(<GateBadges frame={unknown} />);
    const badges = Array.from(container.querySelectorAll('button'));
    expect(badges.length).toBe(3);
    for (const badge of badges) {
      expect(badge.className).toContain('slate');
      expect(badge.className).not.toContain('nominal');
    }
  });
});

describe('BodyMap rendering', () => {
  it('renders one clickable row per system and marks unknown as grey', () => {
    const organs: OrganReading[] = [organ, { ...organ, system: 'metabolic', label: 'Metabolic & Gut', status: 'NOT_AVAILABLE' }];
    const onSelect = vi.fn();
    const { container } = render(<BodyMap organs={organs} selected={null} onSelect={onSelect} />);
    expect(screen.getByText('Heart & Vessels')).toBeTruthy();
    expect(screen.getByText('N/A')).toBeTruthy();
    const chips = Array.from(container.querySelectorAll('span')).filter((s) =>
      ['UNKNOWN', 'N/A'].includes(s.textContent ?? ''));
    expect(chips.length).toBe(2);
    for (const chip of chips) {
      expect(chip.className).toContain('slate');
      expect(chip.className).not.toContain('nominal');
    }
  });

  it('shows the demo-threshold label and an allowed action in the detail panel', () => {
    render(<OrganDetail organ={organ} />);
    expect(screen.getByText(/DEMO THRESHOLD/)).toBeTruthy();
    expect(screen.getByText('Repeat measurement')).toBeTruthy();
    expect(screen.getByText('UNKNOWN')).toBeTruthy();
  });

  it('prompts when nothing is selected', () => {
    render(<OrganDetail organ={null} />);
    expect(screen.getByText(/Select a system on the body map/)).toBeTruthy();
  });
});
