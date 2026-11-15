import { useEffect, useRef, useState } from 'react';
import { MousePointerClick, RotateCcw } from 'lucide-react';
import { api } from '../../lib/api';
import { median } from '../../lib/clinical';
import { num } from '../../lib/format';
import { useWorkstation } from '../../state/WorkstationProvider';
import { Button, Card, CardHeader, ErrorNotice } from '../ui';
import { cn } from '../../lib/utils';

type Phase = 'idle' | 'waiting' | 'ready' | 'complete' | 'saving';
const TRIALS = 5;

export function PVTTool({ onSaved }: { onSaved: () => void }) {
  const { submitExam } = useWorkstation();
  const [phase, setPhase] = useState<Phase>('idle');
  const [times, setTimes] = useState<number[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [early, setEarly] = useState(false);
  const timer = useRef<ReturnType<typeof setTimeout> | undefined>(undefined);
  const started = useRef(0);
  const phaseRef = useRef<Phase>('idle');
  const timesRef = useRef<number[]>([]);
  const savingRef = useRef(false);

  const changePhase = (next: Phase) => { phaseRef.current = next; setPhase(next); };
  const clearTimer = () => { if (timer.current !== undefined) clearTimeout(timer.current); timer.current = undefined; };

  useEffect(() => () => { clearTimer(); savingRef.current = false; }, []);

  const arm = () => {
    clearTimer();
    setEarly(false);
    changePhase('waiting');
    timer.current = setTimeout(() => {
      started.current = performance.now();
      changePhase('ready');
    }, 1200 + Math.random() * 1800);
  };

  const save = async (values: number[]) => {
    if (savingRef.current) return;
    savingRef.current = true;
    changePhase('saving');
    const ok = await submitExam('Reaction test', () => api.examPvt(values));
    savingRef.current = false;
    if (ok) onSaved();
    else {
      changePhase('complete');
      setError('The result could not be saved. Retry without repeating the test.');
    }
  };

  const click = () => {
    if (phaseRef.current === 'idle') { arm(); return; }
    if (phaseRef.current === 'waiting') {
      clearTimer();
      setEarly(true);
      changePhase('idle');
      return;
    }
    if (phaseRef.current !== 'ready') return;
    const elapsed = performance.now() - started.current;
    if (!Number.isFinite(elapsed) || elapsed <= 0 || elapsed > 10000) {
      setError('That trial was outside the accepted range. Restart the test.');
      changePhase('idle');
      return;
    }
    const next = [...timesRef.current, Math.round(elapsed * 10) / 10];
    timesRef.current = next;
    setTimes(next);
    if (next.length >= TRIALS) {
      changePhase('complete');
      void save(next);
    } else arm();
  };

  const reset = () => {
    clearTimer();
    timesRef.current = [];
    setTimes([]);
    setError(null);
    setEarly(false);
    changePhase('idle');
  };

  const result = median(times);
  return (
    <Card>
      <CardHeader eyebrow="Tool 01 · Alertness" title="15-second reaction test" description="Five trials. Wait for the dark target, then click. This measures reaction time, not fitness for duty." />
      <div className="p-5">
        {error ? <div className="mb-3"><ErrorNotice>{error}</ErrorNotice></div> : null}
        <button
          type="button"
          onClick={click}
          disabled={phase === 'complete' || phase === 'saving'}
          className={cn(
            'flex min-h-44 w-full flex-col items-center justify-center rounded-xl border px-5 py-6 text-center transition-colors',
            phase === 'ready' ? 'border-primary bg-primary text-white' : 'border-line bg-page text-ink',
            (phase === 'complete' || phase === 'saving') && 'cursor-default',
          )}
          aria-label={phase === 'ready' ? 'Click reaction target now' : phase === 'waiting' ? 'Wait for reaction target' : 'Start reaction test'}
        >
          <MousePointerClick size={24} strokeWidth={1.5} className={cn('mb-3', phase === 'ready' ? 'text-white' : 'text-ink-label')} aria-hidden />
          <span className="text-lg font-semibold">
            {phase === 'idle' && (times.length ? 'Continue test' : 'Start reaction test')}
            {phase === 'waiting' && 'Wait for the target…'}
            {phase === 'ready' && 'Click now'}
            {phase === 'complete' && 'Five trials recorded'}
            {phase === 'saving' && 'Saving result…'}
          </span>
          <span className={cn('mt-1 text-xs', phase === 'ready' ? 'text-white/75' : 'text-ink-subtle')}>
            {phase === 'waiting' ? 'Clicking early restarts this trial; it is not recorded.' : phase === 'ready' ? 'React as quickly as you can.' : `${times.length} of ${TRIALS} trials complete`}
          </span>
        </button>
        {early ? <p className="mt-2 text-xs text-watch-text" role="status">Too early. That trial was discarded. Start again when you are ready.</p> : null}
        <div className="mt-4 flex items-center gap-2" aria-label={`${times.length} of ${TRIALS} trials complete`}>
          {Array.from({ length: TRIALS }, (_, index) => (
            <div key={index} className={cn('flex h-9 flex-1 items-center justify-center rounded-md border text-xs', times[index] !== undefined ? 'border-line bg-white text-ink' : 'border-line bg-page text-ink-label')}>
              <span className="num">{times[index] !== undefined ? Math.round(times[index]!) : index + 1}</span>
            </div>
          ))}
        </div>
        <div className="mt-4 flex items-center justify-between gap-3">
          <div className="text-xs text-ink-subtle">Median <span className="num font-medium text-ink">{num(result, 0)} ms</span> · demo alert above <span className="num">350 ms</span></div>
          <div className="flex gap-2">
            <Button variant="ghost" size="sm" onClick={reset} disabled={phase === 'saving'}><RotateCcw size={13} aria-hidden /> Restart</Button>
            {phase === 'complete' ? <Button size="sm" onClick={() => void save(times)}>Retry save</Button> : null}
          </div>
        </div>
        <p className="mt-3 text-2xs leading-4 text-ink-label">A successful save refreshes the Brain & Sleep evidence and re-runs the deterministic gates. Timing uses performance.now(); no raw timing samples are written to the audit ledger.</p>
      </div>
    </Card>
  );
}
