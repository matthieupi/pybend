import { chromium } from '../../tests/frontend/node_modules/playwright/index.mjs';
import { writeFile } from 'node:fs/promises';
import assert from 'node:assert/strict';

const origin = process.argv[2];
const results = {steps: [], errors: [], requests: []};
const browser = await chromium.launch({headless: true});
const context = await browser.newContext();
const page = await context.newPage();
page.setDefaultTimeout(7000);
page.on('pageerror', e => results.errors.push(e.message));
page.on('response', async r => {
  if (['POST', 'PUT', 'DELETE'].includes(r.request().method()) || r.status() >= 400) {
    results.requests.push({method: r.request().method(), url: r.url(), status: r.status(),
      body: /login|register/.test(r.url()) ? '[auth response redacted]' : await r.text().catch(() => '')});
  }
});

async function step(name, fn) {
  try { await fn(); results.steps.push({name, status: 'PASS'}); return true; }
  catch (e) { results.steps.push({name, status: 'FAIL', error: e.message}); return false; }
}
async function login(p, email) {
  await p.goto(origin + '/login.html');
  await p.locator('#email').fill(email);
  await p.locator('#password').fill('tutorial-only-password');
  await p.getByRole('button', {name: 'Sign in'}).click();
  await p.waitForURL(origin + '/');
  await p.goto(origin + '/index.html');
  await p.locator('ntx-list .add-btn').waitFor();
}
try {
  for (const name of ['Alice', 'Bob']) {
    const r = await context.request.post(origin + '/users/register', {data: {
      name, email: `${name.toLowerCase()}@example.com`, password: 'tutorial-only-password'}});
    assert.ok([200, 409].includes(r.status())); // HTTP lane may already have registered fixtures.
  }
  await step('browser login + collection + permissions', async () => {
    await login(page, 'alice@example.com');
    assert.equal(await page.evaluate(async () => (await import('/utils/Permissions.js')).permissions.user.role), 'user');
  });
  const token = await page.evaluate(() => localStorage.getItem('jwtToken'));
  const headers = {'x-access-token': token};
  await step('label HTML rejected at generated API', async () => {
    const r = await context.request.post(origin + '/labels', {headers, data: {name: '<b>bad</b>'}});
    assert.equal(r.status(), 422);
    assert.equal((await context.request.post(origin + '/labels', {headers, data: {name: 'bug'}})).status(), 201);
  });
  const created = await step('native collection create', async () => {
    await page.locator('ntx-list .add-btn').click();
    await page.locator('ntx-modal ntx-item input[data-key="name"]').fill('Browser issue');
    await page.getByRole('button', {name: 'Create', exact: true}).click();
    await page.locator('ntx-list ntx-item').first().waitFor();
    const rows = await (await context.request.get(origin + '/issues', {headers})).json();
    assert.equal(rows.length, 1);
    assert.equal(rows[0].name, 'Browser issue');
  });
  assert.ok(created, 'Native UI creation must succeed; no HTTP fallback is permitted');
  const rows = await (await context.request.get(origin + '/issues', {headers})).json();
  const id = rows[0].id;
  await step('native edit + save persisted', async () => {
    await page.locator('ntx-list ntx-item').first().getByTitle('Edit', {exact: true}).click();
    await page.locator('ntx-list ntx-item').first().locator('input[data-key="name"]').fill('Browser edited');
    await page.locator('ntx-list ntx-item').first().getByTitle('Save', {exact: true}).click();
    await page.waitForTimeout(600);
    const saved = await (await context.request.get(origin + `/issues/${id}`, {headers})).json();
    assert.equal(saved.name, 'Browser edited');
  });
  await step('native resolve action persisted', async () => {
    await page.reload();
    const method = page.locator('ntx-method[method="resolve"]');
    await method.locator('input[data-key="resolution"], textarea[data-key="resolution"]').fill('Browser resolved');
    await method.locator('button[type="submit"]').click();
    await page.waitForTimeout(600);
    const saved = await (await context.request.get(origin + `/issues/${id}`, {headers})).json();
    assert.equal(saved.status, 'closed');
    assert.equal(saved.resolution, 'Browser resolved');
  });
  results.dom = await page.locator('body').evaluate(el => {
    function collect(e) { return e.outerHTML + [...e.querySelectorAll('*')].filter(x => x.shadowRoot).map(x => collect(x.shadowRoot)).join('\n'); }
    return collect(el);
  });
  const bobContext = await browser.newContext();
  const bob = await bobContext.newPage();
  bob.setDefaultTimeout(7000);
  await step('second browser user login, isolated collection, denied API operations', async () => {
    await login(bob, 'bob@example.com');
    const h = {'x-access-token': await bob.evaluate(() => localStorage.getItem('jwtToken'))};
    assert.deepEqual(await (await bobContext.request.get(origin + '/issues', {headers: h})).json(), []);
    for (const [method, path, data] of [['GET', `/issues/${id}`], ['PUT', `/issues/${id}`, {name: 'Denied'}],
      ['POST', `/issues/${id}/resolve`, {resolution: 'Denied'}], ['DELETE', `/issues/${id}`]]) {
      const r = await bobContext.request.fetch(origin + path, {method, headers: h, data});
      assert.equal(r.status(), 403, `${method} ${path}`);
    }
  });
} finally {
  await writeFile(new URL('./t02e-browser-results.json', import.meta.url), JSON.stringify(results, null, 2));
  await browser.close();
  console.log(JSON.stringify(results.steps, null, 2));
  if (results.steps.some(s => s.status === 'FAIL')) process.exitCode = 1;
}
