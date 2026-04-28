#!/usr/bin/env node
// Shared Playwright webServer launcher.
//
// Playwright may start webServer before globalSetup, so the isolated test DB
// must be created and seeded inside the server command itself. This keeps app
// startup deterministic and gives teardown a marker file to clean up.
import { spawn, execFileSync } from 'child_process';
import { existsSync, mkdtempSync, writeFileSync } from 'fs';
import { join } from 'path';
import { tmpdir } from 'os';
import { PYTHON_BIN, PYTHONPATH, REPO_ROOT, repoPath } from './paths.js';

const APPS = {
  core: {
    dir: repoPath('examples/core'),
    dbName: 'test.db',
    tmpPrefix: 'ntx-e2e-',
    markerEnv: '__NTT_E2E_MARKER',
    defaultMarker: 'ntx-e2e-dbpath.txt',
    port: '5000',
    resetArg: '--reset',
  },
  grants: {
    dir: repoPath('examples/grants'),
    dbName: 'test_grants.db',
    tmpPrefix: 'ntx-grants-e2e-',
    markerEnv: '__NTT_E2E_MARKER',
    defaultMarker: 'ntx-grants-e2e-dbpath.txt',
    port: '5000',
    resetArg: '--reset',
  },
  veille: {
    dir: repoPath('apps/veille'),
    dbName: 'veille-test.db',
    tmpPrefix: 'ntx-veille-e2e-',
    markerEnv: '__NTX_VEILLE_E2E_MARKER',
    defaultMarker: 'ntx-veille-e2e-dbpath.txt',
    port: '5010',
    resetArg: '--reset',
    extraEnv: { N3TX_CHAT_LLM: 'test' },
  },
  perf: {
    dir: repoPath('examples/core'),
    dbName: 'perf.db',
    tmpPrefix: 'ntx-perf-',
    markerEnv: '__NTT_E2E_MARKER',
    defaultMarker: 'ntx-e2e-dbpath.txt',
    port: '5099',
    resetArg: '--reset',
    extraEnv: { NTT_PROFILING: '1' },
  },
};

const appName = process.argv[2];
const app = APPS[appName];

if (!app) {
  console.error(`Usage: node tests/e2e/start-e2e-app.js ${Object.keys(APPS).join('|')}`);
  process.exit(2);
}

if (!existsSync(app.dir)) {
  console.error(`[E2E] App directory does not exist: ${app.dir}`);
  process.exit(2);
}

const tmpDir = mkdtempSync(join(tmpdir(), app.tmpPrefix));
const dbPath = join(tmpDir, app.dbName);
const markerPath = process.env[app.markerEnv] || join(tmpdir(), app.defaultMarker);
const profilingDir = process.env.NTT_PROFILING_DIR || join(REPO_ROOT, '.traces/.profiling');

writeFileSync(markerPath, dbPath);

const env = {
  ...process.env,
  PYTHONPATH,
  N3TX_SQLITE_DB: dbPath,
  NTT_SQLITE_DB: dbPath,
  N3TX_PORT: app.port,
  NTT_PORT: app.port,
  N3TX_API_URL: `http://localhost:${app.port}`,
  [app.markerEnv]: markerPath,
  NTT_PROFILING_DIR: profilingDir,
  ...(app.extraEnv || {}),
};

console.error(`[E2E] Seeding ${appName} database: ${dbPath}`);
execFileSync(PYTHON_BIN, ['seed.py', app.resetArg].filter(Boolean), {
  cwd: app.dir,
  env,
  stdio: 'pipe',
  timeout: appName === 'perf' ? 60000 : 30000,
});

console.error(`[E2E] Starting ${appName} app on port ${app.port}`);
const child = spawn(PYTHON_BIN, ['main.py'], {
  cwd: app.dir,
  env,
  stdio: 'inherit',
});

const forward = (signal) => {
  if (!child.killed) child.kill(signal);
};

process.on('SIGTERM', () => forward('SIGTERM'));
process.on('SIGINT', () => forward('SIGINT'));

child.on('exit', (code, signal) => {
  if (signal) process.kill(process.pid, signal);
  process.exit(code ?? 0);
});
