import type { ButtonHTMLAttributes, HTMLAttributes, ReactNode } from 'react';
import { AlertCircle, ArrowRight, LoaderCircle } from 'lucide-react';
import type { Tone } from '../lib/clinical';
import { cn } from '../lib/utils';

export function Card({ className, ...props }: HTMLAttributes<HTMLDivElement>) {
  return <div className={cn('card-surface', className)} {...props} />;
}

export function CardHeader({ eyebrow, title, description, action }: {
  eyebrow?: string; title: string; description?: string; action?: ReactNode;
}) {
  return (
    <div className="flex items-start justify-between gap-4 border-b border-line px-5 py-4">
      <div>
        {eyebrow ? <div className="label-micro mb-1">{eyebrow}</div> : null}
        <h2 className="text-md font-semibold text-ink">{title}</h2>
        {description ? <p className="mt-1 max-w-prose text-sm text-ink-body">{description}</p> : null}
      </div>
      {action}
    </div>
  );
}

type ButtonProps = ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: 'primary' | 'secondary' | 'ghost' | 'blue';
  size?: 'sm' | 'md' | 'lg';
  busy?: boolean;
};

export function Button({ variant = 'primary', size = 'md', busy, className, children, disabled, ...props }: ButtonProps) {
  return (
    <button
      className={cn(
        'inline-flex items-center justify-center gap-2 rounded-lg font-medium transition-colors duration-150 disabled:cursor-not-allowed disabled:opacity-50',
        size === 'sm' && 'h-8 px-3 text-xs',
        size === 'md' && 'h-10 px-4 text-sm',
        size === 'lg' && 'h-12 px-5 text-md',
        variant === 'primary' && 'bg-primary text-white hover:bg-primary-hover',
        variant === 'secondary' && 'border border-line bg-white text-ink hover:border-line-strong hover:bg-page',
        variant === 'ghost' && 'text-ink-body hover:bg-neutral-soft hover:text-ink',
        variant === 'blue' && 'bg-primary-blue text-white hover:bg-primary-blue-hover',
        className,
      )}
      disabled={disabled || busy}
      {...props}
    >
      {busy ? <LoaderCircle size={15} className="animate-spin" aria-hidden /> : null}
      {children}
    </button>
  );
}

export function Badge({ tone = 'neutral', children, className }: {
  tone?: Tone; children: ReactNode; className?: string;
}) {
  return (
    <span
      data-tone={tone}
      className={cn(
        'inline-flex items-center gap-1.5 rounded-full border px-2.5 py-0.5 text-2xs font-semibold',
        tone === 'nominal' && 'border-nominal/20 bg-nominal-soft text-nominal-text',
        tone === 'watch' && 'border-watch/25 bg-watch-soft text-watch-text',
        tone === 'critical' && 'border-critical/20 bg-critical-soft text-critical-text',
        tone === 'neutral' && 'border-line bg-neutral-soft text-neutral-text',
        className,
      )}
    >
      {children}
    </span>
  );
}

export function StatusDot({ tone, pulse = false }: { tone: Tone; pulse?: boolean }) {
  return (
    <span className="relative inline-flex h-2.5 w-2.5 shrink-0" aria-hidden>
      {pulse ? <span className={cn('absolute inset-0 rounded-full opacity-40 animate-pulse-ring', toneBg(tone))} /> : null}
      <span className={cn('relative inline-flex h-2.5 w-2.5 rounded-full', toneBg(tone))} />
    </span>
  );
}

function toneBg(tone: Tone): string {
  if (tone === 'nominal') return 'bg-nominal';
  if (tone === 'watch') return 'bg-watch';
  if (tone === 'critical') return 'bg-critical';
  return 'bg-neutral';
}

