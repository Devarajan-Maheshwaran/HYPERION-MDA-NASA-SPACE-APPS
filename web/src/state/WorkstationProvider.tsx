import { createContext, useCallback, useContext, useEffect, useRef, useState, type ReactNode } from 'react';
import { api } from '../lib/api';
import type { WorkstationState } from '../lib/types';

interface WorkstationContextValue {
  state: WorkstationState | null;
  loading: boolean;
  busy: boolean;
  error: string | null;
  revision: number;
  lastUpdated: string | null;
  notice: string | null;
  reload: () => Promise<void>;
  selectScenario: (scenarioId: string) => Promise<void>;
  selectHabitat: (habitat: string) => Promise<void>;
  selectMode: (mode: 'REAL_EMPIRICAL' | 'SIMULATED_FALLBACK') => Promise<void>;
  submitExam: (label: string, request: () => Promise<WorkstationState>) => Promise<boolean>;
  dismissNotice: () => void;
}

const WorkstationContext = createContext<WorkstationContextValue | null>(null);

export function WorkstationProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<WorkstationState | null>(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [revision, setRevision] = useState(0);
  const [lastUpdated, setLastUpdated] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const busyRef = useRef(false);
  const requestSequence = useRef(0);
  const mounted = useRef(true);

  const load = useCallback(async (interactive = false) => {
    const sequence = ++requestSequence.current;
    if (interactive) setBusy(true);
    try {
      const next = await api.state();
      if (!mounted.current || sequence !== requestSequence.current) return;
      setState(next);
      setLastUpdated(next.generated_at);
      setError(null);
    } catch (cause) {
      if (!mounted.current || sequence !== requestSequence.current) return;
      setError(cause instanceof Error ? cause.message : 'Could not reach the workstation API.');
    } finally {
      if (mounted.current && sequence === requestSequence.current) {
        setLoading(false);
        if (interactive) setBusy(false);
      }
    }
  }, []);

  useEffect(() => {
    mounted.current = true;
    void load();
    const timer = window.setInterval(() => {
      if (!busyRef.current && document.visibilityState !== 'hidden') void load();
    }, 15000);
    return () => {
      mounted.current = false;
      window.clearInterval(timer);
      requestSequence.current += 1;
    };
  }, [load]);

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
      setState(next);
      setLastUpdated(next.generated_at);
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
  }, []);

  const selectScenario = useCallback(async (scenarioId: string) => {
    await mutate(() => api.scenario({ scenario_id: scenarioId }), 'Scenario loaded. Safety gates re-evaluated.');
  }, [mutate]);

  const selectHabitat = useCallback(async (habitat: string) => {
    await mutate(() => api.scenario({ habitat }), 'Mission habitat updated.');
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

  const value: WorkstationContextValue = {
    state, loading, busy, error, revision, lastUpdated, notice,
    reload: () => load(true),
    selectScenario, selectHabitat, selectMode, submitExam,
    dismissNotice: () => setNotice(null),
  };

  return <WorkstationContext.Provider value={value}>{children}</WorkstationContext.Provider>;
}

export function useWorkstation(): WorkstationContextValue {
  const context = useContext(WorkstationContext);
  if (!context) throw new Error('useWorkstation must be used inside WorkstationProvider');
  return context;
}
