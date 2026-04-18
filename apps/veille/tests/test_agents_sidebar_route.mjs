import test from 'node:test';
import assert from 'node:assert/strict';

import {
  mountVeilleSidebar,
} from './sidebar_agents_helpers.mjs';

test('veille sidebar declares an AgentActor route template with the Agents label', async () => {
  const { sidebar } = await mountVeilleSidebar();
  const agentTemplate = [...sidebar.children].find((child) => child.getAttribute('model') === 'AgentActor');

  assert.ok(agentTemplate, 'expected Veille sidebar to include an AgentActor route template');
  assert.equal(agentTemplate.tagName.toLowerCase(), 'ntx-agents');
  assert.equal(agentTemplate.getAttribute('sidebar-label'), 'Agents');
});
