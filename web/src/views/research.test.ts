import { describe, expect, it } from 'vitest';
import { extractHrRows } from './ResearchView';

// Shape taken from the committed experiments/m6/outputs/results.json.
const real = {
  hr: {
    primary: {
      models: {
        A0: { aggregate: { mae: { mean: 24.177234, ci_low: 12.00258, ci_high: 41.169426 } } },
        A1: { aggregate: { mae: { mean: 23.671, ci_low: 13.2, ci_high: 38.9 } } },
        A2: { aggregate: { mae: { mean: 46.32, ci_low: 30.1, ci_high: 62.4 } } },
      },
    },
  },
};

describe('M6 result extraction', () => {
  it('reads mean MAE and the bootstrap interval from the real structure', () => {
    const rows = extractHrRows(real);
    expect(rows.map((r) => r.model)).toEqual(['A0', 'A1', 'A2']);
    expect(rows[0]?.mae).toBeCloseTo(24.177234);
    expect(rows[0]?.ciLow).toBeCloseTo(12.00258);
    expect(rows[0]?.ciHigh).toBeCloseTo(41.169426);
  });

  it('returns nothing rather than inventing rows when the shape is absent', () => {
    expect(extractHrRows(null)).toEqual([]);
    expect(extractHrRows({})).toEqual([]);
    expect(extractHrRows({ hr: {} })).toEqual([]);
    expect(extractHrRows({ hr: { primary: { models: { A0: {} } } } })).toEqual([]);
  });

  it('shows A2 worse than the trivial baseline, without hiding it', () => {
    const rows = extractHrRows(real);
    const a0 = rows.find((r) => r.model === 'A0')?.mae ?? 0;
    const a2 = rows.find((r) => r.model === 'A2')?.mae ?? 0;
    expect(a2).toBeGreaterThan(a0);
  });
});
