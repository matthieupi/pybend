import { test, expect } from './fixtures/parallel.js';
import { loginAndOpenVeilleAssistant, sendVeilleChatTurn } from './fixtures/ui.js';

test('thread_id stays stable across subsequent chat turns', async ({ page }) => {
  const streamPayloads = [];
  page.on('request', (request) => {
    if (request.url().includes('/agentic_stream') && request.method() === 'POST') {
      streamPayloads.push(request.postDataJSON());
    }
  });

  await loginAndOpenVeilleAssistant(page);
  await sendVeilleChatTurn(page, 'Hello assistant');
  await sendVeilleChatTurn(page, 'And again');
  await sendVeilleChatTurn(page, 'Summarize our conversation');

  expect(streamPayloads).toHaveLength(3);
  expect(streamPayloads[1]?.thread_id).toBeTruthy();
  expect(streamPayloads[2]?.thread_id).toBeTruthy();
  expect(streamPayloads[2]?.thread_id).toBe(streamPayloads[1]?.thread_id);
});
