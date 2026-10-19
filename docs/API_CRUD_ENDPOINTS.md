# Standard CRUD Endpoints

This document describes the auto-generated CRUD endpoints available for every storable model in N3TX.

All CRUD route handlers call `.model_response()`, which injects `$schema` and `$id` metadata into every response. This runs the composable dump pipeline (`proto_dump`), making each response self-describing.

## Endpoint Pattern

For a model with `__tablename__ = 'users'`, N3TX generates:

| Operation | Method | Path | Description |
|-----------|--------|------|-------------|
| Schema | GET | `/User` | Get model JSON schema |
| Class-name list mirror | GET | `/User/_` | Explicit collection mirror of `/users` |
| Class-name create mirror | POST | `/User` | Create mirror of `/users` |
| Class-name read mirror | GET | `/User/{id}` | Read mirror of `/users/{id}` |
| Class-name update mirror | PUT | `/User/{id}` | Update mirror of `/users/{id}` |
| Class-name delete mirror | DELETE | `/User/{id}` | Delete mirror of `/users/{id}` |
| Create | POST | `/users` | Create new user |
| List | GET | `/users` | Get all users |
| Read | GET | `/users/{id}` | Get specific user |
| Update | PUT | `/users/{id}` | Update user |
| Delete | DELETE | `/users/{id}` | Delete user |

**Note**: `GET /{ClassName}` remains the schema endpoint. Class-name collection
reads use the explicit `_` marker (`GET /{ClassName}/_`), and class-name writes
reuse the same handlers or actor TX contracts as table-name routes. Literal
`@expose_route` methods may also have class-name mirrors; there is no generic
method catch-all.

---

## Get Model Schema

Retrieve the JSON schema definition for a model, including its fields, validation rules, and custom methods.

### Request

```
GET /{ModelName}
```

**Path Parameters**: None

**Query Parameters**: None

**Request Body**: None

### Response

**Status**: 200 OK

**Body**: JSON schema object with `$schema` and `$id` at the top level, and `$id` on each `$defs` entry.

```json
{
  "$schema": "http://localhost:8000/Schema",
  "$id": "http://localhost:8000/User",
  "type": "object",
  "properties": {
    "id": {
      "type": "integer",
      "title": "Id"
    },
    "name": {
      "type": "string",
      "title": "Name"
    },
    "email": {
      "type": "string",
      "title": "Email"
    },
    "age": {
      "type": "integer",
      "title": "Age"
    }
  },
  "required": ["name", "email"],
  "title": "User",
  "methods": {
    "login": {
      "route": "/login",
      "methods": ["POST"],
      "scope": "staticmethod",
      "parameters": {
        "email": {"type": "string"},
        "password": {"type": "string"}
      },
      "returns": {
        "type": "$ref",
        "$ref": "#/$defs/User"
      }
    }
  },
  "$defs": {
    "User": {
      "$id": "http://localhost:8000/User"
    }
  }
}
```

**Frontend Usage**:
- Generate forms dynamically
- Validate inputs before sending
- Discover available custom methods
- Generate TypeScript interfaces

### Example

```javascript
// Fetch schema to build dynamic form
const schema = await fetch('http://localhost:8000/User').then(r => r.json());

// Schema includes $schema and $id at top level
console.log(schema['$schema']); // "http://localhost:8000/Schema"
console.log(schema['$id']);     // "http://localhost:8000/User"

// Extract required fields
const requiredFields = schema.required; // ["name", "email"]

// Build form fields
Object.entries(schema.properties).forEach(([key, prop]) => {
  if (key === 'id') return; // Skip ID field
  
  createFormField({
    name: key,
    type: prop.type,
    required: requiredFields.includes(key)
  });
});
```

---

## Create Resource

Create a new resource instance.

### Request

```
POST /{resource}
```

**Path Parameters**: None

**Query Parameters**: None

**Request Headers**:
- `Content-Type: application/json` (required)

**Request Body**: JSON object matching model schema (excluding `id`)

Example for User model:
```json
{
  "name": "Alice Johnson",
  "email": "alice@example.com",
  "age": 28
}
```

**Field Requirements**:
- All fields marked `required` in schema must be present
- `id` field should NOT be included (auto-generated)
- Optional fields can be omitted
- Foreign keys should be integers (IDs)

