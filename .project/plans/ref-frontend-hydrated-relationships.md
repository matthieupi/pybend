# Frontend Hydrated Relationship Migration

## ✅ Outcome

Align the frontend with the simplified backend relationship contract:

- Scalar `T` remains a hydrated child object.
- `list[T]` remains an ordered array of hydrated child objects.
- Child identity always comes from its flat backend `$id`, such as `/Comment/2`.
- The frontend never synthesizes parent-scoped entity URLs.
- `AgentActor.tools: list[AgentTool]` renders hydrated tool objects correctly.
- Explicit pointer forms retain their existing ref/populate behavior.

This is a dedicated frontend plan. It must not modify backend storage, cascade, authorization, or route generation.

## 📍 Contract

```text
Owned backend relationship response
  T       -> {$schema, $id, id, ...}
  list[T] -> [{$schema, $id, id, ...}, ...]

Frontend
  -> register child DynamicClass instances
  -> preserve objects in parent value
  -> use child $id as authoritative href
  -> render without refetching
```

`Ref[T]` and `list[Ref[T]]` remain pointers. Do not globally remove href handling.

## 💻 Method Signature Surface

```text
packages/n3tx-core/.../NTT.js
  / function normalizePopulated(entity, schema)
  / DynamicClass.ATTACH(data, tx)
  / DynamicClass.prototype._response_(data, tx)

packages/n3tx-agents/.../ntx-agent.js
  / renderTools()
  / renderToolsColored()
  / _toolName(tool)
  + _toolDescription(tool)
```

No backend signatures change in this plan.

## 🛠️ Implementation steps

### 1. Add failing hydrated-object runtime tests

**Files**

- `tests/frontend/tests/core/NTT.test.js`
- `tests/frontend/tests/integration/entity-lifecycle.test.js`
- `tests/frontend/tests/integration/nested-entities.test.js`

Test a parent response containing scalar and collection children:

```javascript
{
  id: 1,
  $id: "/Product/1",
  featured_comment: {
    id: 2,
    $schema: "/Comment",
    $id: "/Comment/2",
    text: "Featured",
  },
  comments: [{
    id: 3,
    $schema: "/Comment",
    $id: "/Comment/3",
    text: "Child",
  }],
}
```

Assert:

- Parent values remain objects, not href strings.
- Child instances are registered in the appropriate DynamicClass cache.
- Child `href` equals its flat `$id`.
- Array order is retained.
- No fetch occurs for already hydrated children.

### 2. Narrow `normalizePopulated()`

**File**

- `packages/n3tx-core/src/n3tx_core/static/core/NTT.js`

Remove generic conversion of hydrated model objects into href arrays.

For ordinary `T`/`list[T]`:

1. Resolve child type from `$schema` or unambiguous schema metadata.
2. Register the hydrated child.
3. Preserve the child object in the parent value.
4. Recursively normalize explicit pointer fields inside the child if needed.

For compatibility wrappers such as `{data, meta}`, preserve hydrated `data` objects rather than reducing them to hrefs. Do not invent a new public metadata API in this pass.

Restrict href normalization to schema shapes that unambiguously represent `Ref[T]` or `list[Ref[T]]`; generic `$ref` alone may also describe owned `T`.

### 3. Remove parent-scoped identity overrides

In `DynamicClass.ATTACH`:

```diff
- instance.href = tx.meta?.href || instance.href
+ instance.href = instance.value?.$id || instance.href
```

For missing instances, fetch through the flat class member URL derived from the child DynamicClass. Do not use parent-scoped `tx.meta.href` as entity identity or transport URL.

Update component tests that currently expect `/Product/1/Comment/2` to expect `/Comment/2`.

### 4. Fix optimistic relationship responses

Current toggle handling synthesizes:

```javascript
`${this.href}/${field}/${data.id}`
```

Delete that identity construction.

Preferred behavior:

- If the method response includes a hydrated child or `$id`, register and apply it.
- If it includes only an ID, derive the flat URL from the relationship target schema—not the parent URL—and trigger the existing authoritative refresh when target type is unavailable.
- Never construct `/Parent/id/field/child-id`.

Add tests for comment/like/favorite responses and verify state contains either a hydrated object or a valid flat child identity until refresh.

### 5. Render hydrated `AgentTool` objects

**Files**

- `packages/n3tx-agents/src/n3tx_agents/static/components/ntx-agent.js`
- new `tests/frontend/tests/components/ntx-agent.test.js`

