import * as React from 'react';
import { AnimatePresence, motion } from 'motion/react';
import { Check, RefreshCw } from 'lucide-react';
import { api } from '../lib/api';
import { useSession } from '../hooks/useSession';
import type { Alert } from '../lib/types';
import { AlertBanner, Badge, Button, Card, CardContent, CardDescription, CardHeader,
  CardTitle, Dialog, EmptyState, StatusDot, Table, Td, Textarea, Th } from '../components/ui';
import { LaneBadge } from '../components/AppShell';
import { formatTime } from '../lib/utils';
import { stateLabel, stateTone } from '../lib/status';
import { zoneContainer, zoneItem, SPRING } from '../lib/motion';
import { cn } from '../lib/utils';

export function SurgeonQueue() {
  const { role, subjects, subjectId } = useSession();
  const [alerts, setAlerts] = React.useState<Alert[]>([]);
  const [error, setError] = React.useState<string | null>(null);
  const [acking, setAcking] = React.useState<Alert | null>(null);
  const [note, setNote] = React.useState('');
  const [busy, setBusy] = React.useState(false);
  const [loading, setLoading] = React.useState(true);

  const load = React.useCallback(async () => {
    try {
      setAlerts((await api.alerts()).alerts);
      setError(null);
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : String(exc));
      setAlerts([]);
    } finally {
      setLoading(false);
    }
  }, []);

  React.useEffect(() => {
    void load();
    const timer = setInterval(() => void load(), 3000);
    return () => clearInterval(timer);
  }, [load]);

  const acknowledge = async () => {
    if (!acking) return;
    setBusy(true);
    try {
      await api.ack(acking.alert_id, note);
      setAcking(null);
      setNote('');
      await load();
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : String(exc));
    } finally {
      setBusy(false);
    }
  };

  const open = alerts.filter((alert) => !alert.acknowledged_at);
  const closed = alerts.filter((alert) => alert.acknowledged_at);
  const canAck = role === 'flight-surgeon';

  return (
    <motion.div variants={zoneContainer} initial="hidden" animate="show" className="space-y-3">
      {error ? (
        <AlertBanner tone="alert" title="Alert queue unavailable">
          {error}<div>Treat the queue as UNKNOWN until it reloads.</div>
        </AlertBanner>
      ) : null}

      <motion.div variants={zoneItem}>
        <Card>
          <CardContent className="flex flex-wrap items-center gap-2 py-3">
            <span className="microlabel mr-1">Crew</span>
            {subjects.map((subject) => {
              const subjectAlerts = open.filter((alert) => alert.subject_id === subject.subject_id);
              const worst = subjectAlerts.some((alert) => alert.severity === 'ALERT') ? 'SURGEON_ALERT'
                : subjectAlerts.length ? 'CREW_CHECK' : null;
              return (
                <span key={subject.subject_id} className={cn(
                  'flex items-center gap-2 rounded-md border px-2.5 py-1.5',
                  subject.subject_id === subjectId ? 'border-accent/40 bg-accent-dim' : 'border-hairline bg-base',
                )}>
                  <StatusDot tone={worst ? stateTone(worst) : 'unknown'} pulse={Boolean(worst)} />
                  <span className="tnum text-xs text-ink">{subject.subject_id}</span>
                  <span className="text-[10px] text-ink-faint">
                    {worst ? stateLabel(worst) : 'No open alert'}
                  </span>
                  <Badge tone={subject.calibration.calibrated ? 'info' : 'unknown'}>
                    {subject.calibration.calibrated ? 'cal' : 'uncal'}
                  </Badge>
                </span>
              );
            })}
          </CardContent>
        </Card>
      </motion.div>

      <motion.div variants={zoneItem}>
        <Card>
          <CardHeader className="flex-row flex-wrap items-center justify-between gap-2">
            <div>
              <CardTitle>Open alerts <span className="tnum text-ink-muted">({open.length})</span></CardTitle>
              <CardDescription>Deterministic gate output only. Acknowledgement is audited in the local hash chain.</CardDescription>
            </div>
            <div className="flex items-center gap-2">
              <LaneBadge />
              <Button variant="outline" size="sm" onClick={() => void load()}>
                <RefreshCw size={12} strokeWidth={1.75} /> Refresh
              </Button>
            </div>
          </CardHeader>
          <CardContent className="p-0">
            {loading ? (
              <div className="p-4 text-xs text-ink-faint">Loading queue…</div>
            ) : open.length === 0 ? (
              <div className="p-4">
                <EmptyState title="No open alerts" detail="Alerts appear when a scenario produces a surgeon alert or a crew-check hold." />
              </div>
            ) : (
              <ul className="divide-y divide-hairline">
                <AnimatePresence initial={false}>
                  {open.map((alert) => (
                    <motion.li key={alert.alert_id} layout initial={{ opacity: 0, y: 6 }}
                      animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }} transition={SPRING}
                      className="px-4 py-3 transition-colors hover:bg-white/[0.02]">
                      <div className="flex flex-wrap items-center gap-2">
                        <StatusDot tone={alert.severity === 'ALERT' ? 'alert' : 'watch'} pulse />
                        <Badge tone={alert.severity === 'ALERT' ? 'alert' : 'watch'}>{alert.severity}</Badge>
                        <Badge tone={stateTone(alert.state)}>{stateLabel(alert.state)}</Badge>
                        <span className="tnum text-xs text-ink-secondary">{alert.subject_id}</span>
                        <Badge tone="unknown">{alert.lane}</Badge>
                        <span className="tnum ml-auto text-[11px] text-ink-faint">{formatTime(alert.created_at)}</span>
                      </div>
                      <p className="mt-1.5 text-xs leading-relaxed text-ink-secondary">{alert.reason}</p>
                      {alert.non_rate_flags.length ? (
                        <p className="mt-1 text-xs font-semibold text-state-alert">
                          Non-rate finding (never suppressed): {alert.non_rate_flags.join(', ')}
                        </p>
                      ) : null}
                      <div className="mt-2 flex flex-wrap items-center gap-2">
                        {alert.actions.map((action) => (
                          <span key={action} className="rounded border border-hairline bg-base px-2 py-1 text-[11px] text-ink">
                            {action}
                          </span>
                        ))}
                        <Button size="sm" className="ml-auto" disabled={!canAck}
                          onClick={() => { setAcking(alert); setNote(''); }}>
                          <Check size={12} strokeWidth={1.75} />
                          {canAck ? 'Acknowledge' : 'Surgeon role required'}
                        </Button>
                      </div>
                    </motion.li>
                  ))}
                </AnimatePresence>
              </ul>
            )}
          </CardContent>
        </Card>
      </motion.div>

      <motion.div variants={zoneItem}>
        <Card>
          <CardHeader><CardTitle>Acknowledged <span className="tnum text-ink-muted">({closed.length})</span></CardTitle></CardHeader>
          <CardContent className="p-0">
            {closed.length === 0 ? (
              <div className="p-4"><EmptyState title="Nothing acknowledged yet" /></div>
            ) : (
              <div className="max-h-[360px] overflow-auto">
                <Table>
                  <thead><tr><Th>Time</Th><Th>Subject</Th><Th>State</Th><Th>By</Th><Th>Note</Th></tr></thead>
                  <tbody>
                    {closed.map((alert) => (
                      <tr key={alert.alert_id} className="transition-colors hover:bg-white/[0.02]">
                        <Td>{formatTime(alert.acknowledged_at ?? '')}</Td>
                        <Td>{alert.subject_id}</Td>
                        <Td className="font-sans">{stateLabel(alert.state)}</Td>
                        <Td>{alert.acknowledged_by}</Td>
                        <Td className="max-w-[280px] truncate font-sans">{alert.ack_note || '—'}</Td>
                      </tr>
                    ))}
                  </tbody>
                </Table>
              </div>
            )}
          </CardContent>
        </Card>
      </motion.div>

      <Dialog open={acking !== null} title="Acknowledge alert" onClose={() => setAcking(null)}>
        <div className="space-y-3">
          <p className="text-xs text-ink-muted">
            <span className="tnum">{acking?.subject_id}</span> · {acking ? stateLabel(acking.state) : ''} · {acking?.reason}
          </p>
          <Textarea rows={3} value={note} onChange={(event) => setNote(event.target.value)}
            placeholder="Optional note (audited, no raw measurements stored)" />
          <div className="flex justify-end gap-2">
            <Button variant="outline" onClick={() => setAcking(null)}>Cancel</Button>
            <Button onClick={() => void acknowledge()} disabled={busy}>
              {busy ? 'Saving…' : 'Confirm acknowledgement'}
            </Button>
          </div>
        </div>
      </Dialog>
    </motion.div>
  );
}
