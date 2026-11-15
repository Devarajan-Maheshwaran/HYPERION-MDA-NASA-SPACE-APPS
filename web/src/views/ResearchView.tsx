import * as React from 'react';
import { motion } from 'motion/react';
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import { api } from '../lib/api';
import { useSession } from '../hooks/useSession';
import type { Channel } from '../lib/types';
import { AlertBanner, Badge, Card, CardContent, CardDescription, CardHeader,
  CardTitle, EmptyState, Select, Table, Tabs, TabsContent, Td, Th } from '../components/ui';
import { zoneContainer, zoneItem } from '../lib/motion';

interface HrRow { model?: string; mae?: number; ciLow?: number | null; ciHigh?: number | null }

const AXIS_TICK = { fontSize: 10, fill: '#6B7280', fontFamily: 'JetBrains Mono' };

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
    <motion.div variants={zoneContainer} initial="hidden" animate="show" className="space-y-3">
      {error ? <AlertBanner tone="alert" title="Research data unavailable">{error}</AlertBanner> : null}
      <motion.div variants={zoneItem}>
        <Tabs active={tab} onChange={setTab} label="Research sections" tabs={[
          { id: 'm6', label: 'M6 measured results' },
          { id: 'registry', label: `Channel registry (${summary?.total ?? '—'})` },
          { id: 'lab', label: 'NASA lab lane' },
          { id: 'provenance', label: 'Provenance & limits' },
        ]}>
          <TabsContent value="m6">
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
                          <BarChart data={hrRows} margin={{ top: 8, right: 12, bottom: 4, left: -18 }} accessibilityLayer>
                            <CartesianGrid stroke="rgba(255,255,255,0.05)" vertical={false} />
                            <XAxis dataKey="model" stroke="rgba(255,255,255,0.12)" tickLine={false} tick={AXIS_TICK} />
                            <YAxis stroke="rgba(255,255,255,0.12)" tickLine={false} axisLine={false} tick={AXIS_TICK} width={44} />
                            <Tooltip cursor={{ fill: 'rgba(255,255,255,0.03)' }} isAnimationActive={false}
                              contentStyle={{ background: '#181B21', border: '1px solid rgba(255,255,255,0.12)', borderRadius: 6, fontSize: 11, fontFamily: 'JetBrains Mono' }} />
                            <Bar dataKey="mae" name="Heart-rate MAE (bpm)" fill="#58A6FF" radius={[3, 3, 0, 0]} isAnimationActive={false} />
                          </BarChart>
                        </ResponsiveContainer>
                      </div>
                      <div className="overflow-auto">
                        <Table>
                          <thead><tr><Th>Model</Th><Th className="text-right">Mean MAE (bpm)</Th><Th className="text-right">Participant bootstrap 95% CI</Th></tr></thead>
                          <tbody>
                            {hrRows.map((row) => (
                              <tr key={String(row.model)} className="transition-colors hover:bg-white/[0.02]">
                                <Td>{String(row.model)}</Td>
                                <Td className="text-right text-ink">{typeof row.mae === 'number' ? row.mae.toFixed(2) : 'Not available'}</Td>
                                <Td className="text-right text-[11px]">
                                  {typeof row.ciLow === 'number' && typeof row.ciHigh === 'number'
                                    ? `[${row.ciLow.toFixed(2)}, ${row.ciHigh.toFixed(2)}]` : 'Not available'}
                                </Td>
                              </tr>
                            ))}
                          </tbody>
                        </Table>
                      </div>
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
          </TabsContent>

          <TabsContent value="registry">
            {tab === 'registry' ? (
              <Card>
                <CardHeader className="flex-row flex-wrap items-center justify-between gap-2">
                  <div>
                    <CardTitle>Signal registry · <span className="tnum">{summary?.total ?? '—'}</span> channels</CardTitle>
                    <CardDescription>Value-free registry from the existing module. Counts are computed, not typed.</CardDescription>
                  </div>
                  <div className="flex flex-wrap items-center gap-1.5">
                    {Object.entries(summary?.by_status ?? {}).map(([status, count]) => (
                      <Badge key={status} tone={status === 'UNAVAILABLE' ? 'unknown' : 'info'}>{status}: {count}</Badge>
                    ))}
                    <Select aria-label="Filter by region" value={region} onChange={(event) => setRegion(event.target.value)}>
                      {regions.map((item) => <option key={item} value={item}>{item === 'all' ? 'All regions' : item}</option>)}
                    </Select>
                  </div>
                </CardHeader>
                <CardContent className="p-0">
                  <div className="max-h-[560px] overflow-auto">
                    <Table>
                      <thead><tr><Th>Channel</Th><Th>Region</Th><Th>Status</Th><Th>Unit</Th><Th>Sampling</Th></tr></thead>
                      <tbody>
                        {filtered.map((channel) => (
                          <tr key={channel.channel_id} className="transition-colors hover:bg-white/[0.02]">
                            <Td className="text-[11px] text-ink">{channel.label}</Td>
                            <Td className="font-sans">{channel.region}</Td>
                            <Td><Badge tone={channel.status === 'UNAVAILABLE' ? 'unknown' : 'info'}>{channel.status}</Badge></Td>
                            <Td>{channel.unit || 'Not available'}</Td>
                            <Td className="max-w-[320px] whitespace-normal font-sans text-[10px] text-ink-muted">{channel.sampling}</Td>
                          </tr>
                        ))}
                      </tbody>
                    </Table>
                  </div>
                </CardContent>
              </Card>
            ) : null}
          </TabsContent>

          <TabsContent value="lab">
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
                      <div className="mt-1">Run <code className="tnum">python -m hyperion_mda.osdr_fetch</code> to
                        download and verify the file. Nothing is substituted in its place.</div>
                    </AlertBanner>
                  ) : (
                    <>
                      <p className="mb-2 text-xs text-ink-muted">{lab.detail}</p>
                      <div className="max-h-[480px] overflow-auto">
                        <Table>
                          <thead><tr><Th>Row</Th><Th>Subject</Th><Th>Analyte</Th><Th className="text-right">Value</Th><Th>Unit</Th>
                            <Th>Timepoint</Th><Th className="text-right">z</Th><Th>Note</Th></tr></thead>
                          <tbody>
                            {lab.rows.slice(0, 200).map((row, index) => (
                              <tr key={index} className="transition-colors hover:bg-white/[0.02]">
                                <Td>{String(row.row_number ?? '')}</Td>
                                <Td>{String(row.subject_id ?? '')}</Td>
                                <Td className="text-[11px]">{String(row.signal ?? '')}</Td>
                                <Td className="text-right">{row.value === null ? 'NA' : String(row.value)}</Td>
                                <Td>{String(row.unit ?? '')}</Td>
                                <Td>{String(row.timepoint ?? '')}</Td>
                                <Td className="text-right">{typeof row.z_score === 'number' ? row.z_score.toFixed(2) : '—'}</Td>
                                <Td className="max-w-[260px] whitespace-normal font-sans text-[10px] text-ink-muted">{String(row.score_note ?? '')}</Td>
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
          </TabsContent>

          <TabsContent value="provenance">
            {tab === 'provenance' ? (
              <Card>
                <CardHeader><CardTitle>Provenance and limits</CardTitle></CardHeader>
                <CardContent className="space-y-2 text-xs leading-relaxed text-ink-secondary">
                  <p><strong className="text-ink">NASA OSD-575:</strong> real Inspiration4 serum CMP, 4 crew, 19 analytes, 7 sparse
                    timepoints. No licence stated in the record, so the raw CSV is not bundled and no derived
                    OSD-575 measurements are tracked in git.</p>
                  <p><strong className="text-ink">PhysioNet Wrist PPG During Exercise v1.0.0:</strong> 8 non-astronaut adults,
                    ODC-By 1.0. Raw recordings are cached outside the repo; derived M6 outputs are tracked with
                    attribution.</p>
                  <p><strong className="text-ink">SIMULATED / INJECTED:</strong> fixed formulas and operator-injected conditions.
                    Not measured, not from a device, not astronaut data.</p>
                  <p><strong className="text-ink">Not implemented:</strong> neural risk heads, MC-dropout, Flower federated learning,
                    Opacus DP-SGD, GOES radiation ingest, WESAD (gate NO-GO), and any on-chain ledger.</p>
                  <p><strong className="text-ink">Gates:</strong> deterministic. Gate 1 ships uncalibrated. Activity is per-person
                    scale-normalised, never ENMO in g. Non-rate findings are never suppressed. A hard HR ceiling
                    and a latching hold timeout bound the exercise filter.</p>
                  <p className="text-ink-faint">See <code className="tnum">docs/SAFETY_ISSUES.md</code> and
                    <code className="tnum"> docs/REQUIREMENTS-TRACEABILITY.md</code> for the full deviation list.</p>
                </CardContent>
              </Card>
            ) : null}
          </TabsContent>
        </Tabs>
      </motion.div>
    </motion.div>
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
