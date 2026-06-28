# Plan 2 — E2E App Server Harness, Option B

## Purpose

Implement the **Option B class-based E2E app server harness** for frontend Playwright tests.

This corresponds to candidate #2 from `.project/plans/frontend-test-architecture-deepening-candidates.md`: **Unified E2E app/server lifecycle harness**.

The goal is to deepen the local app lifecycle module so Playwright configs and fixtures no longer duplicate setup logic for:

- app profiles (`core`, `grants`, `veille`, `perf`)
- temp SQLite DB allocation
- Python environment construction
- seeding via `seed.py --reset`
- app process spawn
- readiness probing
- marker files for Playwright `webServer` mode
- process shutdown
- temp directory cleanup

This is a **test infrastructure refactor**. It should not change application behavior or E2E test assertions.

---

## Chosen Design: Option B — Class-Based App Server Harness

Use a lifecycle object with an explicit state model:

```js
const server = await E2EAppServer.for('core')
  .withPort(5000)
  .withTempDatabase()
  .withSeedReset()
  .withMarker(process.env.__NTT_E2E_MARKER)
  .start();

await server.ready();
await server.stop();
```

Why Option B fits this target:

- The app server lifecycle has real state: profile, temp dir, DB path, env, child process, marker files, readiness status, cleanup status.
- Serial Playwright `webServer` mode and parallel worker fixture need the same lifecycle with slightly different process ownership.
- A class gives one obvious place for durable lifecycle invariants and debug logging.
- The public interface remains small while the implementation can hide platform/process details.

---

## Problem Statement

The current E2E server lifecycle is split across multiple files with duplicated responsibilities.

### Serial Playwright path

`playwright.config.js` launches a long-lived process through Playwright `webServer`:

```js
webServer: {
  command: 'node tests/e2e/start-e2e-app.js core',
  cwd: FRONTEND_ROOT,
  env: {
    ...process.env,
    __NTT_E2E_MARKER: E2E_MARKER,
  },
  url: 'http://localhost:5000/Product',
  reuseExistingServer: process.env.N3TX_E2E_REUSE_SERVER === '1',
  timeout: 120000,
}
```

`start-e2e-app.js` owns app profile lookup, temp DB creation, env construction, seeding, process spawning, and marker files:

```js
const tmpDir = mkdtempSync(join(tmpdir(), app.tmpPrefix));
const dbPath = join(tmpDir, app.dbName);
const markerPath = process.env[app.markerEnv] || join(tmpdir(), app.defaultMarker);
const pidMarkerPath = `${markerPath}.pid`;

writeFileSync(markerPath, dbPath);

const env = {
  ...process.env,
  PYTHONPATH,
  N3TX_SQLITE_DB: dbPath,
  NTT_SQLITE_DB: dbPath,
  N3TX_PORT: app.port,
  NTT_PORT: app.port,
  N3TX_API_URL: `http://localhost:${app.port}`,
  N3TX_DEBUG: 'false',
  [app.markerEnv]: markerPath,
  ...(app.extraEnv || {}),
};

execFileSync(PYTHON_BIN, ['seed.py', app.resetArg].filter(Boolean), { cwd: app.dir, env });
child = spawn(PYTHON_BIN, ['main.py'], { cwd: app.dir, env, detached: true });
writeFileSync(pidMarkerPath, String(child.pid));
```

### Parallel Playwright path

`fixtures/parallel.js` does a second version of the same lifecycle per worker:

```js
const port = BASE_PORT + workerInfo.parallelIndex;
const baseURL = `http://localhost:${port}`;
const appDir = repoPath('examples/core');
const tmpDir = mkdtempSync(join(tmpdir(), `ntx-e2e-parallel-${workerInfo.parallelIndex}-`));
const dbPath = join(tmpDir, 'test.db');

const env = {
  ...process.env,
  PYTHONPATH,
  N3TX_SQLITE_DB: dbPath,
  NTT_SQLITE_DB: dbPath,
  N3TX_PORT: String(port),
  NTT_PORT: String(port),
  N3TX_API_URL: baseURL,
  N3TX_DEBUG: 'false',
};

