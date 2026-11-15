// Instrument-grade primitives. Hairline borders, no shadows, one accent.
// Dialogs/tabs use Radix UI for focus trapping, keyboard support and ARIA wiring;
// Motion only supplies the visual transition. Semantic tone is exposed as
// data-tone so tests assert meaning, not class names.

import * as React from 'react';
import * as RadixDialog from '@radix-ui/react-dialog';
import * as RadixTabs from '@radix-ui/react-tabs';
import { AnimatePresence, motion } from 'motion/react';
import { X } from 'lucide-react';
import { cn } from '../../lib/utils';
import { toneClass, type Tone } from '../../lib/status';
import { drawerVariants, EXIT, EASE_CRISP, pillTransition, pressable } from '../../lib/motion';

/* ---------------------------------------------------------------- surfaces */

export function Card({ className, ...props }: React.HTMLAttributes<HTMLDivElement>) {
  return <div className={cn('rounded-xl border border-hairline bg-surface', className)} {...props} />;
}

export function CardHeader({ className, ...props }: React.HTMLAttributes<HTMLDivElement>) {
  return <div className={cn('flex flex-col gap-0.5 border-b border-hairline px-4 py-3', className)} {...props} />;
}

export function CardTitle({ className, ...props }: React.HTMLAttributes<HTMLHeadingElement>) {
  return <h3 className={cn('text-sm font-semibold tracking-[-0.01em] text-ink', className)} {...props} />;
}

export function CardDescription({ className, ...props }: React.HTMLAttributes<HTMLParagraphElement>) {
  return <p className={cn('text-xs leading-relaxed text-ink-muted', className)} {...props} />;
}

export function CardContent({ className, ...props }: React.HTMLAttributes<HTMLDivElement>) {
  return <div className={cn('p-4', className)} {...props} />;
}

/* ---------------------------------------------------------------- controls */

type ButtonVariant = 'default' | 'outline' | 'ghost' | 'danger' | 'success';

export interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant;
  size?: 'sm' | 'md';
}

const BUTTON_VARIANT: Record<ButtonVariant, string> = {
  default: 'bg-accent text-base font-semibold hover:bg-accent-hover border-transparent',
  outline: 'bg-transparent text-ink border-hairline-strong hover:bg-white/[0.04]',
  ghost: 'bg-transparent text-ink-secondary border-transparent hover:bg-white/[0.04] hover:text-ink',
  danger: 'bg-state-alert/15 text-state-alert border-state-alert/30 hover:bg-state-alert/25',
  success: 'bg-state-ok/15 text-state-ok border-state-ok/30 hover:bg-state-ok/25',
};

export function Button({ className, variant = 'default', size = 'md', type = 'button', ...props }: ButtonProps) {
  return (
    <motion.button
      {...pressable}
      type={type}
      className={cn(
        'inline-flex select-none items-center justify-center gap-1.5 rounded-md border font-medium',
        'transition-colors duration-150 ease-crisp',
        'disabled:pointer-events-none disabled:opacity-35',
        size === 'sm' ? 'h-6 px-2 text-xs' : 'h-8 px-3 text-sm',
        BUTTON_VARIANT[variant],
        className,
      )}
      // Motion's drag/animation props collide with React's button events; cast is local.
      {...(props as React.ComponentProps<typeof motion.button>)}
    />
  );
}

export function Kbd({ children, className }: { children: React.ReactNode; className?: string }) {
  return (
    <kbd className={cn(
      'tnum inline-flex h-[18px] min-w-[18px] items-center justify-center rounded border border-hairline',
      'bg-white/[0.03] px-1 text-[10px] font-medium text-ink-muted', className,
    )}>
      {children}
    </kbd>
  );
}

/* ------------------------------------------------------------------ status */

export interface BadgeProps extends React.HTMLAttributes<HTMLSpanElement> {
  tone?: Tone;
}

export function Badge({ className, tone = 'unknown', ...props }: BadgeProps) {
  return (
    <span
      data-tone={tone}
      className={cn(
        'tnum inline-flex items-center gap-1 rounded border px-1.5 py-[1px] text-[10px] font-medium uppercase tracking-[0.06em]',
        toneClass(tone), className,
      )}
      {...props}
    />
  );
}

