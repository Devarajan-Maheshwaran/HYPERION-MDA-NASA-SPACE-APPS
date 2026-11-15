// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { Badge, Button, EmptyState, ErrorNotice, Gauge, MetricTile, Tabs } from './ui';

afterEach(cleanup);

describe('clinical UI primitives', () => {
  it('keeps unknown badges neutral and semantic badges distinct', () => {
    render(<><Badge tone="neutral">UNKNOWN</Badge><Badge tone="nominal">NOMINAL</Badge><Badge tone="critical">ALERT</Badge></>);
    expect(screen.getByText('UNKNOWN').getAttribute('data-tone')).toBe('neutral');
    expect(screen.getByText('NOMINAL').getAttribute('data-tone')).toBe('nominal');
    expect(screen.getByText('ALERT').getAttribute('data-tone')).toBe('critical');
  });

  it('exposes tabs as an accessible tablist', () => {
    const onChange = vi.fn();
    render(<Tabs label="Panels" active="a" onChange={onChange} items={[{ id: 'a', label: 'A' }, { id: 'b', label: 'B' }]} />);
    expect(screen.getByRole('tablist', { name: 'Panels' })).toBeTruthy();
    expect(screen.getByRole('tab', { name: 'A' }).getAttribute('aria-selected')).toBe('true');
    fireEvent.click(screen.getByRole('tab', { name: 'B' }));
    expect(onChange).toHaveBeenCalledWith('b');
  });

  it('renders a bounded freshness gauge', () => {
    render(<Gauge value={140} label="Freshness" />);
    const gauge = screen.getByRole('progressbar', { name: 'Freshness' });
    expect(gauge.getAttribute('aria-valuenow')).toBe('100');
  });

  it('disables busy buttons and keeps retry actions available', () => {
    const onClick = vi.fn();
    render(<Button busy onClick={onClick}>Save</Button>);
    const button = screen.getByRole('button', { name: 'Save' });
    expect((button as HTMLButtonElement).disabled).toBe(true);
    fireEvent.click(button);
    expect(onClick).not.toHaveBeenCalled();
  });

  it('renders missing measurements as a dash, never zero', () => {
    render(<MetricTile label="ONSD" value="—" unit="mm" />);
    expect(screen.getByText('—')).toBeTruthy();
  });

  it('renders error and empty states with actionable text', () => {
    const onRetry = vi.fn();
    render(<><ErrorNotice onRetry={onRetry}>Offline</ErrorNotice><EmptyState title="No telemetry" detail="Select a scenario." /></>);
    expect(screen.getByRole('alert').textContent).toContain('Offline');
    fireEvent.click(screen.getByRole('button', { name: 'Retry' }));
    expect(onRetry).toHaveBeenCalled();
    expect(screen.getByText('No telemetry')).toBeTruthy();
  });
});
