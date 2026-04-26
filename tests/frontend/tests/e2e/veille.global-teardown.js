import { rmSync, readFileSync, existsSync } from 'fs';
import { tmpdir } from 'os';
import { join } from 'path';

export default async function globalTeardown() {
  const markerPath = join(tmpdir(), 'ntx-veille-e2e-dbpath.txt');
  if (!existsSync(markerPath)) return;

  const dbPath = readFileSync(markerPath, 'utf-8').trim();
  const dir = dbPath.replace(/\/[^/]+$/, '');

  try {
    if (existsSync(dir)) {
      rmSync(dir, { recursive: true, force: true });
      console.log(`[Veille E2E teardown] Cleaned up test DB: ${dbPath}`);
    }
  } catch (err) {
    console.warn(`[Veille E2E teardown] Cleanup warning: ${err.message}`);
  }

  try {
    rmSync(markerPath, { force: true });
  } catch {
    // ignore
  }
}
