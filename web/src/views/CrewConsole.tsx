import * as React from 'react';
import { api } from '../lib/api';
import type { OrgansResponse } from '../lib/types';
import { useSession } from '../hooks/useSession';
import { BodyMap, OrganDetail } from '../components/BodyMap';
import { ActivityChart, FrameStats, VitalsChart } from '../components/VitalsChart';
import { GateBadges } from '../components/GateBadges';
import { AlertBanner, Badge, Card, CardContent, CardDescription, CardHeader, CardTitle,
  EmptyState, Stat } from '../components/ui';
import { stateLabel, stateTone } from '../lib/status';

export function CrewConsole() {
  const { frame, history, subjectId, habitat, running, role } = useSession();
  const [organs, setOrgans] = React.useState<OrgansResponse | null>(null);
  const [selected, setSelected] = React.useState<string | null>('heart');
  const [organError, setOrganError] = React.useState<string | null>(null);

  const loadOrgans = React.useCallback(async () => {
    try {
      setOrgans(await api.organs(subjectId));
      setOrganError(null);
    } catch (exc) {
      setOrganError(exc instanceof Error ? exc.message : String(exc));
      setOrgans(null);
    }
  }, [subjectId]);

  React.useEffect(() => {
    void loadOrgans();
    const timer = setInterval(() => void loadOrgans(), 10000);
    return () => clearInterval(timer);
  }, [loadOrgans]);

  const canReadOrgans = role === 'crew' || role === 'flight-surgeon' || role === 'ops';
  const activeOrgan = organs?.organs.find((organ) => organ.system === selected) ?? null;

  return (
    <div className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_400px]">
      <div className="space-y-4">
        <Card>
          <CardHeader className="flex-row items-center justify-between gap-2">
            <div>
              <CardTitle>Live vitals · {subjectId}</CardTitle>
              <CardDescription>
                {habitat} · deterministic gates, no neural model in the decision path
              </CardDescription>
            </div>
            <div className="flex items-center gap-2">
              {frame ? <Badge tone={stateTone(frame.state)}>{stateLabel(frame.state)}</Badge> : null}
              <Badge tone={running ? 'info' : 'unknown'}>{running ? 'Streaming' : 'Idle'}</Badge>
            </div>
          </CardHeader>
          <CardContent className="space-y-3">
            <FrameStats frame={frame} />
            <VitalsChart history={history} />
            {history.length ? (
              <div>
                <div className="mb-1 text-[10px] font-semibold uppercase tracking-wider text-slate-500">
                  Activity · per-person rest scales (dimensionless, not ENMO in g)
                </div>
                <ActivityChart history={history} />
              </div>
            ) : null}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Three-stage trust gate</CardTitle>
            <CardDescription>
              Click a gate to see the exact evidence behind its verdict. Every verdict is a pure
              function of the frame and this person&apos;s calibration.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <GateBadges frame={frame} />
          </CardContent>
        </Card>

        {frame?.actions.length ? (
          <Card>
            <CardHeader>
              <CardTitle>Guided action</CardTitle>
              <CardDescription>
                Action text is restricted to four non-treatment strings. No fluid, salt, medication
                or therapy advice is issued by this prototype.
              </CardDescription>
            </CardHeader>
            <CardContent className="flex flex-wrap gap-2">
              {frame.actions.map((action) => (
                <span key={action} className="rounded-lg border border-sky-500/40 bg-sky-500/10 px-3 py-2 text-sm font-medium text-slate-100">
                  {action}
                </span>
              ))}
            </CardContent>
          </Card>
        ) : null}
      </div>

      <div className="space-y-4">
        <Card>
          <CardHeader>
            <CardTitle>Six-system body map</CardTitle>
            <CardDescription>Demo rule table on crew-entered checks. Not NASA-STD-3001 compliance.</CardDescription>
          </CardHeader>
          <CardContent>
            {!canReadOrgans ? (
              <EmptyState title="Not available for this role"
                detail="Switch to Crew, Flight surgeon or Ops to view organ status." />
            ) : organError ? (
              <AlertBanner tone="alert" title="Organ status unavailable">{organError}</AlertBanner>
            ) : organs ? (
              <BodyMap organs={organs.organs} selected={selected} onSelect={setSelected} />
            ) : (
              <EmptyState title="Loading organ status" />
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader><CardTitle>System detail</CardTitle></CardHeader>
          <CardContent><OrganDetail organ={activeOrgan} /></CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Standard Measures readiness shield</CardTitle>
            <CardDescription>Engagement counter only. No clinical or readiness meaning.</CardDescription>
          </CardHeader>
          <CardContent className="grid grid-cols-2 gap-2">
            <Stat label="Check streak" value={`${organs?.readiness.streak_days ?? 0} d`} />
            <Stat label="Days logged" value={organs?.readiness.days_logged ?? 0} />
            <p className="col-span-2 text-[10px] leading-relaxed text-slate-500">
              {organs?.readiness.note ?? 'Log crew checks to build a streak.'}
            </p>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
