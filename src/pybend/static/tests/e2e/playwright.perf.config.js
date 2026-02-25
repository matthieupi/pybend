// @ts-check
import { defineConfig } from '@playwright/test';
import { resolve, dirname } from 'path';
import { fileURLToPath } from 'url';

const __dirname = dirname(fileURLToPath(import.meta.url));
const WORKSPACE = resolve(__dirname, '..', '..', '..', '..', '..');
const EXAMPLE_DIR = resolve(WORKSPACE, 'src', 'pybend', 'example');
const PROFILING_DIR = resolve(WORKSPACE, '.profiling');

export default defineConfig({
  testDir: '.',
  testMatch: 'performance.spec.js',
  globalSetup: './perf-global-setup.js',
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
    command: `cd "${EXAMPLE_DIR}" && PYBEND_PROFILING=1 PYBEND_PROFILING_DIR="${PROFILING_DIR}" PYBEND_PORT=5099 python3 main.py`,
    url: 'http://localhost:5099/Product',
    reuseExistingServer: !process.env.CI,
    timeout: 30000,
    stdout: 'ignore',
    stderr: 'pipe',
  },
});
