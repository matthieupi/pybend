/**
 * Playwright global setup — creates and seeds an isolated test database.
 *
 * Sets N3TX_SQLITE_DB to a temp file so the server launched by
 * playwright.config.js never touches the production database.
 */
import { execFileSync } from 'child_process';
import { mkdtempSync, writeFileSync } from 'fs';
import { join } from 'path';
import { tmpdir } from 'os';
import { PYTHON_BIN, PYTHONPATH, repoPath } from './paths.js';

const EXAMPLE_DIR = repoPath('examples/core');

export default async function globalSetup() {
  // Create a temp directory for the E2E test database
  const dir = mkdtempSync(join(tmpdir(), 'ntx-e2e-'));
  const dbPath = join(dir, 'test.db');

  // Store paths so globalTeardown can clean up and webServer can use them
  process.env.N3TX_SQLITE_DB = dbPath;
  process.env.__NTT_E2E_TMPDIR = dir;

  // Write a marker file so the webServer process (separate process) picks up
  // the DB path — Playwright passes env to the webServer command automatically.
  // We also write the path to a well-known file that globalTeardown can read.
  const runId = process.env.PLAYWRIGHT_RUN_ID || `${process.pid}-${Date.now()}`;
  const markerPath = process.env.__NTT_E2E_MARKER || join(tmpdir(), `ntx-e2e-dbpath-${runId}.txt`);
  writeFileSync(markerPath, dbPath);
  process.env.__NTT_E2E_MARKER = markerPath;

  // Seed the test database by running the seed script with the test DB
  console.log(`[E2E setup] Creating test DB: ${dbPath}`);
  execFileSync(
    PYTHON_BIN,
    ['seed.py'],
    {
      cwd: EXAMPLE_DIR,
      stdio: 'pipe',
      timeout: 30000,
      env: { ...process.env, PYTHONPATH, N3TX_SQLITE_DB: dbPath },
    }
  );
  console.log('[E2E setup] Test DB seeded successfully');
}
