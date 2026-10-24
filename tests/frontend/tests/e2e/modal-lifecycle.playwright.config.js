import { defineConfig } from '@playwright/test';
import { join } from 'node:path';
import { tmpdir } from 'node:os';

// Deliberately serverless: the spec intercepts every request and serves only
// synthetic HTML and the checked-out modal's two assets. No app fixture or DB.
export default defineConfig({
  testDir: '.',
  testMatch: 'modal-lifecycle.spec.js',
  workers: 1,
  retries: 0,
  timeout: 15000,
  expect: { timeout: 1200 },
  outputDir: process.env.MODAL_LIFECYCLE_OUTPUT_DIR ||
    join(tmpdir(), `n3tx-modal-lifecycle-${Date.now()}-${process.pid}`),
  reporter: 'list',
  use: {
    browserName: 'chromium',
    viewport: { width: 900, height: 700 },
    trace: 'on',
    screenshot: 'only-on-failure',
    serviceWorkers: 'block',
  },
});