### Response

**Success Status**: 201 Created

**Success Body**: Created resource with assigned ID, plus `$schema` and `$id` metadata

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

**Error Responses**:

| Status | Cause | Detail |
|--------|-------|--------|
| 400 | Missing required field | `"Missing field: email"` |
| 400 | Validation error | Custom validation message |
| 422 | Invalid field type | `"Invalid field 'age': invalid literal for int()"` |

### Example

```javascript
// Create new user
async function createUser(userData) {
  const response = await fetch('http://localhost:8000/users', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json'
    },
    body: JSON.stringify({
      name: 'Alice Johnson',
      email: 'alice@example.com',
      age: 28
    })
  });
  
  if (!response.ok) {
    const error = await response.json();
    console.error('Failed to create user:', error.detail);
    return null;
  }
  
  const user = await response.json();
  // user.$schema === "http://localhost:8000/User"
  // user.$id === "http://localhost:8000/User/1"
  return user;
}
```

---

## List Resources

Retrieve instances of a resource, with optional pagination.

### Request

```
GET /{resource}
GET /{resource}?limit=20&offset=0
```

**Path Parameters**: None

**Query Parameters**:

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `limit` | integer (1–100) | No | Maximum number of records to return. Enables paginated response format. |
| `offset` | integer (>= 0) | No | Number of records to skip. Used with `limit` for page navigation. |

**Request Body**: None

### Response

#### Without pagination (backward compatible)

When no `limit` parameter is provided, returns a plain array:

**Status**: 200 OK

**Body**: Array of resource objects, each with `$schema` and `$id`

```json
[
  {
    "$schema": "http://localhost:8000/User",
    "$id": "http://localhost:8000/User/1",
    "id": 1,
    "name": "Alice Johnson",
    "email": "alice@example.com",
    "age": 28
  },
  {
    "$schema": "http://localhost:8000/User",
    "$id": "http://localhost:8000/User/2",
    "id": 2,
    "name": "Bob Smith",
    "email": "bob@example.com",
    "age": 32
  }
]
```

#### With pagination

When `limit` is provided, returns a wrapped object with `data` and `meta`:

**Status**: 200 OK

**Body**:

```json
{
  "data": [
    {
      "$schema": "http://localhost:8000/User",
      "$id": "http://localhost:8000/User/1",
      "id": 1,
      "name": "Alice Johnson",
      "email": "alice@example.com",
      "age": 28
    },
    {
      "$schema": "http://localhost:8000/User",
      "$id": "http://localhost:8000/User/2",
      "id": 2,
      "name": "Bob Smith",
      "email": "bob@example.com",
      "age": 32
    }
  ],
  "meta": {
    "total": 47,
    "limit": 20,
    "offset": 0,
    "has_more": true
  }
}
```

**Meta fields**:

| Field | Type | Description |
|-------|------|-------------|
| `total` | integer | Total number of matching records in the database. |
| `limit` | integer | The limit that was requested. |
| `offset` | integer | The offset that was applied. |
| `has_more` | boolean | `true` if there are more records beyond this page. |

**Edge Cases**:
- Empty database returns empty array `[]` (unpaginated) or `{"data": [], "meta": {"total": 0, ...}}` (paginated)
- No sorting by default (order is implementation-defined)
- `limit` without `offset` defaults to offset 0
- `offset` without `limit` is ignored (no effect)

### Examples

```javascript
// Get all users (unpaginated — backward compatible)
const users = await fetch('http://localhost:8000/users')
  .then(r => r.json());

console.log(`Found ${users.length} users`);

// Display in UI
users.forEach(user => {
  console.log(user['$id']); // e.g., "http://localhost:8000/User/1"
  renderUserCard(user);
});
```

```javascript
// Paginated request — first page
const page1 = await fetch('http://localhost:8000/users?limit=20&offset=0')
  .then(r => r.json());

console.log(`Showing ${page1.data.length} of ${page1.meta.total} users`);

// Load next page if available
if (page1.meta.has_more) {
  const page2 = await fetch('http://localhost:8000/users?limit=20&offset=20')
    .then(r => r.json());
  console.log(`Page 2: ${page2.data.length} users`);
}
```

