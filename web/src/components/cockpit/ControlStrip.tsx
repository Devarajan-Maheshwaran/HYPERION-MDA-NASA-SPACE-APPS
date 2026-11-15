import { Pause, Play, RotateCcw, SkipForward, Wifi, WifiOff } from 'lucide-react';
import type { HabitatKey, WorkstationState } from '../../lib/types';
import type { StreamHealth } from '../../state/WorkstationProvider';
import { useWorkstation } from '../../state/WorkstationProvider';
import { missionClock, num } from '../../lib/format';
import { SCENARIOS } from '../../lib/clinical';
import { Button } from '../ui';
import { cn } from '../../lib/utils';

const HEALTH_LABEL: Record<StreamHealth, string> = {
  live: 'SSE LIVE',
  connecting: 'CONNECTING',
  polling: 'POLLING FALLBACK',
  offline: 'DISCONNECTED',
};

/** One row: clock, transport, lane, habitat. Nothing here scrolls or hides. */
export function ControlStrip({ state }: { state: WorkstationState }) {
  const {
    busy, streamHealth, play, pause, step, resetCase,
    selectScenario, selectReplay, selectHabitat, setBlackout,
  } = useWorkstation();
  const running = state.running;
  const replay = state.replay;
  const connected = streamHealth === 'live';

  return (
    <section aria-label="Mission clock and transport" className="rounded-xl border border-line bg-white px-3 py-2.5 shadow-card">
      <div className="flex flex-wrap items-center gap-x-3 gap-y-2">
        <div className="flex items-center gap-2">
          <span className={cn('relative flex h-2.5 w-2.5 shrink-0', !running && 'opacity-40')} aria-hidden>
            {running ? <span className="absolute inset-0 rounded-full bg-nominal opacity-40 animate-pulse-ring" /> : null}
            <span className={cn('relative h-2.5 w-2.5 rounded-full', running ? 'bg-nominal' : 'bg-neutral')} />
          </span>
          <span className="num text-xs font-semibold text-ink">{running ? 'LIVE 1.0 Hz' : 'PAUSED'}</span>
          <span className="num rounded-md border border-line bg-page px-2 py-1 text-xs font-medium text-ink" aria-label="Mission elapsed time">
            {missionClock(state.t_s)}
          </span>
        </div>

        <div className="flex items-center gap-1.5">
          <Button size="sm" variant="secondary" disabled={busy} onClick={() => void (running ? pause() : play())}
                  aria-label={running ? 'Pause mission clock' : 'Play mission clock'}>
            {running ? <Pause size={13} aria-hidden /> : <Play size={13} aria-hidden />}
            {running ? 'Pause' : 'Play'}
          </Button>
          <Button size="sm" variant="secondary" disabled={busy} onClick={() => void step(10)} aria-label="Step forward 10 seconds">
            <SkipForward size={13} aria-hidden /> Step +10 s
          </Button>
          <Button size="sm" variant="ghost" disabled={busy} onClick={() => void resetCase()} aria-label="Reset case to nominal">
            <RotateCcw size={13} aria-hidden /> Reset Case
          </Button>
        </div>

        <div className="ml-auto flex items-center gap-1.5" aria-label="Stream health">
          {connected ? <Wifi size={13} className="text-nominal-text" aria-hidden /> : <WifiOff size={13} className="text-watch-text" aria-hidden />}
          <span className={cn('num text-2xs font-semibold', connected ? 'text-nominal-text' : 'text-watch-text')}>
            {HEALTH_LABEL[streamHealth]}
          </span>
        </div>
      </div>

      <div className="mt-2.5 flex flex-wrap items-center gap-x-3 gap-y-2 border-t border-line pt-2.5">
        <div className="flex flex-wrap items-center gap-1.5" role="group" aria-label="Simulated scenario">
          <span className="label-micro mr-0.5">Sim</span>
          {SCENARIOS.filter((scenario) => state.demo_scenarios.some((item) => item.id === scenario.id)).map((scenario) => (
            <button
              key={scenario.id}
              type="button"
              disabled={busy}
              aria-pressed={!replay?.active && state.scenario_key === scenario.id}
              onClick={() => void selectScenario(scenario.id)}
              className={cn(
                'h-8 rounded-lg border px-2.5 text-2xs font-medium transition-colors disabled:opacity-60',
                !replay?.active && state.scenario_key === scenario.id
                  ? 'border-primary bg-primary text-white'
                  : 'border-line bg-white text-ink-body hover:border-line-strong',
              )}
            >
              <span className="num mr-1 opacity-70">{scenario.stage}</span>{scenario.label}
            </button>
          ))}
        </div>

        <label className="flex items-center gap-2 text-2xs text-ink-subtle">
          <span className="label-micro">Replay</span>
          <select
            className="h-8 rounded-lg border border-line bg-white px-2 text-xs text-ink disabled:opacity-60"
            value={replay?.active && replay.participant ? replay.participant : ''}
            disabled={busy || replay?.available === false}
            aria-label="Recorded human replay participant, not astronauts"
            onChange={(event) => { if (event.target.value) void selectReplay(event.target.value); }}
          >
            <option value="">Recorded human · n=8</option>
            {(replay?.participants ?? []).map((participant) => (
              <option key={participant} value={participant}>{participant} · non-astronaut</option>
            ))}
          </select>
        </label>

        <label className="flex items-center gap-2 text-2xs text-ink-subtle">
          <span className="label-micro">Habitat / comms</span>
          <select
            className="h-8 rounded-lg border border-line bg-white px-2 text-xs text-ink disabled:opacity-60"
            value={state.habitat}
            disabled={busy}
            aria-label="Mission habitat and comms delay"
            onChange={(event) => void selectHabitat(event.target.value as HabitatKey)}
          >
            {state.habitat_options.map((option) => (
              <option key={option.key} value={option.key}>{option.label}</option>
            ))}
          </select>
        </label>

        {state.comms ? (
          <span className="num rounded-md bg-page px-2 py-1 text-2xs text-ink-body">
            delay {num(state.comms.profile.delay_s, 1)} s
          </span>
        ) : null}

        <label className="flex items-center gap-2 text-2xs text-ink-body">
          <input
            type="checkbox"
            className="h-3.5 w-3.5 rounded border-line-strong"
            checked={state.comms?.blackout ?? false}
            disabled={busy}
            onChange={(event) => void setBlackout(event.target.checked)}
          />
          Rover blackout
        </label>

        <span className="num ml-auto text-2xs text-ink-label">{state.case_id ?? 'case-default'}</span>
      </div>
    </section>
  );
}
