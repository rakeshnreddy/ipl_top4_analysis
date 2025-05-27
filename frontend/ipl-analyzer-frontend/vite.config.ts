import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import { configDefaults } from 'vitest/config'; // Import configDefaults

// https://vitejs.dev/config/
export default defineConfig({
  base: '/ipl-analyser/',
  plugins: [react()],
  test: {
    globals: true, // Optional: to use Vitest globals like describe, it, expect without importing
    environment: 'jsdom', // To simulate a browser environment for React components later
    setupFiles: './src/setupTests.ts', // Optional: if you need global test setup
    exclude: [ // Ensure Vitest doesn't try to run tests in node_modules etc.
        ...configDefaults.exclude, 
        'e2e/**' // if you have e2e tests in a separate folder
    ],
    coverage: { // Optional: basic coverage setup
        provider: 'v8',
        reporter: ['text', 'json', 'html'],
    },
  },
});
