---
name: n3tx-ui-components
description: N3TX Web Components, custom renderers, Component/NTTElement/ListElement lifecycle, router-mounted components, and frontend customization. Use when creating or changing N3TX UI components.
argument-hint: "<component task>"
---

# N3TX UI Components

N3TX UI customization should compose with schema-driven components.

## Component hierarchy

```text
Component
  -> NTTElement       single entity base
       -> ntx-item
  -> ListElement      collection base
       -> ntx-list, ntx-table
  -> ntx-method
       -> ntx-stream
            -> NTTStreamAgent
```

## Custom renderer pattern

Backend schema selects the component:

```python
class Product(ActorModel):
    __ui__ = {'renderer': {'detail': 'my-product-detail', 'list': 'ntx-list'}}
```

Frontend registers the element:

```javascript
import { NTTElement } from './components/NTTElement.js';

class MyProductDetail extends NTTElement {
  render() {
    super.render?.();
    // Use this.value / schema-driven data, not duplicated contracts.
  }
}

customElements.define('my-product-detail', MyProductDetail);
```

## Lifecycle guidance

- `connectedCallback()` attaches the component and loads schema/entity data.
- `prerender()` creates stable structure before schema arrives.
- `render()` is schema-aware and should be additive.
- For streams, cancel in `disconnectedCallback()`.

## Router-mounted attrs

Router sets attributes such as:

- `model="Product"` for collection routes
- `ref="Product/1"` or full URL for entity routes
- `method="run"` for action routes
- `data-model` for nested semantic model identity

## Guardrails

- Do not duplicate backend model fields in component constants.
- Do not bypass N3TX transport for entity/method calls.
- Do not wipe structural DOM created by `prerender()` in `render()`.
- Do not make custom components own authorization; read schema/permissions.

## Verification

- Component is registered before route attempts to mount it.
- It renders from schema/entity data.
- It handles loading/empty/error states.
- Vitest covers schema-to-DOM behavior where possible.

## Source-reading policy

Inspect framework source only when docs/skills are insufficient, do not cover the intended implementation, or observed behavior contradicts docs. Update/propose docs when gaps are found.
