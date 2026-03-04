/**
 * Playwright global setup for grants e2e tests.
 *
 * Creates an isolated temp database, seeds it with grants test data,
 * and stores the path so the webServer process picks it up.
 */
import { execSync } from 'child_process';
import { mkdtempSync, writeFileSync } from 'fs';
import { join } from 'path';
import { tmpdir } from 'os';

const GRANTS_DIR = '/workspace/src/pybend/example_grants';

export default async function globalSetup() {
  const dir = mkdtempSync(join(tmpdir(), 'pybend-grants-e2e-'));
  const dbPath = join(dir, 'test_grants.db');

  process.env.PYBEND_SQLITE_DB = dbPath;
  process.env.__PYBEND_E2E_TMPDIR = dir;

  const markerPath = join(tmpdir(), 'pybend-grants-e2e-dbpath.txt');
  writeFileSync(markerPath, dbPath);
  process.env.__PYBEND_E2E_MARKER = markerPath;

  console.log(`[Grants E2E setup] Creating test DB: ${dbPath}`);
  execSync(
    `cd ${GRANTS_DIR} && PYBEND_SQLITE_DB="${dbPath}" python3 seed.py`,
    { stdio: 'pipe', timeout: 30000 }
  );
  console.log('[Grants E2E setup] Test DB seeded successfully');
}
