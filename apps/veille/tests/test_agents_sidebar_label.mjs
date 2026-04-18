import test from 'node:test';
import assert from 'node:assert/strict';

import {
  mountVeilleSidebar,
  renderedSidebarLabels,
} from './sidebar_agents_helpers.mjs';

test('agents entry is visible in the veille sidebar shell', async () => {
  const { sidebar } = await mountVeilleSidebar();
  const labels = renderedSidebarLabels(sidebar);

  assert.ok(
    labels.includes('Agents'),
    `expected sidebar labels to include Agents, got: ${labels.join(', ')}`,
  );
});