export function StatusDot({ tone = 'unknown', pulse = false, className }: { tone?: Tone; pulse?: boolean; className?: string }) {
  const colour: Record<Tone, string> = {
    nominal: 'bg-state-ok', watch: 'bg-state-watch', alert: 'bg-state-alert',
    unknown: 'bg-state-unknown', info: 'bg-state-info',
  };
  return (
    <span data-tone={tone} aria-hidden
      className={cn('inline-block h-1.5 w-1.5 shrink-0 rounded-full', colour[tone], pulse && 'animate-pulse-dot', className)} />
  );
}

/* ------------------------------------------------------------------ inputs */

export function Input({ className, ...props }: React.InputHTMLAttributes<HTMLInputElement>) {
  return (
    <input className={cn(
      'tnum h-8 w-full rounded-md border border-hairline bg-base px-2.5 text-sm text-ink',
      'placeholder:text-ink-faint focus:border-accent/60 focus:outline-none transition-colors duration-150',
      className,
    )} {...props} />
  );
}

export function Select({ className, ...props }: React.SelectHTMLAttributes<HTMLSelectElement>) {
  return (
    <select className={cn(
      'h-7 rounded-md border border-hairline bg-surface-2 px-2 text-xs text-ink',
      'focus:border-accent/60 focus:outline-none', className,
    )} {...props} />
  );
}

export function Label({ className, ...props }: React.LabelHTMLAttributes<HTMLLabelElement>) {
  return <label className={cn('microlabel', className)} {...props} />;
}

export function Textarea({ className, ...props }: React.TextareaHTMLAttributes<HTMLTextAreaElement>) {
  return (
    <textarea className={cn(
      'w-full rounded-md border border-hairline bg-base px-2.5 py-2 text-sm text-ink',
      'placeholder:text-ink-faint focus:border-accent/60 focus:outline-none', className,
    )} {...props} />
  );
}

/* ------------------------------------------------------- segmented control */

export interface SegmentedProps<T extends string> {
  options: Array<{ id: T; label: string }>;
  value: T;
  onChange: (id: T) => void;
  layoutId: string;
  className?: string;
  size?: 'sm' | 'md';
}

/** Timeframe / filter switcher with a shared-element sliding indicator. */
export function Segmented<T extends string>({
  options, value, onChange, layoutId, className, size = 'sm',
}: SegmentedProps<T>) {
  return (
    <div role="group" className={cn('inline-flex items-center gap-0.5 rounded-md border border-hairline bg-surface p-0.5', className)}>
      {options.map((option) => {
        const active = option.id === value;
        return (
          <button key={option.id} type="button" onClick={() => onChange(option.id)} aria-pressed={active}
            className={cn(
              'tnum relative rounded px-2 font-medium transition-colors duration-150',
              size === 'sm' ? 'h-[22px] text-xs' : 'h-7 text-sm',
              active ? 'text-ink' : 'text-ink-muted hover:text-ink-secondary',
            )}>
            {active ? (
              <motion.span layoutId={layoutId} transition={pillTransition}
                className="absolute inset-0 rounded bg-white/[0.07] ring-1 ring-inset ring-white/[0.06]" />
            ) : null}
            <span className="relative z-10">{option.label}</span>
          </button>
        );
      })}
    </div>
  );
}

export interface TabsProps {
  tabs: Array<{ id: string; label: string }>;
  active: string;
  onChange: (id: string) => void;
  className?: string;
  children?: React.ReactNode;
  label?: string;
}

/** Radix tabs: roving focus + arrow keys, with a Motion shared underline. */
export function Tabs({ tabs, active, onChange, className, children, label = 'Sections' }: TabsProps) {
  return (
    <RadixTabs.Root value={active} onValueChange={onChange}>
      <RadixTabs.List aria-label={label} className={cn('flex items-center gap-4 overflow-x-auto border-b border-hairline', className)}>
        {tabs.map((tab) => {
          const isActive = tab.id === active;
          return (
            <RadixTabs.Trigger key={tab.id} value={tab.id}
              className={cn(
                'relative -mb-px shrink-0 py-2 text-sm font-medium transition-colors duration-150',
                'data-[state=active]:text-ink text-ink-muted hover:text-ink-secondary',
              )}>
              {tab.label}
              {isActive ? (
                <motion.span layoutId={`tab-underline-${tabs.map((t) => t.id).join('-')}`}
                  transition={pillTransition} className="absolute inset-x-0 -bottom-px h-[2px] bg-accent" />
              ) : null}
            </RadixTabs.Trigger>
          );
        })}
      </RadixTabs.List>
      {children}
    </RadixTabs.Root>
  );
}

