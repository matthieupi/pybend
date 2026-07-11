# Data Models Reference

This document provides detailed schema reference for the example models in N3TX. Use this as a template for understanding the schema structure of your own models.

---

## How to Read This Document

Each model section includes:

1. **Model Overview** - Purpose and relationships
2. **Schema Reference** - Available endpoints and fields
3. **Field Details** - Types, constraints, validation
4. **Example Requests/Responses** - Real-world usage (all responses include `$schema` and `$id`)
5. **Frontend Integration** - TypeScript interfaces and usage patterns

---

## User Model

User accounts in the system.

### Endpoints

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/User` | Get schema |
| POST | `/users` | Create user |
| GET | `/users` | List all users |
| GET | `/users/{id}` | Get user |
| PUT | `/users/{id}` | Update user |
| DELETE | `/users/{id}` | Delete user |
| POST | `/users/login` | Custom: Login |

### Schema

```json
{
  "$schema": "http://localhost:8000/Schema",
  "$id": "http://localhost:8000/User",
  "type": "object",
  "properties": {
    "id": {
      "type": "integer",
      "description": "Auto-generated unique identifier"
    },
    "name": {
      "type": "string",
      "description": "User's full name"
    },
    "email": {
      "type": "string",
      "description": "User's email address"
    },
    "age": {
      "type": "integer",
      "description": "User's age (optional)"
    }
  },
  "required": ["name", "email"]
}
```

### Field Details

| Field | Type | Required | Constraints | Description |
|-------|------|----------|-------------|-------------|
| `id` | integer | No (auto) | Read-only, auto-increment | Unique identifier |
| `name` | string | Yes | - | Full name |
| `email` | string | Yes | Must be valid email | Email address |
| `age` | integer | No | Must be positive | Age in years |

### Create User

**Request**:
```bash
POST /users
Content-Type: application/json

{
  "name": "Alice Johnson",
  "email": "alice@example.com",
  "age": 28
}
```

**Response** (201 Created):
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

### Get User

**Request**:
```bash
GET /users/1
```

**Response** (200 OK):
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

### List Users

**Request**:
```bash
GET /users
```

**Response** (200 OK):
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

### Update User

**Request** (partial writable representation):
```bash
PUT /users/1
Content-Type: application/json

{
  "age": 29
}
```

Generated `PUT` routes merge the patch with the current entity and validate the
complete result through the original model. Omitted fields remain unchanged.

**Response** (200 OK):
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

### Delete User

**Request**:
```bash
DELETE /users/1
```

**Response** (200 OK):
```json
{
  "message": "Deleted successfully"
}
```

### Custom: Login

Authenticate user and return user object.

**Request**:
```bash
POST /users/login
Content-Type: application/json

{
  "email": "alice@example.com",
  "password": "secret123"
}
```

**Response** (200 OK):
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

**Error Response** (401 Unauthorized):
```json
{
  "detail": [
    {
      "error": "Invalid credentials"
    }
  ]
}
```

### TypeScript Interface

```typescript
interface User {
  $schema: string;
  $id: string;
  id: number;
  name: string;
  email: string;
  age?: number;
}

