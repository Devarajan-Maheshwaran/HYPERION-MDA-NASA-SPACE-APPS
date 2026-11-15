import * as React from 'react';
import { NavLink, useNavigate } from 'react-router-dom';
import { motion } from 'motion/react';
import {
  Activity, ChevronsLeft, ChevronsRight, FlaskConical, Gauge, LayoutGrid,
  ScrollText, Stethoscope, TriangleAlert, type LucideIcon,
} from 'lucide-react';
import { useSession } from '../../hooks/useSession';
import { cn } from '../../lib/utils';
import { pillTransition, pressable } from '../../lib/motion';
import { Kbd } from '../ui';
import type { Role } from '../../lib/types';

export interface NavItem {
  to: string;
  label: string;
  icon: LucideIcon;
  shortcut: string;
  roles: Role[];
}

export const NAV_ITEMS: NavItem[] = [
  { to: '/workstation', label: 'Live workstation', icon: Gauge, shortcut: 'G W', roles: ['crew', 'flight-surgeon', 'ops', 'researcher'] },
  { to: '/overview', label: 'Overview', icon: LayoutGrid, shortcut: 'G D', roles: ['crew', 'flight-surgeon', 'ops', 'researcher'] },
  { to: '/crew', label: 'Crew console', icon: Activity, shortcut: 'G C', roles: ['crew', 'flight-surgeon', 'ops'] },
  { to: '/crew/checks', label: 'Crew checks', icon: Stethoscope, shortcut: 'G H', roles: ['crew', 'flight-surgeon'] },
  { to: '/surgeon', label: 'Alert queue', icon: TriangleAlert, shortcut: 'G A', roles: ['flight-surgeon', 'ops'] },
  { to: '/ops', label: 'Operations', icon: Gauge, shortcut: 'G O', roles: ['crew', 'flight-surgeon', 'ops'] },
  { to: '/research', label: 'Research', icon: FlaskConical, shortcut: 'G R', roles: ['crew', 'flight-surgeon', 'ops', 'researcher'] },
];

const ROLE_LABEL: Record<Role, string> = {
  crew: 'Crew', 'flight-surgeon': 'Flight surgeon', ops: 'Operations', researcher: 'Researcher',
};

export function Rail({
  collapsed, onToggle,
}: { collapsed: boolean; onToggle: () => void }) {
  const { role, subjectId, habitat, frame } = useSession();
  const navigate = useNavigate();
  const items = React.useMemo(() => NAV_ITEMS.filter((item) => item.roles.includes(role)), [role]);

  // G-then-key chord navigation, matching the indicators in the rail.
  React.useEffect(() => {
    let armed = false;
    let timer: ReturnType<typeof setTimeout> | undefined;
    const onKey = (event: KeyboardEvent) => {
      const target = event.target as HTMLElement | null;
      if (target && ['INPUT', 'TEXTAREA', 'SELECT'].includes(target.tagName)) return;
      if (event.metaKey || event.ctrlKey || event.altKey) return;
      if (!armed && event.key.toLowerCase() === 'g') {
        armed = true;
        timer = setTimeout(() => { armed = false; }, 1200);
        return;
      }
      if (!armed) return;
      armed = false;
      if (timer) clearTimeout(timer);
      const match = items.find((item) => item.shortcut.split(' ')[1]?.toLowerCase() === event.key.toLowerCase());
      if (match) { event.preventDefault(); navigate(match.to); }
    };
    window.addEventListener('keydown', onKey);
    return () => { window.removeEventListener('keydown', onKey); if (timer) clearTimeout(timer); };
  }, [items, navigate]);

  return (
    <motion.aside
      animate={{ width: collapsed ? 64 : 220 }}
      transition={pillTransition}
      className="relative z-30 hidden shrink-0 flex-col border-r border-hairline bg-surface md:flex"
    >
      {/* workspace switcher */}
      <div className={cn('flex h-[52px] items-center gap-2 border-b border-hairline px-3', collapsed && 'justify-center px-0')}>
        <div className="flex h-6 w-6 shrink-0 items-center justify-center rounded bg-accent text-[11px] font-bold text-base">
          H
        </div>
        {!collapsed ? (
          <div className="min-w-0 flex-1">
            <div className="truncate text-sm font-semibold tracking-[-0.01em] text-ink">HYPERION-MDA</div>
            <div className="tnum truncate text-[10px] text-ink-faint">{habitat}</div>
          </div>
        ) : null}
      </div>

      <nav className="flex-1 space-y-0.5 overflow-y-auto p-2">
        {!collapsed ? <div className="microlabel px-2 pb-1.5 pt-1">Workstation</div> : null}
        {items.map((item) => (
          <NavLink key={item.to} to={item.to} title={collapsed ? item.label : undefined}>
            {({ isActive }) => (
              <motion.div
                {...pressable}
                className={cn(
                  'relative flex h-8 items-center gap-2.5 rounded-md px-2 transition-colors duration-150',
                  collapsed && 'justify-center px-0',
                  isActive ? 'text-ink' : 'text-ink-secondary hover:bg-white/[0.03] hover:text-ink',
                )}
              >
                {isActive ? (
                  <motion.span
                    layoutId="rail-active"
                    transition={pillTransition}
                    className="absolute inset-0 rounded-md bg-white/[0.06] ring-1 ring-inset ring-white/[0.05]"
                  />
                ) : null}
                {isActive ? (
                  <motion.span
                    layoutId="rail-accent"
                    transition={pillTransition}
                    className="absolute left-0 top-1/2 h-4 w-[2px] -translate-y-1/2 rounded-r bg-accent"
                  />
                ) : null}
                <item.icon size={15} strokeWidth={1.75} className="relative z-10 shrink-0" />
                {!collapsed ? (
                  <>
                    <span className="relative z-10 flex-1 truncate text-sm font-medium">{item.label}</span>
                    <Kbd className="relative z-10">{item.shortcut}</Kbd>
                  </>
                ) : null}
              </motion.div>
            )}
          </NavLink>
        ))}
      </nav>

      {/* subject + role readout — deliberately not an auth claim */}
      <div className={cn('border-t border-hairline p-2', collapsed && 'px-1')}>
        {!collapsed ? (
          <div className="rounded-md border border-hairline bg-base px-2.5 py-2">
            <div className="microlabel">Active subject</div>
            <div className="tnum mt-0.5 truncate text-xs text-ink">{subjectId}</div>
            <div className="mt-1.5 flex items-center justify-between gap-1">
              <span className="text-[10px] text-ink-muted">{ROLE_LABEL[role]}</span>
              <span className="tnum text-[10px] text-ink-faint">{frame ? `${frame.t_s.toFixed(0)}s` : 'idle'}</span>
            </div>
          </div>
        ) : (
          <div className="flex justify-center py-1">
            <ScrollText size={14} strokeWidth={1.75} className="text-ink-faint" />
          </div>
        )}
        <button
          type="button"
          onClick={onToggle}
          aria-label={collapsed ? 'Expand navigation' : 'Collapse navigation'}
          className={cn(
            'mt-1.5 flex h-7 w-full items-center gap-2 rounded-md px-2 text-ink-muted',
            'transition-colors hover:bg-white/[0.03] hover:text-ink', collapsed && 'justify-center px-0',
          )}
        >
          {collapsed ? <ChevronsRight size={14} strokeWidth={1.75} /> : <ChevronsLeft size={14} strokeWidth={1.75} />}
          {!collapsed ? <span className="text-xs">Collapse</span> : null}
        </button>
      </div>
    </motion.aside>
  );
}
