import { describe, expect, it } from 'vitest';
import { commsDelay, freshnessPercent, gateTone, median, organTone, recommendedTool, triageTone } from './clinical';
import { exerciseState, makeState, sansState } from '../test/fixtures';

describe('clinical display helpers', () => {
  it('never paints unknown or missing states green', () => {
    expect(organTone('UNKNOWN')).toBe('neutral');
    expect(organTone('NOT_AVAILABLE')).toBe('neutral');
    expect(gateTone(undefined)).toBe('neutral');
    expect(gateTone({ gate: 1, outcome: 'UNKNOWN', reason: '', evidence: {} })).toBe('neutral');
    expect(triageTone('UNKNOWN')).toBe('neutral');
  });

  it('treats protective gate interventions as watch, not critical', () => {
    expect(gateTone({ gate: 2, outcome: 'BLOCK', reason: '', evidence: {} })).toBe('watch');
    expect(gateTone({ gate: 3, outcome: 'HOLD', reason: '', evidence: {} })).toBe('watch');
  });

  it('clamps freshness to a percentage and preserves missing data', () => {
    expect(freshnessPercent(null)).toBeNull();
    expect(freshnessPercent(undefined)).toBeNull();
    expect(freshnessPercent(Number.NaN)).toBeNull();
    expect(freshnessPercent(0.18)).toBe(18);
    expect(freshnessPercent(1.4)).toBe(100);
    expect(freshnessPercent(-0.2)).toBe(0);
  });

  it('routes the recommended crew check from the gate, not a guess', () => {
    expect(recommendedTool(makeState())).toBe('pvt');
    expect(recommendedTool(sansState())).toBe('ultrasound');
    expect(recommendedTool(exerciseState())).toBe('pvt');
  });

  it('computes a median without mutating the input', () => {
    const values = [310, 288, 340, 305, 295];
    expect(median(values)).toBe(305);
    expect(values).toEqual([310, 288, 340, 305, 295]);
    expect(median([280, 300])).toBe(290);
    expect(median([])).toBeNull();
  });

  it('shows the transit communication delay and never invents a rover delay', () => {
    expect(commsDelay('transit')).toBe('20 min');
    expect(commsDelay('rover')).toBe('—');
  });
});
