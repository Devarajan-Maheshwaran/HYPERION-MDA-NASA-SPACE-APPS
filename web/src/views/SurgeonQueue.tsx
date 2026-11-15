import * as React from 'react';
import { api } from '../lib/api';
import { useSession } from '../hooks/useSession';
import type { Alert } from '../lib/types';
import { AlertBanner, Badge, Button, Card, CardContent, CardDescription, CardHeader,
  CardTitle, Dialog, EmptyState, Table, Td, Textarea, Th } from '../components/ui';
import { LaneBadge } from '../components/AppShell';
import { formatTime } from '../lib/utils';
import { stateLabel, stateTone } from '../lib/status';

export function SurgeonQueue() {
  const { role, subjects, subjectId } = useSession();
  const [alerts, setAlerts] = React.useState<Alert[]>([]);
  const [error, setError] = React.useState<string | null>(null);
  const [acking, setAcking] = React.useState<Alert | null>(null);
  const [note, setNote] = React.useState('');
  const [busy, setBusy] = React.useState(false);

  const load = React.useCallback(async () => {
    try {
      setAlerts((await api.alerts()).alerts);
      setError(null);
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : String(exc));
      setAlerts([]);
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
    <div className="space-y-4">
      {error ? <AlertBanner tone="alert" title="Alert queue unavailable">{error}
        <div>Treat the queue as UNKNOWN until it reloads.</div></AlertBanner> : null}

      <div className="grid gap-3 sm:grid-cols-3">
        {subjects.map((subject) => {
          const subjectAlerts = open.filter((alert) => alert.subject_id === subject.subject_id);
          const worst = subjectAlerts.some((alert) => alert.severity === 'ALERT') ? 'SURGEON_ALERT'
            : subjectAlerts.length ? 'CREW_CHECK' : 'UNKNOWN';
          return (
            <Card key={subject.subject_id} className={subject.subject_id === subjectId ? 'ring-1 ring-sky-500' : ''}>
              <CardContent className="space-y-2">
                <div className="flex items-center justify-between gap-2">
                  <span className="text-sm font-semibold text-slate-100">{subject.subject_id}</span>
                  <Badge tone={subjectAlerts.length ? stateTone(worst) : 'unknown'}>
                    {subjectAlerts.length ? stateLabel(worst) : 'No open alert'}
                  </Badge>
                </div>
                <div className="text-[11px] text-slate-500">{subject.label}</div>
                <Badge tone={subject.calibration.calibrated ? 'info' : 'unknown'}>
                  {subject.calibration.calibrated ? 'Demo calibration present' : 'Uncalibrated'}
                </Badge>
              </CardContent>
            </Card>
          );
        })}
      </div>

      <Card>
        <CardHeader className="flex-row items-center justify-between">
          <div>
            <CardTitle>Open alerts ({open.length})</CardTitle>
            <CardDescription>
              Deterministic gate output only. Acknowledgement is audited in the local hash chain.
            </CardDescription>
          </div>
          <div className="flex items-center gap-2"><LaneBadge /><Button variant="outline" size="sm" onClick={() => void load()}>Refresh</Button></div>
        </CardHeader>
        <CardContent>
          {open.length === 0 ? (
            <EmptyState title="No open alerts" detail="Alerts appear when a scenario produces a surgeon alert or a crew-check hold." />
          ) : (
            <div className="space-y-2">
              {open.map((alert) => (
                <div key={alert.alert_id} className="rounded-lg border border-ink-600 bg-ink-900/60 p-3">
                  <div className="flex flex-wrap items-center gap-2">
                    <Badge tone={alert.severity === 'ALERT' ? 'alert' : 'watch'}>{alert.severity}</Badge>
                    <Badge tone={stateTone(alert.state)}>{stateLabel(alert.state)}</Badge>
                    <span className="text-xs text-slate-400">{alert.subject_id}</span>
                    <Badge tone="info">{alert.lane}</Badge>
                    <span className="ml-auto text-[11px] text-slate-500">{formatTime(alert.created_at)}</span>
                  </div>
                  <p className="mt-1.5 text-xs text-slate-300">{alert.reason}</p>
                  {alert.non_rate_flags.length ? (
                    <p className="mt-1 text-xs font-semibold text-alert">
                      Non-rate finding (never suppressed): {alert.non_rate_flags.join(', ')}
                    </p>
                  ) : null}
                  <div className="mt-2 flex flex-wrap items-center gap-2">
                    {alert.actions.map((action) => (
                      <span key={action} className="rounded border border-sky-500/40 bg-sky-500/10 px-2 py-1 text-[11px] text-slate-100">
                        {action}
                      </span>
                    ))}
                    <Button size="sm" className="ml-auto" disabled={!canAck}
                      onClick={() => { setAcking(alert); setNote(''); }}>
                      {canAck ? 'Acknowledge' : 'Surgeon role required'}
                    </Button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader><CardTitle>Acknowledged ({closed.length})</CardTitle></CardHeader>
        <CardContent>
          {closed.length === 0 ? <EmptyState title="Nothing acknowledged yet" /> : (
            <Table>
              <thead><tr><Th>Time</Th><Th>Subject</Th><Th>State</Th><Th>By</Th><Th>Note</Th></tr></thead>
              <tbody>
                {closed.map((alert) => (
                  <tr key={alert.alert_id}>
                    <Td>{formatTime(alert.acknowledged_at ?? '')}</Td>
                    <Td>{alert.subject_id}</Td>
                    <Td>{stateLabel(alert.state)}</Td>
                    <Td>{alert.acknowledged_by}</Td>
                    <Td className="max-w-[280px] truncate">{alert.ack_note || '—'}</Td>
                  </tr>
                ))}
              </tbody>
            </Table>
          )}
        </CardContent>
      </Card>

      <Dialog open={acking !== null} title="Acknowledge alert" onClose={() => setAcking(null)}>
        <div className="space-y-3">
          <p className="text-xs text-slate-400">
            {acking?.subject_id} · {acking ? stateLabel(acking.state) : ''} · {acking?.reason}
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
    </div>
  );
}
