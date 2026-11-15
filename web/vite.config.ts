import { defineConfig } from 'vitest/config';
import react from '@vitejs/plugin-react';

// The browser must never call localhost directly: it uses relative /api URLs and this
// dev server proxies them to the backend. In production the API serves the built SPA.
export default defineConfig({
  plugins: [react()],
  server: {
    host: '0.0.0.0',
    port: 5173,
    strictPort: true,
    // The Arena live preview proxies under https://{port}-{sandbox}.e2b.app
    allowedHosts: ['.e2b.app', 'localhost', '127.0.0.1'],
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
        // SSE must not be buffered by the proxy.
        configure: (proxy) => {
          proxy.on('proxyRes', (proxyRes) => {
            if (proxyRes.headers['content-type']?.includes('text/event-stream')) {
              proxyRes.headers['cache-control'] = 'no-cache, no-transform';
            }
          });
        },
      },
    },
  },
  preview: { host: '0.0.0.0', port: 4173, allowedHosts: ['.e2b.app'] },
  build: {
    outDir: 'dist',
    sourcemap: false,
    rollupOptions: {
      output: {
        manualChunks: {
          react: ['react', 'react-dom', 'react-router-dom'],
          charts: ['recharts'],
        },
      },
    },
  },
  test: { environment: 'node', include: ['src/**/*.test.ts', 'src/**/*.test.tsx'], setupFiles: ['./src/test/setup.ts'] },
});