export function Gauge({ value, tone = 'neutral', label }: {
  value: number | null; tone?: Tone; label: string;
}) {
  const width = value === null ? 0 : Math.max(0, Math.min(100, value));
  return (
    <div
      role="progressbar"
      aria-label={label}
      aria-valuemin={0}
      aria-valuemax={100}
      aria-valuenow={value === null ? undefined : Math.round(width)}
      className="h-1.5 w-full overflow-hidden rounded-full bg-neutral-soft"
    >
      <div className={cn('gauge-fill h-full rounded-full', toneBg(tone))} style={{ width: `${width}%` }} />
    </div>
  );
}

export interface TabItem { id: string; label: string; badge?: ReactNode }

export function Tabs({ items, active, onChange, label, className }: {
  items: TabItem[]; active: string; onChange: (id: string) => void; label: string; className?: string;
}) {
  return (
    <div role="tablist" aria-label={label} className={cn('inline-flex rounded-lg border border-line bg-neutral-soft p-1', className)}>
      {items.map((item) => (
        <button
          key={item.id}
          type="button"
          role="tab"
          aria-selected={active === item.id}
          className={cn(
            'inline-flex h-9 items-center justify-center gap-2 rounded-md px-4 text-sm font-medium transition-colors',
            active === item.id ? 'bg-white text-ink shadow-card' : 'text-ink-subtle hover:text-ink',
          )}
          onClick={() => onChange(item.id)}
        >
          {item.label}{item.badge}
        </button>
      ))}
    </div>
  );
}

export function ErrorNotice({ title = 'Something needs attention', children, onRetry }: {
  title?: string; children: ReactNode; onRetry?: () => void;
}) {
  return (
    <div role="alert" className="flex items-start gap-3 rounded-xl border border-critical/20 bg-critical-soft px-4 py-3 text-critical-text">
      <AlertCircle size={17} className="mt-0.5 shrink-0" aria-hidden />
      <div className="min-w-0 flex-1">
        <div className="text-sm font-semibold">{title}</div>
        <div className="mt-0.5 text-sm">{children}</div>
      </div>
      {onRetry ? <Button variant="secondary" size="sm" onClick={onRetry}>Retry</Button> : null}
    </div>
  );
}

export function EmptyState({ title, detail, action }: { title: string; detail: string; action?: ReactNode }) {
  return (
    <div className="flex min-h-48 flex-col items-center justify-center px-6 py-10 text-center">
      <div className="mb-3 flex h-10 w-10 items-center justify-center rounded-full border border-line bg-page text-ink-label">
        <ArrowRight size={17} aria-hidden />
      </div>
      <h3 className="text-md font-semibold">{title}</h3>
      <p className="mt-1 max-w-sm text-sm text-ink-body">{detail}</p>
      {action ? <div className="mt-4">{action}</div> : null}
    </div>
  );
}

export function PageSkeleton() {
  return (
    <div className="mx-auto max-w-content animate-pulse px-6 py-12" aria-label="Loading workstation" role="status">
      <div className="h-3 w-56 rounded bg-line" />
      <div className="mt-5 h-10 w-2/3 rounded bg-line" />
      <div className="mt-4 h-4 w-1/2 rounded bg-line" />
      <div className="mt-10 grid gap-4 md:grid-cols-3">
        {[0, 1, 2].map((item) => <div key={item} className="h-44 rounded-xl border border-line bg-white" />)}
      </div>
    </div>
  );
}

export function MetricTile({ label, value, unit, detail }: {
  label: string; value: ReactNode; unit?: string; detail?: ReactNode;
}) {
  return (
    <div className="rounded-lg border border-line bg-page px-3 py-3">
      <div className="label-micro">{label}</div>
      <div className="mt-1.5 flex items-baseline gap-1">
        <span className="num text-lg font-medium text-ink">{value}</span>
        {unit ? <span className="num text-xs text-ink-subtle">{unit}</span> : null}
      </div>
      {detail ? <div className="mt-1 text-2xs leading-4 text-ink-subtle">{detail}</div> : null}
    </div>
  );
}