execFileSync(PYTHON_BIN, ['seed.py', '--reset'], { cwd: appDir, env });
const child = spawn(PYTHON_BIN, ['main.py'], { cwd: appDir, env });
await waitForServer(baseURL);
```

### Teardown drift

`global-teardown.js` kills PID markers and removes temp dirs, but app-specific teardowns only remove DB temp dirs:

```js
// global-teardown.js kills PID marker if present
if (existsSync(pidMarkerPath)) {
  const pid = Number(readFileSync(pidMarkerPath, 'utf-8').trim());
  if (pid) process.kill(pid, 'SIGTERM');
}
```

```js
// grants-global-teardown.js / veille.global-teardown.js remove marker dir only
const dbPath = readFileSync(markerPath, 'utf-8').trim();
const dir = dbPath.replace(/\/[^/]+$/, '');
rmSync(dir, { recursive: true, force: true });
```

This makes future changes error-prone: an agent or developer can update one path and leave another stale.

---

## Target Architecture

```text
Playwright config / fixture
        |
        v
+---------------------------+
| E2EAppServer              |
| - profile                 |
| - runtime paths/env       |
| - DB temp dir             |
| - seed command            |
| - child process           |
| - marker files            |
| - readiness probe         |
| - cleanup                 |
+-------------+-------------+
              |
              +-----------------------+
              |                       |
              v                       v
  serial webServer CLI        parallel worker fixture
  start-e2e-app.js            fixtures/parallel.js
  thin wrapper                thin wrapper
```

The class becomes the single owner of app lifecycle semantics. Existing Playwright configs remain mostly unchanged at first; their command still invokes `start-e2e-app.js`, but that script delegates to `E2EAppServer`.

---

## Proposed File Layout

```text
tests/frontend/tests/e2e/
├── harness/
│   ├── app-server.js          # E2EAppServer class
│   ├── app-profiles.js        # core/grants/veille/perf profile definitions
│   ├── process.js             # stopProcess(), signal helpers
│   └── readiness.js           # waitForServer()/readiness probes
├── start-e2e-app.js           # thin CLI wrapper around E2EAppServer
├── global-teardown.js         # thin marker cleanup wrapper
├── grants-global-teardown.js  # either delegates or removed after config migration
├── veille.global-teardown.js  # either delegates or removed after config migration
└── fixtures/parallel.js       # worker fixture uses E2EAppServer
```

Keep profile definitions out of the class so Playwright configs and tests can inspect app settings without constructing processes.

---

## Public Interface Sketch

### App profile

```ts
type E2EAppProfile = {
  name: 'core' | 'grants' | 'veille' | 'perf';
  dir: string;
  dbName: string;
  tmpPrefix: string;
  markerEnv: string;
  defaultMarker: string;
  defaultPort: number;
  resetArg: string | null;
  readinessPath: string;
  seedTimeoutMs: number;
  startTimeoutMs: number;
  extraEnv?: Record<string, string>;
};
```

Initial profiles should preserve current behavior:

| App | Directory | DB | Port | Readiness | Extra env |
|---|---|---|---:|---|---|
| `core` | `examples/core` | `test.db` | 5000 | `/Product` | none |
| `grants` | `examples/grants` | `test_grants.db` | 5000 | `/Grant` | none |
| `veille` | `apps/veille` | `veille-test.db` | 5010 | `/login.html` | `N3TX_CHAT_LLM=test` |
| `perf` | `examples/core` | `perf.db` | 5099 | `/Product` | `NTT_PROFILING=1` |

### `E2EAppServer`

```ts
class E2EAppServer {
  static for(appName: string): E2EAppServer;

  withPort(port: number | string): this;
  withBaseURL(baseURL: string): this;
  withTempDatabase(options?: { tmpPrefix?: string; dbName?: string }): this;
  withDatabase(dbPath: string): this;
  withSeedReset(resetArg?: string | null): this;
  withEnv(env: Record<string, string>): this;
  withMarker(markerPath?: string | null): this;
  withDetachedProcess(detached?: boolean): this;
  withDebugLabel(label: string): this;

  get profile(): E2EAppProfile;
  get baseURL(): string;
  get dbPath(): string;
  get markerPath(): string | null;
  get env(): Record<string, string>;

  prepare(): this;
  seed(): void;
  start(): Promise<this>;
  ready(timeoutMs?: number): Promise<void>;
  stop(): Promise<void>;
  cleanup(): Promise<void>;
  writeMarkers(): void;
}
```

### Typical serial CLI usage

```js
const server = await E2EAppServer.for(appName)
  .withMarker(process.env[profile.markerEnv])
  .withDetachedProcess(true)
  .start();

server.installSignalHandlers({ exitOnly: true });
server.keepAlive();
```

`start-e2e-app.js` should continue to behave like a long-running Playwright `webServer.command`: it starts the app, writes markers, and stays alive until Playwright stops it.

### Typical parallel fixture usage

```js
const server = await E2EAppServer.for('core')
  .withPort(BASE_PORT + workerInfo.parallelIndex)
  .withTempDatabase({ tmpPrefix: `ntx-e2e-parallel-${workerInfo.parallelIndex}-` })
  .withDebugLabel(`parallel:${workerInfo.parallelIndex}`)
  .start();

