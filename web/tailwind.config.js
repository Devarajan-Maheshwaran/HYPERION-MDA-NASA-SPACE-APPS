/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        // Status palette. UNKNOWN / STALE / NOT_AVAILABLE / FAILED are deliberately
        // neutral-grey, never green. See docs/SAFETY_ISSUES.md S7.
        ink: { 900: '#0b1220', 800: '#111a2b', 700: '#18233a', 600: '#22304d' },
        nominal: '#22c55e',
        watch: '#f59e0b',
        alert: '#ef4444',
        unknown: '#64748b',
        lab: '#38bdf8',
        simulated: '#a78bfa',
        injected: '#fb7185',
        recorded: '#34d399',
      },
      fontFamily: {
        mono: ['ui-monospace', 'SFMono-Regular', 'Menlo', 'monospace'],
      },
    },
  },
  plugins: [],
};