// API Client
class UserAPI {
  async create(data: Omit<User, 'id' | '$schema' | '$id'>): Promise<User> {
    const response = await fetch('/users', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data)
    });
    return await response.json();
  }
  
  async get(id: number): Promise<User> {
    const response = await fetch(`/users/${id}`);
    return await response.json();
  }
  
  async list(): Promise<User[]> {
    const response = await fetch('/users');
    return await response.json();
  }
  
  async update(id: number, data: Partial<User>): Promise<User> {
    const response = await fetch(`/users/${id}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data)
    });
    return await response.json();
  }
  
  async delete(id: number): Promise<void> {
    await fetch(`/users/${id}`, { method: 'DELETE' });
  }
  
  async login(email: string, password: string): Promise<User> {
    const response = await fetch('/users/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email, password })
    });
    return await response.json();
  }
}
```

---

## Product Model

Products available in the system.

### Endpoints

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/Product` | Get schema |
| POST | `/products` | Create product |
| GET | `/products` | List all products |
| GET | `/products/{id}` | Get product |
| PUT | `/products/{id}` | Update product |
| DELETE | `/products/{id}` | Delete product |
| POST | `/products/{id}/comment` | Custom: Add comment |
| POST | `/products/{id}/favorite` | Custom: Toggle favorite |
| GET | `/products/comments` | Collection: All comments across products |
| GET | `/products/likes` | Collection: All favorites across products |

### Schema

```json
{
  "$schema": "http://localhost:8000/Schema",
  "$id": "http://localhost:8000/Product",
  "type": "object",
  "properties": {
    "id": {
      "type": "integer"
    },
    "name": {
      "type": "string",
      "description": "Product name"
    },
    "price": {
      "type": "number",
      "description": "Price in USD"
    },
    "description": {
      "type": "string",
      "description": "Product description",
      "default": ""
    },
    "comments": {
      "type": "array",
      "items": {
        "$ref": "#/$defs/Comment"
      },
      "default": []
    }
  },
  "required": ["name", "price"],
  "$defs": {
    "Comment": {
      "$id": "http://localhost:8000/Comment"
    }
  }
}
```

### Field Details

| Field | Type | Required | Constraints | Description |
|-------|------|----------|-------------|-------------|
| `id` | integer | No (auto) | Read-only | Unique identifier |
| `name` | string | Yes | - | Product name |
| `price` | float | Yes | Must be positive | Price in USD |
| `description` | string | No | - | Product description |
| `comments` | array | No | `list[Comment]` hydrated objects | Related comments |
| `favorites` | array | No | `list[Like]` hydrated objects | Users who favorited |

### Create Product

**Request**:
```bash
POST /products
Content-Type: application/json

{
  "name": "Laptop",
  "price": 999.99,
  "description": "High-performance laptop"
}
```

**Response** (201 Created):
```json
{
  "$schema": "http://localhost:8000/Product",
  "$id": "http://localhost:8000/Product/1",
  "id": 1,
  "name": "Laptop",
  "price": 999.99,
  "description": "High-performance laptop",
  "comments": []
}
```

### Update Product Price

**Request**:
```bash
PUT /products/1
Content-Type: application/json

{
  "price": 899.99
}
```

**Response** (200 OK):
```json
{
  "$schema": "http://localhost:8000/Product",
  "$id": "http://localhost:8000/Product/1",
  "id": 1,
  "name": "Laptop",
  "price": 899.99,
  "description": "High-performance laptop",
  "comments": []
}
```

### Custom: Add Comment

Add a comment to a product. The `user` parameter is injected server-side from the JWT token (not sent in the request body).

**Request**:
```bash
POST /products/1/comment
Content-Type: application/json
x-access-token: <JWT>

{
  "comment": {
    "name": "Great product!",
    "description": "Very satisfied with this purchase"
  }
}
```

**Note**: The `comment` parameter is a nested object matching the Comment schema. `user_owner` is auto-injected from the JWT.

**Response** (200 OK):
```json
{
  "$schema": "http://localhost:8000/Comment",
  "$id": "http://localhost:8000/Product/1/Comment/1",
  "id": 1,
  "name": "Great product!",
  "description": "Very satisfied with this purchase",
  "user_owner": 1,
  "product_id": 1
}
```

### Custom: Toggle Favorite

Toggle product favorite status. No request body needed. Requires authentication.

**Request**:
```bash
POST /products/1/favorite
Content-Type: application/json
x-access-token: <JWT>

{}
```

**Response** (200 OK):
```json
{"action": "favorited"}
```

Or if already favorited:
```json
{"action": "unfavorited"}
```

### TypeScript Interface

```typescript
interface Product {
  $schema: string;
  $id: string;
  id: number;
  name: string;
  price: number;
  description?: string;
  comments?: number[];  // Array of comment IDs
}

interface CommentData {
  name: string;
  description?: string;
  user_owner: number;
}

class ProductAPI {
  async create(data: Omit<Product, 'id' | '$schema' | '$id'>): Promise<Product> {
    const response = await fetch('/products', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data)
    });
    return await response.json();
  }
  
  async get(id: number): Promise<Product> {
    const response = await fetch(`/products/${id}`);
    return await response.json();
  }
  
  async list(): Promise<Product[]> {
    const response = await fetch('/products');
    return await response.json();
  }
  
  async update(id: number, data: Partial<Product>): Promise<Product> {
    const response = await fetch(`/products/${id}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data)
    });
    return await response.json();
  }
  
  async addComment(productId: number, comment: CommentData): Promise<Comment> {
    const response = await fetch(`/products/${productId}/comment`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ comment })
    });
    return await response.json();
  }
}
```

---

## Comment Model

Comments on products. The Comment model uses `id` as its primary key field (consistent with Product and User).

### Endpoints

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/Comment` | Get schema |
| POST | `/products/{parent_id}/comments` | Create comment for product |
| GET | `/products/{parent_id}/comments` | List product's comments |
| GET | `/products/{parent_id}/comments/{id}` | Get specific comment |
| PUT | `/products/{parent_id}/comments/{id}` | Update comment |
| DELETE | `/products/{parent_id}/comments/{id}` | Delete comment |
| POST | `/products/{parent_id}/comments/{id}/like` | Toggle like on comment |
| POST | `/products/{parent_id}/comments/{id}/reply` | Reply to comment |

**Note**: Comments are a nested resource under Products. Like and reply are custom methods on comment instances.

### Schema

```json
{
  "$schema": "http://localhost:8000/Schema",
  "$id": "http://localhost:8000/Comment",
  "type": "object",
  "properties": {
    "id": {
      "type": "integer"
    },
    "name": {
      "type": "string",
      "description": "Comment title"
    },
    "description": {
      "type": "string",
      "description": "Comment text",
      "default": ""
    },
    "user_owner": {
      "type": "integer",
      "description": "ID of user who created comment"
    }
  },
  "required": ["name", "user_owner"]
}
```

### Field Details

| Field | Type | Required | Constraints | Description |
|-------|------|----------|-------------|-------------|
| `id` | integer | No (auto) | Read-only | Unique identifier |
| `name` | string | Yes | - | Comment title |
| `description` | string | No | - | Comment text |
| `user_owner` | integer | Yes (protected) | Must be valid User ID | Comment author (auto-injected from JWT) |
| `parent_id` | integer | No | Ref['self'] | Parent comment ID for nesting (replies) |
| `likes` | array | No | `list[Like]` hydrated objects | Users who liked this comment |
| `product_id` | integer | Auto | Set from parent | Product this comment belongs to |

**Important**: `product_id` is automatically set from the URL path parameter when creating comments. `user_owner` is a protected field — auto-injected from JWT on create, stripped from update payloads.

### Create Comment for Product

**Request**:
```bash
POST /products/1/comments
Content-Type: application/json

{
  "name": "Great product!",
  "description": "Very satisfied",
  "user_owner": 1
}
```

**Response** (201 Created):
```json
{
  "$schema": "http://localhost:8000/Comment",
  "$id": "http://localhost:8000/Product/1/Comment/1",
  "id": 1,
  "name": "Great product!",
  "description": "Very satisfied",
  "user_owner": 1,
  "product_id": 1
}
```

**Note**: `product_id` is automatically set to `1` from the URL.

### List Product's Comments

**Request**:
```bash
GET /products/1/comments
```

**Response** (200 OK):
```json
[
  {
    "$schema": "http://localhost:8000/Comment",
    "$id": "http://localhost:8000/Product/1/Comment/1",
    "id": 1,
    "name": "Great product!",
    "description": "Very satisfied",
    "user_owner": 1,
    "product_id": 1
  },
  {
    "$schema": "http://localhost:8000/Comment",
    "$id": "http://localhost:8000/Product/1/Comment/2",
    "id": 2,
    "name": "Fast shipping",
    "description": "Arrived quickly",
    "user_owner": 2,
    "product_id": 1
  }
]
```

### Get Specific Comment

**Request**:
```bash
GET /products/1/comments/1
```

**Response** (200 OK):
```json
{
  "$schema": "http://localhost:8000/Comment",
  "$id": "http://localhost:8000/Product/1/Comment/1",
  "id": 1,
  "name": "Great product!",
  "description": "Very satisfied",
  "user_owner": 1,
  "product_id": 1
}
```

### Update Comment

**Request**:
```bash
PUT /products/1/comments/1
Content-Type: application/json

{
  "description": "Updated: Very satisfied with this purchase!"
}
```

**Response** (200 OK):
```json
{
  "$schema": "http://localhost:8000/Comment",
  "$id": "http://localhost:8000/Product/1/Comment/1",
  "id": 1,
  "name": "Great product!",
  "description": "Updated: Very satisfied with this purchase!",
  "user_owner": 1,
  "product_id": 1
}
```

### Delete Comment

**Request**:
```bash
DELETE /products/1/comments/1
```

**Response** (200 OK):
```json
{
  "message": "Deleted successfully"
}
```

### TypeScript Interface

```typescript
interface Comment {
  $schema: string;
  $id: string;
  id: number;
  name: string;
  description?: string;
  user_owner: number;
  product_id: number;  // Set automatically from parent
}

class CommentAPI {
  async create(productId: number, data: Omit<Comment, 'id' | 'product_id' | '$schema' | '$id'>): Promise<Comment> {
    const response = await fetch(`/products/${productId}/comments`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data)
    });
    return await response.json();
  }
  
  async list(productId: number): Promise<Comment[]> {
    const response = await fetch(`/products/${productId}/comments`);
    return await response.json();
  }
  
  async get(productId: number, commentId: number): Promise<Comment> {
    const response = await fetch(`/products/${productId}/comments/${commentId}`);
    return await response.json();
  }
  
  async update(productId: number, commentId: number, data: Partial<Comment>): Promise<Comment> {
    const response = await fetch(`/products/${productId}/comments/${commentId}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data)
    });
    return await response.json();
  }
  
  async delete(productId: number, commentId: number): Promise<void> {
    await fetch(`/products/${productId}/comments/${commentId}`, {
      method: 'DELETE'
    });
  }
}
```

### Custom: Toggle Like

Toggle like on a comment. No request body needed. Requires authentication.

**Request**:
```bash
POST /products/1/comments/3/like
x-access-token: <JWT>

{}
```

**Response** (200 OK):
```json
{"action": "liked"}
```

### Custom: Reply to Comment

Create a reply to a comment. The reply is a child comment with `parent_id` set.

**Request**:
```bash
POST /products/1/comments/3/reply
Content-Type: application/json
x-access-token: <JWT>

{"text": "I agree, great product!"}
```

**Response** (200 OK): Returns the created reply comment as JSON.

---

## Like Model

Represents a like/favorite action by a user.

### Endpoints

Like is always a nested resource, accessed through join models:

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/products/{parent_id}/comments/{id}/likes` | List likes on a comment |
| GET | `/products/likes` | Collection: all product favorites |

**Note**: Likes are created/deleted via toggle endpoints (`POST .../like` or `POST .../favorite`), not via direct CRUD.

### Field Details

| Field | Type | Required | Constraints | Description |
|-------|------|----------|-------------|-------------|
| `id` | integer | No (auto) | Read-only | Unique identifier |
| `user` | integer | Yes (protected) | Must be valid User ID | User who liked (auto-injected from JWT) |

`user` is a protected field — never sent in the request body.

---

## Complete Frontend Integration Example

### React Component with All Models

```typescript
import React, { useState, useEffect } from 'react';

interface User {
  $schema: string;
  $id: string;
  id: number;
  name: string;
  email: string;
  age?: number;
}

interface Product {
  $schema: string;
  $id: string;
  id: number;
  name: string;
  price: number;
  description?: string;
}

interface Comment {
  $schema: string;
  $id: string;
  id: number;
  name: string;
  description?: string;
  user_owner: number;
  product_id: number;
}

function ProductDetail({ productId, currentUser }: { productId: number, currentUser: User }) {
  const [product, setProduct] = useState<Product | null>(null);
  const [comments, setComments] = useState<Comment[]>([]);
  const [newComment, setNewComment] = useState({ name: '', description: '' });
  
  useEffect(() => {
    loadProduct();
    loadComments();
  }, [productId]);
  
  async function loadProduct() {
    const data = await fetch(`/products/${productId}`).then(r => r.json());
    setProduct(data);
  }
  
  async function loadComments() {
    const data = await fetch(`/products/${productId}/comments`).then(r => r.json());
    setComments(data);
  }
  
  async function handleAddComment(e: React.FormEvent) {
    e.preventDefault();
    
    const comment = await fetch(`/products/${productId}/comments`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        ...newComment,
        user_owner: currentUser.id
      })
    }).then(r => r.json());
    
    setComments([...comments, comment]);
    setNewComment({ name: '', description: '' });
  }
  
  async function handleDeleteComment(commentId: number) {
    await fetch(`/products/${productId}/comments/${commentId}`, {
      method: 'DELETE'
    });
    
    setComments(comments.filter(c => c.id !== commentId));
  }
  
  if (!product) return <div>Loading...</div>;
  
  return (
    <div>
      <h1>{product.name}</h1>
      <p className="price">${product.price}</p>
      <p className="description">{product.description}</p>
      
      <div className="comments">
        <h2>Comments ({comments.length})</h2>
        
        {comments.map(comment => (
          <div key={comment.id} className="comment">
            <h3>{comment.name}</h3>
            <p>{comment.description}</p>
            {comment.user_owner === currentUser.id && (
              <button onClick={() => handleDeleteComment(comment.id)}>
                Delete
              </button>
            )}
          </div>
        ))}
        
        <form onSubmit={handleAddComment}>
          <input
            type="text"
            placeholder="Comment title"
            value={newComment.name}
            onChange={e => setNewComment({ ...newComment, name: e.target.value })}
            required
          />
          <textarea
            placeholder="Comment text"
            value={newComment.description}
            onChange={e => setNewComment({ ...newComment, description: e.target.value })}
          />
          <button type="submit">Add Comment</button>
        </form>
      </div>
    </div>
  );
}
```

---

## Working with Foreign Keys

### Understanding Foreign Key Fields

When a model has a foreign key:

```python
class Comment(ProtoModel):
    user_owner: Ref[User]
```

**In the API**:
- Requests send the **integer ID**: `"user_owner": 1`
- Responses return the **integer ID**: `"user_owner": 1`

**To get the full related object**, make a separate request:

```typescript
// 1. Get comment
const comment = await fetch('/products/1/comments/1').then(r => r.json());
// { $schema: "...", $id: "...", id: 1, user_owner: 1, ... }

// 2. Get the user
const user = await fetch(`/users/${comment.user_owner}`).then(r => r.json());
// { $schema: "...", $id: "...", id: 1, name: "Alice", email: "alice@example.com" }
```

### Helper Function for Resolving Foreign Keys

```typescript
async function resolveRelations<T>(
  obj: T, 
  relations: Record<string, string>
): Promise<T> {
  const resolved = { ...obj };
  
  for (const [field, endpoint] of Object.entries(relations)) {
    const id = (obj as any)[field];
    if (id) {
      (resolved as any)[`${field}_obj`] = await fetch(`${endpoint}/${id}`)
        .then(r => r.json());
    }
  }
  
  return resolved;
}

// Usage
const comment = await fetch('/products/1/comments/1').then(r => r.json());

const enriched = await resolveRelations(comment, {
  user_owner: '/users'
});

console.log(enriched.user_owner); // 1
console.log(enriched.user_owner_obj); // { $schema: "...", $id: "...", id: 1, name: "Alice", ... }
```

---

## Schema Discovery

### Dynamically Generate Forms

```typescript
async function generateForm(modelName: string): Promise<HTMLFormElement> {
  // Get schema
  const schema = await fetch(`/${modelName}`).then(r => r.json());
  
  const form = document.createElement('form');
  
  // Create input for each field
  for (const [fieldName, fieldSchema] of Object.entries(schema.properties)) {
    if (fieldName === 'id') continue; // Skip ID
    
    const isRequired = schema.required?.includes(fieldName);
    
    const label = document.createElement('label');
    label.textContent = fieldName;
    
    let input: HTMLInputElement | HTMLTextAreaElement;
    
    switch (fieldSchema.type) {
      case 'string':
        input = document.createElement('input');
        input.type = 'text';
        break;
      case 'integer':
      case 'number':
        input = document.createElement('input');
        input.type = 'number';
        break;
      case 'boolean':
        input = document.createElement('input');
        input.type = 'checkbox';
        break;
      default:
        input = document.createElement('textarea');
    }
    
    input.name = fieldName;
    input.required = isRequired;
    
    form.appendChild(label);
    form.appendChild(input);
  }
  
  const submit = document.createElement('button');
  submit.type = 'submit';
  submit.textContent = 'Create';
  form.appendChild(submit);
  
  return form;
}

// Usage
const userForm = await generateForm('User');
document.body.appendChild(userForm);
```

---

## Next Steps

- [Standard CRUD Endpoints](./API_CRUD_ENDPOINTS.md) - Complete CRUD reference
- [Custom Endpoints](./API_CUSTOM_ENDPOINTS.md) - Custom method documentation
- [API Overview](./API_OVERVIEW.md) - General conventions and setup

---

## Getting Your Own Model Schemas

For any model in your N3TX application:

```bash
GET /{ModelName}
```

This returns the complete schema including:
- `$schema` pointing to `{API_URL}/Schema`
- `$id` pointing to `{API_URL}/{ModelName}`
- All fields with types and constraints
- Required fields
- Custom methods and their parameters
- Referenced models in `$defs` (each with their own `$id`)

Use this to build dynamic frontends that adapt to backend changes automatically.
