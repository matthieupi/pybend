# Components and navigation

[Frontend guide](ARCHITECTURE.md) · [Lifecycle and custom renderers](../../packages/n3tx-ui/docs/components.md)

Import the module for every tag used by a page. Paths below are browser URLs in
the native combined static namespace, not separate package mounts.

## Component catalog

| Tag / module under `/components/` | Purpose | Main inputs |
|---|---|---|
| `ntx-item.js` | Entity display/edit, validation, methods, delete | `ref="Issue/1"`, `display` |
| `ntx-list.js` | Paginated grid and create modal | `model`, `allow-create`, `headless`, `item-tag`, `item-display`, `router`; optional `query` property or JSON attribute |
| `ntx-table.js` | Sortable table, inline create | `model`, `allow-create`, `router` |
| `ntx-row.js` | Table row with inline editing | Entity ref; normally created by table |
| `ntx-user.js` | User avatar/summary, default larger views | Entity ref |
| `ntx-method.js` | Schema-declared method form/action | `model`, `uuid`, `method`, `layout`, `label` |
| `ntx-stream.js` | Streaming method consumer | Method inputs plus `show-output` |
| `ntx-router.js` | Mounts route views, preserves home slot | `name`, hash behavior |
| `ntx-sidebar.js` | Model navigation and route templates | `router`, `brand`, `subtitle`, `brand-logo` |
| `ntx-topbar.js` | Auth-aware header and user menu | `brand`, slotted navigation |
| `ntx-profile.js` | Profile view | Import when exposing topbar profile route |
| `ntx-theme-button.js` | Configured theme cycling | Explicit placement in shell slots |
| `ntx-icon.js` | Registered SVG, image, emoji or text icon | Icon token |
| `ntx-modal.js` | Modal overlay | Programmatic modal API |
| `ntx-ref-picker.js` | Reference selection/creation | Used by field rendering |
| `ntx-list-field.js` | Array field display/edit | Used by Formidable |

`ntx-favorites` and `ntx-logs` are example-local, not UI package components.
Agent tags are documented by [n3tx-agents](../../packages/n3tx-agents/README.md).

## Entity and collection usage

```html
<!-- With matching module imports and a registered Issue model. -->
<ntx-list model="Issue" allow-create item-display="sm"></ntx-list>
<ntx-item ref="Issue/1" display="lg"></ntx-item>
<ntx-table model="Issue" allow-create></ntx-table>
```

