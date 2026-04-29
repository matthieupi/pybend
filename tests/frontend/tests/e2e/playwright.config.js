// @ts-check
import { defineConfig } from '@playwright/test';
import { join } from 'path';
import { tmpdir } from 'os';
import { FRONTEND_ROOT } from './paths.js';

const RUN_ID = process.env.PLAYWRIGHT_RUN_ID || `${process.pid}-${Date.now()}`;
const E2E_MARKER = process.env.__NTT_E2E_MARKER || join(tmpdir(), `ntx-e2e-dbpath-${RUN_ID}.txt`);

process.env.__NTT_E2E_MARKER = E2E_MARKER;

export default defineConfig({
  testDir: '.',
  testMatch: '**/*.spec.js',
  globalTeardown: './global-teardown.js',
  timeout: 60000,
  expect: {
    timeout: 10000,
  },
  fullyParallel: false,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  workers: 1,
  reporter: 'list',
  use: {
    baseURL: 'http://localhost:5000',
    trace: 'on-first-retry',
    screenshot: 'only-on-failure',
    video: 'retain-on-failure',
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
    command: 'node tests/e2e/start-e2e-app.js core',
    cwd: FRONTEND_ROOT,
    env: {
      ...process.env,
      __NTT_E2E_MARKER: E2E_MARKER,
    },
    url: 'http://localhost:5000/Product',
    reuseExistingServer: process.env.N3TX_E2E_REUSE_SERVER === '1',
    timeout: 120000,
    stdout: 'ignore',
    stderr: 'pipe',
  },
});
