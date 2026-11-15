import * as React from 'react';
import { motion } from 'motion/react';
import { Square } from 'lucide-react';
import { api } from '../lib/api';
import { useSession } from '../hooks/useSession';
import { TelemetryCanvas } from '../components/dashboard/TelemetryCanvas';
import { ActivityFeed } from '../components/dashboard/ActivityFeed';
import { EventTable } from '../components/dashboard/EventTable';
import { Badge, Button, Select, StatusDot } from '../components/ui';
import { zoneContainer, zoneItem } from '../lib/motion';
import { stateLabel, stateTone } from '../lib/status';
import type { ScenarioInfo } from '../lib/types';

export function Overview() {
  const {
    frame, subjectId, subjects, habitat, running, role, session, changeSubject, stopScenario,
  } = useSession();
  const [scenarios, setScenarios] = React.useState<ScenarioInfo[]>([]);
  const canControl = role !== 'researcher';
  const activeSubject = subjects.find((subject) => subject.subject_id === subjectId);
  const scenarioLabel = scenarios.find((scenario) => scenario.scenario_id === (frame?.scenario_id ?? session?.scenario_id))?.label;

  React.useEffect(() => {
    let cancelled = false;
    void api.scenarios().then(
      (result) => { if (!cancelled) setScenarios(result.scenarios); },
      () => { if (!cancelled) setScenarios([]); },
    );
    return () => { cancelled = true; };
  }, []);

  return (
    <motion.div variants={zoneContainer} initial="hidden" animate="show" className="space-y-3">
      <motion.div variants={zoneItem} className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold tracking-[-0.02em] text-ink">Crew health overview</h1>
          <p className="mt-0.5 text-xs text-ink-muted">
            {habitat} · deterministic triage · {scenarioLabel ?? (running ? 'Active scenario' : 'No scenario running')}
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <Select aria-label="Active subject" value={subjectId} onChange={(event) => void changeSubject(event.target.value)}>
            {subjects.map((subject) => <option key={subject.subject_id} value={subject.subject_id}>{subject.subject_id}</option>)}
          </Select>
          <Badge tone={activeSubject?.calibration.calibrated ? 'info' : 'unknown'}>
            {activeSubject?.calibration.calibrated ? 'Demo calibration' : 'Uncalibrated'}
          </Badge>
          {frame ? (
            <span className="flex items-center gap-1.5 rounded-md border border-hairline bg-surface px-2 py-1">
              <StatusDot tone={stateTone(frame.state)} pulse={running} />
              <span className="text-xs text-ink-secondary">{stateLabel(frame.state)}</span>
            </span>
          ) : null}
          {running && canControl ? (
            <Button size="sm" variant="outline" onClick={() => void stopScenario()}>
              <Square size={11} strokeWidth={1.75} /> Stop
            </Button>
          ) : null}
        </div>
      </motion.div>

      {/* Asymmetric bento: the telemetry canvas owns ~65%, the queue ~35%. */}
      <div className="grid gap-3 xl:grid-cols-[minmax(0,65fr)_minmax(300px,35fr)]">
        <motion.div variants={zoneItem} className="min-w-0 xl:h-[440px]">
          <TelemetryCanvas />
        </motion.div>
        <motion.div variants={zoneItem} className="min-w-0 h-[360px] xl:h-[440px]">
          <ActivityFeed />
        </motion.div>
      </div>

      <motion.div variants={zoneItem}>
        <EventTable />
      </motion.div>
    </motion.div>
  );
}
