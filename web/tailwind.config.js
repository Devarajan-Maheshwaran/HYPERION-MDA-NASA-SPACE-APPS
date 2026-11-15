/** Swiss Clinical Minimalist design system — light theme only.
 *  90% neutral (white / slate / black). Colour is reserved for semantic clinical state.
 *  @type {import('tailwindcss').Config}
 */
export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        // Neutral foundation.
        page: '#F8FAFC',
        card: '#FFFFFF',
        line: '#E2E8F0',
        'line-strong': '#CBD5E1',
        ink: {
          DEFAULT: '#0F172A', // headings
          body: '#475569', // body copy
          label: '#94A3B8', // micro labels
          subtle: '#64748B',
        },
        // Interactive primary only.
        primary: {
          DEFAULT: '#0F172A',
          hover: '#1E293B',
          blue: '#2563EB',
          'blue-hover': '#1D4ED8',
          'blue-soft': '#EFF6FF',
        },
        // Semantic clinical states. Nothing else in the UI may use these hues.
        nominal: { DEFAULT: '#10B981', soft: '#ECFDF5', text: '#065F46' },
        watch: { DEFAULT: '#F59E0B', soft: '#FFFBEB', text: '#92400E' },
        critical: { DEFAULT: '#EF4444', soft: '#FEF2F2', text: '#991B1B' },
        neutral: { DEFAULT: '#94A3B8', soft: '#F1F5F9', text: '#475569' },
      },
      fontFamily: {
        sans: ['Inter', 'ui-sans-serif', 'system-ui', '-apple-system', 'Segoe UI', 'sans-serif'],
        mono: ['"JetBrains Mono"', 'ui-monospace', 'SFMono-Regular', 'monospace'],
      },
      fontSize: {
        '2xs': ['11px', { lineHeight: '16px' }],
        xs: ['12px', { lineHeight: '18px' }],
        sm: ['13px', { lineHeight: '20px' }],
        base: ['14px', { lineHeight: '22px' }],
        md: ['15px', { lineHeight: '24px' }],
        lg: ['16px', { lineHeight: '26px' }],
        xl: ['18px', { lineHeight: '28px', letterSpacing: '-0.01em' }],
        '2xl': ['22px', { lineHeight: '30px', letterSpacing: '-0.02em' }],
        '3xl': ['28px', { lineHeight: '36px', letterSpacing: '-0.02em' }],
        hero: ['36px', { lineHeight: '44px', letterSpacing: '-0.03em' }],
      },
      boxShadow: {
        card: '0 1px 3px rgba(15, 23, 42, 0.04)',
        raised: '0 4px 16px rgba(15, 23, 42, 0.06)',
        popover: '0 12px 32px rgba(15, 23, 42, 0.10)',
      },
      borderRadius: { DEFAULT: '8px', lg: '10px', xl: '12px', '2xl': '16px' },
      maxWidth: { content: '1280px', prose: '680px' },
      transitionTimingFunction: { clinical: 'cubic-bezier(0.16, 1, 0.3, 1)' },
      keyframes: {
        'pulse-ring': {
          '0%': { transform: 'scale(0.85)', opacity: '0.55' },
          '70%': { transform: 'scale(1.9)', opacity: '0' },
          '100%': { transform: 'scale(1.9)', opacity: '0' },
        },
        'gate-sweep': {
          '0%': { boxShadow: '0 0 0 0 rgba(37, 99, 235, 0.28)' },
          '100%': { boxShadow: '0 0 0 10px rgba(37, 99, 235, 0)' },
        },
      },
      animation: {
        'pulse-ring': 'pulse-ring 1800ms cubic-bezier(0.16, 1, 0.3, 1) infinite',
        'gate-sweep': 'gate-sweep 450ms cubic-bezier(0.16, 1, 0.3, 1)',
      },
    },
  },
  plugins: [],
};
