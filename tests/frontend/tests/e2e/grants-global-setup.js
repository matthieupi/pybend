/**
 * Playwright global setup for grants e2e tests.
 *
 * Creates an isolated temp database, seeds it with grants test data,
 * and stores the path so the webServer process picks it up.
 */
import { execFileSync } from 'child_process';
import { mkdtempSync, writeFileSync } from 'fs';
import { join } from 'path';
import { tmpdir } from 'os';
import { PYTHON_BIN, repoPath } from './paths.js';

const GRANTS_DIR = repoPath('examples/grants');

export default async function globalSetup() {
  const dir = mkdtempSync(join(tmpdir(), 'ntx-grants-e2e-'));
  const dbPath = join(dir, 'test_grants.db');

  process.env.NTT_SQLITE_DB = dbPath;
  process.env.__NTT_E2E_TMPDIR = dir;

  const markerPath = join(tmpdir(), 'ntx-grants-e2e-dbpath.txt');
  writeFileSync(markerPath, dbPath);
  process.env.__NTT_E2E_MARKER = markerPath;

  console.log(`[Grants E2E setup] Creating test DB: ${dbPath}`);
  execFileSync(
    PYTHON_BIN,
    ['seed.py'],
    {
      cwd: GRANTS_DIR,
      stdio: 'pipe',
      timeout: 30000,
      env: { ...process.env, NTT_SQLITE_DB: dbPath },
    }
  );
  console.log('[Grants E2E setup] Test DB seeded successfully');
}
