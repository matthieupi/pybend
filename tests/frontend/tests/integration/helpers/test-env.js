/**
 * Test environment helpers — bootstraps NTT framework in jsdom.
 * Provides utilities to reset state between tests.
 */
import { vi } from 'vitest';

// Track all fetch mock responses
const fetchResponses = new Map();

/**
 * Configure fetch to respond with specific data for a URL pattern.
 */
export function mockFetch(urlPattern, responseData, options = {}) {
  fetchResponses.set(urlPattern, { data: responseData, ...options });
}

/**
 * Install fetch mock that matches URL patterns.
 */
export function installFetchMock() {
  global.fetch = vi.fn((url, opts) => {
    const urlStr = typeof url === 'string' ? url : url.toString();
    for (const [pattern, response] of fetchResponses) {
      if (urlStr.includes(pattern)) {
        const status = response.status || 200;
        return Promise.resolve({
          ok: status >= 200 && status < 300,
          status,
          json: () => Promise.resolve(response.data),
          text: () => Promise.resolve(JSON.stringify(response.data)),
        });
      }
    }
    // Default 404
    return Promise.resolve({
      ok: false,
      status: 404,
      json: () => Promise.resolve({ error: 'Not found' }),
      text: () => Promise.resolve('Not found'),
    });
  });
}

/**
 * Clear all fetch mock data.
 */
export function clearFetchMocks() {
  fetchResponses.clear();
}

/**
 * Wait for pending microtasks and timers.
 */
export function flush(ms = 0) {
  return new Promise(resolve => setTimeout(resolve, ms));
}

/**
 * Wait for all pending promises to settle.
 */
export async function flushPromises() {
  await new Promise(resolve => setTimeout(resolve, 0));
  await new Promise(resolve => queueMicrotask(resolve));
}
