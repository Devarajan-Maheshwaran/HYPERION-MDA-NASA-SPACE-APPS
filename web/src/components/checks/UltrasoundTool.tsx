import { useCallback, useEffect, useRef, useState, type ChangeEvent } from 'react';
import { Upload } from 'lucide-react';
import { api } from '../../lib/api';
import { num } from '../../lib/format';
import { useWorkstation } from '../../state/WorkstationProvider';
import { Badge, Button, Card, CardHeader, ErrorNotice } from '../ui';

type Point = { x: number; y: number };
type Caliper = { a: Point; b: Point };
type Preset = 'nominal' | 'sans';
const WIDTH = 560;
const HEIGHT = 260;
const DEFAULT_SCALE = 20;

export function UltrasoundTool({ onSaved }: { onSaved: () => void }) {
  const { submitExam } = useWorkstation();
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const imageRef = useRef<HTMLImageElement | null>(null);
  const objectUrlRef = useRef<string | null>(null);
  const [preset, setPreset] = useState<Preset | null>('nominal');
  const [uploaded, setUploaded] = useState(false);
  const [scale, setScale] = useState(String(DEFAULT_SCALE));
  const [caliper, setCaliper] = useState<Caliper | null>(null);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const presetMm = preset === 'sans' ? 6.1 : 4.6;
  const pixelsPerMm = Number(scale);
  const validScale = Number.isFinite(pixelsPerMm) && pixelsPerMm > 0;
  const measuredMm = preset ? presetMm : caliper && validScale ? Math.hypot(caliper.b.x - caliper.a.x, caliper.b.y - caliper.a.y) / pixelsPerMm : null;

  const draw = useCallback(() => {
    const canvas = canvasRef.current;
    const context = canvas?.getContext('2d');
    if (!canvas || !context) return;
    context.clearRect(0, 0, WIDTH, HEIGHT);
    context.fillStyle = '#F1F5F9';
    context.fillRect(0, 0, WIDTH, HEIGHT);

    if (uploaded && imageRef.current) {
      const image = imageRef.current;
      const ratio = Math.min(WIDTH / image.naturalWidth, HEIGHT / image.naturalHeight);
      const width = image.naturalWidth * ratio;
      const height = image.naturalHeight * ratio;
      context.drawImage(image, (WIDTH - width) / 2, (HEIGHT - height) / 2, width, height);
    } else {
      // An explicitly synthetic teaching frame, not a patient image or a diagnostic model.
      context.fillStyle = '#FFFFFF';
      context.fillRect(16, 16, WIDTH - 32, HEIGHT - 32);
      context.strokeStyle = '#E2E8F0';
      context.lineWidth = 1;
      for (let y = 32; y < HEIGHT; y += 24) {
        context.beginPath(); context.moveTo(16, y); context.lineTo(WIDTH - 16, y); context.stroke();
      }
      context.fillStyle = '#CBD5E1';
      context.beginPath();
      context.ellipse(280, 65, 100, 51, 0, 0, Math.PI * 2);
      context.fill();
      context.fillStyle = '#94A3B8';
      context.fillRect(252, 105, 56, 139);
      context.fillStyle = '#64748B';
      context.fillRect(268, 105, 24, 139);
      context.fillStyle = '#475569';
      context.font = '11px Inter, sans-serif';
      context.fillText('SYNTHETIC SAMPLE · NOT A PATIENT SCAN', 28, 36);
      context.fillText('Globe', 392, 67);
      context.fillText('Optic nerve sheath', 330, 185);
    }

    // The measurement plane is 3 mm behind the posterior globe in the synthetic frame.
    if (!uploaded && validScale) {
      const y = 116 + 3 * pixelsPerMm;
      context.setLineDash([4, 4]);
      context.strokeStyle = '#94A3B8';
      context.beginPath(); context.moveTo(190, y); context.lineTo(370, y); context.stroke();
      context.setLineDash([]);
      context.fillStyle = '#64748B';
      context.font = '10px Inter, sans-serif';
      context.fillText('3 mm retrobulbar plane', 374, Math.min(y + 3, HEIGHT - 12));
    }

    const line = preset && !uploaded && validScale
      ? { a: { x: 280 - presetMm * pixelsPerMm / 2, y: Math.min(116 + 3 * pixelsPerMm, HEIGHT - 20) }, b: { x: 280 + presetMm * pixelsPerMm / 2, y: Math.min(116 + 3 * pixelsPerMm, HEIGHT - 20) } }
      : caliper;
    if (line) {
      context.strokeStyle = '#0F172A';
      context.lineWidth = 2;
      context.beginPath(); context.moveTo(line.a.x, line.a.y); context.lineTo(line.b.x, line.b.y); context.stroke();
      for (const point of [line.a, line.b]) {
        context.fillStyle = '#FFFFFF';
        context.strokeStyle = '#0F172A';
        context.beginPath(); context.arc(point.x, point.y, 4, 0, Math.PI * 2); context.fill(); context.stroke();
      }
    }
  }, [uploaded, validScale, pixelsPerMm, preset, presetMm, caliper]);

  useEffect(() => { draw(); }, [draw]);
  useEffect(() => () => { if (objectUrlRef.current) URL.revokeObjectURL(objectUrlRef.current); }, []);

  const choosePreset = (next: Preset) => {
    if (objectUrlRef.current) URL.revokeObjectURL(objectUrlRef.current);
    objectUrlRef.current = null;
    imageRef.current = null;
    setUploaded(false);
    setPreset(next);
    setScale(String(DEFAULT_SCALE));
    setCaliper(null);
    setError(null);
  };

  const upload = (event: ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    event.target.value = '';
    if (!file) return;
    if (!file.type.startsWith('image/')) { setError('Choose an image file.'); return; }
    if (objectUrlRef.current) URL.revokeObjectURL(objectUrlRef.current);
    const url = URL.createObjectURL(file);
    objectUrlRef.current = url;
    const image = new Image();
    image.onload = () => {
      imageRef.current = image;
      setUploaded(true);
      setPreset(null);
      setCaliper(null);
      setScale('');
      setError(null);
    };
    image.onerror = () => {
      URL.revokeObjectURL(url);
      objectUrlRef.current = null;
      setError('That image could not be decoded. Choose a PNG, JPEG or WebP frame.');
    };
    image.src = url;
  };

  const placePoint = (event: React.MouseEvent<HTMLCanvasElement>) => {
    if (preset) return;
    const rect = event.currentTarget.getBoundingClientRect();
    if (!rect.width || !rect.height) return;
    const point = {
      x: Math.max(0, Math.min(WIDTH, (event.clientX - rect.left) * WIDTH / rect.width)),
      y: Math.max(0, Math.min(HEIGHT, (event.clientY - rect.top) * HEIGHT / rect.height)),
    };
    setCaliper((current) => !current || current.b.x !== current.a.x || current.b.y !== current.a.y ? { a: point, b: point } : { a: current.a, b: point });
  };

  const save = async () => {
    setError(null);
    if (!preset && (!caliper || !validScale)) {
      setError('Place two caliper points and enter the image scale in pixels per millimetre. An image without a scale cannot yield millimetres.');
      return;
    }
    if (measuredMm === null || measuredMm < 1 || measuredMm > 15) {
      setError('The measured diameter must be within the demo range of 1–15 mm. Check the scale and caliper placement.');
      return;
    }
    setSaving(true);
    const payload = preset ? { sample: preset } : {
      px_per_mm: pixelsPerMm, x1: caliper!.a.x, y1: caliper!.a.y, x2: caliper!.b.x, y2: caliper!.b.y,
    };
    const ok = await submitExam('Eye ultrasound', () => api.examUltrasound(payload));
    setSaving(false);
    if (ok) onSaved();
  };

  return (
    <Card>
      <CardHeader eyebrow="Tool 02 · SANS watch" title="Guided eye ultrasound" description="Measure the optic nerve sheath 3 mm behind the globe. Use a labelled sample, or upload a frame and supply its pixel scale." action={<Badge tone="neutral">Manual caliper</Badge>} />
      <div className="p-5">
        {error ? <div className="mb-3"><ErrorNotice>{error}</ErrorNotice></div> : null}
        <div className="mb-3 flex flex-wrap items-center gap-2">
          <Button variant={preset === 'nominal' ? 'primary' : 'secondary'} size="sm" onClick={() => choosePreset('nominal')}>Sample · 4.6 mm</Button>
          <Button variant={preset === 'sans' ? 'primary' : 'secondary'} size="sm" onClick={() => choosePreset('sans')}>Sample · 6.1 mm</Button>
          <label className="ml-auto inline-flex h-8 cursor-pointer items-center gap-2 rounded-lg border border-line bg-white px-3 text-xs font-medium text-ink hover:bg-page">
            <Upload size={13} aria-hidden /> Upload frame
            <input type="file" accept="image/*" className="sr-only" onChange={upload} aria-label="Upload ultrasound frame" />
          </label>
        </div>
        <canvas
          ref={canvasRef}
          width={WIDTH}
          height={HEIGHT}
          onClick={placePoint}
          className="aspect-[560/260] w-full rounded-lg border border-line bg-page"
          aria-label={uploaded ? 'Uploaded ultrasound frame. Click two points across the optic nerve sheath.' : 'Synthetic ultrasound sample with a three millimetre retrobulbar measurement plane.'}
        />
        <div className="mt-3 grid gap-3 sm:grid-cols-[1fr_auto]">
          <label className="block">
            <span className="label-micro">Image scale · pixels per mm</span>
            <input
              type="number"
              min="0.01"
              step="0.01"
              value={scale}
              onChange={(event) => { setScale(event.target.value); if (!uploaded) setPreset(null); }}
              placeholder="Required for uploaded images"
              className="num mt-1 h-10 w-full rounded-lg border border-line bg-white px-3 text-sm text-ink outline-none focus:border-primary-blue"
            />
          </label>
          <div className="rounded-lg border border-line bg-page px-4 py-2">
            <div className="label-micro">ONSD</div>
            <div className="num mt-0.5 text-xl font-medium text-ink">{num(measuredMm)} <span className="text-xs text-ink-subtle">mm</span></div>
          </div>
        </div>
        <p className="mt-2 text-2xs leading-4 text-ink-subtle">
          {preset ? 'Known sample diameter. Switch to a custom measurement by editing the scale or uploading a frame.' : 'Click once for the first sheath edge and again for the second. The line is a manual measurement, not automated diagnosis.'}
        </p>
        <div className="mt-4 flex items-center justify-between gap-3 border-t border-line pt-4">
          <span className="text-2xs text-ink-label">Demo alert at <span className="num">ONSD ≥ 5.8 mm</span> · not a validated clinical limit</span>
          <Button onClick={() => void save()} busy={saving} disabled={measuredMm === null}>Save eye measurement</Button>
        </div>
      </div>
    </Card>
  );
}
