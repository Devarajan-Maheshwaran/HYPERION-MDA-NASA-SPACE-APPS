import { expect, vi } from 'vitest';

/** Fail a test on React warnings/errors rather than silently printing them. */
export function expectNoConsoleErrors() {
  const error = vi.spyOn(console, 'error').mockImplementation(() => {});
  const warn = vi.spyOn(console, 'warn').mockImplementation(() => {});
  return () => {
    const messages = [...error.mock.calls, ...warn.mock.calls].map((call) => call.map(String).join(' '));
    error.mockRestore();
    warn.mockRestore();
    expect(messages, messages.join('\n')).toEqual([]);
  };
}
