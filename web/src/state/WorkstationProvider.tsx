import { createContext, useCallback, useContext, useEffect, useRef, useState, type ReactNode } from 'react';
import { api, subscribeState } from '../lib/api';
import type { OutboxPacket, WorkstationState } from '../lib/types';

export type StreamHealth = 'connecting' | 'live' | 'polling' | 'offline';

interface WorkstationContextValue {
  state: WorkstationState | null;
  loading: boolean;
  busy: boolean;
  error: string | null;
  revision: number;
  lastUpdated: string | null;
  notice: string | null;
  streamHealth: StreamHealth;
  reload: () => Promise<void>;
  selectScenario: (scenarioId: string) => Promise<void>;
  selectReplay: (participant: string) => Promise<void>;
  selectHabitat: (habitat: string) => Promise<void>;
  selectMode: (mode: 'REAL_EMPIRICAL' | 'SIMULATED_FALLBACK') => Promise<void>;
  submitExam: (label: string, request: () => Promise<WorkstationState>) => Promise<boolean>;
  play: () => Promise<void>;
  pause: () => Promise<void>;
  step: (dtS?: number) => Promise<void>;
  resetCase: () => Promise<void>;
  setBlackout: (blackout: boolean) => Promise<void>;
  acknowledge: (packet: OutboxPacket, directive: string) => Promise<boolean>;
  dismissNotice: () => void;
}

const WorkstationContext = createContext<WorkstationContextValue | null>(null);

/** While SSE is healthy we still refresh occasionally, so a dropped server-side
 *  subscriber cannot leave the cockpit frozen. When SSE is down this becomes the
 *  primary 1 Hz-ish transport instead of the old 15 s poll. */
const LIVE_RESYNC_MS = 20000;
const FALLBACK_POLL_MS = 2000;