try {
  await use({ baseURL: server.baseURL, port: server.port, dbPath: server.dbPath });
} finally {
  await server.stop();
  await server.cleanup();
}
```

---

## State Model

`E2EAppServer` should make lifecycle transitions explicit.

```text
new
 |
 v
configured
 |
 v
prepared        -> temp dir/db path/env resolved
 |
 v
seeded          -> seed.py completed
 |
 v
started         -> child process spawned
 |
 v
ready           -> readiness URL responds OK
 |
 v
stopped         -> child terminated or marker PID killed
 |
 v
cleaned         -> temp dir and markers removed
```

Implementation does not need a complex state machine, but it should guard obvious misuse:

- cannot `seed()` before DB/env are prepared
- cannot `ready()` before start
- `stop()` and `cleanup()` should be idempotent
- errors should include app name, cwd, port, and DB path

---

## Implementation Steps

### Step 1 — Extract app profiles

Create `tests/frontend/tests/e2e/harness/app-profiles.js`.

Move the current `APPS` object from `start-e2e-app.js` into exported profiles:

```js
export const APP_PROFILES = {
  core: {
    name: 'core',
    dir: repoPath('examples/core'),
    dbName: 'test.db',
    tmpPrefix: 'ntx-e2e-',
    markerEnv: '__NTT_E2E_MARKER',
    defaultMarker: 'ntx-e2e-dbpath.txt',
    defaultPort: 5000,
    resetArg: '--reset',
    readinessPath: '/Product',
    seedTimeoutMs: 60000,
    startTimeoutMs: 120000,
  },
  // grants, veille, perf...
};

export function getAppProfile(name) {
  const profile = APP_PROFILES[name];
  if (!profile) throw new Error(`Unknown E2E app profile: ${name}`);
  return profile;
}
```

Preserve current names and environment variables exactly.

### Step 2 — Add process/readiness helpers

Create:

- `tests/frontend/tests/e2e/harness/process.js`
- `tests/frontend/tests/e2e/harness/readiness.js`

Process helper:

```js
export async function stopProcess(child, timeoutMs = 5000) {
  if (!child || child.killed) return;
  // SIGTERM, wait, SIGKILL fallback
}

export function killPid(pid, signal = 'SIGTERM') {
  try { if (pid) process.kill(pid, signal); } catch {}
}
```

Readiness helper:

```js
export async function waitForServer(baseURL, path, timeoutMs = 30000) {
  const url = new URL(path, baseURL).toString();
  // poll fetch until ok, then return
}
```

Use the existing polling semantics from `fixtures/parallel.js`.

### Step 3 — Implement `E2EAppServer`

Create `tests/frontend/tests/e2e/harness/app-server.js`.

Core responsibilities:

1. Resolve profile.
2. Validate app directory exists.
3. Resolve port/baseURL.
4. Allocate temp dir and DB path.
5. Build environment:
   - `PYTHONPATH`
   - `N3TX_SQLITE_DB`
   - `NTT_SQLITE_DB`
   - `N3TX_PORT`
   - `NTT_PORT`
   - `N3TX_API_URL`
   - `N3TX_DEBUG=false`
   - `NTT_PROFILING_DIR`
   - profile `extraEnv`
6. Write marker and PID marker if requested.
7. Run seed command.
8. Spawn app process.
9. Wait for readiness unless caller opts out.
10. Stop and cleanup idempotently.

Pseudo-code:

```js
export class E2EAppServer {
  static for(appName) {
    return new E2EAppServer(getAppProfile(appName));
  }

  constructor(profile) {
    this._profile = profile;
    this._port = profile.defaultPort;
    this._detached = false;
    this._seedResetArg = profile.resetArg;
  }

  prepare() {
    if (!existsSync(this.profile.dir)) throw new Error(...);
    this._tmpDir ||= mkdtempSync(join(tmpdir(), this.profile.tmpPrefix));
    this._dbPath ||= join(this._tmpDir, this.profile.dbName);
    this._baseURL ||= `http://localhost:${this._port}`;
    this._env = this._buildEnv();
    this._prepared = true;
    return this;
  }

  seed() {
    this.prepare();
    execFileSync(PYTHON_BIN, ['seed.py', this._seedResetArg].filter(Boolean), {
      cwd: this.profile.dir,
      env: this.env,
      stdio: 'pipe',
      timeout: this.profile.seedTimeoutMs,
    });
    this._seeded = true;
  }

