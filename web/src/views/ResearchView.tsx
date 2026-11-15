import * as React from 'react';
import { Bar, BarChart, CartesianGrid, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import { api } from '../lib/api';
import { useSession } from '../hooks/useSession';
import type { Channel } from '../lib/types';
import { AlertBanner, Badge, Button, Card, CardContent, CardDescription, CardHeader,
  CardTitle, EmptyState, Table, Tabs, Td, Th } from '../components/ui';

interface HrRow { model?: string; mae?: number; ciLow?: number | null; ciHigh?: number | null }

export function ResearchView() {
  const { role } = useSession();
  const [tab, setTab] = React.useState('m6');
  const [channels, setChannels] = React.useState<Channel[]>([]);
  const [summary, setSummary] = React.useState<{ total: number; by_status: Record<string, number> } | null>(null);
  const [m6, setM6] = React.useState<Record<string, unknown> | null>(null);
  const [m6Detail, setM6Detail] = React.useState('');
  const [lab, setLab] = React.useState<{ available: boolean; detail: string; rows: Array<Record<string, unknown>> } | null>(null);
  const [error, setError] = React.useState<string | null>(null);
  const [region, setRegion] = React.useState('all');

  const load = React.useCallback(async () => {
    try {
      const registry = await api.registry();
      setChannels(registry.channels);
      setSummary({ total: registry.total, by_status: registry.by_status });
      setError(null);
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : String(exc));
    }
    try {
      const result = await api.m6();
      setM6(result.results);
      setM6Detail(result.detail);
    } catch {
      setM6(null);
      setM6Detail('Not available for this role.');
    }
    try {
      const result = await api.lab();
      setLab({ available: result.available, detail: result.detail, rows: result.rows });
    } catch {
      setLab(null);
    }
  }, []);

  React.useEffect(() => { void load(); }, [load]);

  const regions = React.useMemo(() => ['all', ...new Set(channels.map((c) => c.region))], [channels]);
  const filtered = region === 'all' ? channels : channels.filter((c) => c.region === region);
  const hrRows = extractHrRows(m6);

  return (
    <div className="space-y-4">
      {error ? <AlertBanner tone="alert" title="Research data unavailable">{error}</AlertBanner> : null}
      <Tabs active={tab} onChange={setTab} tabs={[
        { id: 'm6', label: 'M6 measured results' },
        { id: 'registry', label: `Channel registry (${summary?.total ?? '—'})` },
        { id: 'lab', label: 'NASA lab lane' },
        { id: 'provenance', label: 'Provenance & limits' },
      ]} />

      {tab === 'm6' ? (
        <Card>
          <CardHeader>
            <CardTitle>M6 leave-one-participant-out baselines</CardTitle>
            <CardDescription>
              Read-only committed outputs from non-astronaut PhysioNet recordings (ODC-By 1.0).
              {m6Detail ? ` ${m6Detail}` : ''} These are measured offline results, not app predictions.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            {role === 'crew' ? (
              <EmptyState title="Not available for this role" detail="Switch to Researcher, Ops or Flight surgeon." />
            ) : hrRows.length ? (
              <>
                <div className="h-[260px] w-full">
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart data={hrRows} margin={{ top: 8, right: 12, bottom: 4, left: -8 }}>
                      <CartesianGrid stroke="#22304d" strokeDasharray="3 3" />
                      <XAxis dataKey="model" stroke="#64748b" tick={{ fontSize: 10 }} />
                      <YAxis stroke="#64748b" tick={{ fontSize: 10 }}
                        label={{ value: 'MAE (bpm)', angle: -90, position: 'insideLeft', fill: '#64748b', fontSize: 10 }} />
                      <Tooltip contentStyle={{ background: '#111a2b', border: '1px solid #22304d', fontSize: 11 }} />
                      <Legend wrapperStyle={{ fontSize: 10 }} />
                      <Bar dataKey="mae" name="Heart-rate MAE (bpm)" fill="#38bdf8" />
                    </BarChart>
                  </ResponsiveContainer>
                </div>
                <Table>
                  <thead><tr><Th>Model</Th><Th>Mean MAE (bpm)</Th><Th>Participant bootstrap 95% CI</Th></tr></thead>
                  <tbody>
                    {hrRows.map((row) => (
                      <tr key={String(row.model)}>
                        <Td>{String(row.model)}</Td>
                        <Td className="font-mono">{typeof row.mae === 'number' ? row.mae.toFixed(2) : 'Not available'}</Td>
                        <Td className="font-mono text-[11px] text-slate-400">
                          {typeof row.ciLow === 'number' && typeof row.ciHigh === 'number'
                            ? `[${row.ciLow.toFixed(2)}, ${row.ciHigh.toFixed(2)}]`
                            : 'Not available'}
                        </Td>
                      </tr>
                    ))}
                  </tbody>
                </Table>
                <AlertBanner tone="watch" title="What this does not show">
                  A2 (the motion-heavy comparator) is worse than the trivial baseline on this dataset.
                  Motion destroys the wrist PPG signal. That result is shown, not hidden. No astronaut
                  wearable data exists publicly, and none of this is a clinical performance claim.
                </AlertBanner>
              </>
            ) : (
              <EmptyState title="M6 results not available" detail={m6Detail} />
            )}
          </CardContent>
        </Card>
      ) : null}

      {tab === 'registry' ? (
        <Card>
          <CardHeader className="flex-row flex-wrap items-center justify-between gap-2">
            <div>
              <CardTitle>Signal registry · {summary?.total ?? '—'} channels</CardTitle>
              <CardDescription>
                Value-free registry from the existing module. Counts are computed, not typed.
              </CardDescription>
            </div>
            <div className="flex flex-wrap gap-1">
              {Object.entries(summary?.by_status ?? {}).map(([status, count]) => (
                <Badge key={status} tone={status === 'UNAVAILABLE' ? 'unknown' : 'info'}>{status}: {count}</Badge>
              ))}
            </div>
          </CardHeader>
          <CardContent className="space-y-2">
            <div className="flex flex-wrap gap-1">
              {regions.map((item) => (
                <Button key={item} size="sm" variant={region === item ? 'default' : 'outline'}
                  onClick={() => setRegion(item)}>{item}</Button>
              ))}
            </div>
            <div className="max-h-[520px] overflow-auto">
              <Table>
                <thead><tr><Th>Channel</Th><Th>Region</Th><Th>Status</Th><Th>Unit</Th><Th>Sampling</Th></tr></thead>
                <tbody>
                  {filtered.map((channel) => (
                    <tr key={channel.channel_id}>
                      <Td className="font-mono text-[11px]">{channel.label}</Td>
                      <Td>{channel.region}</Td>
                      <Td><Badge tone={channel.status === 'UNAVAILABLE' ? 'unknown' : 'info'}>{channel.status}</Badge></Td>
                      <Td>{channel.unit || 'Not available'}</Td>
                      <Td className="max-w-[320px] text-[10px] text-slate-400">{channel.sampling}</Td>
                    </tr>
                  ))}
                </tbody>
              </Table>
            </div>
          </CardContent>
        </Card>
      ) : null}

      {tab === 'lab' ? (
        <Card>
          <CardHeader>
            <CardTitle>NASA OSD-575 lab lane</CardTitle>
            <CardDescription>
              Real astronaut serum laboratory values, SHA-256 verified on load. Sparse timepoints,
              not telemetry. The CSV is fetched on demand and never bundled.
            </CardDescription>
          </CardHeader>
          <CardContent>
            {!lab ? (
              <EmptyState title="Not available for this role" />
            ) : !lab.available ? (
              <AlertBanner tone="unknown" title="Not available">{lab.detail}
                <div className="mt-1">Run <code className="font-mono">python -m hyperion_mda.osdr_fetch</code> to
                  download and verify the file. Nothing is substituted in its place.</div>
              </AlertBanner>
            ) : (
              <>
                <p className="mb-2 text-xs text-slate-400">{lab.detail}</p>
                <div className="max-h-[480px] overflow-auto">
                  <Table>
                    <thead><tr><Th>Row</Th><Th>Subject</Th><Th>Analyte</Th><Th>Value</Th><Th>Unit</Th>
                      <Th>Timepoint</Th><Th>z</Th><Th>Note</Th></tr></thead>
                    <tbody>
                      {lab.rows.slice(0, 200).map((row, index) => (
                        <tr key={index}>
                          <Td>{String(row.row_number ?? '')}</Td>
                          <Td>{String(row.subject_id ?? '')}</Td>
                          <Td className="font-mono text-[11px]">{String(row.signal ?? '')}</Td>
                          <Td className="font-mono">{row.value === null ? 'NA' : String(row.value)}</Td>
                          <Td>{String(row.unit ?? '')}</Td>
                          <Td>{String(row.timepoint ?? '')}</Td>
                          <Td className="font-mono">{typeof row.z_score === 'number' ? row.z_score.toFixed(2) : '—'}</Td>
                          <Td className="max-w-[260px] text-[10px] text-slate-400">{String(row.score_note ?? '')}</Td>
                        </tr>
                      ))}
                    </tbody>
                  </Table>
                </div>
              </>
            )}
          </CardContent>
        </Card>
      ) : null}

      {tab === 'provenance' ? (
        <Card>
          <CardHeader><CardTitle>Provenance and limits</CardTitle></CardHeader>
          <CardContent className="space-y-2 text-xs leading-relaxed text-slate-300">
            <p><strong>NASA OSD-575:</strong> real Inspiration4 serum CMP, 4 crew, 19 analytes, 7 sparse
              timepoints. No licence stated in the record, so the raw CSV is not bundled and no derived
              OSD-575 measurements are tracked in git.</p>
            <p><strong>PhysioNet Wrist PPG During Exercise v1.0.0:</strong> 8 non-astronaut adults,
              ODC-By 1.0. Raw recordings are cached outside the repo; derived M6 outputs are tracked with
              attribution.</p>
            <p><strong>SIMULATED / INJECTED:</strong> fixed formulas and operator-injected conditions.
              Not measured, not from a device, not astronaut data.</p>
            <p><strong>Not implemented:</strong> neural risk heads, MC-dropout, Flower federated learning,
              Opacus DP-SGD, GOES radiation ingest, WESAD (gate NO-GO), and any on-chain ledger.</p>
            <p><strong>Gates:</strong> deterministic. Gate 1 ships uncalibrated. Activity is per-person
              scale-normalised, never ENMO in g. Non-rate findings are never suppressed. A hard HR ceiling
              and a latching hold timeout bound the exercise filter.</p>
            <p className="text-slate-500">See <code className="font-mono">docs/SAFETY_ISSUES.md</code> and
              <code className="font-mono"> docs/REQUIREMENTS-TRACEABILITY.md</code> for the full deviation list.</p>
          </CardContent>
        </Card>
      ) : null}
    </div>
  );
}

/**
 * Reads the committed M6 structure: hr.primary.models.{A0..A5}.aggregate.mae.{mean,ci_low,ci_high}.
 * Exported for testing against the real results.json shape.
 */
export function extractHrRows(m6: Record<string, unknown> | null): HrRow[] {
  if (!m6) return [];
  const hr = m6.hr as Record<string, unknown> | undefined;
  const primary = hr?.primary as Record<string, unknown> | undefined;
  const models = primary?.models as Record<string, unknown> | undefined;
  if (!models) return [];
  const rows: HrRow[] = [];
  for (const [model, value] of Object.entries(models)) {
    const aggregate = (value as Record<string, unknown>)?.aggregate as Record<string, unknown> | undefined;
    const mae = aggregate?.mae as Record<string, unknown> | undefined;
    if (mae && typeof mae.mean === 'number') {
      rows.push({
        model,
        mae: mae.mean,
        ciLow: typeof mae.ci_low === 'number' ? mae.ci_low : null,
        ciHigh: typeof mae.ci_high === 'number' ? mae.ci_high : null,
      });
    }
  }
  return rows.sort((a, b) => String(a.model).localeCompare(String(b.model)));
}
