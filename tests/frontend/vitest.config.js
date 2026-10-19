import { defineConfig } from 'vitest/config';
import path from 'path';

const coreStatic = path.resolve(__dirname, '../../packages/n3tx-core/src/n3tx_core/static');
const uiStatic = path.resolve(__dirname, '../../packages/n3tx-ui/src/n3tx_ui/static');
const agentsStatic = path.resolve(__dirname, '../../packages/n3tx-agents/src/n3tx_agents/static');

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
    alias: [
      // Core framework JS (core/, utils/, transport/, config.js)
      { find: /^(\.\.\/)+core\//, replacement: coreStatic + '/core/' },
      { find: /^(\.\.\/)+utils\/icon-resolver\.js$/, replacement: uiStatic + '/utils/icon-resolver.js' },
      { find: /^(\.\.\/)+utils\//, replacement: coreStatic + '/utils/' },
      { find: /^(\.\.\/)+config\.js$/, replacement: coreStatic + '/config.js' },
      // Cross-package static imports used by n3tx-agents components
      { find: /^\.\/ntx-item\.js$/, replacement: uiStatic + '/components/ntx-item.js' },
      { find: /^\.\/ntx-list\.js$/, replacement: uiStatic + '/components/ntx-list.js' },
      { find: /^\.\/ntx-stream\.js$/, replacement: uiStatic + '/components/ntx-stream.js' },
      { find: /^\.\/ntx-sidebar-link-item\.js$/, replacement: uiStatic + '/components/ntx-sidebar-link-item.js' },
      { find: /^\.\/ntx-icon\.js$/, replacement: uiStatic + '/components/ntx-icon.js' },
      // UI components (components/, widgets/, generators/, vendor/)
      { find: /^(\.\.\/)+components\//, replacement: uiStatic + '/components/' },
      { find: /^(\.\.\/)+widgets\//, replacement: uiStatic + '/widgets/' },
      { find: /^(\.\.\/)+generators\//, replacement: uiStatic + '/generators/' },
      { find: /^(\.\.\/)+vendor\//, replacement: uiStatic + '/vendor/' },
    ]
  }
});
