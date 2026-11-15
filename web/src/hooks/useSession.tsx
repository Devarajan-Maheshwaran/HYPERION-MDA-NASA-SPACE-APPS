import * as React from 'react';
import { api, setRole, subscribeFrames } from '../lib/api';
import type { Frame, Habitat, Role, SessionResponse, Subject } from '../lib/types';

interface SessionContextValue {
  session: SessionResponse | null;
  role: Role;
  subjectId: string;
  habitat: Habitat;
  subjects: Subject[];
  error: string | null;
  loading: boolean;
  frame: Frame | null;
  history: Frame[];
  connected: boolean;
  running: boolean;
  refresh: () => Promise<void>;
  changeRole: (role: Role) => Promise<void>;
  changeSubject: (id: string) => Promise<void>;
  changeHabitat: (habitat: Habitat) => Promise<void>;
  startScenario: (id: string) => Promise<void>;
  stopScenario: () => Promise<void>;
  pushFrame: (frame: Frame) => void;
}

const SessionContext = React.createContext<SessionContextValue | null>(null);
const MAX_HISTORY = 240;

export function SessionProvider({ children }: { children: React.ReactNode }) {
  const [session, setSession] = React.useState<SessionResponse | null>(null);
  const [role, setLocalRole] = React.useState<Role>('crew');
  const [error, setError] = React.useState<string | null>(null);
  const [loading, setLoading] = React.useState(true);
  const [frame, setFrame] = React.useState<Frame | null>(null);
  const [history, setHistory] = React.useState<Frame[]>([]);
  const [connected, setConnected] = React.useState(false);
  const [running, setRunning] = React.useState(false);

  const pushFrame = React.useCallback((next: Frame) => {
    setFrame(next);
    setHistory((prev) => [...prev, next].slice(-MAX_HISTORY));
  }, []);

  const refresh = React.useCallback(async () => {
    try {
      const data = await api.session();
      setSession(data);
      setLocalRole(data.role);
      setRole(data.role);
      setRunning(data.running);
      setError(null);
      const state = await api.streamState();
      if (state.frame) setFrame(state.frame);
      if (state.history.length) setHistory(state.history.slice(-MAX_HISTORY));
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : String(exc));
    } finally {
      setLoading(false);
    }
  }, []);

  React.useEffect(() => {
    void refresh();
  }, [refresh]);

  React.useEffect(() => subscribeFrames(pushFrame, setConnected), [pushFrame]);

  // The server advances frames; this drives it while a scenario is running so the demo
  // is live without a background worker on the backend.
  React.useEffect(() => {
    if (!running) return;
    const timer = setInterval(() => {
      void api.step(1).then(
        (result) => pushFrame(result.frame),
        () => setRunning(false),
      );
    }, 1000);
    return () => clearInterval(timer);
  }, [running, pushFrame]);

  const changeRole = React.useCallback(
    async (next: Role) => {
      setRole(next);
      setLocalRole(next);
      try {
        const data = await api.setSession({ role: next });
        setSession(data);
        setError(null);
      } catch (exc) {
        setError(exc instanceof Error ? exc.message : String(exc));
      }
    },
    [],
  );

  const changeSubject = React.useCallback(async (id: string) => {
    try {
      const data = await api.setSession({ subject_id: id });
      setSession(data);
      setHistory([]);
      setFrame(null);
      setError(null);
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : String(exc));
    }
  }, []);

  const changeHabitat = React.useCallback(async (habitat: Habitat) => {
    try {
      setSession(await api.setSession({ habitat }));
      setError(null);
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : String(exc));
    }
  }, []);

  const startScenario = React.useCallback(
    async (id: string) => {
      try {
        const result = await api.startScenario(id);
        setHistory([result.frame]);
        setFrame(result.frame);
        setRunning(true);
        setError(null);
        await refresh();
        setRunning(true);
      } catch (exc) {
        setError(exc instanceof Error ? exc.message : String(exc));
      }
    },
    [refresh],
  );

  const stopScenario = React.useCallback(async () => {
    try {
      await api.stop();
      setRunning(false);
      setError(null);
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : String(exc));
    }
  }, []);

  const value: SessionContextValue = {
    session,
    role,
    subjectId: session?.subject_id ?? 'demo-crew-1',
    habitat: session?.habitat ?? 'Space Station (0g)',
    subjects: session?.subjects ?? [],
    error,
    loading,
    frame,
    history,
    connected,
    running,
    refresh,
    changeRole,
    changeSubject,
    changeHabitat,
    startScenario,
    stopScenario,
    pushFrame,
  };

  return <SessionContext.Provider value={value}>{children}</SessionContext.Provider>;
}

export function useSession(): SessionContextValue {
  const context = React.useContext(SessionContext);
  if (!context) throw new Error('useSession must be used inside SessionProvider');
  return context;
}
