/**
 * Playwright global teardown for grants e2e tests.
 * Removes the isolated test database.
 */
import { rmSync, readFileSync, existsSync } from 'fs';
import { tmpdir } from 'os';
import { join } from 'path';

export default async function globalTeardown() {
  const markerPath = join(tmpdir(), 'ntx-grants-e2e-dbpath.txt');
  if (!existsSync(markerPath)) return;

  const dbPath = readFileSync(markerPath, 'utf-8').trim();
  const dir = dbPath.replace(/\/[^/]+$/, '');

  try {
    if (existsSync(dir)) {
      rmSync(dir, { recursive: true, force: true });
      console.log(`[Grants E2E teardown] Cleaned up test DB: ${dbPath}`);
    }
  } catch (err) {
    console.warn(`[Grants E2E teardown] Cleanup warning: ${err.message}`);
  }

  try {
    rmSync(markerPath, { force: true });
  } catch {
    // ignore
  }
}