export function TabsContent({ value, className, children }: { value: string; className?: string; children: React.ReactNode }) {
  return (
    <RadixTabs.Content value={value} className={cn('pt-4 focus-visible:outline-none', className)}>
      {children}
    </RadixTabs.Content>
  );
}

/* ------------------------------------------------------------------- table */

export function Table({ className, ...props }: React.TableHTMLAttributes<HTMLTableElement>) {
  return <table className={cn('tnum w-full border-collapse text-left text-xs', className)} {...props} />;
}

export function Th({ className, ...props }: React.ThHTMLAttributes<HTMLTableCellElement>) {
  return (
    <th className={cn(
      'sticky top-0 z-10 whitespace-nowrap border-b border-hairline bg-surface px-3 py-2',
      'text-[10px] font-semibold uppercase tracking-[0.08em] text-ink-muted', className,
    )} {...props} />
  );
}

export function Td({ className, ...props }: React.TdHTMLAttributes<HTMLTableCellElement>) {
  return <td className={cn('whitespace-nowrap border-b border-hairline/60 px-3 py-1.5 text-ink-secondary', className)} {...props} />;
}

/* ------------------------------------------------------------ overlay/feedback */

type ShellVariant = 'dialog' | 'drawer' | 'palette';

interface DialogShellProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  title: string;
  subtitle?: string;
  children: React.ReactNode;
  variant?: ShellVariant;
  hideHeader?: boolean;
  className?: string;
}

const SHELL_POSITION: Record<ShellVariant, string> = {
  dialog: 'fixed inset-0 z-50 flex items-start justify-center p-4 pt-[12vh]',
  drawer: 'fixed right-0 top-0 z-50 flex h-full w-full max-w-[440px] flex-col border-l border-hairline-strong bg-surface',
  palette: 'fixed inset-0 z-[60] flex items-start justify-center p-4 pt-[14vh]',
};

const SHELL_PANEL: Record<ShellVariant, string> = {
  dialog: 'pointer-events-auto w-full max-w-lg overflow-hidden rounded-xl border border-hairline-strong bg-surface',
  drawer: 'flex h-full w-full flex-col',
  palette: 'pointer-events-auto w-full max-w-[560px] overflow-hidden rounded-xl border border-hairline-strong bg-surface',
};

/**
 * One accessible overlay implementation for dialogs, drawers and the palette.
 * Radix handles focus trap, focus restore, Escape, outside click and aria-hidden
 * on the rest of the app; Motion handles the entrance/exit only.
 */
export function DialogShell({
  open, onOpenChange, title, subtitle, children, variant = 'dialog', hideHeader = false, className,
}: DialogShellProps) {
  const initial = variant === 'drawer' ? { x: '100%' }
    : variant === 'palette' ? { opacity: 0, y: 6, scale: 0.985 }
    : { opacity: 0, y: 6, scale: 0.99 };
  const animate = variant === 'drawer' ? { x: 0 } : { opacity: 1, y: 0, scale: 1 };
  const exit = variant === 'drawer' ? { x: '100%', transition: EXIT }
    : { opacity: 0, y: 4, scale: 0.99, transition: EXIT };

  return (
    <RadixDialog.Root open={open} onOpenChange={onOpenChange}>
      <AnimatePresence>
        {open ? (
          <RadixDialog.Portal forceMount>
            <RadixDialog.Overlay asChild forceMount>
              <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
                transition={{ duration: 0.12, ease: EASE_CRISP }}
                className={cn('fixed inset-0 bg-black/60 backdrop-blur-[2px]', variant === 'drawer' ? 'z-40' : 'z-50')} />
            </RadixDialog.Overlay>
            <RadixDialog.Content asChild forceMount>
              <motion.div
                {...(variant === 'drawer' ? { variants: drawerVariants, initial: 'hidden', animate: 'show', exit: 'exit' }
                  : { initial, animate, exit, transition: { duration: 0.18, ease: EASE_CRISP } })}
                className={cn(SHELL_POSITION[variant], variant !== 'drawer' && 'pointer-events-none')}
              >
                <div className={cn(SHELL_PANEL[variant], className)}>
                  {!subtitle ? (
                    <RadixDialog.Description className="sr-only">
                      {variant === 'palette' ? 'Search commands, scenarios and subjects.' : `${title}. Press Escape to close.`}
                    </RadixDialog.Description>
                  ) : null}
                  {hideHeader ? (
                    <RadixDialog.Title className="sr-only">{title}</RadixDialog.Title>
                  ) : (
                    <header className="flex items-start justify-between gap-3 border-b border-hairline px-4 py-3">
                      <div className="min-w-0">
                        <RadixDialog.Title className="truncate text-sm font-semibold text-ink">{title}</RadixDialog.Title>
                        {subtitle ? (
                          <RadixDialog.Description className="tnum mt-0.5 truncate text-xs text-ink-muted">
                            {subtitle}
                          </RadixDialog.Description>
                        ) : null}
                      </div>
                      <RadixDialog.Close asChild>
                        <Button variant="ghost" size="sm" aria-label={variant === 'drawer' ? 'Close detail panel' : 'Close dialog'}>
                          <X size={14} strokeWidth={1.75} />
                        </Button>
                      </RadixDialog.Close>
                    </header>
                  )}
                  <div className={cn(variant === 'drawer' ? 'flex-1 overflow-y-auto p-4' : variant === 'dialog' ? 'p-4' : '')}>
                    {children}
                  </div>
                </div>
              </motion.div>
            </RadixDialog.Content>
          </RadixDialog.Portal>
        ) : null}
      </AnimatePresence>
    </RadixDialog.Root>
  );
}

