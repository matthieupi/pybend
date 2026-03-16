/**
 * Playwright global teardown — removes the E2E test database.
 */
import { rmSync, readFileSync, existsSync } from 'fs';
import { tmpdir } from 'os';
import { join } from 'path';

export default async function globalTeardown() {
  // Read the DB path from the marker file
  const markerPath = join(tmpdir(), 'ntx-e2e-dbpath.txt');
  if (!existsSync(markerPath)) return;

  const dbPath = readFileSync(markerPath, 'utf-8').trim();
  const dir = dbPath.replace(/\/[^/]+$/, '');

  // Clean up test DB and temp directory
  try {
    if (existsSync(dir)) {
      rmSync(dir, { recursive: true, force: true });
      console.log(`[E2E teardown] Cleaned up test DB: ${dbPath}`);
    }
  } catch (err) {
    console.warn(`[E2E teardown] Cleanup warning: ${err.message}`);
  }

  // Remove marker file
  try {
    rmSync(markerPath, { force: true });
  } catch {
    // ignore
  }
}