  async start() {
    this.seed();
    this._child = spawn(PYTHON_BIN, ['main.py'], {
      cwd: this.profile.dir,
      env: this.env,
      detached: this._detached,
      stdio: this._stdio,
    });
    this.writeMarkers();
    await this.ready();
    return this;
  }
}
```

### Step 4 — Convert `start-e2e-app.js` into a thin wrapper

Replace inline lifecycle logic with `E2EAppServer`.

Desired shape:

```js
#!/usr/bin/env node
import { E2EAppServer } from './harness/app-server.js';
import { getAppProfile } from './harness/app-profiles.js';

const appName = process.argv[2];
const profile = getAppProfile(appName);

const server = await E2EAppServer.for(appName)
  .withMarker(process.env[profile.markerEnv])
  .withDetachedProcess(true)
  .withStdio('ignore')
  .start();

process.on('SIGTERM', () => process.exit(0));
process.on('SIGINT', () => process.exit(0));

server.keepAlive();
```

Important compatibility point:

- Current serial wrapper intentionally does **not** forward Playwright lifecycle signals to the app. `global-teardown.js` owns cleanup through PID marker. Preserve this initially.

### Step 5 — Convert parallel fixture to use `E2EAppServer`

Change `fixtures/parallel.js` so the worker fixture delegates lifecycle:

```js
const server = await E2EAppServer.for('core')
  .withPort(BASE_PORT + workerInfo.parallelIndex)
  .withTempDatabase({ tmpPrefix: `ntx-e2e-parallel-${workerInfo.parallelIndex}-` })
  .withDebugLabel(`parallel:${workerInfo.parallelIndex}`)
  .withStdio(process.env.N3TX_E2E_PARALLEL_DEBUG === '1' ? 'pipe' : 'ignore')
  .start();

