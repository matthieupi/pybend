import { test, expect } from './fixtures/parallel.js';
import { loginAndOpenVeilleAssistant, sendVeilleChatTurn } from './fixtures/ui.js';

test('only the first chat request creates the thread', async ({ page }) => {
  const streamPayloads = [];
  page.on('request', (request) => {
    if (request.url().includes('/agentic_stream') && request.method() === 'POST') {
      streamPayloads.push(request.postDataJSON());
    }
  });

  await loginAndOpenVeilleAssistant(page);
  await sendVeilleChatTurn(page, 'Hello assistant');
  await sendVeilleChatTurn(page, 'And again');
  await sendVeilleChatTurn(page, 'One more time');

  expect(streamPayloads).toHaveLength(3);
  expect(streamPayloads[0]?.thread_id).toBeUndefined();
  expect(streamPayloads[1]?.thread_id).toBeTruthy();
  expect(streamPayloads[2]?.thread_id).toBeTruthy();
});
