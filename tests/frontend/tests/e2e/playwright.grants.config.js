/**
 * Playwright config for grants example app E2E tests.
 *
 * Uses an isolated test database via NTT_SQLITE_DB env var.
 * The global setup seeds the DB, the webServer launches the grants app against it.
 */
import { defineConfig } from '@playwright/test';
import { join } from 'path';
import { tmpdir } from 'os';
import { FRONTEND_ROOT } from './paths.js';

const GRANTS_MARKER = process.env.__NTT_E2E_MARKER || join(tmpdir(), 'ntx-grants-e2e-dbpath.txt');
process.env.__NTT_E2E_MARKER = GRANTS_MARKER;

export default defineConfig({
  testDir: '.',
  testMatch: 'grants-*.spec.js',
  globalTeardown: './grants-global-teardown.js',
  timeout: 30000,
  expect: { timeout: 10000 },
  fullyParallel: false,
  workers: 1,
  reporter: 'list',
  use: {
    baseURL: 'http://localhost:5000',
    trace: 'on-first-retry',
    screenshot: 'only-on-failure',
  },
  projects: [
    {
      name: 'chromium',
      use: {
        browserName: 'chromium',
        viewport: { width: 1280, height: 720 },
      },
    },
  ],
  webServer: {
    command: 'node tests/e2e/start-e2e-app.js grants',
    cwd: FRONTEND_ROOT,
    env: {
      ...process.env,
      __NTT_E2E_MARKER: GRANTS_MARKER,
    },
    url: 'http://localhost:5000/Grant',
    reuseExistingServer: process.env.N3TX_E2E_REUSE_SERVER === '1',
    timeout: 30000,
    stdout: 'ignore',
    stderr: 'pipe',
  },
});