try {
  await use({ baseURL: server.baseURL, port: server.port, dbPath: server.dbPath });
} finally {
  await server.stop();
  await server.cleanup();
}
```

Keep the exported Playwright fixture API stable:

```js
await use({ baseURL, port, dbPath });
```

### Step 6 — Unify marker cleanup

Add a marker cleanup helper, either inside `app-server.js` as a static method or in `harness/cleanup.js`:

```js
export async function cleanupMarker(markerPath) {
  const pidMarkerPath = `${markerPath}.pid`;
  kill pid if marker exists;
  read db path;
  rm temp dir;
  rm marker and pid marker;
}
```

Update:

- `global-teardown.js`
- `grants-global-teardown.js`
- `veille.global-teardown.js`

to delegate to the same helper.

Compatibility path:

```js
export default async function globalTeardown() {
  const markerPath = process.env.__NTT_E2E_MARKER || join(tmpdir(), 'ntx-e2e-dbpath.txt');
  await cleanupMarker(markerPath, { label: 'E2E teardown' });
}
```

This preserves current config references while eliminating behavior drift.

### Step 7 — Add harness tests

Because this harness spawns Python apps and writes temp DBs, keep tests focused and local-substitutable.

Recommended file:

```text
tests/frontend/tests/e2e/harness/app-server.test.js
```

If Vitest does not currently include E2E harness unit tests, place tests where the frontend unit runner can execute them without Playwright browser startup, or add them to a suitable Node/Vitest suite only if available. If no Node test lane exists, defer full automated harness tests and verify through Playwright smoke runs.

Testable units without starting Python:

| Unit | Test |
|---|---|
| profile lookup | known profiles return expected port/readiness/env |
| env construction | `N3TX_SQLITE_DB`, `NTT_SQLITE_DB`, `N3TX_API_URL`, `PYTHONPATH` are set |
| marker cleanup | temp dir and marker files are removed; PID kill is best-effort |
| readiness URL construction | base URL + readiness path normalize correctly |

Integration smoke with actual app:

```bash
cd /workspace/tests/frontend && npx playwright test --config=tests/e2e/playwright.config.js tests/e2e/page-load.spec.js
```

### Step 8 — Documentation update

Update `FRONTEND.md` E2E test environment section after implementation.

Document:

- `E2EAppServer` owns app lifecycle.
- `start-e2e-app.js` is only a CLI wrapper.
- parallel fixture uses the same lifecycle class.
- where to add new app profiles.
- marker cleanup behavior.

---

## Migration Strategy

### Phase 1 — Introduce class behind existing CLI

- Add `harness/app-profiles.js`, `harness/app-server.js`, helpers.
- Convert `start-e2e-app.js` only.
- Run serial core E2E smoke.

This validates Playwright `webServer.command` compatibility.

### Phase 2 — Convert parallel fixture

- Convert `fixtures/parallel.js` to `E2EAppServer`.
- Preserve `parallelServer` fixture shape.
- Run parallel core smoke.

### Phase 3 — Unify teardown helpers

- Add shared marker cleanup.
- Convert global, grants, and veille teardowns to delegate.
- Verify grants/veille smoke.

### Phase 4 — Simplify config comments and stale setup files

- Remove stale comments claiming global setup seeds DB where this is no longer true.
- Audit obsolete `*-global-setup.js` files in a separate cleanup PR/step if present.

Do not combine Phase 4 with lifecycle behavior changes unless the diff stays small.

---

## Verification Commands

Narrow serial core smoke:

```bash
cd /workspace/tests/frontend && npx playwright test --config=tests/e2e/playwright.config.js tests/e2e/page-load.spec.js
```

Parallel core smoke:

```bash
cd /workspace/tests/frontend && npx playwright test --config=tests/e2e/playwright.parallel.config.js tests/e2e/page-load.spec.js
```

Grants smoke:

```bash
cd /workspace/tests/frontend && npx playwright test --config=tests/e2e/playwright.grants.config.js
```

Veille smoke:

```bash
cd /workspace/tests/frontend && npx playwright test --config=tests/e2e/veille.playwright.config.js tests/e2e/veille-dashboard.spec.js
```

Perf smoke only if lifecycle changes affect perf profile:

```bash
cd /workspace/tests/frontend && npx playwright test --config=tests/e2e/playwright.perf.config.js
```

Aggregate frontend runner after targeted checks:

```bash
cd /workspace && python3 scripts/test-frontend.py --suite e2e-core
```

---

## Acceptance Criteria

- `E2EAppServer` class exists and owns app lifecycle state.
- App profiles are centralized in one module.
- `start-e2e-app.js` delegates to `E2EAppServer` and preserves existing CLI behavior.
- `fixtures/parallel.js` uses `E2EAppServer` and preserves the `parallelServer` fixture contract.
- Marker cleanup is shared by global/grants/veille teardown paths.
- Core serial smoke passes.
- Core parallel smoke passes.
- Grants and Veille smoke checks pass or any failures are unrelated to lifecycle and documented.
- `FRONTEND.md` documents the new lifecycle owner.

---

## Risks and Mitigations

| Risk | Impact | Mitigation |
|---|---|---|
| Playwright `webServer` expects command process to stay alive | Tests may fail before app is reachable | Preserve `start-e2e-app.js` keep-alive behavior |
| Detached serial process cleanup changes | Orphaned Python processes | Preserve PID marker cleanup first; only later consider direct signal forwarding |
| Parallel workers collide on ports or DB paths | Flaky tests | Keep `BASE_PORT + parallelIndex` and per-worker temp prefix |
| App profile env drift | Tests point to wrong DB/API URL | Centralize env construction and preserve existing variable names |
| Teardown kills wrong PID | Developer process risk | Only kill PID from marker created by harness; best-effort and idempotent |
| Harness tests spawn slow app processes | Slower unit suite | Keep unit tests pure; use Playwright smoke for real app lifecycle |

---

## Non-Goals / Guardrails

- Do not change test assertions or app behavior.
- Do not migrate Playwright specs to Vitest in this plan.
- Do not redesign seed scripts.
- Do not remove app-specific teardown files until configs are migrated or wrappers are proven stable.
- Do not introduce new external dependencies.
- Do not use shell-specific process management that breaks cross-platform Node semantics beyond current Linux CI assumptions.

---

## Follow-Up Plans

1. Remove obsolete `*-global-setup.js` files after confirming active configs no longer reference them.
2. Add a semantic E2E API/session/page-object layer from candidate #3.
3. Consider a Playwright config factory that consumes `APP_PROFILES` directly.
4. Add richer lifecycle diagnostics: app stderr capture on readiness failure, seed output on seed failure, and temp artifact retention behind `N3TX_E2E_KEEP_ARTIFACTS=1`.

---

## Critical Files for Implementation

- `tests/frontend/tests/e2e/harness/app-server.js`
- `tests/frontend/tests/e2e/harness/app-profiles.js`
- `tests/frontend/tests/e2e/start-e2e-app.js`
- `tests/frontend/tests/e2e/fixtures/parallel.js`
- `tests/frontend/tests/e2e/global-teardown.js`
