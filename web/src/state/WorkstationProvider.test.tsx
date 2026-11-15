// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { act, cleanup, render, screen, waitFor } from '@testing-library/react';
import type { ReactNode } from 'react';
import { WorkstationProvider, useWorkstation } from './WorkstationProvider';
import { api } from '../lib/api';
import { makeState } from '../test/fixtures';
import { expectNoConsoleErrors } from '../test/console';

vi.mock('../lib/api', async () => {
  const actual = await vi.importActual<typeof import('../lib/api')>('../lib/api');
  return { ...actual, api: { ...actual.api, state: vi.fn() } };
});

type Listener = (event: { data: string }) => void;

class FakeEventSource {
  static instances: FakeEventSource[] = [];
  static present = true;
  readonly url: string;
  closed = false;
  private listeners = new Map<string, Listener[]>();

  constructor(url: string) {
    this.url = url;
    FakeEventSource.instances.push(this);
  }

  addEventListener(type: string, listener: Listener): void {
    const list = this.listeners.get(type) ?? [];
    list.push(listener);
    this.listeners.set(type, list);
  }

  emit(type: string, data?: unknown): void {
    for (const listener of this.listeners.get(type) ?? []) {
      listener({ data: typeof data === 'string' ? data : JSON.stringify(data) });
    }
  }

  close(): void { this.closed = true; }
}

function Consumer() {
  const { state, streamHealth, error, loading } = useWorkstation();
  return (
    <div>
      <span data-testid="health">{streamHealth}</span>
      <span data-testid="time">{state?.t_s ?? 'none'}</span>
      <span data-testid="loading">{String(loading)}</span>
      <span data-testid="error">{error ?? ''}</span>
    </div>
  );
}

function renderProvider(ui: ReactNode = <Consumer />) {
  return render(<WorkstationProvider>{ui}</WorkstationProvider>);
}

const originalEventSource = globalThis.EventSource;

beforeEach(() => {
  FakeEventSource.instances = [];
  vi.mocked(api.state).mockResolvedValue(makeState());
  Object.defineProperty(globalThis, 'EventSource', { value: FakeEventSource, configurable: true, writable: true });
});

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
  vi.useRealTimers();
  Object.defineProperty(globalThis, 'EventSource', { value: originalEventSource, configurable: true, writable: true });
});

describe('WorkstationProvider SSE transport', () => {
  it('marks the stream live on open and applies state snapshots without polling', async () => {
    const assertQuiet = expectNoConsoleErrors();
    renderProvider();
    await screen.findByTestId('time');
    await waitFor(() => expect(FakeEventSource.instances).toHaveLength(1));
    const source = FakeEventSource.instances[0]!;
    expect(source.url).toBe('/api/stream/events');

    act(() => source.emit('open'));
    await waitFor(() => expect(screen.getByTestId('health').textContent).toBe('live'));

    const callsBefore = vi.mocked(api.state).mock.calls.length;
    act(() => source.emit('state', makeState({ t_s: 42 })));
    await waitFor(() => expect(screen.getByTestId('time').textContent).toBe('42'));
    expect(screen.getByTestId('loading').textContent).toBe('false');
    // A healthy SSE stream must not trigger the 2 s fallback poll.
    expect(vi.mocked(api.state).mock.calls.length).toBe(callsBefore);
    assertQuiet();
  });

  it('ignores malformed snapshots instead of crashing the stream', async () => {
    const assertQuiet = expectNoConsoleErrors();
    renderProvider();
    await waitFor(() => expect(FakeEventSource.instances).toHaveLength(1));
    const source = FakeEventSource.instances[0]!;
    act(() => {
      source.emit('open');
      source.emit('state', '{not json');
    });
    await waitFor(() => expect(screen.getByTestId('health').textContent).toBe('live'));
    expect(screen.getByTestId('time').textContent).toBe('2');
    assertQuiet();
  });

  it('falls back to polling when SSE errors and reconnects after the retry delay', async () => {
    const assertQuiet = expectNoConsoleErrors();
    renderProvider();
    await waitFor(() => expect(FakeEventSource.instances).toHaveLength(1));
    const first = FakeEventSource.instances[0]!;
    act(() => first.emit('open'));
    await waitFor(() => expect(screen.getByTestId('health').textContent).toBe('live'));

    vi.mocked(api.state).mockResolvedValue(makeState({ t_s: 99 }));
    act(() => first.emit('error'));
    expect(first.closed).toBe(true);
    expect(screen.getByTestId('health').textContent).toBe('polling');

    // Real timers: the 2 s fallback poll must refresh state, and subscribeState
    // must open a replacement EventSource after its 2 s reconnect delay.
    await waitFor(() => expect(screen.getByTestId('time').textContent).toBe('99'), { timeout: 4000 });
    await waitFor(() => expect(FakeEventSource.instances.length).toBeGreaterThanOrEqual(2), { timeout: 4000 });
    assertQuiet();
  });

  it('uses the polling fallback when EventSource is unavailable', async () => {
    Object.defineProperty(globalThis, 'EventSource', { value: undefined, configurable: true, writable: true });
    const assertQuiet = expectNoConsoleErrors();
    renderProvider();
    await screen.findByTestId('time');
    expect(screen.getByTestId('health').textContent).toBe('polling');
    expect(FakeEventSource.instances).toHaveLength(0);
    assertQuiet();
  });

  it('surfaces an API-down error and keeps the last known state', async () => {
    const assertQuiet = expectNoConsoleErrors();
    renderProvider();
    await screen.findByTestId('time');
    vi.mocked(api.state).mockRejectedValue(new Error('Failed to fetch'));
    // Force a resync by dropping SSE; the fallback poll should surface the error.
    const source = FakeEventSource.instances[0]!;
    act(() => source.emit('error'));
    await waitFor(() => expect(screen.getByTestId('error').textContent).toBe('Failed to fetch'), { timeout: 4000 });
    expect(screen.getByTestId('health').textContent).toBe('offline');
    expect(screen.getByTestId('time').textContent).toBe('2');
    assertQuiet();
  });

  it('closes the stream and cancels reconnects on unmount', async () => {
    const assertQuiet = expectNoConsoleErrors();
    const { unmount } = renderProvider();
    await waitFor(() => expect(FakeEventSource.instances).toHaveLength(1));
    const source = FakeEventSource.instances[0]!;
    act(() => source.emit('open'));
    unmount();
    expect(source.closed).toBe(true);
    // Give any stray reconnect timer a chance to fire; none should.
    await new Promise((resolve) => setTimeout(resolve, 2500));
    expect(FakeEventSource.instances).toHaveLength(1);
    assertQuiet();
  });
});