```bash
# curl examples
curl http://localhost:8000/users                      # All records (plain array)
curl 'http://localhost:8000/users?limit=10'           # First 10 (paginated)
curl 'http://localhost:8000/users?limit=10&offset=10' # Next 10
```

**Note**: The frontend `<ntx-list>` component uses pagination automatically, requesting 20 items at a time and rendering a "Load More" button when `has_more` is true.

---

## Get Single Resource

Retrieve a specific resource by ID.

### Request

```
GET /{resource}/{id}
```

**Path Parameters**:
- `id` (integer, required): Resource ID

**Query Parameters**: None

**Request Body**: None

### Response

**Success Status**: 200 OK

**Success Body**: Resource object with `$schema` and `$id`

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

**Error Responses**:

| Status | Cause | Detail |
|--------|-------|--------|
| 404 | Resource not found | `"Not found"` |

### Example

```javascript
// Get specific user
async function getUser(userId) {
  const response = await fetch(`http://localhost:8000/users/${userId}`);
  
  if (response.status === 404) {
    console.error('User not found');
    return null;
  }
  
  return await response.json();
}

// Usage
const user = await getUser(1);
if (user) {
  console.log(user['$schema']); // "http://localhost:8000/User"
  displayUserProfile(user);
}
```

---

## Update Resource

Update an existing resource.

> **Generated-route contract:** HTTP `PUT` is patch-oriented. Omitted fields
> remain unchanged. Supplied fields are merged with the current entity and the
> complete result is validated through the original model before only the
> supplied fields are persisted.

### Request

```
PUT /{resource}/{id}
```

**Path Parameters**:
- `id` (integer, required): Resource ID

**Query Parameters**: None

**Request Headers**:
- `Content-Type: application/json` (required)

**Request Body**: Partial writable model representation

```json
{
  "name": "Alice Johnson",
  "email": "alice@example.com",
  "age": 29
}
```

**Update Behavior**:
- Omitted fields remain unchanged, including required and defaulted fields
- The merged complete entity must pass the original model's validation
- An explicit `[]` or `{}` replaces/clears the complete stored field
- Do not send the `id` field; identity comes from the route
- Backend-owned protected fields are stripped
- Foreign keys can be updated by passing new ID

For append/remove/toggle behavior on relationship collections, prefer a
domain-specific `@expose_route` method instead of client-side array replacement.

### Response

**Success Status**: 200 OK

**Success Body**: Updated resource (complete object) with `$schema` and `$id`

```json
{
  "$schema": "http://localhost:8000/User",
  "$id": "http://localhost:8000/User/1",
  "id": 1,
  "name": "Alice Johnson",
  "email": "alice@example.com",
  "age": 29
}
```

**Error Responses**:

| Status | Cause | Detail |
|--------|-------|--------|
| 404 | Resource not found | `"Not found"` |
| 400 | Validation error | Custom validation message |
| 422 | Invalid field type | `"Invalid field 'age': ..."` |

### Example

```javascript
// Update user's email
async function updateUserEmail(userId, newEmail) {
  const current = await getUser(userId);
  const { id, $id, $schema, ...writable } = current;
  const response = await fetch(`http://localhost:8000/users/${userId}`, {
    method: 'PUT',
    headers: {
      'Content-Type': 'application/json'
    },
    body: JSON.stringify({ ...writable, email: newEmail })
  });
  
  if (!response.ok) {
    const error = await response.json();
    console.error('Update failed:', error.detail);
    return null;
  }
  
  return await response.json(); // Complete updated object with $schema and $id
}

