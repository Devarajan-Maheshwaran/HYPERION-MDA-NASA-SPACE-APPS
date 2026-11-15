/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        // Swiss-industrial base. No gradients, no glows.
        base: '#0B0C0E',
        surface: {
          DEFAULT: '#13151A',
          2: '#181B21',
          3: '#1E222A',
        },
        hairline: 'rgba(255,255,255,0.07)',
        'hairline-strong': 'rgba(255,255,255,0.12)',
        // One functional accent. Primary actions and active states only.
        accent: {
          DEFAULT: '#F59E0B',
          hover: '#FBBF24',
          dim: 'rgba(245,158,11,0.12)',
        },
        ink: {
          DEFAULT: '#E7E9EC',
          secondary: '#9CA3AC',
          muted: '#6B7280',
          faint: '#4B5158',
        },
        // Semantic instrument states. Distinct from the accent hue.
        state: {
          ok: '#3FB950',
          watch: '#DB6D28',
          alert: '#F85149',
          unknown: '#6E7681',
          info: '#58A6FF',
        },
      },
      fontFamily: {
        sans: ['"Plus Jakarta Sans"', 'ui-sans-serif', 'system-ui', 'sans-serif'],
        mono: ['"JetBrains Mono"', 'ui-monospace', 'SFMono-Regular', 'monospace'],
      },
      fontSize: {
        '2xs': ['10px', { lineHeight: '14px', letterSpacing: '0.04em' }],
        xs: ['11px', { lineHeight: '16px' }],
        sm: ['12px', { lineHeight: '18px' }],
        base: ['13px', { lineHeight: '20px' }],
        lg: ['15px', { lineHeight: '22px' }],
        xl: ['18px', { lineHeight: '24px', letterSpacing: '-0.01em' }],
        '2xl': ['22px', { lineHeight: '28px', letterSpacing: '-0.02em' }],
        '3xl': ['28px', { lineHeight: '34px', letterSpacing: '-0.02em' }],
      },
      borderRadius: { DEFAULT: '6px', md: '6px', lg: '8px', xl: '10px' },
      transitionTimingFunction: { crisp: 'cubic-bezier(0.16, 1, 0.3, 1)' },
      keyframes: {
        shimmer: { '100%': { transform: 'translateX(100%)' } },
        'pulse-dot': { '0%,100%': { opacity: '1' }, '50%': { opacity: '0.35' } },
      },
      animation: {
        shimmer: 'shimmer 1.6s infinite',
        'pulse-dot': 'pulse-dot 2s cubic-bezier(0.4,0,0.6,1) infinite',
      },
    },
  },
  plugins: [],
};
