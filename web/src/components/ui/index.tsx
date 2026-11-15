// Local shadcn-style primitives. No runtime UI-kit dependency.

import * as React from 'react';
import { cn } from '../../lib/utils';
import { toneClass, type Tone } from '../../lib/status';

export function Card({ className, ...props }: React.HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      className={cn('rounded-xl border border-ink-600 bg-ink-800/70 shadow-lg backdrop-blur', className)}
      {...props}
    />
  );
}

export function CardHeader({ className, ...props }: React.HTMLAttributes<HTMLDivElement>) {
  return <div className={cn('flex flex-col gap-1 border-b border-ink-600 p-4', className)} {...props} />;
}

export function CardTitle({ className, ...props }: React.HTMLAttributes<HTMLHeadingElement>) {
  return <h3 className={cn('text-sm font-semibold tracking-wide text-slate-100', className)} {...props} />;
}

export function CardDescription({ className, ...props }: React.HTMLAttributes<HTMLParagraphElement>) {
  return <p className={cn('text-xs leading-relaxed text-slate-400', className)} {...props} />;
}

export function CardContent({ className, ...props }: React.HTMLAttributes<HTMLDivElement>) {
  return <div className={cn('p-4', className)} {...props} />;
}

type ButtonVariant = 'default' | 'outline' | 'ghost' | 'danger' | 'success';

export interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant;
  size?: 'sm' | 'md';
}

const BUTTON_VARIANT: Record<ButtonVariant, string> = {
  default: 'bg-sky-600 text-white hover:bg-sky-500 border-transparent',
  outline: 'bg-transparent text-slate-200 border-ink-600 hover:bg-ink-700',
  ghost: 'bg-transparent text-slate-300 border-transparent hover:bg-ink-700',
  danger: 'bg-alert/90 text-white hover:bg-alert border-transparent',
  success: 'bg-nominal/90 text-ink-900 hover:bg-nominal border-transparent',
};

export function Button({ className, variant = 'default', size = 'md', ...props }: ButtonProps) {
  return (
    <button
      className={cn(
        'inline-flex items-center justify-center gap-2 rounded-lg border font-medium transition-colors',
        'disabled:cursor-not-allowed disabled:opacity-40',
        'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-sky-400/70',
        size === 'sm' ? 'px-2.5 py-1 text-xs' : 'px-3.5 py-2 text-sm',
        BUTTON_VARIANT[variant],
        className,
      )}
      {...props}
    />
  );
}

export interface BadgeProps extends React.HTMLAttributes<HTMLSpanElement> {
  tone?: Tone;
}

export function Badge({ className, tone, ...props }: BadgeProps) {
  return (
    <span
      className={cn(
        'inline-flex items-center gap-1 rounded-md border px-2 py-0.5 text-[11px] font-semibold uppercase tracking-wider',
        tone ? toneClass(tone) : 'border-ink-600 bg-ink-700 text-slate-300',
        className,
      )}
      {...props}
    />
  );
}

export function Input({ className, ...props }: React.InputHTMLAttributes<HTMLInputElement>) {
  return (
    <input
      className={cn(
        'w-full rounded-lg border border-ink-600 bg-ink-900 px-3 py-2 text-sm text-slate-100',
        'placeholder:text-slate-500 focus:border-sky-500 focus:outline-none focus:ring-1 focus:ring-sky-500',
        className,
      )}
      {...props}
    />
  );
}

export function Select({ className, ...props }: React.SelectHTMLAttributes<HTMLSelectElement>) {
  return (
    <select
      className={cn(
        'rounded-lg border border-ink-600 bg-ink-900 px-3 py-2 text-sm text-slate-100',
        'focus:border-sky-500 focus:outline-none focus:ring-1 focus:ring-sky-500',
        className,
      )}
      {...props}
    />
  );
}

export function Label({ className, ...props }: React.LabelHTMLAttributes<HTMLLabelElement>) {
  return <label className={cn('text-xs font-medium text-slate-300', className)} {...props} />;
}

