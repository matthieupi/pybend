import test from 'node:test';
import assert from 'node:assert/strict';

import {
  clickSidebarHeader,
  mountVeilleSidebar,
} from './sidebar_agents_helpers.mjs';

test('expanding the Sources sidebar section keeps the compact nested list fallback', async () => {
  const { sidebar } = await mountVeilleSidebar();
  clickSidebarHeader(sidebar, 'Source');

  const section = sidebar.shadowRoot.querySelector('.model-section[data-model="Source"]');
  const nestedList = section?.querySelector('.model-records ntx-list');
  const nestedTable = section?.querySelector('.model-records ntx-table');

  assert.equal(section?.classList.contains('expanded'), true);
  assert.ok(nestedList, 'expected expanding Source to keep the nested ntx-list dropdown shell');
  assert.equal(nestedTable, null);
});
