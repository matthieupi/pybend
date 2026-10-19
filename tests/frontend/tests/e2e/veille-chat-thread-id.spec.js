import { test, expect } from './fixtures/parallel.js';
import { loginAndOpenVeilleAssistant, sendVeilleChatTurn } from './fixtures/ui.js';

test('second chat request includes thread_id from the current conversation', async ({ page }) => {
  const streamPayloads = [];
  page.on('request', (request) => {
    if (request.url().includes('/agentic_stream') && request.method() === 'POST') {
      streamPayloads.push(request.postDataJSON());
    }
  });

  await loginAndOpenVeilleAssistant(page);
  await sendVeilleChatTurn(page, 'Hello assistant');
  await sendVeilleChatTurn(page, 'What did I just ask you?');

  expect(streamPayloads).toHaveLength(2);
  expect(streamPayloads[0]?.thread_id).toBeUndefined();
  expect(streamPayloads[1]?.thread_id).toBeTruthy();
});