// Update multiple fields while preserving the complete current representation
await fetch('http://localhost:8000/users/1', {
  method: 'PUT',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    name: 'Alice Johnson',
    age: 29,
    email: 'alice.new@example.com'
  })
});
```

**Concurrency warning**: updates are last-write-wins. A stale complete object can
overwrite a newer scalar or collection value. Re-fetch before updating when
concurrent writers are possible.

**Idempotency**: PUT requests are idempotent - making the same request multiple times produces the same result.

---

## Delete Resource

Permanently delete a resource.

### Request

```
DELETE /{resource}/{id}
```

**Path Parameters**:
- `id` (integer, required): Resource ID

**Query Parameters**: None

**Request Body**: None

### Response

**Success Status**: 200 OK

**Success Body**: Confirmation message

```json
{
  "message": "Deleted successfully"
}
```

**Error Responses**:

| Status | Cause | Detail |
|--------|-------|--------|
| 404 | Resource not found | `"Not found"` |

### Example

```javascript
// Delete user
async function deleteUser(userId) {
  const confirmed = confirm('Are you sure you want to delete this user?');
  if (!confirmed) return false;
  
  const response = await fetch(`http://localhost:8000/users/${userId}`, {
    method: 'DELETE'
  });
  
  if (response.status === 404) {
    alert('User not found');
    return false;
  }
  
  if (response.ok) {
    const result = await response.json();
    console.log(result.message); // "Deleted successfully"
    return true;
  }
  
  return false;
}
```

**Important Notes**:
- Deletion is permanent (no soft delete by default)
- No cascade delete by default (foreign key references may become orphaned)
- Idempotent: Deleting same ID twice returns 404 on second attempt

---

## Nested Resource Endpoints

When models have many-to-many relationships, N3TX creates nested endpoints under parent resources.

### Pattern

For a Product with Comments:

```python
class Product(ProtoModel):
    __tablename__ = 'products'
    comments: List[Comment] = []
```

Generated endpoints:

| Operation | Method | Path | Description |
|-----------|--------|------|-------------|
| Create | POST | `/products/{parent_id}/comments` | Add comment to product |
| List | GET | `/products/{parent_id}/comments` | Get product's comments |
| Read | GET | `/products/{parent_id}/comments/{id}` | Get specific comment |
| Update | PUT | `/products/{parent_id}/comments/{id}` | Update comment |
| Delete | DELETE | `/products/{parent_id}/comments/{id}` | Remove comment |

### Create Nested Resource

```
POST /{parent_resource}/{parent_id}/{child_resource}
```

**Path Parameters**:
- `parent_id` (integer, required): Parent resource ID

**Request Body**: Child resource data

```json
{
  "text": "Great product!",
  "rating": 5,
  "user": 1
}
```

**Response** (201 Created):
```json
{
  "$schema": "http://localhost:8000/Comment",
  "$id": "http://localhost:8000/Product/5/Comment/1",
  "id": 1,
  "text": "Great product!",
  "rating": 5,
  "user": 1,
  "product_id": 5
}
```

**Note**: `product_id` foreign key is automatically added.

### List Nested Resources

```
GET /{parent_resource}/{parent_id}/{child_resource}
```

Returns only child resources belonging to specified parent:

```json
[
  {
    "$schema": "http://localhost:8000/Comment",
    "$id": "http://localhost:8000/Product/5/Comment/1",
    "id": 1,
    "text": "Great product!",
    "product_id": 5,
    "user": 1
  },
  {
    "$schema": "http://localhost:8000/Comment",
    "$id": "http://localhost:8000/Product/5/Comment/2",
    "id": 2,
    "text": "Fast shipping",
    "product_id": 5,
    "user": 2
  }
]
```

### Example: Product Comments

```javascript
// Add comment to product
async function addComment(productId, commentData) {
  return await fetch(`http://localhost:8000/products/${productId}/comments`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(commentData)
  }).then(r => r.json());
}

// Get all comments for a product
async function getProductComments(productId) {
  return await fetch(`http://localhost:8000/products/${productId}/comments`)
    .then(r => r.json());
}

// Update a comment
async function updateComment(productId, commentId, updates) {
  return await fetch(
    `http://localhost:8000/products/${productId}/comments/${commentId}`,
    {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(updates)
    }
  ).then(r => r.json());
}

// Delete a comment
async function deleteComment(productId, commentId) {
  return await fetch(
    `http://localhost:8000/products/${productId}/comments/${commentId}`,
    { method: 'DELETE' }
  ).then(r => r.json());
}
```

---

## Collection Routes

When join models are registered (e.g., `ProductComment`, `ProductLike`), N3TX generates **collection routes** that return all child records across all parents.

### Pattern

```
GET /{parent_table}/{child_table}
```

### Examples

| Route | Returns |
|-------|---------|
| `GET /products/comments` | All comments across all products |
| `GET /products/likes` | All favorites across all products |

### Response

Collection routes support the same pagination as regular list endpoints:

```bash
# All comments (unpaginated)
GET /products/comments

