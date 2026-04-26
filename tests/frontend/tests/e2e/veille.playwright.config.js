// @ts-check
import { defineConfig } from '@playwright/test';
import { existsSync } from 'fs';

const PYTHONPATH = [
  '/workspace/packages/n3tx-core/src',
  '/workspace/packages/n3tx-ui/src',
  '/workspace/packages/n3tx-actors/src',
  '/workspace/packages/n3tx-agents/src',
].join(':');
const PYTHON_BIN = existsSync('/workspace/.venv-e2e/bin/python')
  ? '/workspace/.venv-e2e/bin/python'
  : 'python3';

export default defineConfig({
  testDir: '.',
  testMatch: '**/veille-*.spec.js',
  globalSetup: './veille.global-setup.js',
  globalTeardown: './veille.global-teardown.js',
  timeout: 30000,
  expect: {
    timeout: 10000,
  },
  fullyParallel: false,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  workers: 1,
  reporter: 'list',
  use: {
    baseURL: 'http://localhost:5010',
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
    command: `${PYTHON_BIN} main.py`,
    cwd: '/workspace/apps/veille',
    env: {
      ...process.env,
      PYTHONPATH,
      N3TX_PORT: '5010',
      N3TX_API_URL: 'http://localhost:5010',
      N3TX_CHAT_LLM: 'test',
    },
    url: 'http://localhost:5010/login.html',
    reuseExistingServer: !process.env.CI,
    timeout: 60000,
    stdout: 'ignore',
    stderr: 'pipe',
  },
});
