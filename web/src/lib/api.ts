// Relative URLs only. The browser never addresses localhost; Vite proxies /api in dev
// and FastAPI serves the SPA in production.

import type {
  Alert,
  AuditEntry,
  Calibration,
  Channel,
  Envelope,
  Frame,
  LaneInfo,
  ManualCheck,
  OrgansResponse,
  Role,
  ScenarioInfo,
  SessionResponse,
  StreamStateResponse,
} from './types';

export class ApiError extends Error {
  constructor(
    public readonly status: number,
    message: string,
  ) {
    super(message);
    this.name = 'ApiError';
  }
}

let currentRole: Role = 'crew';

export function setRole(role: Role): void {
  currentRole = role;
}

export function getRole(): Role {
  return currentRole;
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const response = await fetch(path, {
    ...init,
    headers: {
      'Content-Type': 'application/json',
      'X-Role': currentRole,
      ...(init.headers ?? {}),
    },
  });
  if (!response.ok) {
    let detail = `${response.status} ${response.statusText}`;
    try {
      const body = (await response.json()) as { detail?: unknown };
      if (typeof body.detail === 'string') detail = body.detail;
    } catch {
      // keep the status line
    }
    throw new ApiError(response.status, detail);
  }
  return (await response.json()) as T;
}

export interface HealthResponse extends Envelope {
  version: string;
  status: string;
  lanes: Record<string, boolean>;
  allowed_actions: string[];
  hard_hr_ceiling_bpm: number;
  max_suppression_hold_s: number;
  auth: string;
}

export const api = {
  health: () => request<HealthResponse>('/api/health'),
  session: () => request<SessionResponse>('/api/session'),
  setSession: (payload: { role?: Role; subject_id?: string; habitat?: string }) =>
    request<SessionResponse>('/api/session', { method: 'POST', body: JSON.stringify(payload) }),
  lanes: () => request<Envelope & { lanes: LaneInfo[] }>('/api/lanes'),
  registry: () =>
    request<Envelope & { total: number; by_status: Record<string, number>; channels: Channel[] }>(
      '/api/registry',
    ),
  scenarios: () => request<Envelope & { scenarios: ScenarioInfo[] }>('/api/scenarios'),
  startScenario: (id: string) =>
    request<Envelope & { frame: Frame; scenario: ScenarioInfo }>(
      `/api/scenarios/${encodeURIComponent(id)}/start`,
      { method: 'POST' },
    ),
  stop: () => request<Envelope & { running: boolean }>('/api/stream/stop', { method: 'POST' }),
  step: (dt = 1) =>
    request<Envelope & { frame: Frame; alert: Alert | null }>(`/api/stream/step?dt_s=${dt}`, {
      method: 'POST',
    }),
  streamState: () => request<StreamStateResponse>('/api/stream/state'),
  organs: (subjectId?: string) =>
    request<OrgansResponse>(
      `/api/organs${subjectId ? `?subject_id=${encodeURIComponent(subjectId)}` : ''}`,
    ),
  calibrate: (subjectId: string) =>
    request<Envelope & { calibration: Calibration }>(
      `/api/calibration/${encodeURIComponent(subjectId)}`,
      { method: 'POST' },
    ),
  uncalibrate: (subjectId: string) =>
    request<Envelope & { calibration: Calibration }>(
      `/api/calibration/${encodeURIComponent(subjectId)}`,
      { method: 'DELETE' },
    ),
  manual: (subjectId: string) =>
    request<Envelope & { checks: ManualCheck[]; validity_hours: Record<string, number> }>(
      `/api/manual/${encodeURIComponent(subjectId)}`,
    ),
  postManual: (check: Partial<ManualCheck>) =>
    request<Envelope & { check: ManualCheck }>('/api/manual', {
      method: 'POST',
      body: JSON.stringify(check),
    }),
  pvt: (subjectId: string, reactionMs: number[]) =>
    request<Envelope & { median_ms: number; n: number; lapses_over_350ms: number }>('/api/pvt', {
      method: 'POST',
      body: JSON.stringify({ subject_id: subjectId, reaction_ms: reactionMs }),
    }),
  alerts: () => request<Envelope & { alerts: Alert[] }>('/api/alerts'),
  ack: (alertId: string, note: string) =>
    request<Envelope & { alert: Alert }>(`/api/alerts/${encodeURIComponent(alertId)}/ack`, {
      method: 'POST',
      body: JSON.stringify({ note }),
    }),
  audit: () => request<Envelope & { entries: AuditEntry[] }>('/api/audit'),
  verifyAudit: () =>
    request<Envelope & { ok: boolean; entries: number; first_bad_index: number | null; reason: string }>(
      '/api/audit/verify',
    ),
  m6: () =>
    request<Envelope & { available: boolean; detail: string; results: Record<string, unknown> | null }>(
      '/api/research/m6',
    ),
  lab: () =>
    request<
      Envelope & {
        available: boolean;
        detail: string;
        rows: Array<Record<string, unknown>>;
        sha256?: string;
      }
    >('/api/lab/osd575'),
};

/** SSE with automatic reconnect. Returns an unsubscribe function. */
export function subscribeFrames(
  onFrame: (frame: Frame) => void,
  onStatus?: (connected: boolean) => void,
): () => void {
  let source: EventSource | null = null;
  let closed = false;
  let retry: ReturnType<typeof setTimeout> | undefined;

  const connect = (): void => {
    if (closed) return;
    source = new EventSource('/api/stream/events');
    source.addEventListener('open', () => onStatus?.(true));
    source.addEventListener('frame', (event) => {
      try {
        onFrame(JSON.parse((event as MessageEvent<string>).data) as Frame);
      } catch {
        // ignore a malformed frame rather than breaking the stream
      }
    });
    source.addEventListener('error', () => {
      onStatus?.(false);
      source?.close();
      if (!closed) retry = setTimeout(connect, 2000);
    });
  };

  connect();
  return () => {
    closed = true;
    if (retry) clearTimeout(retry);
    source?.close();
    onStatus?.(false);
  };
}
