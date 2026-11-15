import * as React from 'react';
import { AnimatePresence, motion } from 'motion/react';
import { Check, ChevronRight, Radio } from 'lucide-react';
import { api } from '../../lib/api';
import { useSession } from '../../hooks/useSession';
import type { Alert, AuditEntry } from '../../lib/types';
import { Button, EmptyState, Skeleton, StatusDot } from '../ui';
import { relativeTime } from '../../lib/format';
import { stateLabel, type Tone } from '../../lib/status';
import { SPRING } from '../../lib/motion';
import { cn } from '../../lib/utils';

interface FeedItem {
  id: string;
  kind: 'alert' | 'audit';
  title: string;
  detail: string;
  ts: string;
  tone: Tone;
  lane: string;
  alert?: Alert;
}

const EVENT_LABEL: Record<string, string> = {
  'scenario.start': 'Scenario started',
  'scenario.stop': 'Stream stopped',
  'calibration.create': 'Calibration created',
  'calibration.delete': 'Calibration cleared',
  'manual.entry': 'Crew check logged',
  'pvt.result': 'Reaction test logged',
  'alert.raise': 'Alert raised',
  'alert.ack': 'Alert acknowledged',
  'session.change': 'Session changed',
};

function toneForEvent(event: string): Tone {
  if (event === 'alert.raise') return 'alert';
  if (event === 'alert.ack') return 'nominal';
  if (event.startsWith('calibration')) return 'info';
  return 'unknown';
}

