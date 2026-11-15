// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { Badge, Button, Dialog, Drawer, Segmented } from './index';

afterEach(cleanup);

describe('redesign primitives', () => {
  it('keeps unknown badges neutral', () => {
    render(<Badge tone="unknown">UNKNOWN</Badge>);
    const badge = screen.getByText('UNKNOWN');
    expect(badge.getAttribute('data-tone')).toBe('unknown');
    expect(badge.className).not.toContain('state-ok');
  });

  it('renders an accessible dialog with a close control', () => {
    const onClose = vi.fn();
    render(<Dialog open title="Acknowledge alert" onClose={onClose}><p>Body</p></Dialog>);
    expect(screen.getByRole('dialog')).toBeTruthy();
    expect(screen.getByText('Acknowledge alert')).toBeTruthy();
    fireEvent.click(screen.getByRole('button', { name: 'Close dialog' }));
    expect(onClose).toHaveBeenCalled();
  });

  it('renders a slide-over drawer with a subtitle', () => {
    render(<Drawer open title="Frame T+0042s" subtitle="demo-crew-1" onClose={() => undefined}><p>Detail</p></Drawer>);
    expect(screen.getByRole('dialog', { name: 'Frame T+0042s' })).toBeTruthy();
    expect(screen.getByText('demo-crew-1')).toBeTruthy();
  });

  it('exposes pressed state on segmented controls', () => {
    const onChange = vi.fn();
    render(<Segmented layoutId="test" value="2m" onChange={onChange}
      options={[{ id: '30s', label: '30s' }, { id: '2m', label: '2m' }]} />);
    expect(screen.getByRole('button', { name: '2m' }).getAttribute('aria-pressed')).toBe('true');
    fireEvent.click(screen.getByRole('button', { name: '30s' }));
    expect(onChange).toHaveBeenCalledWith('30s');
  });

  it('defaults buttons to type=button so they do not submit forms accidentally', () => {
    render(<Button>Run</Button>);
    expect(screen.getByRole('button', { name: 'Run' }).getAttribute('type')).toBe('button');
  });
});
