import test from 'node:test';
import assert from 'node:assert/strict';

import {
  clickSidebarHeader,
  mountVeilleSidebar,
} from './sidebar_agents_helpers.mjs';

test('expanding the Agents sidebar section creates the nested agents list shell', async () => {
  const { sidebar } = await mountVeilleSidebar();
  clickSidebarHeader(sidebar, 'AgentActor');

  const section = sidebar.shadowRoot.querySelector('.model-section[data-model="AgentActor"]');
  const nestedList = section?.querySelector('.model-records ntx-agents');

  assert.equal(section?.classList.contains('expanded'), true);
  assert.ok(nestedList, 'expected expanding AgentActor to create a nested ntx-agents shell');
});
