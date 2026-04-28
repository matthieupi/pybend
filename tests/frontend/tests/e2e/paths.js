import { existsSync } from 'fs';
import { dirname, join, resolve } from 'path';
import { fileURLToPath } from 'url';

export const E2E_DIR = dirname(fileURLToPath(import.meta.url));
export const FRONTEND_ROOT = resolve(E2E_DIR, '../..');
export const REPO_ROOT = process.env.N3TX_REPO_ROOT || resolve(FRONTEND_ROOT, '../..');

export const PYTHONPATH = [
  join(REPO_ROOT, 'packages/n3tx-core/src'),
  join(REPO_ROOT, 'packages/n3tx-ui/src'),
  join(REPO_ROOT, 'packages/n3tx-actors/src'),
  join(REPO_ROOT, 'packages/n3tx-agents/src'),
].join(':');

const ACTIVE_VENV_PYTHON = process.env.VIRTUAL_ENV
  ? join(process.env.VIRTUAL_ENV, 'bin/python')
  : null;

export const PYTHON_BIN = ACTIVE_VENV_PYTHON && existsSync(ACTIVE_VENV_PYTHON)
  ? ACTIVE_VENV_PYTHON
  : 'python3';

export function repoPath(...parts) {
  return join(REPO_ROOT, ...parts);
}
