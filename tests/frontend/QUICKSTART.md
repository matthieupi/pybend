# Frontend test quickstart

For building an application, use [Getting started](../../docs/GETTING_STARTED.md)
and the [frontend guide](../../docs/frontend/ARCHITECTURE.md).

With local Node test dependencies available, from `tests/frontend/`:

```bash
npm test
# Or one mocked integration group:
npm test -- tests/integration/schema-bootstrap.test.js
```

With Playwright Chromium and the example app's Python dependencies available:

```bash
npm run test:e2e
```

The default browser lane starts isolated core app servers and temporary databases
per worker. Do not start a server manually or use a live database. The
[harness guide](README.md) explains interpreter selection, suite choices, readiness
helpers, cleanup, output artifacts and troubleshooting boundaries.