export function ActivityFeed() {
  const { role, frame } = useSession();
  const [alerts, setAlerts] = React.useState<Alert[]>([]);
  const [audit, setAudit] = React.useState<AuditEntry[]>([]);
  const [loading, setLoading] = React.useState(true);
  const [error, setError] = React.useState<string | null>(null);
  const [acking, setAcking] = React.useState<string | null>(null);
  const [now, setNow] = React.useState(() => Date.now());

  const canReadAudit = role !== 'crew';
  const canReadAlerts = role !== 'researcher';
  const canAck = role === 'flight-surgeon';

  const load = React.useCallback(async () => {
    if (canReadAlerts) {
      try {
        const alertResult = await api.alerts();
        setAlerts(alertResult.alerts);
        setError(null);
      } catch (exc) {
        setError(exc instanceof Error ? exc.message : String(exc));
        setAlerts([]);
      }
    } else {
      setAlerts([]);
      setError(null);
    }
    if (canReadAudit) {
      try {
        setAudit((await api.audit()).entries);
      } catch {
        setAudit([]);
      }
    } else {
      setAudit([]);
    }
    setLoading(false);
  }, [canReadAudit, canReadAlerts]);

  React.useEffect(() => {
    void load();
    const timer = setInterval(() => { void load(); setNow(Date.now()); }, 3000);
    return () => clearInterval(timer);
  }, [load]);

  const items = React.useMemo<FeedItem[]>(() => {
    const fromAlerts: FeedItem[] = alerts.map((alert) => ({
      id: `alert-${alert.alert_id}`,
      kind: 'alert',
      title: alert.acknowledged_at ? 'Alert acknowledged' : stateLabel(alert.state),
      detail: alert.reason,
      ts: alert.acknowledged_at ?? alert.created_at,
      tone: alert.acknowledged_at ? 'nominal' : alert.severity === 'ALERT' ? 'alert' : 'watch',
      lane: alert.lane,
      alert,
    }));
    const fromAudit: FeedItem[] = audit
      .filter((entry) => entry.event !== 'alert.raise' && entry.event !== 'alert.ack')
      .map((entry) => ({
        id: `audit-${entry.seq}`,
        kind: 'audit',
        title: EVENT_LABEL[entry.event] ?? entry.event,
        detail: `${entry.role} · ${entry.subject_id}`,
        ts: entry.ts,
        tone: toneForEvent(entry.event),
        lane: entry.lane,
      }));
    return [...fromAlerts, ...fromAudit]
      .sort((a, b) => new Date(b.ts).getTime() - new Date(a.ts).getTime())
      .slice(0, 40);
  }, [alerts, audit]);

  const acknowledge = async (alertId: string) => {
    setAcking(alertId);
    try {
      await api.ack(alertId, 'Acknowledged from activity feed');
      await load();
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : String(exc));
    } finally {
      setAcking(null);
    }
  };

  const openCount = alerts.filter((alert) => !alert.acknowledged_at).length;

  return (
    <section className="flex h-full min-h-0 flex-col rounded-xl border border-hairline bg-surface">
      <header className="flex shrink-0 items-center justify-between gap-2 border-b border-hairline px-4 py-3">
        <div className="flex items-center gap-2">
          <Radio size={14} strokeWidth={1.75} className={cn(frame ? 'text-accent' : 'text-ink-faint')} />
          <h2 className="text-sm font-semibold text-ink">Live activity</h2>
        </div>
        <span className="tnum flex items-center gap-1.5 text-[10px] text-ink-faint">
          {openCount > 0 ? (
            <>
              <StatusDot tone="alert" pulse />
              <span className="text-state-alert">{openCount} OPEN</span>
            </>
          ) : (
            <>{items.length} EVENTS</>
          )}
        </span>
      </header>

      <div className="min-h-0 flex-1 overflow-y-auto">
        {loading ? (
          <div className="space-y-2 p-3">
            {[0, 1, 2, 3].map((index) => <Skeleton key={index} className="h-[52px] w-full" />)}
          </div>
        ) : error ? (
          <div className="p-3">
            <div data-tone="alert" className="rounded-md border border-state-alert/30 bg-state-alert/10 px-3 py-2 text-xs text-state-alert">
              Feed unavailable — {error}. Treat the queue as UNKNOWN.
            </div>
          </div>
        ) : items.length === 0 ? (
          <div className="p-3">
            <EmptyState title="No activity yet" detail="Events appear as scenarios run and checks are logged." />
          </div>
        ) : (
          <ul className="divide-y divide-hairline/60">
            <AnimatePresence initial={false}>
              {items.map((item) => (
                <motion.li
                  key={item.id}
                  layout
                  initial={{ opacity: 0, y: -6 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0 }}
                  transition={SPRING}
                  className="group flex gap-2.5 px-4 py-2.5 transition-colors hover:bg-white/[0.02]"
                >
                  <StatusDot tone={item.tone} className="mt-1.5" pulse={item.kind === 'alert' && !item.alert?.acknowledged_at} />
                  <div className="min-w-0 flex-1">
                    <div className="flex items-baseline justify-between gap-2">
                      <span className="truncate text-xs font-medium text-ink">{item.title}</span>
                      <span className="tnum shrink-0 text-[10px] text-ink-faint">{relativeTime(item.ts, now)}</span>
                    </div>
                    <p className="mt-0.5 line-clamp-2 text-[11px] leading-snug text-ink-muted">{item.detail}</p>
                    <div className="mt-1 flex items-center gap-2">
                      <span className="tnum text-[9px] uppercase tracking-[0.06em] text-ink-faint">{item.lane}</span>
                      {item.alert && !item.alert.acknowledged_at && canAck ? (
                        <Button size="sm" variant="ghost"
                          className="h-5 opacity-0 transition-opacity group-hover:opacity-100 focus-visible:opacity-100"
                          disabled={acking === item.alert.alert_id}
                          onClick={() => void acknowledge(item.alert!.alert_id)}>
                          <Check size={11} strokeWidth={1.75} />
                          {acking === item.alert.alert_id ? 'Saving' : 'Ack'}
                        </Button>
                      ) : null}
                      {item.alert?.non_rate_flags.length ? (
                        <span className="tnum text-[9px] text-state-alert">NON-RATE · NEVER SUPPRESSED</span>
                      ) : null}
                    </div>
                  </div>
                  <ChevronRight size={12} strokeWidth={1.75}
                    className="mt-1 shrink-0 text-ink-faint opacity-0 transition-opacity group-hover:opacity-100" />
                </motion.li>
              ))}
            </AnimatePresence>
          </ul>
        )}
      </div>

      {!canReadAudit || !canReadAlerts ? (
        <footer className="shrink-0 border-t border-hairline px-4 py-2 text-[10px] text-ink-faint">
          {!canReadAlerts ? 'Alert queue is hidden for the Researcher role. ' : ''}
          {!canReadAudit ? 'Audit events are hidden for the Crew role.' : 'Audit events are shown.'}
        </footer>
      ) : null}
    </section>
  );
}
