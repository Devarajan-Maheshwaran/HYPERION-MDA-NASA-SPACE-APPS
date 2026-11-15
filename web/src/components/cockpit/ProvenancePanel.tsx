import { useEffect, useState } from 'react';
import { ChevronDown, Database, FlaskConical, Satellite } from 'lucide-react';
import { api } from '../../lib/api';
import type { WorkstationState } from '../../lib/types';
import { num, relativeTime } from '../../lib/format';
import { Badge, Card } from '../ui';
import { cn } from '../../lib/utils';

interface LabPayload {
  available: boolean;
  detail: string;
  rows: Array<Record<string, unknown>>;
  sha256?: string;
  provenance?: string;
}

/** Three lanes, never merged: verified lab rows, recorded non-astronaut replay, GOES flux. */
export function ProvenancePanel({ state }: { state: WorkstationState }) {
  const goes = state.sources.goes;
  const replay = state.replay;
  return (
    <Card className="overflow-hidden">
      <div className="border-b border-line px-4 py-3">
        <span className="label-micro">Data provenance · three separate lanes</span>
      </div>
      <div className="divide-y divide-line">
        <LabDrawer />

        <div className="px-4 py-3">
          <div className="flex items-center justify-between gap-2">
            <span className="flex items-center gap-1.5 text-xs font-semibold text-ink">
              <FlaskConical size={13} aria-hidden /> Recorded human replay
            </span>
            <Badge tone={replay?.available ? 'nominal' : 'neutral'}>
              {replay?.available ? 'VERIFIED ROWS' : 'NOT AVAILABLE'}
            </Badge>
          </div>
          <p className="mt-1 text-2xs leading-4 text-ink-subtle">
            PhysioNet Wrist PPG During Exercise v1.0.0 ·{' '}
            <span className="num">{replay?.n_windows ?? 0}</span> windows ·{' '}
            <span className="num">{replay?.participants.length ?? 0}</span> participants
          </p>
          <p className="mt-1 text-2xs font-semibold leading-4 text-watch-text">
            RECORDED · NON-ASTRONAUT · terrestrial exercise, not spaceflight and not clinical validation.
          </p>
          {replay?.active ? (
            <p className="num mt-1 text-2xs text-ink-body">
              streaming {replay.participant} · window <span className="font-semibold">{replay.window_index ?? '—'}</span>
              {' '}/ {replay.active_windows ?? replay.n_windows} · {num(replay.window_s, 0)} s window → 1 Hz
            </p>
          ) : null}
          <p className="mt-1 text-2xs leading-4 text-ink-label">{replay?.time_compressed ?? ''}</p>
        </div>

        <div className="px-4 py-3">
          <div className="flex items-center justify-between gap-2">
            <span className="flex items-center gap-1.5 text-xs font-semibold text-ink">
              <Satellite size={13} aria-hidden /> NOAA GOES proton flux
            </span>
            <Badge tone={goes.available ? 'nominal' : 'neutral'}>{goes.available ? 'CACHED FEED' : 'UNREACHABLE'}</Badge>
          </div>
          <p className="num mt-1 text-2xs leading-4 text-ink-subtle">
            unit <b className="font-semibold text-ink">{goes.unit ?? 'pfu'}</b>
            {goes.unit_long ? ` · ${goes.unit_long}` : ''}
          </p>
          <p className="num mt-0.5 text-2xs text-ink-subtle">
            cache age {goes.cache_age_s === null || goes.cache_age_s === undefined
              ? '—' : `${num(goes.cache_age_s, 0)} s`}
            {goes.latest_sample ? ` · latest ${num(goes.latest_sample.flux, 3)} pfu` : ''}
          </p>
          <p className="mt-1 text-2xs font-semibold leading-4 text-watch-text">
            {goes.dose_note ?? 'Integral proton flux in pfu — not tissue dose (mGy/day).'}
          </p>
          {!goes.available ? (
            <p className="mt-1 text-2xs leading-4 text-ink-label">{goes.detail ?? 'No cached feed. No value is invented.'}</p>
          ) : null}
        </div>
      </div>
    </Card>
  );
}

function LabDrawer() {
  const [open, setOpen] = useState(false);
  const [lab, setLab] = useState<LabPayload | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [fetchedAt, setFetchedAt] = useState<string | null>(null);

  useEffect(() => {
    if (!open || lab) return;
    let cancelled = false;
    void api.lab()
      .then((payload) => {
        if (cancelled) return;
        setLab(payload);
        setFetchedAt(payload.generated_at);
      })
      .catch((cause: unknown) => {
        if (!cancelled) setError(cause instanceof Error ? cause.message : 'Lab lane unavailable.');
      });
    return () => { cancelled = true; };
  }, [open, lab]);

  const columns = lab?.rows[0] ? Object.keys(lab.rows[0]).slice(0, 5) : [];

  return (
    <div className="px-4 py-3">
      <button type="button" className="flex w-full items-center justify-between gap-2 text-left"
              aria-expanded={open} onClick={() => setOpen((value) => !value)}>
        <span className="flex items-center gap-1.5 text-xs font-semibold text-ink">
          <Database size={13} aria-hidden /> OSD-575 pre/post lab
        </span>
        <span className="flex items-center gap-1.5">
          <Badge tone={lab?.available ? 'nominal' : 'neutral'}>
            {lab ? (lab.available ? `${lab.rows.length} VERIFIED ROWS` : 'NOT CACHED') : 'LAB DATA'}
          </Badge>
          <ChevronDown size={13} className={cn('text-ink-label transition-transform', open && 'rotate-180')} aria-hidden />
        </span>
      </button>
      <p className="mt-1 text-2xs leading-4 text-ink-subtle">
        Rodent hindlimb-unloading muscle study. Laboratory animal data — not astronaut telemetry
        and not an environmental sensor.
      </p>
      {open ? (
        <div className="mt-2">
          {error ? <p className="text-2xs text-critical-text">{error}</p> : null}
          {!lab && !error ? <p className="text-2xs text-ink-label">Loading verified rows…</p> : null}
          {lab && !lab.available ? (
            <p className="text-2xs leading-4 text-ink-label">{lab.detail}</p>
          ) : null}
          {lab?.available ? (
            <>
              <p className="num text-2xs text-ink-label">
                sha256 {lab.sha256 ? `${lab.sha256.slice(0, 16)}…` : '—'} · fetched {fetchedAt ? relativeTime(fetchedAt) : '—'}
              </p>
              <div className="mt-1.5 max-h-44 overflow-auto rounded-md border border-line">
                <table className="w-full text-left">
                  <thead className="sticky top-0 bg-page">
                    <tr>{columns.map((column) => (
                      <th key={column} className="num px-2 py-1 text-2xs font-semibold text-ink-subtle">{column}</th>
                    ))}</tr>
                  </thead>
                  <tbody>
                    {lab.rows.slice(0, 12).map((row, index) => (
                      <tr key={index} className="border-t border-line">
                        {columns.map((column) => (
                          <td key={column} className="num px-2 py-1 text-2xs text-ink-body">
                            {String(row[column] ?? '—')}
                          </td>
                        ))}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </>
          ) : null}
        </div>
      ) : null}
    </div>
  );
}