Implement:

```javascript
_toolName(tool) {
  if (tool && typeof tool === "object") {
    return tool.target || tool.name || `⚙ #${tool.id ?? "?"}`;
  }
  return this._legacyToolName(String(tool ?? ""));
}

_toolDescription(tool) {
  return tool && typeof tool === "object"
    ? tool.description || ""
    : "";
}
```

Apply the same extraction in normal and colored rendering. Escape labels and descriptions. Do not fetch tools; they are already hydrated.

Test hydrated tools, descriptions, multiple tools, empty state, actor-address strings, and legacy URL strings.

### 6. Separate generic routing from removed relationship routes

Review:

- `tests/frontend/tests/core/route-functions.test.js`
- `tests/frontend/tests/core/Router.test.js`
- `tests/frontend/tests/components/ntx-router.test.js`
- `packages/n3tx-core/src/n3tx_core/static/core/Router.js`

Preserve generic multi-segment application routing where independently useful. Remove or relabel only assertions claiming parent-scoped nested paths are canonical relationship identity or generated CRUD routes.

No active test should present `/Parent/id/Child/id` as the current child `$id`.

### 7. Update frontend documentation

Update:

- `FRONTEND.md`
- `tests/frontend/README.md`
- `docs/frontend/ACTORS.md`
- `docs/frontend/COMPONENTS.md`
- `docs/frontend/PACKAGE_ARCHITECTURE.md`
- `packages/n3tx-ui/docs/components.md`
- `packages/n3tx-agents/docs/agent-actor.md`

Document:

- Owned children arrive hydrated automatically.
- Parent values preserve object/object-array shape.
- `$id` is flat and backend-authoritative.
- `populate` is for pointer relationships, not owned objects.
- Nested relationship routes and ListRef href arrays are removed.
- Agent tools are hydrated `AgentTool` records.

Leave historical `.project/**` and changelogs untouched unless they incorrectly claim to be active reference docs.

## 🔎 Review checkpoints

### Checkpoint 1 — Runtime representation

```diff
- comments: ["/Product/1/Comment/2"]
+ comments: [{id: 2, $id: "/Comment/2", $schema: "/Comment", ...}]
```

### Checkpoint 2 — Identity

```diff
- child.href = tx.meta.href
+ child.href = child.value.$id
```

### Checkpoint 3 — Agent tools

```diff
- tools.map(href => String(href))
+ tools.map(tool => tool.target ?? legacyStringFallback(tool))
```

## ⚠️ Risks

| Risk | Mitigation |
|---|---|
| Generic `$ref` cannot distinguish owned and pointer fields | Use runtime `$schema` plus explicit schema markers; do not guess |
| Existing components expect strings | Update focused consumers and preserve string fallback only for pointer/legacy inputs |
| Router supports unrelated nested views | Relabel relationship tests rather than broadly deleting generic routing |
| Optimistic response lacks child type | Trigger authoritative refresh instead of synthesizing parent-scoped identity |
| Cache gets duplicate child objects | Key by canonical flat `$id` and reuse existing DynamicClass registration |

## 🧪 Verification

```bash
cd /workspace/tests/frontend
npx vitest run \
  tests/core/NTT.test.js \
  tests/core/Component.test.js \
  tests/integration/entity-lifecycle.test.js \
  tests/integration/nested-entities.test.js \
  tests/components/ntx-agent.test.js \
  tests/components/ntx-agents.test.js

npx vitest run
npx playwright test --config=tests/e2e/playwright.config.js
```

## ✅ Acceptance criteria

- Hydrated `T` remains an object in frontend state.
- Hydrated `list[T]` remains an ordered object array.
- Child DynamicClass instances use flat backend `$id`.
- No frontend path synthesizes parent-scoped child identity.
- Existing hydrated children are not refetched.
- Explicit pointer forms retain ref/populate compatibility.
- Agent tools render meaningful target and description values.
- Active frontend tests/docs no longer claim ListRef or nested relationship routes are current behavior.
- Full frontend unit and E2E suites pass.

### Critical Files for Implementation

- `packages/n3tx-core/src/n3tx_core/static/core/NTT.js`
- `packages/n3tx-core/src/n3tx_core/static/core/Router.js`
- `packages/n3tx-agents/src/n3tx_agents/static/components/ntx-agent.js`
- `tests/frontend/tests/integration/nested-entities.test.js`
- `tests/frontend/tests/components/ntx-agent.test.js`
