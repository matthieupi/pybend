// @ts-check
import { defineConfig } from '@playwright/test';
import { join } from 'path';
import { tmpdir } from 'os';
import { FRONTEND_ROOT, REPO_ROOT } from './paths.js';

const PROFILING_DIR = join(REPO_ROOT, '.traces', '.profiling');
const PERF_MARKER = process.env.__NTT_E2E_MARKER || join(tmpdir(), 'ntx-e2e-dbpath.txt');

process.env.__NTT_E2E_MARKER = PERF_MARKER;
process.env.NTT_PROFILING_DIR = process.env.NTT_PROFILING_DIR || PROFILING_DIR;

export default defineConfig({
  testDir: '.',
  testMatch: 'performance.spec.js',
  globalTeardown: './global-teardown.js',
  timeout: 120000,
  expect: {
    timeout: 15000,
  },
  fullyParallel: false,
  forbidOnly: !!process.env.CI,
  retries: 0,
  workers: 1,
  reporter: 'list',
  use: {
    baseURL: 'http://localhost:5099',
    trace: 'off',
    screenshot: 'off',
    video: 'off',
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
    command: 'node tests/e2e/start-e2e-app.js perf',
    cwd: FRONTEND_ROOT,
    env: {
      ...process.env,
      __NTT_E2E_MARKER: PERF_MARKER,
      NTT_PROFILING_DIR: PROFILING_DIR,
    },
    url: 'http://localhost:5099/Product',
    reuseExistingServer: process.env.N3TX_E2E_REUSE_SERVER === '1',
    timeout: 30000,
    stdout: 'ignore',
    stderr: 'pipe',
  },
});
