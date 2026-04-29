/**
 * Performance profiling test suite.
 *
 * Measures key user workflows at different data scale tiers to show how
 * performance changes as data grows. The API-side profiling runner handles
 * seeding at each tier; this test captures browser-side timings.
 *
 * Outputs: .traces/.profiling/frontend_perf_{label}.json
 *
 * Environment variables:
 *   PERF_LABEL  - Tag for this run (e.g. "baseline", "optimized"). Default: "run"
 *   PERF_TIER   - Data tier used for seeding (set by perf-global-setup.js). Default: "full"
 */
import { test, expect } from './fixtures/parallel.js';
import { authPayload } from './fixtures/auth.js';
import { readFileSync, writeFileSync, mkdirSync } from 'fs';
import { join, dirname } from 'path';
import { fileURLToPath } from 'url';
import { REPO_ROOT } from './paths.js';

const __dirname = dirname(fileURLToPath(import.meta.url));

// Load harness code once at module level — injected into pages via addScriptTag
const harnessCode = readFileSync(join(__dirname, 'perf-harness.js'), 'utf-8');

// Resolve profiling output dir: env var > repository root.
const PROFILING_DIR = process.env.NTT_PROFILING_DIR || join(REPO_ROOT, '.traces', '.profiling');
const LABEL = process.env.PERF_LABEL || 'run';
const TIER = process.env.PERF_TIER || 'full';

// Ensure output directory exists
try { mkdirSync(PROFILING_DIR, { recursive: true }); } catch {}

const results = [];
let errorCount = 0;

function record(name, durationMs, extra = {}) {
  const entry = {
    name,
    tier: TIER,
    label: LABEL,
    duration_ms: Math.round(durationMs * 100) / 100,
    timestamp: Date.now(),
    ...extra,
  };
  if (extra.error) {
    errorCount++;
    console.log(`    !! ${name}: ${extra.error_detail || 'unexpected status'}`);
  }
  results.push(entry);
}

/**
 * Record an API request with timing and error detection.
 */
async function timedRequest(request, name, method, url, opts = {}) {
  const expectStatus = opts.expectStatus || 200;
  delete opts.expectStatus;

  const start = performance.now();
  const resp = await request[method](url, opts);
  const ms = performance.now() - start;

  const status = resp.status();
  const ok = status === expectStatus;
  const extra = { status };
  if (!ok) {
    extra.error = true;
    extra.error_detail = `expected ${expectStatus}, got ${status} (${method.toUpperCase()} ${url})`;
  }
  record(name, ms, extra);
  return resp;
}

/**
 * Collect JS performance measures from the page and record them.
 */
async function harvestPerfMeasures(page, prefix = '') {
  const measures = await page.evaluate(() => {
    const entries = performance.getEntriesByType('measure');
    const data = entries.map(e => ({ name: e.name, duration: e.duration }));
    performance.clearMeasures();
    performance.clearMarks();
    return data;
  });
  for (const m of measures) {
    record(`${prefix}js:${m.name}`, m.duration);
  }
  return measures;
}

async function waitForRenderedProductItem(page) {
  await page.waitForFunction(() => {
    const list = document.querySelector('#product-list');
    const item = list?.shadowRoot?.querySelector('.list-grid ntx-item');
    return !!item?.shadowRoot?.querySelector('.card');
  }, { timeout: 15000 });
}

async function waitForRenderedRouterItem(page) {
  await page.waitForFunction(() => {
    const router = document.querySelector('ntx-router');
    const item = router?.shadowRoot?.querySelector('ntx-item');
    return !!item?.shadowRoot?.querySelector('.card');
  }, { timeout: 10000 });
}


