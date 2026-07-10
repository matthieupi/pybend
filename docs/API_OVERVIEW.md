# N3TX API Documentation

**Version**: 0.8.2
**Base URL**: `http://localhost:8000` (default, configurable)  
**Protocol**: REST over HTTP/HTTPS  
**Content-Type**: `application/json` for generated JSON APIs; optional file upload/download routes use multipart and binary responses.

## Purpose

N3TX automatically generates a complete REST API from your Python model definitions. This documentation explains how to interact with the generated endpoints from a frontend perspective.

## Routing Modes

N3TX supports two routing modes, selectable via the `routing` parameter:

### Direct Routing (default)

```python
app = create_app(models=[Product, User], storage="sqlite:///app.db")
# or explicitly:
app = create_app(models=[Product, User], storage="sqlite:///app.db", routing='direct')
```

HTTP requests go directly to route handlers which call StorableMixin CRUD methods. This is the simplest mode — no actor system involvement in request processing.

### Actor Routing (Level 3)

```python
app = create_app(models=[Product, User], storage="sqlite:///app.db", routing='actor')
```

HTTP requests are translated into TX messages routed through the Matrix actor system:

```
HTTP Request → NetworkAPI adapter → TX → Matrix → ActorModel.handler_crud → StorableMixin
HTTP Response ← NetworkAPI adapter ← TX ← Matrix ← ActorModel.handler_crud ←
```

Actor routing enables interceptors (e.g., authentication at the protocol boundary), lifecycle events, and uniform message-based architecture across all protocols (HTTP, MCP, ActivityPub).

Both modes produce identical API endpoints and response formats. The choice is transparent to API consumers.

---

## Key Concepts

### Models & Resources

Each N3TX model becomes a REST resource with automatic CRUD endpoints. For example:

- `User` model -> `/users` endpoints
- `Product` model -> `/products` endpoints
- `Comment` model -> `/comments` endpoints

### Automatic Endpoint Generation

For every model marked as `__storable__ = True`, N3TX generates:

1. **Schema Endpoint** - Get the model's JSON schema
2. **Create** - Create new resource
3. **List** - Get all resources
4. **Get** - Get single resource by ID
5. **Update** - Update existing resource
6. **Delete** - Delete resource

### Response Metadata

All CRUD route handlers call `.model_response()`, which injects two metadata fields at the top of every response object:

- `$schema` - URL to the model's JSON Schema (e.g., `http://localhost:8000/User`)
- `$id` - canonical class-name URL to this specific resource instance (e.g., `http://localhost:8000/User/1`)

This makes every response self-describing, allowing clients to discover schema information directly from the payload.

### Custom Endpoints

Models can expose additional endpoints using the `@expose_route` decorator. These appear as:

- Static methods -> `/{resource}{custom_path}`
- Class methods -> `/{resource}{custom_path}`
- Instance methods -> `/{resource}/{id}{custom_path}`

Optional packages can also register package-owned routes through model capability
hooks. For example, `n3tx-files` adds multipart/binary routes for `File` because
file bytes cannot be represented as normal JSON method payloads.

### Optional File API (`n3tx-files`)

When an app registers `n3tx_files.File`, these routes are available in addition
to normal File metadata CRUD/schema routes:

| Operation | Method | Path | Body/Response |
|---|---|---|---|
| Upload bytes | POST | `/files/upload` | multipart form field `upload`; returns `File.model_response()` |
| Download bytes | GET | `/files/{id}/download` | binary stream |
| Download mirror | GET | `/File/{id}/download` | binary stream |

Downloads support `Range: bytes=start-end`. Successful range reads return
`206 Partial Content` and `Content-Range`.

`File.resolve(address)` and typed method materialization support these internal
addresses:

```text
n3tx://files/{id}
/files/{id}
/File/{id}
```

### Nested Resources (Many-to-Many)

When models have relationships, N3TX creates nested endpoints:

- Parent resource: `/products`
- Child resources: `/products/{parent_id}/comments`

---

## General API Conventions

### Request Format

Most generated API requests use:
- **Content-Type**: `application/json`
- **Accept**: `application/json`

Exceptions:
- `POST /files/upload` uses `multipart/form-data` with a form field named
  `upload`.
- `GET /files/{id}/download` and `GET /File/{id}/download` return binary bytes,
  not JSON.

### Response Format

All successful responses return JSON with `$schema` and `$id` metadata at the top, followed by the resource data:

```json
{
  "$schema": "http://localhost:8000/User",
  "$id": "http://localhost:8000/User/1",
  "id": 1,
  "name": "Alice Johnson",
  "email": "alice@example.com",
  "age": 28
}
```

### `$id` Migration Note

N3TX response identity is class-name based. A response fetched through either
`/users/1` or `/User/1` advertises:

```json
{
  "$schema": "http://localhost:8000/User",
  "$id": "http://localhost:8000/User/1"
}
```