export function WorkstationProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<WorkstationState | null>(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [revision, setRevision] = useState(0);
  const [lastUpdated, setLastUpdated] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [streamHealth, setStreamHealth] = useState<StreamHealth>('connecting');
  const busyRef = useRef(false);
  const requestSequence = useRef(0);
  const mounted = useRef(true);
  const liveRef = useRef(false);

  const accept = useCallback((next: WorkstationState) => {
    setState(next);
    setLastUpdated(next.generated_at);
    setError(null);
  }, []);

  const load = useCallback(async (interactive = false) => {
    const sequence = ++requestSequence.current;
    if (interactive) setBusy(true);
    try {
      const next = await api.state();
      if (!mounted.current || sequence !== requestSequence.current) return;
      accept(next);
    } catch (cause) {
      if (!mounted.current || sequence !== requestSequence.current) return;
      setError(cause instanceof Error ? cause.message : 'Could not reach the workstation API.');
      setStreamHealth('offline');
    } finally {
      if (mounted.current && sequence === requestSequence.current) {
        setLoading(false);
        if (interactive) setBusy(false);
      }
    }
  }, [accept]);

  useEffect(() => {
    mounted.current = true;
    void load();
    // EventSource is absent in some test/embedded environments; the poll keeps working.
    const unsubscribe = typeof EventSource === 'function'
      ? subscribeState(
          (next) => {
            if (!mounted.current || busyRef.current) return;
            liveRef.current = true;
            // SSE snapshots must not clobber an in-flight interactive response.
            requestSequence.current += 1;
            accept(next);
            setLoading(false);
          },
          (connected) => {
            if (!mounted.current) return;
            liveRef.current = connected;
            setStreamHealth(connected ? 'live' : 'polling');
          },
        )
      : () => undefined;
    if (typeof EventSource !== 'function') setStreamHealth('polling');

    const lastResync = { current: Date.now() };
    const timer = window.setInterval(() => {
      if (busyRef.current || document.visibilityState === 'hidden') return;
      if (liveRef.current) {
        // Cheap periodic resync only; SSE is carrying the 1 Hz frames.
        if (Date.now() - lastResync.current >= LIVE_RESYNC_MS) {
          lastResync.current = Date.now();
          void load();
        }
      } else {
        void load();
      }
    }, FALLBACK_POLL_MS);

    return () => {
      mounted.current = false;
      window.clearInterval(timer);
      unsubscribe();
      requestSequence.current += 1;
    };
  }, [load, accept]);

  const mutate = useCallback(async (request: () => Promise<WorkstationState>, success?: string): Promise<boolean> => {
    if (busyRef.current) return false;
    busyRef.current = true;
    setBusy(true);
    setError(null);
    setNotice(null);
    const sequence = ++requestSequence.current;
    try {
      const next = await request();
      if (!mounted.current || sequence !== requestSequence.current) return false;
      accept(next);
      setRevision((value) => value + 1);
      if (success) setNotice(success);
      return true;
    } catch (cause) {
      if (mounted.current && sequence === requestSequence.current) {
        setError(cause instanceof Error ? cause.message : 'The request could not be completed.');
      }
      return false;
    } finally {
      busyRef.current = false;
      if (mounted.current && sequence === requestSequence.current) setBusy(false);
    }
  }, [accept]);

  const selectScenario = useCallback(async (scenarioId: string) => {
    await mutate(() => api.scenario({ scenario_id: scenarioId }), 'Scenario loaded. Safety gates re-evaluated.');
  }, [mutate]);

  const selectReplay = useCallback(async (participant: string) => {
    await mutate(() => api.scenario({ replay_participant: participant }),
      `Recorded non-astronaut replay ${participant} loaded. Not astronaut telemetry.`);
  }, [mutate]);

  const selectHabitat = useCallback(async (habitat: string) => {
    await mutate(() => api.scenario({ habitat }), 'Mission habitat and comms delay updated.');
  }, [mutate]);

  const selectMode = useCallback(async (mode: 'REAL_EMPIRICAL' | 'SIMULATED_FALLBACK') => {
    await mutate(
      () => api.scenario(mode === 'SIMULATED_FALLBACK' ? { mode, scenario_id: 'nominal-orbital' } : { mode }),
      mode === 'REAL_EMPIRICAL'
        ? 'Real-source mode selected. No live astronaut telemetry is connected.'
        : 'Explicitly simulated fallback loaded.',
    );
  }, [mutate]);

  const submitExam = useCallback(async (label: string, request: () => Promise<WorkstationState>) => {
    return mutate(request, `${label} saved. Freshness and safety gates updated.`);
  }, [mutate]);

  const play = useCallback(async () => { await mutate(() => api.transport('play')); }, [mutate]);
  const pause = useCallback(async () => { await mutate(() => api.transport('pause')); }, [mutate]);
  const step = useCallback(async (dtS = 10) => { await mutate(() => api.transport('step', dtS)); }, [mutate]);
  const resetCase = useCallback(async () => {
    await mutate(() => api.resetCase(), 'Case reset to nominal monitoring. The audit chain was preserved.');
  }, [mutate]);

  const setBlackout = useCallback(async (blackout: boolean) => {
    // The blackout endpoint returns an outbox envelope, so refresh the full state after it.
    if (busyRef.current) return;
    busyRef.current = true;
    setBusy(true);
    try {
      await api.setBlackout(blackout);
      const next = await api.state();
      if (mounted.current) accept(next);
      setNotice(blackout ? 'Rover blackout engaged. New packets queue until the link returns.' : 'Link restored. Queued packets released.');
    } catch (cause) {
      if (mounted.current) setError(cause instanceof Error ? cause.message : 'Could not change the comms link.');
    } finally {
      busyRef.current = false;
      if (mounted.current) setBusy(false);
    }
  }, [accept]);

  const acknowledge = useCallback(async (packet: OutboxPacket, directive: string) => {
    return mutate(() => api.acknowledgePacket(packet.packet_id, directive),
      'Directive sent. Acknowledgement receipt written to the local audit chain.');
  }, [mutate]);

  const value: WorkstationContextValue = {
    state, loading, busy, error, revision, lastUpdated, notice, streamHealth,
    reload: () => load(true),
    selectScenario, selectReplay, selectHabitat, selectMode, submitExam,
    play, pause, step, resetCase, setBlackout, acknowledge,
    dismissNotice: () => setNotice(null),
  };

  return <WorkstationContext.Provider value={value}>{children}</WorkstationContext.Provider>;
}

export function useWorkstation(): WorkstationContextValue {
  const context = useContext(WorkstationContext);
  if (!context) throw new Error('useWorkstation must be used inside WorkstationProvider');
  return context;
}
