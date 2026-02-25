import { defineConfig } from 'vitest/config';

export default defineConfig({
  test: {
    environment: 'jsdom',
    globals: true,
    setupFiles: ['./tests/setup.js'],
    include: ['tests/**/*.test.js'],
    testTimeout: 10000,
    restoreMocks: true,
  },
  resolve: {
    alias: {
      // Allow tests to import source modules directly
    }
  }
});
