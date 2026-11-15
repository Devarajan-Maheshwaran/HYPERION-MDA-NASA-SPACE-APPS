import type { OrganReading } from '../lib/types';
import { organTone } from '../lib/clinical';
import { cn } from '../lib/utils';

const NODES: Record<string, { x: number; y: number }> = {
  'head-eyes': { x: 180, y: 54 },
  heart: { x: 193, y: 142 },
  'chest-immune': { x: 166, y: 160 },
  metabolic: { x: 180, y: 218 },
  bones: { x: 151, y: 302 },
  brain: { x: 180, y: 34 },
};

const COLORS = { nominal: '#10B981', watch: '#F59E0B', critical: '#EF4444', neutral: '#94A3B8' } as const;

export function BodyMap({ organs, selected, onSelect }: {
  organs: OrganReading[]; selected: string; onSelect: (system: string) => void;
}) {
  return (
    <div className="relative mx-auto w-full max-w-[360px]" aria-label="Six organ systems">
      <svg viewBox="0 0 360 420" className="w-full" role="img" aria-label="Medical illustration of the human body with six selectable organ systems">
        <defs>
          <linearGradient id="body-fill" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="#FFFFFF" />
            <stop offset="100%" stopColor="#F8FAFC" />
          </linearGradient>
        </defs>
        {/* Front-facing anatomical outline, deliberately monochrome. */}
        <g fill="url(#body-fill)" stroke="#CBD5E1" strokeWidth="1.5" strokeLinejoin="round">
          <ellipse cx="180" cy="48" rx="27" ry="33" />
          <path d="M168 79 L168 96 C150 101 137 108 132 121 L120 176 L113 236 C112 244 116 250 122 250 C128 250 132 245 133 238 L141 187 L148 158 L146 226 C145 244 148 258 153 270 L150 338 L146 390 C145 399 150 405 158 405 C166 405 171 400 172 392 L180 330 L188 392 C189 400 194 405 202 405 C210 405 215 399 214 390 L210 338 L207 270 C212 258 215 244 214 226 L212 158 L219 187 L227 238 C228 245 232 250 238 250 C244 250 248 244 247 236 L240 176 L228 121 C223 108 210 101 192 96 L192 79" />
        </g>
        {/* Minimal internal landmarks. */}
        <g fill="none" stroke="#E2E8F0" strokeWidth="1.2">
          <path d="M158 128 C165 122 174 122 180 128 C186 122 195 122 202 128" />
          <path d="M155 138 C160 132 172 132 178 140 M182 140 C188 132 200 132 205 138" />
          <path d="M180 128 L180 248" strokeDasharray="3 4" />
          <path d="M158 205 C166 198 194 198 202 205 C206 216 198 232 180 234 C162 232 154 216 158 205Z" />
          <path d="M160 262 C170 268 190 268 200 262" />
          <path d="M163 285 L160 330 M197 285 L200 330" />
          <circle cx="171" cy="47" r="3" /><circle cx="189" cy="47" r="3" />
          <path d="M172 62 C177 65 183 65 188 62" />
        </g>
        {organs.map((organ) => {
          const node = NODES[organ.system];
          if (!node) return null;
          const active = selected === organ.system;
          const color = COLORS[organTone(organ.status)];
          return (
            <g
              key={organ.system}
              role="button"
              tabIndex={0}
              aria-label={`${organ.label}: ${organ.status}`}
              aria-pressed={active}
              className="cursor-pointer outline-none"
              onClick={() => onSelect(organ.system)}
              onKeyDown={(event) => {
                if (event.key === 'Enter' || event.key === ' ') {
                  event.preventDefault();
                  onSelect(organ.system);
                }
              }}
            >
              <title>{organ.label} · {organ.status}</title>
              {active ? (
                <circle cx={node.x} cy={node.y} r="10" fill="none" stroke={color} strokeWidth="1.5" className="animate-pulse-ring" style={{ transformOrigin: `${node.x}px ${node.y}px` }} />
              ) : null}
              <circle cx={node.x} cy={node.y} r={active ? 8 : 6.5} fill="#FFFFFF" stroke={color} strokeWidth={active ? 2 : 1.5} />
              <circle cx={node.x} cy={node.y} r={active ? 3.5 : 2.5} fill={color} />
              <circle cx={node.x} cy={node.y} r="16" fill="transparent" />
            </g>
          );
        })}
      </svg>
      <div className="mt-1 grid grid-cols-2 gap-1.5">
        {organs.map((organ) => {
          const active = selected === organ.system;
          return (
            <button
              key={organ.system}
              type="button"
              aria-pressed={active}
              onClick={() => onSelect(organ.system)}
              className={cn(
                'flex items-center gap-2 rounded-md border px-2.5 py-1.5 text-left text-2xs font-medium transition-colors',
                active ? 'border-line-strong bg-page text-ink' : 'border-transparent text-ink-subtle hover:bg-page',
              )}
            >
              <span className="h-1.5 w-1.5 shrink-0 rounded-full" style={{ backgroundColor: COLORS[organTone(organ.status)] }} aria-hidden />
              {organ.label}
            </button>
          );
        })}
      </div>
    </div>
  );
}
