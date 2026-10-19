# n3tx-ui

Schema-driven Web Components, forms, widgets, themes, and the Python
`ViewableMixin` capability. Depends on `n3tx-core` for the browser entity runtime,
actor messaging, transport, and abstract component bridge.

## Start here

```bash
pip install n3tx-ui
# From an N3TX checkout, for package development:
pip install -e packages/n3tx-ui
```

Use the [application tutorial](../../docs/GETTING_STARTED.md), then the
[frontend guide](../../docs/frontend/ARCHITECTURE.md) for a complete native shell.
`create_app(static_dir=...)` serves app overrides and installed package assets
under one root URL namespace. Do not mount only this package at `/static/ui`:
its JavaScript imports core files through sibling paths.

Import `n3tx_ui` **before** defining models with `__ui__` or `__viewable__`.
Importing registers the mixin and schema stage; it is not just a path helper.
`get_static_dir()` returns this package's asset directory for integration tooling.
Installing assets does not register browser tags: import each used component
module, including app-specific renderers.

```text
n3tx-core: NTT / Actor / Matrix / Component / transport
                              ^
n3tx-ui:   components / Formidable / widgets / themes
                              ^
application: model UI hints / shell / custom renderers
```

## Reference map

| Topic | Guide |
|---|---|
| Tags, attributes, navigation and shell composition | [Frontend components](../../docs/frontend/COMPONENTS.md) |
| Component hierarchy, lifecycle, safe renderer extension | [Components](docs/components.md) |
| Runtime-schema forms, reading values, validation | [Formidable](docs/formidable.md) |
| Field rendering and custom widgets | [Widgets](docs/widgets.md) |
| Theme setup, tokens, shadow styles | [Styling](docs/styling.md) |
| Python capability, schema hints, HTML view routes | [ViewableMixin](docs/viewable-mixin.md) |
| Unit and browser checks | [Frontend tests](../../tests/frontend/README.md) |

UI visibility is not server enforcement. Client-side validation is partial;
the backend validates writes. Generated HTML is not a general sanitizer for
untrusted content. See the form and widget references for concrete limitations.