Legacy table-name routes such as `/users/1` remain supported as compatibility
transport paths, but new clients should treat `$id` as the canonical entity URL.
Nested entities use parent-scoped class-name identity such as
`/Product/1/Comment/2`. N3TX does not emit `$href` or `links`; `$id` is the
single response identity.

All error responses return:
```json
{
  "detail": [
    {
      "file": "path/to/file.py",
      "line": 42,
      "function": "function_name",
      "code": "source code line",
      "error": "Error message"
    }
  ]
}
```

### HTTP Methods Semantics

| Method | Purpose | Idempotent | Safe |
|--------|---------|------------|------|
| GET | Retrieve resource(s) | Yes | Yes |
| POST | Create resource or trigger action | No | No |
| PUT | Update complete writable resource representation (generated routes) | Yes | No |
| DELETE | Remove resource | Yes | No |

### Status Codes

| Code | Meaning | When Used |
|------|---------|-----------|
| 200 | OK | Successful GET, PUT, DELETE |
| 201 | Created | Successful POST (resource created) |
| 400 | Bad Request | Validation error, missing required fields |
| 404 | Not Found | Resource with given ID doesn't exist |
| 422 | Unprocessable Entity | Invalid field type or format |
| 500 | Internal Server Error | Unexpected server error |

---

## Foreign Keys & Relationships

### Understanding Foreign Keys

When a model has a foreign key reference:

```python
class Comment(ProtoModel):
    user: Ref[User]  # Foreign key to User
```

**In Requests** - Send the ID as an integer:
```json
{
  "text": "Great product!",
  "user": 1
}
```

**In Responses** - Receive the ID as an integer, along with `$schema` and `$id` metadata:
```json
{
  "$schema": "http://localhost:8000/Comment",
  "$id": "http://localhost:8000/Product/5/Comment/1",
  "id": 1,
  "text": "Great product!",
  "user": 1
}
```

**To Get Full Object** - Make a separate request:
```javascript
// First, get the comment
const comment = await fetch('/Comment/1').then(r => r.json());

// Then, get the full user object
const user = await fetch(`/users/${comment.user}`).then(r => r.json());
```

### Local Model Collections

When models have local owned collections, N3TX stores ordered child ids on the
parent and returns hydrated child objects in the parent response:

```python
class Product(ProtoModel):
    comments: list[Comment] = Field(default=[])
```

Example response:

```json
{
  "$schema": "http://localhost:8000/Product",
  "$id": "http://localhost:8000/Product/5",
  "id": 5,
  "comments": [
    {
      "$schema": "http://localhost:8000/Comment",
      "$id": "http://localhost:8000/Comment/1",
      "id": 1,
      "text": "Great!",
      "user": "http://localhost:8000/User/1"
    }
  ]
}
```

Use custom model methods for domain-specific append/toggle actions. Shared
relationships should be modeled with explicit link models; `ManyToMany[T]` is a
legacy helper for existing shared-link cases.

---

## Data Types

### Type Mapping

| Python Type | JSON Type | Example |
|-------------|-----------|---------|
| `str` | string | `"hello"` |
| `int` | number | `42` |
| `float` | number | `3.14` |
| `bool` | boolean | `true` |
| `Optional[T]` | T or null | `"value"` or `null` |
| `List[T]` | array | `[1, 2, 3]` |
| `Ref[Model]` | number | `1` |
| `datetime` (as string) | string (ISO 8601) | `"2025-01-15T10:00:00Z"` |
| `Enum` | string | `"pending"` |

### Date/Time Format

All datetime fields are strings in ISO 8601 format:
- `"2025-01-15T10:00:00Z"` (UTC)
- `"2025-01-15T10:00:00-05:00"` (with timezone)

Frontend should parse these using `new Date()` or date libraries.

### Enums

Enum fields accept and return string values:

```python
class OrderStatus(str, Enum):
    PENDING = "pending"
    SHIPPED = "shipped"
```

Valid values in requests:
```json
{
  "status": "pending"
}
```

Invalid values return 422 with validation error.

---

## Error Handling

### Error Response Structure

All errors return this structure:
```json
{
  "detail": [
    {
      "file": "models/product_model.py",
      "line": 42,
      "function": "apply_discount",
      "code": "self.price = self.price * (1 - percentage / 100)",
      "error": "Discount percentage must be between 0 and 100"
    }
  ]
}
```

### Common Error Scenarios

#### 1. Missing Required Field (400)

Request:
```json
{
  "name": "Product"
}
```

Response:
```json
{
  "detail": [
    {
      "file": "...",
      "error": "Field required: price"
    }
  ]
}
```

#### 2. Invalid Field Type (422)

Request:
```json
{
  "name": "Product",
  "price": "not-a-number"
}
```

Response (422):
```json
{
  "detail": "Invalid field 'price': could not convert string to float"
}
```

#### 3. Resource Not Found (404)

Request: `GET /users/999`

Response (404):
```json
{
  "detail": "Not found"
}
```

#### 4. Validation Error (400)

Custom validation in model fails:

