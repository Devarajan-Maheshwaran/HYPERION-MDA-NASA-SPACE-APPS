import { useState, type FormEvent } from 'react';
import { api } from '../../lib/api';
import { useWorkstation } from '../../state/WorkstationProvider';
import { Button, Card, CardHeader, ErrorNotice } from '../ui';

const FIELDS = [
  { key: 'glucose_mgdl', label: 'Glucose', unit: 'mg/dL', min: 20, max: 600, step: 1, placeholder: '92' },
  { key: 'temp_c', label: 'Temperature', unit: '°C', min: 30, max: 43, step: 0.1, placeholder: '36.8' },
  { key: 'sleep_hrs', label: 'Sleep', unit: 'h', min: 0, max: 24, step: 0.1, placeholder: '7.2' },
  { key: 'water_ml', label: 'Water intake', unit: 'mL', min: 0, max: 10000, step: 50, placeholder: '1800' },
  { key: 'ared_min', label: 'ARED exercise', unit: 'min', min: 0, max: 600, step: 1, placeholder: '30' },
  { key: 'mood_score', label: 'Mood', unit: '1–10', min: 1, max: 10, step: 1, placeholder: '7' },
] as const;

type FieldKey = (typeof FIELDS)[number]['key'] | 'bp_sys' | 'bp_dia';

export function VitalsTool({ onSaved }: { onSaved: () => void }) {
  const { submitExam } = useWorkstation();
  const [values, setValues] = useState<Partial<Record<FieldKey, string>>>({});
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const set = (key: FieldKey, value: string) => setValues((current) => ({ ...current, [key]: value }));

  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setError(null);
    const payload: Record<string, number> = {};
    for (const [key, raw] of Object.entries(values)) {
      if (raw === undefined || raw.trim() === '') continue;
      const value = Number(raw);
      if (!Number.isFinite(value)) { setError(`Enter a valid number for ${key.replace(/_/g, ' ')}.`); return; }
      payload[key] = value;
    }
    if (!Object.keys(payload).length) { setError('Enter at least one measurement before saving.'); return; }
    if (('bp_sys' in payload) !== ('bp_dia' in payload)) { setError('Enter systolic and diastolic blood pressure together.'); return; }
    if (payload['bp_sys'] !== undefined && payload['bp_dia'] !== undefined && payload['bp_dia'] >= payload['bp_sys']) {
      setError('Diastolic pressure must be lower than systolic pressure.'); return;
    }
    setSaving(true);
    const ok = await submitExam('Crew vitals', () => api.examVitals(payload));
    setSaving(false);
    if (ok) onSaved();
  };

  return (
    <Card>
      <CardHeader eyebrow="Tool 03 · Episodic evidence" title="Keyboard crew vitals" description="Log the measurements you have. Blank fields are left unchanged; saved checks refresh their freshness weights." />
      <form className="p-5" onSubmit={(event) => void submit(event)}>
        {error ? <div className="mb-4"><ErrorNotice>{error}</ErrorNotice></div> : null}
        <fieldset>
          <legend className="label-micro mb-2">Blood pressure · mmHg</legend>
          <div className="grid grid-cols-2 gap-3">
            <NumberField label="Systolic" unit="mmHg" min={50} max={250} step={1} placeholder="122" value={values.bp_sys ?? ''} onChange={(value) => set('bp_sys', value)} />
            <NumberField label="Diastolic" unit="mmHg" min={30} max={150} step={1} placeholder="78" value={values.bp_dia ?? ''} onChange={(value) => set('bp_dia', value)} />
          </div>
        </fieldset>
        <div className="mt-4 grid grid-cols-2 gap-3 lg:grid-cols-3">
          {FIELDS.map((field) => (
            <NumberField key={field.key} label={field.label} unit={field.unit} min={field.min} max={field.max} step={field.step} placeholder={field.placeholder} value={values[field.key] ?? ''} onChange={(value) => set(field.key, value)} />
          ))}
        </div>
        <div className="mt-5 flex flex-wrap items-center justify-between gap-3 border-t border-line pt-4">
          <p className="max-w-sm text-2xs leading-4 text-ink-label">Crew-entered values are unverified demo inputs. The audit records measurement kinds and counts, never the raw values.</p>
          <Button type="submit" busy={saving}>Save vitals & re-run gates</Button>
        </div>
      </form>
    </Card>
  );
}

function NumberField({ label, unit, min, max, step, placeholder, value, onChange }: {
  label: string; unit: string; min: number; max: number; step: number; placeholder: string;
  value: string; onChange: (value: string) => void;
}) {
  return (
    <label className="block">
      <span className="mb-1 flex items-center justify-between gap-2 text-xs font-medium text-ink-body">
        {label}<span className="num text-2xs font-normal text-ink-label">{unit}</span>
      </span>
      <input
        type="number"
        inputMode="decimal"
        min={min}
        max={max}
        step={step}
        placeholder={placeholder}
        value={value}
        onChange={(event) => onChange(event.target.value)}
        className="num h-10 w-full rounded-lg border border-line bg-white px-3 text-sm text-ink outline-none placeholder:text-ink-label focus:border-primary-blue"
      />
    </label>
  );
}
