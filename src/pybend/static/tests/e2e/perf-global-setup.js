/**
 * Playwright global setup for performance tests.
 * Uses seed_perf.py with configurable tier (via PERF_TIER env, default "full").
 * Sets PYBEND_SQLITE_DB to a temp file for isolation.
 */
import { execSync } from 'child_process';
import { mkdtempSync, writeFileSync } from 'fs';
import { join, resolve, dirname } from 'path';
import { tmpdir } from 'os';
import { fileURLToPath } from 'url';

const __dirname = dirname(fileURLToPath(import.meta.url));
const WORKSPACE = resolve(__dirname, '..', '..', '..', '..', '..');
const SEED_SCRIPT = resolve(WORKSPACE, 'src', 'pybend', 'core', 'tests', 'profiling', 'seed_perf.py');

export default async function globalSetup() {
  const dir = mkdtempSync(join(tmpdir(), 'pybend-perf-'));
  const dbPath = join(dir, 'perf.db');
  const tier = process.env.PERF_TIER || 'full';

  process.env.PYBEND_SQLITE_DB = dbPath;
  process.env.PYBEND_PORT = '5099';
  process.env.__PYBEND_E2E_TMPDIR = dir;

  const markerPath = join(tmpdir(), 'pybend-e2e-dbpath.txt');
  writeFileSync(markerPath, dbPath);
  process.env.__PYBEND_E2E_MARKER = markerPath;

  console.log(`[Perf setup] Creating test DB: ${dbPath} (tier=${tier})`);
  execSync(
    `PYBEND_SQLITE_DB="${dbPath}" PYTHONPATH="${WORKSPACE}/src" python3 "${SEED_SCRIPT}" --reset --tier ${tier}`,
    { stdio: 'pipe', timeout: 60000 }
  );
  console.log('[Perf setup] Test DB seeded successfully');
}
