# N3TXTX Quickstart

## 1. Setup

Point the framework to your backend in `config.js`:

```js
export const config = {
    API_URL: 'http://localhost:5000',
    // ...
};
```

## 2. Minimal Page

```html
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>My App</title>
    <link rel="stylesheet" href="./dark-theme.css">
</head>
<body>

    <!-- Display a list of Products from the backend -->
    <ntx-list model="Product"></ntx-list>

    <script type="module">
        import { Matrix, matrix } from './core/Matrix.js';
        import { N3TX } from './core/N3TX.js';
        import { config } from './config.js';
        import './components/ntx-item.js';
        import './components/ntx-list.js';
    </script>

</body>
</html>
```

That's it. The `<ntx-list>` component will:
1. Fetch the schema from `GET /Product`
2. Discover the CRUD endpoint from `__tablename__` (e.g. `/products`)
3. Pull all records and render editable `<ntx-item>` cards

## 3. Key Concepts

| Concept | What it is |
|---------|-----------|
| **Matrix** | The root actor — routes all messages between local actors and the backend |
| **N3TX** | Named Transfer Type — type registry (static) + entity base class (instance) |
| **DynClass** | DynamicClass — runtime-generated N3TX subclass per model (e.g. "Product"), holds schema and instances |
| **TX** | A message (transaction) flowing through the actor system |
| **Component** | Base class for web components — connects HTML elements to the actor system |

## 4. Web Components

### `<ntx-list>`

Displays all records for a model.

```html
<ntx-list model="Product"></ntx-list>
```

- `model` — the backend model name (must match the registered name, e.g. `Product`, `User`)

### `<ntx-item>`

Displays a single record. Usually created automatically by `<ntx-list>`, but can be used standalone:

```html
<ntx-item ref="Product/4"></ntx-item>
```

- `ref` — the N3TX address (`ModelName/id`)
- Click the pencil icon to edit, click save to persist changes to the backend

## 5. How It Works

```
Browser                          Backend
-------                          -------
<ntx-list model="Product">
   |
   +- ATTACH --> N3TX (static)
   |              +- GET /Product -----------> Schema
   |              +- Creates DynClass "Product"
   |              +- GET /products -----------> [records]
   |              |
   |              +- DynClass.READ creates N3TX instances
   |                    (Product/1, Product/2, ...)
   |
   +- Renders <ntx-item ref="Product/1">
                   |
                   +- ATTACH --> N3TX --> DynClass --> N3TX instance
                   |              +- DESCRIBE --> Item
                   |
                   +- On save: UPDATE --> N3TX --> PUT /products/1
```

## 6. Configuration Reference

| Key | Default | Description |
|-----|---------|-------------|
| `API_URL` | `http://localhost:5000` | Backend base URL |
| `WS_URL` | `ws://localhost:8765` | WebSocket URL (when using WS transport) |
| `LOGGING` | `3` | Log verbosity (0=off, 3=verbose) |
| `DEBUG` | `true` | Enable debug output |

## Further Reading

See the `docs/` folder:
- `ARCHITECTURE.md` — full system design
- `ACTORS.md` — the actor model in depth
- `COMPONENTS.md` — web component API
- `MESSAGE_PROTOCOL.md` — TX message format and flows
- `TRANSPORT.md` — HTTP and WebSocket transport layer
