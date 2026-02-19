# NTTTX Quickstart

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
    <ntt-list model="Product"></ntt-list>

    <script type="module">
        import { Matrix, matrix } from './core/Matrix.js';
        import { NTT } from './core/NTT.js';
        import { config } from './config.js';
        import './components/ntt-item.js';
        import './components/ntt-list.js';
    </script>

</body>
</html>
```

That's it. The `<ntt-list>` component will:
1. Fetch the schema from `GET /Product`
2. Discover the CRUD endpoint from `__tablename__` (e.g. `/products`)
3. Pull all records and render editable `<ntt-item>` cards

## 3. Key Concepts

| Concept | What it is |
|---------|-----------|
| **Matrix** | The root actor — routes all messages between local actors and the backend |
| **NTT** | Named Transfer Type — type registry (static) + entity base class (instance) |
| **DynClass** | DynamicClass — runtime-generated NTT subclass per model (e.g. "Product"), holds schema and instances |
| **TX** | A message (transaction) flowing through the actor system |
| **Component** | Base class for web components — connects HTML elements to the actor system |

## 4. Web Components

### `<ntt-list>`

Displays all records for a model.

```html
<ntt-list model="Product"></ntt-list>
```

- `model` — the backend model name (must match the registered name, e.g. `Product`, `User`)

### `<ntt-item>`

Displays a single record. Usually created automatically by `<ntt-list>`, but can be used standalone:

```html
<ntt-item ref="Product/4"></ntt-item>
```

- `ref` — the NTT address (`ModelName/id`)
- Click the pencil icon to edit, click save to persist changes to the backend

## 5. How It Works

```
Browser                          Backend
-------                          -------
<ntt-list model="Product">
   |
   +- ATTACH --> NTT (static)
   |              +- GET /Product -----------> Schema
   |              +- Creates DynClass "Product"
   |              +- GET /products -----------> [records]
   |              |
   |              +- DynClass.READ creates NTT instances
   |                    (Product/1, Product/2, ...)
   |
   +- Renders <ntt-item ref="Product/1">
                   |
                   +- ATTACH --> NTT --> DynClass --> NTT instance
                   |              +- DESCRIBE --> Item
                   |
                   +- On save: UPDATE --> NTT --> PUT /products/1
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
