/**
 * Playwright global teardown — removes the E2E test database.
 */
import { rmSync, readFileSync, existsSync } from 'fs';
import { tmpdir } from 'os';
import { join } from 'path';

export default async function globalTeardown() {
  // Read the DB path from the marker file
  const markerPath = process.env.__NTT_E2E_MARKER || join(tmpdir(), 'ntx-e2e-dbpath.txt');
  const pidMarkerPath = `${markerPath}.pid`;
  if (!existsSync(markerPath)) return;

  if (existsSync(pidMarkerPath)) {
    try {
      const pid = Number(readFileSync(pidMarkerPath, 'utf-8').trim());
      if (pid) process.kill(pid, 'SIGTERM');
    } catch {
      // Process may already be gone.
    }
  }

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
    rmSync(pidMarkerPath, { force: true });
  } catch {
    // ignore
  }
}
