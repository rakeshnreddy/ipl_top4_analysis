import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import { configDefaults } from 'vitest/config';
import { sitemapPlugin } from './build/sitemap';
import { sharePreloadsPlugin } from './build/share-preloads';
import { leaguePagesPlugin } from './build/league-pages';
import { liveCricketEntryPlugin } from './build/live-cricket';
import { trustPagesPlugin } from './build/trust-pages';
import { siteSeoPlugin } from './build/site-seo';

// https://vitejs.dev/config/
export default defineConfig({
  base: '/',
  // SITE_URL (the deployed address) turns on sitemap.xml.
  plugins: [react(), sitemapPlugin(process.env.SITE_URL), sharePreloadsPlugin(), leaguePagesPlugin(process.env.SITE_URL), liveCricketEntryPlugin(process.env.SITE_URL), trustPagesPlugin(), siteSeoPlugin()],
  build: {
    rollupOptions: {
      // Static entries for season forecasts, the share kit, and live cricket.
      input: {
        main: 'index.html',
        share: 'share.html',
        cricket: 'cricket/index.html',
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
