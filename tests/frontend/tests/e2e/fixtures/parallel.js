import { test as base, expect } from '@playwright/test';
import { execFileSync, spawn } from 'child_process';
import { mkdtempSync, rmSync } from 'fs';
import { join } from 'path';
import { tmpdir } from 'os';
import { scheduler } from 'node:timers/promises';
import { PYTHON_BIN, PYTHONPATH, REPO_ROOT, repoPath } from '../paths.js';

const PARALLEL_ENABLED = process.env.N3TX_E2E_PARALLEL === '1';
const BASE_PORT = Number(process.env.N3TX_E2E_PARALLEL_BASE_PORT || 5100);

async function waitForServer(baseURL, timeoutMs = 30000) {
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    try {
      const resp = await fetch(`${baseURL}/Product`);
      if (resp.ok) return;
    } catch {
      // Server not ready yet.
    }
    await scheduler.wait(250);
  }
  throw new Error(`Parallel E2E server not ready: ${baseURL}`);
}

async function stopProcess(child) {
  if (!child || child.killed) return;
  let exited = false;
  const exitedPromise = new Promise((resolve) => child.once('exit', () => {
    exited = true;
    resolve();
  }));

  child.kill('SIGTERM');
  await Promise.race([
    exitedPromise,
    scheduler.wait(5000).then(() => {
      if (!exited) child.kill('SIGKILL');
    }),
  ]);
}

export const test = base.extend({
  parallelServer: [async ({}, use, workerInfo) => {
    if (!PARALLEL_ENABLED) {
      await use(null);
      return;
    }

    const port = BASE_PORT + workerInfo.parallelIndex;
    const baseURL = `http://localhost:${port}`;
    const appDir = repoPath('examples/core');
    const tmpDir = mkdtempSync(join(tmpdir(), `ntx-e2e-parallel-${workerInfo.parallelIndex}-`));
    const dbPath = join(tmpDir, 'test.db');
    const profilingDir = process.env.NTT_PROFILING_DIR || join(REPO_ROOT, '.traces/.profiling');
    const env = {
      ...process.env,
      PYTHONPATH,
      N3TX_SQLITE_DB: dbPath,
      NTT_SQLITE_DB: dbPath,
      N3TX_PORT: String(port),
      NTT_PORT: String(port),
      N3TX_API_URL: baseURL,
      N3TX_DEBUG: 'false',
      NTT_PROFILING_DIR: profilingDir,
    };

    execFileSync(PYTHON_BIN, ['seed.py', '--reset'], {
      cwd: appDir,
      env,
      stdio: 'pipe',
      timeout: 30000,
    });

    const child = spawn(PYTHON_BIN, ['main.py'], {
      cwd: appDir,
      env,
      stdio: ['ignore', 'ignore', 'pipe'],
    });

    child.stderr.on('data', (chunk) => {
      if (process.env.N3TX_E2E_PARALLEL_DEBUG === '1') {
        process.stderr.write(`[parallel:${workerInfo.parallelIndex}] ${chunk}`);
      }
    });

    try {
      await waitForServer(baseURL);
      await use({ baseURL, port, dbPath });
    } finally {
      await stopProcess(child);
      rmSync(tmpDir, { recursive: true, force: true });
    }
  }, { scope: 'worker', auto: true }],

  baseURL: async ({ baseURL, parallelServer }, use) => {
    await use(parallelServer?.baseURL || baseURL);
  },
});

export { expect };