test.describe.serial('Performance Profiling', () => {

  test('1. Schema fetch timing (cold + warm)', async ({ request }) => {
    // Only top-level models — child models (Comment, Like) are in $defs, no standalone route
    for (const model of ['Product', 'User']) {
      await timedRequest(request, `schema_${model}_cold`, 'get', `/${model}`);
      await timedRequest(request, `schema_${model}_warm_1`, 'get', `/${model}`);
      await timedRequest(request, `schema_${model}_warm_2`, 'get', `/${model}`);
    }
  });


  test('2. Page load + bootstrap timing', async ({ page }) => {
    const navStart = performance.now();
    await page.goto('/', { waitUntil: 'networkidle' });
    const networkIdleMs = performance.now() - navStart;
    record('page_load_network_idle', networkIdleMs);

    // Wait for product items to render (bootstrap complete)
    const renderStart = performance.now();
    await waitForRenderedProductItem(page);
    const firstItemMs = performance.now() - renderStart;
    record('first_item_render_after_idle', firstItemMs);

    record('page_load_total', networkIdleMs + firstItemMs);

    // Inject perf harness for any subsequent measures
    await page.addScriptTag({ content: harnessCode, type: 'module' });

    // Harvest JS perf measures from the bootstrap
    await harvestPerfMeasures(page, 'bootstrap:');
  });


  test('3. Product list API timing (with depth)', async ({ request }) => {
    // Match backend profiling: test depth=0,1,2 at limit=10,25
    for (const depth of [0, 1, 2]) {
      for (const limit of [10, 25]) {
        const resp = await timedRequest(request,
          `list_products_d${depth}_limit_${limit}`, 'get',
          `/products?limit=${limit}&depth=${depth}`);
        const body = await resp.json();
        const count = body.data ? body.data.length : 0;
        // Amend the last result with item count
        results[results.length - 1].items_returned = count;
      }
    }

    // Full collection fetch
    await timedRequest(request, 'list_products_all', 'get', '/products?limit=100');
  });


  test('4. User list API timing', async ({ request }) => {
    await timedRequest(request, 'list_users', 'get', '/users');
  });


  test('5. Product detail navigation', async ({ page }) => {
    await page.goto('/', { waitUntil: 'networkidle' });
    await waitForRenderedProductItem(page);

    // Inject perf harness before interaction
    await page.addScriptTag({ content: harnessCode, type: 'module' });

    // Click first product item to navigate to detail
    const navStart = performance.now();
    await page.locator('#product-list').locator('ntx-item').first().click();
    // Wait for the routed detail item to render inside the router shadow DOM.
    await waitForRenderedRouterItem(page);
    const detailMs = performance.now() - navStart;
    record('product_detail_navigation', detailMs);

    await harvestPerfMeasures(page, 'detail:');
  });


  test('6. Individual product fetches (with depth)', async ({ request }) => {
    // Login first (auth required for individual reads)
    const loginResp = await request.post('/users/login', {
      data: { email: 'alice@example.com', password: 'alice123' },
    });
    const token = authPayload(await loginResp.json()).token;
    if (!token) {
      record('get_product_skipped', 0, { error: true, error_detail: 'login failed, skipping' });
      return;
    }
    const headers = { 'x-access-token': token };

    for (const depth of [0, 1, 2]) {
      for (const pid of [1, 2, 3]) {
        await timedRequest(request, `get_product_${pid}_d${depth}`, 'get',
          `/products/${pid}?depth=${depth}`, { headers });
      }
    }
  });


  test('7. Child collections: comments + favorites', async ({ request }) => {
    const loginResp = await request.post('/users/login', {
      data: { email: 'alice@example.com', password: 'alice123' },
    });
    const token = authPayload(await loginResp.json()).token;
    if (!token) {
      record('child_collections_skipped', 0, { error: true, error_detail: 'login failed' });
      return;
    }
    const headers = { 'x-access-token': token };

    // Comments on products
    for (const pid of [1, 2]) {
      await timedRequest(request, `get_product_${pid}_comments`, 'get',
        `/products/${pid}/comments`, { headers });
    }

    // Favorites on products
    for (const pid of [1, 2]) {
      await timedRequest(request, `get_product_${pid}_favorites`, 'get',
        `/products/${pid}/favorites`, { headers });
    }
  });


  test('8. Login flow API timing', async ({ request }) => {
    await timedRequest(request, 'login_api', 'post', '/users/login', {
      data: { email: 'alice@example.com', password: 'alice123' },
    });
  });


  test('9. Write operations: creates, comments, favorites', async ({ request }) => {
    // Get token first
    const loginResp = await request.post('/users/login', {
      data: { email: 'alice@example.com', password: 'alice123' },
    });
    const token = authPayload(await loginResp.json()).token;
    if (!token) {
      record('write_ops_skipped', 0, { error: true, error_detail: 'login failed' });
      return;
    }
    const headers = { 'x-access-token': token };

    // Multiple product creates
    for (let i = 1; i <= 3; i++) {
      await timedRequest(request, `create_product_${i}`, 'post', '/products', {
        headers,
        data: {
          name: `Perf Test Product ${i} (${TIER})`,
          price: 49.99 + i * 10,
          description: `Created during Playwright profiling #${i}`,
        },
        expectStatus: 201,
      });
    }

    // Comments on different products
    for (const pid of [1, 2]) {
      await timedRequest(request, `comment_on_product_${pid}`, 'post',
        `/products/${pid}/comment`, {
          headers,
          data: {
            comment: {
              name: `Perf comment on p${pid}`,
              description: 'Comment from Playwright profiling',
            },
          },
        });
    }

    // Favorite multiple products
    for (const pid of [1, 2, 3]) {
      await timedRequest(request, `favorite_product_${pid}`, 'post',
        `/products/${pid}/favorite`, { headers });
    }
  });


  test('10. Full page reload (warm)', async ({ page }) => {
    // First load to warm caches
    await page.goto('/', { waitUntil: 'networkidle' });
    await waitForRenderedProductItem(page);

    // Second load = warm
    const start = performance.now();
    await page.reload({ waitUntil: 'networkidle' });
    await waitForRenderedProductItem(page);
    const warmMs = performance.now() - start;
    record('page_reload_warm', warmMs);

    // Inject perf harness after warm reload
    await page.addScriptTag({ content: harnessCode, type: 'module' });

    await harvestPerfMeasures(page, 'warm_reload:');
  });


  test('11. CDP CPU profile capture', async ({ page }) => {
    const client = await page.context().newCDPSession(page);
    await client.send('Profiler.enable');
    await client.send('Profiler.start');

    await page.goto('/', { waitUntil: 'networkidle' });
    await waitForRenderedProductItem(page);

    // Inject perf harness for any subsequent profiled interactions
    await page.addScriptTag({ content: harnessCode, type: 'module' });

    const { profile } = await client.send('Profiler.stop');
    const cpuProfilePath = join(PROFILING_DIR, `js_cpu_${LABEL}.cpuprofile`);
    writeFileSync(cpuProfilePath, JSON.stringify(profile));
    record('cdp_cpu_profile_captured', 0, { path: cpuProfilePath });

    await client.detach();
  });


  test.afterAll(async () => {
    // Write all collected results
    const outputPath = join(PROFILING_DIR, `frontend_perf_${LABEL}.json`);
    const output = {
      label: LABEL,
      tier: TIER,
      timestamp: new Date().toISOString(),
      errors: errorCount,
      results,
    };
    writeFileSync(outputPath, JSON.stringify(output, null, 2));
    console.log(`\n[Perf] ${results.length} measurements written to ${outputPath}`);
    if (errorCount > 0) {
      console.log(`[Perf] !! ${errorCount} operation(s) returned unexpected status codes`);
    }

    // Print summary table
    console.log(`\n${'Operation'.padEnd(45)} ${'ms'.padStart(10)}`);
    console.log('-'.repeat(57));
    for (const r of results) {
      if (!r.name.startsWith('js:') && !r.name.startsWith('bootstrap:') &&
          !r.name.startsWith('detail:') && !r.name.startsWith('warm_reload:')) {
        const flag = r.error ? ' !!' : '';
        console.log(`${r.name.padEnd(45)} ${r.duration_ms.toFixed(2).padStart(10)}${flag}`);
      }
    }
  });
});
