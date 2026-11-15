import { describe, expect, it } from 'vitest';
import { clockTime, compactHash, missionClock, num, relativeTime, signed } from './format';

describe('instrument formatters', () => {
  it('renders missing numbers as a dash, never zero', () => {
    expect(num(null)).toBe('—');
    expect(num(undefined)).toBe('—');
    expect(num(Number.NaN)).toBe('—');
    expect(num(0)).toBe('0.0');
    expect(num(72.45)).toBe('72.5');
    expect(signed(null)).toBe('—');
    expect(signed(-1.74)).toBe('-1.7');
    expect(signed(2)).toBe('+2.0');
  });

  it('formats a fixed-width mission clock', () => {
    expect(missionClock(42)).toBe('T+0042s');
    expect(missionClock(0)).toBe('T+0000s');
    expect(missionClock(-5)).toBe('T+0000s');
  });

  it('formats relative time without inventing a timestamp', () => {
    const now = Date.parse('2026-11-14T12:00:00Z');
    expect(relativeTime('', now)).toBe('—');
    expect(relativeTime('not-a-date', now)).toBe('—');
    expect(relativeTime('2026-11-14T11:59:58Z', now)).toBe('now');
    expect(relativeTime('2026-11-14T11:59:30Z', now)).toBe('30s ago');
    expect(relativeTime('2026-11-14T11:58:00Z', now)).toBe('2m ago');
  });

  it('handles missing clock and hash inputs', () => {
    expect(clockTime('')).toBe('--:--:--');
    expect(compactHash('')).toBe('—');
    expect(compactHash('abcdef0123456789')).toBe('abcdef01…6789');
  });
});
