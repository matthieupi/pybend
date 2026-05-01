// @ts-check
import { defineConfig } from '@playwright/test';
import baseConfig from './playwright.config.js';

const FAST_SPECS = [
  'tests/e2e/accessibility-unit.spec.js',
  'tests/e2e/authentication.spec.js',
  'tests/e2e/css-and-theming-unit.spec.js',
  'tests/e2e/page-load.spec.js',
  'tests/e2e/product-detail.spec.js',
  'tests/e2e/product-list.spec.js',
  'tests/e2e/route-grammar-smoke.spec.js',
  'tests/e2e/responsive-display.spec.js',
  'tests/e2e/visual-regression.spec.js',
];

export default defineConfig({
  ...baseConfig,
  testMatch: FAST_SPECS,
  // Keep tests within a spec file serial. Parallelism is across selected files,
  // which avoids intra-file assumptions around router/history ordering while
  // still letting the read-only smoke lane use multiple workers.
  fullyParallel: false,
  workers: process.env.N3TX_E2E_FAST_WORKERS
    ? Number(process.env.N3TX_E2E_FAST_WORKERS)
    : process.env.CI ? 2 : 4,
});
