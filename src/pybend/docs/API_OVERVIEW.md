# PyBend API Documentation

**Version**: 0.5.0  
**Base URL**: `http://localhost:8000` (default, configurable)  
**Protocol**: REST over HTTP/HTTPS  
**Content-Type**: `application/json`

## Purpose

PyBend automatically generates a complete REST API from your Python model definitions. This documentation explains how to interact with the generated endpoints from a frontend perspective.

## Key Concepts

### Models & Resources

Each PyBend model becomes a REST resource with automatic CRUD endpoints. For example:

- `User` model -> `/users` endpoints
- `Product` model -> `/products` endpoints
- `Comment` model -> `/comments` endpoints

### Automatic Endpoint Generation

For every model marked as `__storable__ = True`, PyBend generates:

1. **Schema Endpoint** - Get the model's JSON schema
2. **Create** - Create new resource
3. **List** - Get all resources
4. **Get** - Get single resource by ID
5. **Update** - Update existing resource
6. **Delete** - Delete resource

### Response Metadata

All CRUD route handlers call `.model_dump(response=True)`, which injects two metadata fields at the top of every response object:

- `$schema` - URL to the model's JSON Schema (e.g., `http://localhost:8000/User`)
- `$id` - URL to this specific resource instance (e.g., `http://localhost:8000/users/1`)

This makes every response self-describing, allowing clients to discover schema information directly from the payload.

### Custom Endpoints

Models can expose additional endpoints using the `@expose_route` decorator. These appear as:

- Static methods -> `/{resource}{custom_path}`
- Class methods -> `/{resource}{custom_path}`
- Instance methods -> `/{resource}/{id}{custom_path}`

### Nested Resources (Many-to-Many)

When models have relationships, PyBend creates nested endpoints:

- Parent resource: `/products`
- Child resources: `/products/{parent_id}/comments`

---

## General API Conventions

### Request Format

All requests must use:
- **Content-Type**: `application/json`
- **Accept**: `application/json`

### Response Format

All successful responses return JSON with `$schema` and `$id` metadata at the top, followed by the resource data:

```json
{
  "$schema": "http://localhost:8000/User",
  "$id": "http://localhost:8000/users/1",
  "id": 1,
  "name": "Alice Johnson",
  "email": "alice@example.com",
  "age": 28
}
```

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
| PUT | Update entire resource | Yes | No |
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
  "$id": "http://localhost:8000/comments/1",
  "id": 1,
  "text": "Great product!",
  "user": 1
}
```

**To Get Full Object** - Make a separate request:
```javascript
// First, get the comment
const comment = await fetch('/comments/1').then(r => r.json());

// Then, get the full user object
const user = await fetch(`/users/${comment.user}`).then(r => r.json());
```

### Nested Resources (Many-to-Many)

When models have list relationships, PyBend creates join tables and nested endpoints:

```python
class Product(ProtoModel):
    comments: Optional[List[Comment]] = []
```

This creates:
- `POST /products/{parent_id}/comments` - Add comment to product
- `GET /products/{parent_id}/comments` - List product's comments
- `PUT /products/{parent_id}/comments/{id}` - Update comment
- `DELETE /products/{parent_id}/comments/{id}` - Remove comment from product

**Important**: The child resource gets additional foreign key field automatically:
```json
{
  "$schema": "http://localhost:8000/Comment",
  "$id": "http://localhost:8000/comments/1",
  "id": 1,
  "text": "Great!",
  "product_id": 5,
  "user": 1
}
```

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

PyBend does not enforce rate limiting by default. Implement in your backend if needed.

---

## Versioning

**Current Version**: No API versioning

The current API is unversioned. Future versions may add:
- Path-based versioning: `/v1/users`, `/v2/users`
- Header-based versioning: `Accept: application/json; version=1`

---

## OpenAPI / Swagger Documentation

### Interactive Documentation

PyBend automatically generates OpenAPI-compliant documentation:

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