export function Textarea({ className, ...props }: React.TextareaHTMLAttributes<HTMLTextAreaElement>) {
  return (
    <textarea
      className={cn(
        'w-full rounded-lg border border-ink-600 bg-ink-900 px-3 py-2 text-sm text-slate-100',
        'placeholder:text-slate-500 focus:border-sky-500 focus:outline-none',
        className,
      )}
      {...props}
    />
  );
}

export function Table({ className, ...props }: React.TableHTMLAttributes<HTMLTableElement>) {
  return <table className={cn('w-full border-collapse text-left text-xs', className)} {...props} />;
}

export function Th({ className, ...props }: React.ThHTMLAttributes<HTMLTableCellElement>) {
  return (
    <th
      className={cn(
        'border-b border-ink-600 px-3 py-2 font-semibold uppercase tracking-wider text-slate-400',
        className,
      )}
      {...props}
    />
  );
}

export function Td({ className, ...props }: React.TdHTMLAttributes<HTMLTableCellElement>) {
  return <td className={cn('border-b border-ink-700 px-3 py-2 text-slate-200', className)} {...props} />;
}

export interface TabsProps {
  tabs: Array<{ id: string; label: string }>;
  active: string;
  onChange: (id: string) => void;
  className?: string;
}

export function Tabs({ tabs, active, onChange, className }: TabsProps) {
  return (
    <div className={cn('flex flex-wrap gap-1 rounded-lg border border-ink-600 bg-ink-900 p-1', className)}>
      {tabs.map((tab) => (
        <button
          key={tab.id}
          type="button"
          onClick={() => onChange(tab.id)}
          aria-pressed={active === tab.id}
          className={cn(
            'rounded-md px-3 py-1.5 text-xs font-medium transition-colors',
            active === tab.id ? 'bg-sky-600 text-white' : 'text-slate-400 hover:bg-ink-700 hover:text-slate-200',
          )}
        >
          {tab.label}
        </button>
      ))}
    </div>
  );
}

export interface DialogProps {
  open: boolean;
  title: string;
  onClose: () => void;
  children: React.ReactNode;
}

export function Dialog({ open, title, onClose, children }: DialogProps) {
  if (!open) return null;
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4" role="dialog" aria-modal="true">
      <Card className="w-full max-w-lg">
        <CardHeader className="flex-row items-center justify-between">
          <CardTitle>{title}</CardTitle>
          <Button variant="ghost" size="sm" onClick={onClose} aria-label="Close dialog">
            ✕
          </Button>
        </CardHeader>
        <CardContent>{children}</CardContent>
      </Card>
    </div>
  );
}

export function AlertBanner({
  tone = 'unknown',
  title,
  children,
  className,
}: {
  tone?: Tone;
  title: string;
  children?: React.ReactNode;
  className?: string;
}) {
  return (
    <div className={cn('rounded-lg border px-3 py-2 text-xs', toneClass(tone), className)}>
      <div className="font-semibold uppercase tracking-wider">{title}</div>
      {children ? <div className="mt-1 leading-relaxed opacity-90">{children}</div> : null}
    </div>
  );
}

export function Stat({ label, value, hint }: { label: string; value: React.ReactNode; hint?: string }) {
  return (
    <div className="rounded-lg border border-ink-600 bg-ink-900/60 px-3 py-2">
      <div className="text-[10px] font-semibold uppercase tracking-wider text-slate-500">{label}</div>
      <div className="mt-0.5 font-mono text-lg text-slate-100">{value}</div>
      {hint ? <div className="text-[10px] leading-tight text-slate-500">{hint}</div> : null}
    </div>
  );
}

export function EmptyState({ title, detail }: { title: string; detail?: string }) {
  return (
    <div className="rounded-lg border border-dashed border-ink-600 px-4 py-8 text-center">
      <div className="text-sm font-medium text-slate-400">{title}</div>
      {detail ? <div className="mt-1 text-xs text-slate-500">{detail}</div> : null}
    </div>
  );
}