Response (400):
```json
{
  "detail": [
    {
      "error": "Email must be unique"
    }
  ]
}
```

### Frontend Error Handling Pattern

```javascript
async function createUser(userData) {
  try {
    const response = await fetch('/users', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(userData)
    });
    
    if (!response.ok) {
      const error = await response.json();
      
      // Extract error message
      const message = error.detail?.[0]?.error || 'Unknown error';
      
      // Handle based on status
      switch (response.status) {
        case 400:
          // Validation error - show to user
          showValidationError(message);
          break;
        case 404:
          // Not found - redirect or show message
          showNotFoundError();
          break;
        case 422:
          // Invalid format - show field error
          showFieldError(message);
          break;
        default:
          // Server error - log and show generic message
          console.error('API Error:', error);
          showGenericError();
      }
      return null;
    }
    
    return await response.json();
  } catch (err) {
    // Network error
    console.error('Network error:', err);
    showNetworkError();
    return null;
  }
}
```

---

## Rate Limiting

**Current Version**: Not implemented

N3TX does not enforce rate limiting by default. Implement in your backend if needed.

---

## Versioning

**Current Version**: No API versioning

The current API is unversioned. Future versions may add:
- Path-based versioning: `/v1/users`, `/v2/users`
- Header-based versioning: `Accept: application/json; version=1`

---

## OpenAPI / Swagger Documentation

### Interactive Documentation

N3TX automatically generates OpenAPI-compliant documentation:

**FastAPI**: Visit `http://localhost:8000/docs`

This provides:
- Interactive API explorer
- Request/response schemas
- Try-it-out functionality

### Programmatic Schema Access

Get the schema for any model:

```bash
GET /{ModelName}
```

Example:
```bash
GET /User
```

Response:
```json
{
  "$schema": "http://localhost:8000/Schema",
  "$id": "http://localhost:8000/User",
  "type": "object",
  "properties": {
    "id": {"type": "integer"},
    "name": {"type": "string"},
    "email": {"type": "string"}
  },
  "required": ["name", "email"],
  "methods": {
    "login": {
      "route": "/login",
      "methods": ["POST"],
      "parameters": {...},
      "returns": {...}
    }
  },
  "$defs": {
    "User": {
      "$id": "http://localhost:8000/User"
    }
  }
}
```

The `schema()` method adds `$schema` (pointing to `{API_URL}/Schema`) and `$id` (pointing to `{API_URL}/{ClassName}`) to the top-level schema dict, and `$id` to each `$defs` entry.

Storable models can be accessed through either the original table-name API or
the class-name JSON mirror grammar:

```text
GET  /users/1  -> legacy table-name JSON read
GET  /User/1   -> class-name read mirror of the same entity
GET  /User/_   -> class-name collection mirror
POST /User     -> class-name create mirror
PUT  /User/1   -> class-name update mirror
```

Both update route grammars currently validate a complete model body. Callers
must include every required field and preserve current defaulted collection/JSON
values (`list[T]`, `list[Ref[T]]`, plain lists, and dictionaries). Omitted
defaulted fields may be materialized as `[]`, `{}`, or another default and then
persisted. This HTTP behavior is intentionally documented as a compatibility
constraint; Python `Model.update(id, patch)`, actor TX updates, and agent update
tools accept narrow patches. See [CRUD Endpoints](API_CRUD_ENDPOINTS.md#update-resource)
for safe usage guidance.

Entity payloads keep `$schema` pointing to `/{ClassName}` and now advertise
`$id` as `/{ClassName}/{id}`, even when fetched through the legacy table-name
route. Literal custom methods may also be mirrored under class-name paths, for
example `/User/1/run`; there is no generic method catch-all.

View routes reserve `@` for HTML/component entrypoints, for example
`GET /User/@` and frontend hashes such as `#User/@table`; those routes are not
JSON data routes.

Custom method responses, including auth methods such as `/users/login` and
`/users/register`, may be returned either as the method payload directly or under
`data` when response debugging/enveloping is enabled. Browser test helpers should
read auth tokens with `body.token ?? body.data?.token` rather than assuming only
one envelope shape.

This is useful for:
- Dynamic form generation
- Client-side validation
- Auto-generating TypeScript types

---

## CORS

**FastAPI Backend**: CORS is enabled for all origins by default.

If you need to restrict origins, modify `backend.py`:

```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://yourdomain.com"],  # Specific domains
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

---

## Next Steps

- [Standard CRUD Endpoints](./API_CRUD_ENDPOINTS.md) - Complete reference for auto-generated endpoints
- [Custom Endpoints](./API_CUSTOM_ENDPOINTS.md) - How custom `@expose_route` methods work
- [Data Models Reference](./API_DATA_MODELS.md) - Schema for each model with examples

---

## Getting Help

If you encounter issues not covered here:

1. Check the interactive documentation at `/docs`
2. Examine the model schema: `GET /{ModelName}`
3. Check response error details for specific issues
4. Refer to example implementations in the Examples documentation
