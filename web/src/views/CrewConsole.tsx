import * as React from 'react';
import { motion } from 'motion/react';
import { api } from '../lib/api';
import type { OrgansResponse } from '../lib/types';
import { useSession } from '../hooks/useSession';
import { BodyMap, OrganDetail } from '../components/BodyMap';
import { ActivityChart, FrameStats, VitalsChart } from '../components/VitalsChart';
import { GateBadges } from '../components/GateBadges';
import { AlertBanner, Badge, Card, CardContent, CardDescription, CardHeader, CardTitle,
  EmptyState, Skeleton } from '../components/ui';
import { stateLabel, stateTone } from '../lib/status';
import { zoneContainer, zoneItem } from '../lib/motion';

export function CrewConsole() {
  const { frame, history, subjectId, habitat, running, role } = useSession();
  const [organs, setOrgans] = React.useState<OrgansResponse | null>(null);
  const [selected, setSelected] = React.useState<string | null>('heart');
  const [organError, setOrganError] = React.useState<string | null>(null);
  const [organLoading, setOrganLoading] = React.useState(true);

  const loadOrgans = React.useCallback(async () => {
    try {
      setOrgans(await api.organs(subjectId));
      setOrganError(null);
    } catch (exc) {
      setOrganError(exc instanceof Error ? exc.message : String(exc));
      setOrgans(null);
    } finally {
      setOrganLoading(false);
    }
  }, [subjectId]);

  React.useEffect(() => {
    setOrganLoading(true);
    void loadOrgans();
    const timer = setInterval(() => void loadOrgans(), 10000);
    return () => clearInterval(timer);
  }, [loadOrgans]);

  const canReadOrgans = role === 'crew' || role === 'flight-surgeon' || role === 'ops';
  const activeOrgan = organs?.organs.find((organ) => organ.system === selected) ?? null;

  return (
    <motion.div variants={zoneContainer} initial="hidden" animate="show"
      className="grid gap-3 xl:grid-cols-[minmax(0,1fr)_360px]">
      <div className="min-w-0 space-y-3">
        <motion.div variants={zoneItem}>
          <Card>
            <CardHeader className="flex-row flex-wrap items-center justify-between gap-2">
              <div>
                <CardTitle>Live vitals · <span className="tnum">{subjectId}</span></CardTitle>
                <CardDescription>{habitat} · deterministic gates, no neural model in the decision path</CardDescription>
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
                  <div className="microlabel mb-1">Activity · per-person rest scales (dimensionless, not ENMO in g)</div>
                  <ActivityChart history={history} />
                </div>
              ) : null}
            </CardContent>
          </Card>
        </motion.div>

        <motion.div variants={zoneItem}>
          <Card>
            <CardHeader>
              <CardTitle>Three-stage trust gate</CardTitle>
              <CardDescription>
                Select a gate to see the exact evidence behind its verdict. Every verdict is a pure
                function of the frame and this person&apos;s calibration.
              </CardDescription>
            </CardHeader>
            <CardContent><GateBadges frame={frame} /></CardContent>
          </Card>
        </motion.div>

        {frame?.actions.length ? (
          <motion.div variants={zoneItem}>
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
                  <span key={action} className="rounded-md border border-hairline bg-base px-3 py-1.5 text-xs font-medium text-ink">
                    {action}
                  </span>
                ))}
              </CardContent>
            </Card>
          </motion.div>
        ) : null}
      </div>

      <div className="space-y-3">
        <motion.div variants={zoneItem}>
          <Card>
            <CardHeader>
              <CardTitle>Six-system body map</CardTitle>
              <CardDescription>Demo rule table on crew-entered checks. Not NASA-STD-3001 compliance.</CardDescription>
            </CardHeader>
            <CardContent>
              {!canReadOrgans ? (
                <EmptyState title="Not available for this role" detail="Switch to Crew, Flight surgeon or Ops to view organ status." />
              ) : organError ? (
                <AlertBanner tone="alert" title="Organ status unavailable">{organError} — treat as UNKNOWN.</AlertBanner>
              ) : organLoading ? (
                <div className="space-y-2"><Skeleton className="h-[300px] w-full" /><Skeleton className="h-8 w-full" /></div>
              ) : organs ? (
                <BodyMap organs={organs.organs} selected={selected} onSelect={setSelected} />
              ) : (
                <EmptyState title="Organ status not available" />
              )}
            </CardContent>
          </Card>
        </motion.div>

        <motion.div variants={zoneItem}>
          <Card>
            <CardHeader><CardTitle>System detail</CardTitle></CardHeader>
            <CardContent><OrganDetail organ={activeOrgan} /></CardContent>
          </Card>
        </motion.div>

        <motion.div variants={zoneItem}>
          <Card>
            <CardHeader>
              <CardTitle>Standard Measures readiness shield</CardTitle>
              <CardDescription>Engagement counter only. No clinical or readiness meaning.</CardDescription>
            </CardHeader>
            <CardContent>
              <div className="flex items-end gap-6 border-b border-hairline pb-3">
                <div>
                  <div className="microlabel">Check streak</div>
                  <div className="tnum mt-1 text-xl text-ink">{organs ? `${organs.readiness.streak_days} d` : '—'}</div>
                </div>
                <div>
                  <div className="microlabel">Days logged</div>
                  <div className="tnum mt-1 text-xl text-ink">{organs ? organs.readiness.days_logged : '—'}</div>
                </div>
              </div>
              <p className="mt-2 text-[10px] leading-relaxed text-ink-faint">
                {organs?.readiness.note ?? 'Log crew checks to build a streak.'}
              </p>
            </CardContent>
          </Card>
        </motion.div>
      </div>
    </motion.div>
  );
}
