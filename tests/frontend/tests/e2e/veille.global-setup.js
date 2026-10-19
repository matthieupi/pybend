import { execFileSync } from 'child_process';
import { mkdtempSync, writeFileSync } from 'fs';
import { join } from 'path';
import { tmpdir } from 'os';
import { PYTHON_BIN, PYTHONPATH, repoPath } from './paths.js';

const APP_DIR = repoPath('apps/veille');

export default async function globalSetup() {
  const dir = mkdtempSync(join(tmpdir(), 'ntx-veille-e2e-'));
  const dbPath = join(dir, 'veille-test.db');
  const runId = process.env.PLAYWRIGHT_RUN_ID || `${process.pid}-${Date.now()}`;
  const markerPath = process.env.__NTX_VEILLE_E2E_MARKER || join(tmpdir(), `ntx-veille-e2e-dbpath-${runId}.txt`);

  process.env.N3TX_SQLITE_DB = dbPath;
  process.env.__NTX_VEILLE_E2E_TMPDIR = dir;
  process.env.__NTX_VEILLE_E2E_MARKER = markerPath;

  writeFileSync(markerPath, dbPath);

  console.log(`[Veille E2E setup] Creating test DB: ${dbPath}`);
  execFileSync(
    PYTHON_BIN,
    ['seed.py', '--reset'],
    {
      cwd: APP_DIR,
      stdio: 'pipe',
      timeout: 60000,
      env: {
        ...process.env,
        PYTHONPATH,
        N3TX_SQLITE_DB: dbPath,
        N3TX_CHAT_LLM: 'test',
      },
    }
  );
  console.log('[Veille E2E setup] Test DB seeded successfully');
}