`allow-create` requests a permission-gated affordance, not an access grant.
Size modes are `xs`, `sm`, `md`, `lg`, `xl`, with `row` reserved for table rows.
See [adaptive display](../../packages/n3tx-ui/docs/components.md#adaptive-display-and-styles).
List children are selected through templates, `childTag`, and schema hints; see
[collection extension](../../packages/n3tx-ui/docs/components.md#collections).
For separate filtered lists of the same model, use the optional
[instance-owned method-query contract](../../packages/n3tx-ui/docs/components.md#independent-method-query-lists).
It reuses the native list presentation while isolating membership and pagination;
NTT continues sharing record values.

## Method controls

```html
<!-- Assumes Issue.comment exists in schema and Issue/1 exists. -->
<ntx-method model="Issue" uuid="1" method="comment" label="Comment"></ntx-method>
```

| Attribute | Meaning |
|---|---|
| `method` | Schema method name, not arbitrary HTTP path |
| `uuid` | Member ID for instance-scoped methods |
| `layout` | `fieldset`, `inline`, or `button` |
| `mode` | Manual submit or automatic input-driven invocation |
| `label`, `button-label`, `placeholder`, `widget` | Presentation overrides |
| `icon`, `count-field`, `show-label` | Compact button presentation |
| `forward` | Optional result forwarding target |

Optional parameters can be disclosed separately from required ones. For streams,
import/use `ntx-stream`; `show-output` enables the plain response box. See
[stream lifecycle](../../packages/n3tx-ui/docs/components.md#methods-and-streams)
and [transport limitations](TRANSPORT.md).

## Routing

`Router` is the navigation-state actor; `ntx-router` owns DOM mounting. URL hash
sync is enabled by default. The declared light-DOM children form the home view:

```html
<ntx-router name="main">
  <ntx-list model="Issue"></ntx-list>
</ntx-router>
```

| Hash | Meaning |
|---|---|
| Empty hash / `#` | Home slot |
| `#Issue` or `#Issue/@` | Default collection |
| `#Issue/@table` | Named collection view |
| `#Issue/1` or `#Issue/1/@` | Default member view (`display="lg"`) |
| `#Issue/1/@detail` | Named member view |
| `#Issue/1/comment` | Method/action route |
| `#Issue/1/@comment` | View named comment, not a method |
| `#@profile` | App view, conventionally `ntx-profile` |
| `#Issue/1/Comment/2` | Legacy nested alias; resolves child identity `Comment/2` |

```text
default collection -> renderer.page -> renderer.list -> ntx-list
default member     -> renderer.detail -> renderer.item -> ntx-item
named view         -> renderer[view] -> known fallback -> reject unknown
```

Known fallbacks: list/table for collections; item/detail/chat for members. Path
`@view` takes priority over legacy `?view=...`; the internal `view` query key is
not passed as a component attribute. Other view query parameters are passed on.
View tokens and custom-element tags are validated before mounting.

Legacy nested aliases preserve navigation compatibility, not nested storage or
transport identity. The child mounts with `data-model="Comment" ref="Comment/2"`.
Never synthesize a parent-scoped `$id` from a hash route.

Programmatic navigation after the router is connected:

```javascript
import { getRouter } from '/core/Router.js';
const router = getRouter('main');
router.NAVIGATE('Issue/@table');
// For a page-local view without a serializable hash:
router.NAVIGATE({tag: 'ntx-list', attrs: {model: 'Issue'}, title: 'Issues'});
```

`NAVIGATE` normally pushes history; reset navigation clears it. `BACK` restores
the prior view, and returning home reprojects the existing light-DOM slot.
Browser history/deep links are synchronized, but object routes are programmatic
only. Import selected renderer modules yourself; hash routing does not load
arbitrary modules. Python [HTML view routes](../../packages/n3tx-ui/docs/viewable-mixin.md#html-view-routes)
use a different, conventional module-loading shell.

## Shell composition

Sidebar light-DOM children describe model routes. Tables navigate to table views
but use a compact list in their expanded dropdown; custom list surfaces retain
their tag and receive `model`, `router`, `headless`, and `sidebar-dropdown` attrs.

```html
<ntx-sidebar router="main" brand="Tracker">
  <ntx-table model="Issue" allow-create sidebar-label="Issues"></ntx-table>
  <a href="#" icon="dashboard">Home</a>
  <a href="#@profile" icon="user">Profile</a>
  <ntx-theme-button slot="footer"></ntx-theme-button>
</ntx-sidebar>
```

Import sidebar, table, profile and theme-button modules along with the app router.
`sidebar-label` changes navigation copy, not model identity. Dropdown record
anchors use `#Model/id/@`; selected state recognizes legacy forms too. The
sidebar-specific link renderer owns truncated-label hover/focus tooltips and CSS.
Brand navigation resets to home. Plain `#profile` links normalize to app route
`@profile`; explicit `#@profile` remains explicit.

Topbar navigation is supplied through `slot="nav"`; theme controls use
`slot="user-menu"`. See [theme setup](../../packages/n3tx-ui/docs/styling.md).
Shared icon lookup keys are registered through `registerIcons({...})` from
`/utils/icon-resolver.js`. Registry SVG is trusted markup; do not register
user-supplied SVG. Unknown tokens can display as text rather than an icon.

## Verification references

[Router source](../../packages/n3tx-core/src/n3tx_core/static/core/Router.js),
[route parser/resolver tests](../../tests/frontend/tests/core/route-functions.test.js),
[component tests](../../tests/frontend/tests/components/),
[browser route smoke](../../tests/frontend/tests/e2e/route-grammar-smoke.spec.js).
