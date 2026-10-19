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
const E2E_VENV_PYTHON = join(REPO_ROOT, '.venv-e2e/bin/python');
const WORKSPACE_VENV_PYTHON = join(REPO_ROOT, '.venv/bin/python');

export const PYTHON_BIN = [
  ACTIVE_VENV_PYTHON,
  E2E_VENV_PYTHON,
  WORKSPACE_VENV_PYTHON,
].find((pythonBin) => pythonBin && existsSync(pythonBin)) || 'python3';

export function repoPath(...parts) {
  return join(REPO_ROOT, ...parts);
}
