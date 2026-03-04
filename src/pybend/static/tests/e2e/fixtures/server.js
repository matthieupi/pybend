/**
 * Server fixture for Playwright E2E tests.
 *
 * The backend server is managed by Playwright's webServer config
 * in playwright.config.js. This file provides helpers for seeding
 * and resetting test data.
 */
import { exec } from 'child_process';
import { promisify } from 'util';

const execAsync = promisify(exec);
const EXAMPLE_DIR = '/workspace/example_api';

/**
 * Seed the database with test data.
 * Call this before running E2E tests if the DB is empty.
 */
export async function seedDatabase() {
  try {
    const { stdout, stderr } = await execAsync(
      `cd ${EXAMPLE_DIR} && python3 seed.py`,
      { timeout: 30000 }
    );
    console.log('[seed]', stdout);
    if (stderr) console.warn('[seed stderr]', stderr);
  } catch (error) {
    // Seed may report "already has data" — that's fine
    if (!error.stdout?.includes('already has data')) {
      console.error('[seed error]', error.message);
    }
  }
}

/**
 * Reset the database: delete and re-seed.
 */
export async function resetDatabase() {
  try {
    const { stdout } = await execAsync(
      `cd ${EXAMPLE_DIR} && python3 seed.py --reset`,
      { timeout: 30000 }
    );
    console.log('[reset+seed]', stdout);
  } catch (error) {
    console.error('[reset error]', error.message);
  }
}

/**
 * Wait for the server to be ready by polling the schema endpoint.
 * @param {string} baseURL
 * @param {number} timeoutMs
 */
export async function waitForServer(baseURL = 'http://localhost:5000', timeoutMs = 15000) {
  const start = Date.now();
  while (Date.now() - start < timeoutMs) {
    try {
      const resp = await fetch(`${baseURL}/Product`);
      if (resp.ok) return;
    } catch {
      // Server not ready yet
    }
    await new Promise(r => setTimeout(r, 500));
  }
  throw new Error(`Server not ready after ${timeoutMs}ms`);
}
