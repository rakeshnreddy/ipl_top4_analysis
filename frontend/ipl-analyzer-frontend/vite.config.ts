import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import { configDefaults } from 'vitest/config';
import { sitemapPlugin } from './build/sitemap';

// https://vitejs.dev/config/
export default defineConfig({
  base: '/',
  // SITE_URL (the deployed address) turns on sitemap.xml.
  plugins: [react(), sitemapPlugin(process.env.SITE_URL)],
  build: {
    rollupOptions: {
      // Two pages: the standings site and the separate social share kit.
      input: {
        main: 'index.html',
        share: 'share.html',
      },
    },
  },
  test: {
    globals: true,
    environment: 'jsdom',
    setupFiles: './src/setupTests.ts',
    exclude: [
      ...configDefaults.exclude,
      'e2e/**',
    ],
    coverage: {
      provider: 'v8',
      reporter: ['text', 'json', 'html'],
    },
  },
});
