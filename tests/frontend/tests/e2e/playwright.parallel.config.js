// @ts-check
import { defineConfig } from '@playwright/test';
import baseConfig from './playwright.config.js';

process.env.N3TX_E2E_PARALLEL = '1';

export default defineConfig({
  ...baseConfig,
  globalTeardown: undefined,
  webServer: undefined,
  fullyParallel: true,
  workers: process.env.N3TX_E2E_PARALLEL_WORKERS
    ? Number(process.env.N3TX_E2E_PARALLEL_WORKERS)
    : 2,
  use: {
    ...baseConfig.use,
    // The parallel fixture replaces this per worker with an isolated port.
    baseURL: `http://localhost:${process.env.N3TX_E2E_PARALLEL_BASE_PORT || 5100}`,
  },
  testIgnore: [
    '**/grants-create-validation.spec.js',
    '**/performance.spec.js',
    '**/veille-chat*.spec.js',
  ],
});
