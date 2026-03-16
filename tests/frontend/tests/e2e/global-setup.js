/**
 * Playwright global setup — creates and seeds an isolated test database.
 *
 * Sets NTT_SQLITE_DB to a temp file so the server launched by
 * playwright.config.js never touches the production database.
 */
import { execSync } from 'child_process';
import { mkdtempSync, writeFileSync } from 'fs';
import { join } from 'path';
import { tmpdir } from 'os';

const EXAMPLE_DIR = '/workspace/example_api';

export default async function globalSetup() {
  // Create a temp directory for the E2E test database
  const dir = mkdtempSync(join(tmpdir(), 'ntx-e2e-'));
  const dbPath = join(dir, 'test.db');

  // Store paths so globalTeardown can clean up and webServer can use them
  process.env.NTT_SQLITE_DB = dbPath;
  process.env.__NTT_E2E_TMPDIR = dir;

  // Write a marker file so the webServer process (separate process) picks up
  // the DB path — Playwright passes env to the webServer command automatically.
  // We also write the path to a well-known file that globalTeardown can read.
  const markerPath = join(tmpdir(), 'ntx-e2e-dbpath.txt');
  writeFileSync(markerPath, dbPath);
  process.env.__NTT_E2E_MARKER = markerPath;

  // Seed the test database by running the seed script with the test DB
  console.log(`[E2E setup] Creating test DB: ${dbPath}`);
  execSync(
    `cd ${EXAMPLE_DIR} && NTT_SQLITE_DB="${dbPath}" python3 seed.py`,
    { stdio: 'pipe', timeout: 30000 }
  );
  console.log('[E2E setup] Test DB seeded successfully');
}