export interface DialogProps {
  open: boolean;
  title: string;
  onClose: () => void;
  children: React.ReactNode;
}

export function Dialog({ open, title, onClose, children }: DialogProps) {
  return (
    <DialogShell open={open} onOpenChange={(next) => { if (!next) onClose(); }} title={title} variant="dialog">
      {children}
    </DialogShell>
  );
}

export interface DrawerProps {
  open: boolean;
  title: string;
  subtitle?: string;
  onClose: () => void;
  children: React.ReactNode;
}

/** Slide-over detail panel, triggered from a table row. */
export function Drawer({ open, title, subtitle, onClose, children }: DrawerProps) {
  return (
    <DialogShell open={open} onOpenChange={(next) => { if (!next) onClose(); }}
      title={title} subtitle={subtitle} variant="drawer">
      {children}
    </DialogShell>
  );
}

export function AlertBanner({
  tone = 'unknown', title, children, className,
}: { tone?: Tone; title: string; children?: React.ReactNode; className?: string }) {
  return (
    <div data-tone={tone} role="status" className={cn('rounded-md border px-3 py-2 text-xs', toneClass(tone), className)}>
      <div className="text-[10px] font-semibold uppercase tracking-[0.08em]">{title}</div>
      {children ? <div className="mt-1 leading-relaxed opacity-90">{children}</div> : null}
    </div>
  );
}

/** Skeleton that matches the exact dimensions of the content it replaces. */
export function Skeleton({ className }: { className?: string }) {
  return (
    <div aria-hidden className={cn('relative overflow-hidden rounded bg-white/[0.04]', className)}>
      <div className="absolute inset-0 -translate-x-full animate-shimmer bg-gradient-to-r from-transparent via-white/[0.06] to-transparent" />
    </div>
  );
}

export function Stat({ label, value, hint }: { label: string; value: React.ReactNode; hint?: string }) {
  return (
    <div className="px-3 py-2">
      <div className="microlabel">{label}</div>
      <div className="tnum mt-1 text-lg text-ink">{value}</div>
      {hint ? <div className="mt-0.5 text-[10px] text-ink-faint">{hint}</div> : null}
    </div>
  );
}

/** Inline chart-header metric: label above, tabular value beside a unit. */
export function InlineMetric({
  label, value, unit, tone,
}: { label: string; value: string; unit?: string; tone?: Tone }) {
  return (
    <div className="flex flex-col gap-0.5 border-l border-hairline pl-3 first:border-l-0 first:pl-0">
      <span className="microlabel">{label}</span>
      <span className="flex items-baseline gap-1">
        <span data-tone={tone}
          className={cn('tnum text-lg leading-none', tone === 'alert' ? 'text-state-alert'
            : tone === 'watch' ? 'text-state-watch' : 'text-ink')}>
          {value}
        </span>
        {unit ? <span className="tnum text-[10px] text-ink-faint">{unit}</span> : null}
      </span>
    </div>
  );
}

export function EmptyState({ title, detail }: { title: string; detail?: string }) {
  return (
    <div className="flex flex-col items-center justify-center gap-1 rounded-lg border border-dashed border-hairline px-4 py-10 text-center">
      <span className="text-sm font-medium text-ink-secondary">{title}</span>
      {detail ? <span className="max-w-md text-xs leading-relaxed text-ink-faint">{detail}</span> : null}
    </div>
  );
}

export { EXIT, EASE_CRISP };
