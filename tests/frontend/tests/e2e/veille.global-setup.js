import { execSync } from 'child_process';
import { existsSync, mkdtempSync, writeFileSync } from 'fs';
import { join } from 'path';
import { tmpdir } from 'os';

const APP_DIR = '/workspace/apps/veille';
const PYTHONPATH = [
  '/workspace/packages/n3tx-core/src',
  '/workspace/packages/n3tx-ui/src',
  '/workspace/packages/n3tx-actors/src',
  '/workspace/packages/n3tx-agents/src',
].join(':');
const PYTHON_BIN = existsSync('/workspace/.venv-e2e/bin/python')
  ? '/workspace/.venv-e2e/bin/python'
  : 'python3';

export default async function globalSetup() {
  const dir = mkdtempSync(join(tmpdir(), 'ntx-veille-e2e-'));
  const dbPath = join(dir, 'veille-test.db');
  const markerPath = join(tmpdir(), 'ntx-veille-e2e-dbpath.txt');

  process.env.N3TX_SQLITE_DB = dbPath;
  process.env.__NTX_VEILLE_E2E_TMPDIR = dir;
  process.env.__NTX_VEILLE_E2E_MARKER = markerPath;

  writeFileSync(markerPath, dbPath);

  console.log(`[Veille E2E setup] Creating test DB: ${dbPath}`);
  execSync(
    `cd ${APP_DIR} && N3TX_SQLITE_DB="${dbPath}" N3TX_CHAT_LLM=test ${PYTHON_BIN} seed.py --reset`,
    {
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
