/**
 * Playwright config for grants example app E2E tests.
 *
 * Uses an isolated test database via PYBEND_SQLITE_DB env var.
 * The global setup seeds the DB, the webServer launches the grants app against it.
 */
import { defineConfig } from '@playwright/test';

export default defineConfig({
  testDir: '.',
  testMatch: 'grants-*.spec.js',
  globalSetup: './grants-global-setup.js',
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
    command: 'cd /workspace/src/pybend/example_grants && python3 main.py',
    url: 'http://localhost:5000/Grant',
    reuseExistingServer: !process.env.CI,
    timeout: 30000,
    stdout: 'ignore',
    stderr: 'pipe',
  },
});