# Paginated
GET /products/comments?limit=20&offset=0
```

Response format matches the standard list endpoint (plain array without params, `{data, meta}` with pagination).

**Note**: Collection routes are registered before CRUD routes (Pass 1) to avoid path conflicts with `{id:int}` segments. This ensures `/products/comments` is not interpreted as `/products/{id}` with `id="comments"`.

---

## Complete CRUD Workflow Example

```javascript
// 1. Create a product
const product = await fetch('http://localhost:8000/products', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    name: 'Laptop',
    price: 999.99,
    description: 'High-performance laptop'
  })
}).then(r => r.json());

console.log('Created:', product);
// { "$schema": "http://localhost:8000/Product", "$id": "http://localhost:8000/Product/1", "id": 1, "name": "Laptop", ... }

// 2. Get all products
const allProducts = await fetch('http://localhost:8000/products')
  .then(r => r.json());

console.log('Total products:', allProducts.length);

// 3. Get specific product
const retrievedProduct = await fetch('http://localhost:8000/products/1')
  .then(r => r.json());

console.log('Retrieved:', retrievedProduct);
// Includes $schema and $id

// 4. Update product price
const updated = await fetch('http://localhost:8000/products/1', {
  method: 'PUT',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ price: 899.99 })
}).then(r => r.json());

console.log('Updated price:', updated.price); // 899.99

// 5. Add comment to product (nested resource)
const comment = await fetch('http://localhost:8000/products/1/comments', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    text: 'Great laptop!',
    user: 1
  })
}).then(r => r.json());

console.log('Comment added:', comment);
// Includes $schema and $id

// 6. Get product's comments
const comments = await fetch('http://localhost:8000/products/1/comments')
  .then(r => r.json());

console.log('Product has', comments.length, 'comments');

// 7. Delete product
await fetch('http://localhost:8000/products/1', {
  method: 'DELETE'
});

console.log('Product deleted');
```

---

## TypeScript Integration

Generate TypeScript interfaces from schemas:

```typescript
// Fetch schema and generate types
interface User {
  $schema: string;
  $id: string;
  id: number;
  name: string;
  email: string;
  age?: number;
}

// Type-safe API calls
async function getUser(id: number): Promise<User> {
  const response = await fetch(`http://localhost:8000/users/${id}`);
  return await response.json();
}

async function createUser(data: Omit<User, 'id' | '$schema' | '$id'>): Promise<User> {
  const response = await fetch('http://localhost:8000/users', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data)
  });
  return await response.json();
}
```

---

## Performance Considerations

### Response Times

- **List operations**: Use `?limit=N&offset=M` for large datasets. The COUNT query runs before the SELECT, so paginated requests are efficient.
- **Get by ID** is fast (single database lookup)
- **Create/Update/Delete** are typically fast

### Best Practices

1. **Use pagination**: Pass `?limit=20` for list endpoints with many records
2. **Caching**: Consider caching GET responses in frontend
3. **Optimistic updates**: Update UI immediately, revert on error
4. **Batch operations**: For multiple creates, consider custom batch endpoint

### Example: Optimistic Update

```javascript
async function updateUser(userId, updates) {
  // 1. Optimistically update UI
  const oldState = getCurrentUser();
  updateUIWithNewState({ ...oldState, ...updates });
  
  try {
    // 2. Send request
    const result = await fetch(`http://localhost:8000/users/${userId}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(updates)
    });
    
    if (!result.ok) throw new Error('Update failed');
    
    // 3. Confirm with server response (includes $schema and $id)
    const confirmedState = await result.json();
    updateUIWithNewState(confirmedState);
    
  } catch (err) {
    // 4. Revert on error
    updateUIWithNewState(oldState);
    showError('Failed to update user');
  }
}
```

---

## Next Steps

- [Custom Endpoints](./API_CUSTOM_ENDPOINTS.md) - Learn about `@expose_route` methods
- [Data Models Reference](./API_DATA_MODELS.md) - Detailed schemas for each model
- [API Overview](./API_OVERVIEW.md) - General conventions and error handling
