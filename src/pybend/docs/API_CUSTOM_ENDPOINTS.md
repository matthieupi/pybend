# Custom Endpoints

Beyond standard CRUD operations, PyBend models can expose custom business logic through the `@expose_route` decorator. This document explains how these custom endpoints work from a frontend perspective.

## Overview

Custom endpoints are defined in model classes using `@expose_route`:

```python
@expose_route('/login', methods=['POST'])
def login(email: str, password: str) -> User:
    # Custom logic
    return user
```

The decorator creates an HTTP endpoint that frontend can call.

---

## Endpoint URL Patterns

Custom endpoint URLs depend on the method type:

| Method Type | URL Pattern | Example |
|-------------|-------------|---------|
| **Static Method** | `/{resource}{custom_path}` | `POST /users/login` |
| **Class Method** | `/{resource}{custom_path}` | `GET /users/search` |
| **Instance Method** | `/{resource}/{id}{custom_path}` | `POST /products/1/discount` |

### Static Method

Called on the model class, not on a specific instance.

**Backend**:
```python
@staticmethod
@expose_route('/login', methods=['POST'])
def login(email: str, password: str) -> User:
    users = User.list()
    return next(u for u in users if u.email == email)
```

**Frontend**:
```javascript
// POST /users/login
const user = await fetch('http://localhost:8000/users/login', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    email: 'alice@example.com',
    password: 'secret123'
  })
}).then(r => r.json());
```

### Class Method

Called on the model class, has access to `cls`.

**Backend**:
```python
@classmethod
@expose_route('/search', methods=['GET'])
def search(cls, query: str) -> List[User]:
    return [u for u in cls.list() if query in u.name]
```

**Frontend**:
```javascript
// GET /users/search
const users = await fetch('http://localhost:8000/users/search', {
  method: 'GET',  // Note: Even though backend uses GET, you must POST with body
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    query: 'alice'
  })
}).then(r => r.json());
```

**Important**: Custom endpoints always require JSON body, even if declared as GET.

### Instance Method

Operates on a specific resource instance (requires ID in path).

**Backend**:
```python
@expose_route('/discount', methods=['POST'])
def apply_discount(self, percentage: float) -> Product:
    self.price = self.price * (1 - percentage / 100)
    self.save()
    return self
```

**Frontend**:
```javascript
// POST /products/1/discount
const updated = await fetch('http://localhost:8000/products/1/discount', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    percentage: 10
  })
}).then(r => r.json());

console.log('New price:', updated.price);
```

---

## Automatic User Injection

Custom methods can receive the authenticated user automatically by declaring a `user` parameter. The route layer bridges the auth-layer identity (JWT dict) to the model-layer entity, respecting the separation of concerns between the `authorize` package and PyBend models.

### How It Works

When a custom method declares a `user` parameter, the route handler:

1. Skips `user` during request body parsing (it's never read from the POST body)
2. Extracts the JWT identity from the request (`request.state.user`)
3. Resolves the type based on the parameter's type hint:
   - **Model class** (e.g., `User`) — fetches the full model instance via `User.get(user_id)`
   - **`dict`** — passes the raw JWT payload `{"user_id", "email", "role"}`
   - **No type hint** — passes the raw JWT dict

### Example

**Backend**:
```python
from .user_model import User

class Product(ProtoModel):
    @expose_route('/comment', methods=['POST'])
    def comment(self, comment: Comment, user: User = None) -> str:
        comment.user_owner = user.id if user else 1
        comment.__owner__ = self
        comment.save()
        return comment.model_dump_json()
```

**Frontend** — `user` is NOT included in the request body:
```javascript
// POST /products/1/comment
await fetch('http://localhost:8000/products/1/comment', {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json',
    'x-access-token': jwtToken
  },
  body: JSON.stringify({
    comment: { name: "Great product!" }
    // No "user" field — injected server-side from JWT
  })
});
```

### Design: Auth/Model Boundary

The `authorize` package is standalone — it speaks plain dicts (`{"user_id", "email", "role"}`) and has zero PyBend model imports. The `_resolve_user()` bridge in the route layer translates between these two worlds:

```
JWT Middleware (authorize)          Route Layer (_resolve_user)         Model Layer
─────────────────────────          ─────────────────────────          ─────────────
request.state.user =          →    type hint is User?            →    User.get(user_id)
  {"user_id": 1,                     Yes → fetch model instance        → full User instance
   "email": "alice@...",             No  → pass raw dict               → plain dict
   "role": "user"}
```

This keeps the auth package decoupled from models while giving model methods access to the full entity when needed.

### Rules

- `user` is a reserved parameter name — never included in request body parsing
- The `user` parameter should have a default of `None` for unauthenticated endpoints
- Works in both instance methods (`post_with_id`) and class/static methods (`post_no_id`)
- The type hint drives resolution: `User` → model instance, `dict` → raw JWT payload

---

## Request Format

### HTTP Method

Custom endpoints can specify their HTTP method via the decorator:
```python
@expose_route('/action', methods=['POST'])  # POST
@expose_route('/data', methods=['GET'])     # GET (but still requires body)
```

**Frontend Impact**: Always use the specified HTTP method in `fetch()`.

### Request Body

All custom endpoints require a JSON request body containing the method parameters.

**Parameter Mapping**:

Backend method signature:
```python
def custom_method(self, name: str, age: int, active: bool = True):
    pass
```

Frontend request body:
```json
{
  "name": "Alice",
  "age": 28,
  "active": false
}
```

**Rules**:
- Parameter names must match exactly (case-sensitive)
- All parameters without defaults are required
- Parameters with defaults are optional
- `self`, `cls`, and `user` are never included in request body (see [Automatic User Injection](#automatic-user-injection))

---

## Response Format

### Return Types

Custom endpoints can return:

1. **Model Instance** - Returns full object as JSON with `$schema` and `$id` metadata (via `.model_dump(response=True)`)
2. **List of Models** - Returns array of objects, each with `$schema` and `$id`
3. **dict** - Returns custom JSON structure (no automatic metadata)
4. **str** - Returns plain string (wrapped in JSON)
5. **None** - Returns null

When a custom endpoint returns a model instance, the route handler calls `.model_dump(response=True)` to inject `$schema` and `$id` metadata into the response.

### Examples

#### Return Model Instance

**Backend**:
```python
@expose_route('/action', methods=['POST'])
def some_action(self) -> Product:
    # Logic
    return self
```

**Frontend Response**:
```json
{
  "$schema": "http://localhost:8000/Product",
  "$id": "http://localhost:8000/products/1",
  "id": 1,
  "name": "Product",
  "price": 99.99
}
```

#### Return List of Models

**Backend**:
```python
@classmethod
@expose_route('/filter', methods=['POST'])
def filter_products(cls, min_price: float) -> List[Product]:
    return [p for p in cls.list() if p.price >= min_price]
```

**Frontend Response**:
```json
[
  {"$schema": "http://localhost:8000/Product", "$id": "http://localhost:8000/products/1", "id": 1, "name": "Laptop", "price": 999.99},
  {"$schema": "http://localhost:8000/Product", "$id": "http://localhost:8000/products/2", "id": 2, "name": "Phone", "price": 699.99}
]
```

#### Return Custom dict

**Backend**:
```python
@expose_route('/stats', methods=['GET'])
def get_stats(self) -> dict:
    return {
        "total_orders": 42,
        "revenue": 12500.50,
        "average": 297.63
    }
```

**Frontend Response**:
```json
{
  "total_orders": 42,
  "revenue": 12500.5,
  "average": 297.63
}
```

---

## Error Handling

Custom endpoints can fail in several ways:

### Missing Required Parameter (400)

**Request**:
```json
{
  "email": "alice@example.com"
  // Missing required "password" parameter
}
```

**Response** (400):
```json
{
  "detail": "Missing field: password"
}
```

### Invalid Parameter Type (422)

**Request**:
```json
{
  "percentage": "not-a-number"
}
```

**Response** (422):
```json
{
  "detail": "Invalid field 'percentage': could not convert string to float"
}
```

### Resource Not Found (404)

For instance methods, if the ID doesn't exist:

**Request**: `POST /products/999/discount`

**Response** (404):
```json
{
  "detail": "Not found"
}
```

### Custom Business Logic Error (400)

**Backend**:
```python
@expose_route('/discount', methods=['POST'])
def apply_discount(self, percentage: float) -> Product:
    if percentage < 0 or percentage > 100:
        raise ValueError("Discount must be between 0 and 100")
    # ...
```

**Frontend Request**:
```json
{
  "percentage": 150
}
```

**Response** (400):
```json
{
  "detail": [
    {
      "file": "models/product_model.py",
      "line": 23,
      "function": "apply_discount",
      "code": "raise ValueError(...)",
      "error": "Discount must be between 0 and 100"
    }
  ]
}
```

---

## Discovering Custom Endpoints

### Via Model Schema

Get the schema to discover all custom endpoints:

```javascript
const schema = await fetch('http://localhost:8000/User')
  .then(r => r.json());

// Custom endpoints are in the "methods" object
Object.entries(schema.methods).forEach(([methodName, metadata]) => {
  console.log(`${methodName}:`, metadata.route, metadata.methods);
  console.log('Parameters:', metadata.parameters);
  console.log('Returns:', metadata.returns);
});
```

Example output:
```
login: /login ['POST']
Parameters: { email: {type: 'string'}, password: {type: 'string'} }
Returns: { type: '$ref', $ref: '#/$defs/User' }
```

### Via Interactive Documentation

FastAPI: Visit `http://localhost:8000/docs` to see all endpoints including custom ones.

---

## Common Custom Endpoint Patterns

### 1. Authentication

```python
@staticmethod
@expose_route('/login', methods=['POST'])
def login(email: str, password: str) -> dict:
    # Validate credentials
    user = find_user(email)
    if not verify_password(password, user.password_hash):
        raise ValueError("Invalid credentials")
    
    # Generate token
    token = create_session_token(user.id)
    return {
        "token": token,
        "user_id": user.id,
        "email": user.email
    }
```

**Frontend**:
```javascript
const { token, user_id } = await fetch('/users/login', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ email, password })
}).then(r => r.json());

// Store token for future requests
localStorage.setItem('auth_token', token);
```

### 2. Search/Filter

```python
@classmethod
@expose_route('/search', methods=['POST'])
def search(cls, query: str, status: str = None) -> List[Product]:
    results = cls.list()
    if query:
        results = [r for r in results if query.lower() in r.name.lower()]
    if status:
        results = [r for r in results if r.status == status]
    return results
```

**Frontend**:
```javascript
const products = await fetch('/products/search', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    query: 'laptop',
    status: 'available'
  })
}).then(r => r.json());
```

### 3. State Transitions

```python
@expose_route('/publish', methods=['POST'])
def publish(self) -> Article:
    if self.status != 'draft':
        raise ValueError("Only draft articles can be published")
    
    self.status = 'published'
    self.published_at = datetime.now().isoformat()
    self.save()
    return self
```

**Frontend**:
```javascript
async function publishArticle(articleId) {
  try {
    const article = await fetch(`/articles/${articleId}/publish`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({})  // Empty body (no parameters)
    }).then(r => r.json());
    
    console.log('Published:', article.published_at);
    return article;
    
  } catch (err) {
    if (err.message.includes('draft')) {
      alert('Article must be in draft status to publish');
    }
    throw err;
  }
}
```

### 4. Aggregations/Statistics

```python
@classmethod
@expose_route('/statistics', methods=['GET'])
def get_statistics(cls) -> dict:
    orders = cls.list()
    return {
        "total": len(orders),
        "completed": len([o for o in orders if o.status == 'completed']),
        "revenue": sum(o.total for o in orders if o.status == 'completed'),
        "average_value": sum(o.total for o in orders) / len(orders) if orders else 0
    }
```

**Frontend**:
```javascript
const stats = await fetch('/orders/statistics', {
  method: 'GET',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({})
}).then(r => r.json());

renderDashboard(stats);
```

### 5. Batch Operations

```python
@classmethod
@expose_route('/bulk-update', methods=['POST'])
def bulk_update(cls, ids: List[int], updates: dict) -> dict:
    updated_count = 0
    for id in ids:
        cls.update(id, updates)
        updated_count += 1
    
    return {
        "updated": updated_count,
        "ids": ids
    }
```

**Frontend**:
```javascript
// Update multiple products at once
const result = await fetch('/products/bulk-update', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    ids: [1, 2, 3, 4, 5],
    updates: { status: 'archived' }
  })
}).then(r => r.json());

console.log(`Updated ${result.updated} products`);
```

### 6. Toggle Actions (Like/Favorite)

Toggle endpoints create or delete a join table record. Empty body allowed — no payload needed.

```python
@expose_route('/favorite', methods=['POST'], access=AUTHENTICATED)
def favorite(self, user: User = None) -> str:
    """Toggle — create if not favorited, remove if already favorited."""
    existing = ProductLike.find(product_id=self.id, user_id=user.id)
    if existing:
        existing.delete()
        return json.dumps({"action": "unfavorited"})
    else:
        ProductLike.create(...)
        return json.dumps({"action": "favorited"})
```

**Frontend**:
```javascript
// POST /products/1/favorite — empty body
const result = await fetch('/products/1/favorite', {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json',
    'x-access-token': jwtToken
  },
  body: JSON.stringify({})
}).then(r => r.json());

console.log(result.action); // "favorited" or "unfavorited"
```

The frontend `<ntt-method>` component renders toggle methods as compact icon + count pills (heart for like, star for favorite) using the `button` layout hint from `__ui__.methods`.

### 7. Complex Queries

```python
@expose_route('/related-products', methods=['GET'])
def get_related(self, limit: int = 5) -> List[Product]:
    # Find products in same category
    all_products = Product.list()
    related = [
        p for p in all_products 
        if p.category == self.category and p.id != self.id
    ]
    return related[:limit]
```

**Frontend**:
```javascript
// Get related products
const related = await fetch(`/products/1/related-products`, {
  method: 'GET',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ limit: 10 })
}).then(r => r.json());

displayRelatedProducts(related);
```

---

## Working with Complex Parameters

### Nested Objects

**Backend**:
```python
from pydantic import BaseModel

class Address(BaseModel):
    street: str
    city: str
    zip_code: str

@expose_route('/update-address', methods=['POST'])
def update_address(self, address: Address) -> User:
    # address is validated Pydantic model
    self.address = address.model_dump_json()
    self.save()
    return self
```

**Frontend**:
```javascript
await fetch('/users/1/update-address', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    address: {
      street: '123 Main St',
      city: 'Springfield',
      zip_code: '12345'
    }
  })
});
```

### Lists

**Backend**:
```python
@classmethod
@expose_route('/find-by-ids', methods=['POST'])
def find_by_ids(cls, ids: List[int]) -> List[User]:
    all_users = cls.list()
    return [u for u in all_users if u.id in ids]
```

**Frontend**:
```javascript
const users = await fetch('/users/find-by-ids', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    ids: [1, 3, 5, 7]
  })
}).then(r => r.json());
```

### Optional Parameters

**Backend**:
```python
@classmethod
@expose_route('/search', methods=['POST'])
def search(cls, query: str, min_price: float = 0, max_price: float = None) -> List[Product]:
    results = cls.list()
    # Filter logic
    return results
```

**Frontend - All parameters**:
```javascript
await fetch('/products/search', {
  method: 'POST',
  body: JSON.stringify({
    query: 'laptop',
    min_price: 500,
    max_price: 2000
  })
});
```

**Frontend - Only required parameters**:
```javascript
await fetch('/products/search', {
  method: 'POST',
  body: JSON.stringify({
    query: 'laptop'
    // min_price and max_price use defaults
  })
});
```

---

## Example: Complete Authentication Flow

### Backend Endpoints

```python
class User(ProtoModel):
    __storable__ = True
    __tablename__ = 'users'
    
    email: str
    password_hash: str
    
    @staticmethod
    @expose_route('/register', methods=['POST'])
    def register(email: str, password: str) -> dict:
        # Validate email uniqueness
        users = User.list()
        if any(u.email == email for u in users):
            raise ValueError("Email already registered")
        
        # Create user
        user = User.create(User(
            email=email,
            password_hash=hash_password(password)
        ))
        
        return {"user_id": user.id, "email": user.email}
    
    @staticmethod
    @expose_route('/login', methods=['POST'])
    def login(email: str, password: str) -> dict:
        users = User.list()
        user = next((u for u in users if u.email == email), None)
        
        if not user or not verify_password(password, user.password_hash):
            raise ValueError("Invalid credentials")
        
        token = create_token(user.id)
        return {
            "token": token,
            "user_id": user.id,
            "email": user.email
        }
    
    @expose_route('/change-password', methods=['POST'])
    def change_password(self, old_password: str, new_password: str) -> dict:
        if not verify_password(old_password, self.password_hash):
            raise ValueError("Current password is incorrect")
        
        self.password_hash = hash_password(new_password)
        self.save()
        
        return {"message": "Password changed successfully"}
```

### Frontend Implementation

```javascript
class AuthService {
  
  async register(email, password) {
    try {
      const response = await fetch('/users/register', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email, password })
      });
      
      if (!response.ok) {
        const error = await response.json();
        throw new Error(error.detail[0].error);
      }
      
      return await response.json();
      
    } catch (err) {
      if (err.message.includes('already registered')) {
        alert('This email is already registered');
      }
      throw err;
    }
  }
  
  async login(email, password) {
    const response = await fetch('/users/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email, password })
    });
    
    if (!response.ok) {
      throw new Error('Invalid credentials');
    }
    
    const { token, user_id } = await response.json();
    
    // Store auth token
    localStorage.setItem('auth_token', token);
    localStorage.setItem('user_id', user_id);
    
    return { token, user_id };
  }
  
  async changePassword(userId, oldPassword, newPassword) {
    const response = await fetch(`/users/${userId}/change-password`, {
      method: 'POST',
      headers: { 
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${this.getToken()}`
      },
      body: JSON.stringify({
        old_password: oldPassword,
        new_password: newPassword
      })
    });
    
    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.detail[0].error);
    }
    
    return await response.json();
  }
  
  getToken() {
    return localStorage.getItem('auth_token');
  }
  
  logout() {
    localStorage.removeItem('auth_token');
    localStorage.removeItem('user_id');
  }
}

// Usage
const auth = new AuthService();

// Register
await auth.register('alice@example.com', 'SecurePass123');

// Login
const { token, user_id } = await auth.login('alice@example.com', 'SecurePass123');

// Change password
await auth.changePassword(user_id, 'SecurePass123', 'NewSecurePass456');

// Logout
auth.logout();
```

---

## Best Practices

### 1. Always Handle Errors

```javascript
async function callCustomEndpoint() {
  try {
    const response = await fetch('/resource/action', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(params)
    });
    
    if (!response.ok) {
      const error = await response.json();
      // Extract meaningful error message
      const message = error.detail?.[0]?.error || 'Unknown error';
      throw new Error(message);
    }
    
    return await response.json();
    
  } catch (err) {
    console.error('API Error:', err);
    // Show user-friendly message
    showErrorToUser(err.message);
    return null;
  }
}
```

### 2. Validate Before Sending

```javascript
// Check schema first
const schema = await fetch('/Product').then(r => r.json());
const method = schema.methods.apply_discount;

// Validate parameters match schema
const params = { percentage: 10 };
for (const [name, paramSchema] of Object.entries(method.parameters)) {
  if (!(name in params)) {
    console.error(`Missing required parameter: ${name}`);
    return;
  }
}

// Then make request
await fetch('/products/1/apply-discount', {
  method: 'POST',
  body: JSON.stringify(params)
});
```

### 3. Type Safety with TypeScript

```typescript
// Define types based on schema
interface DiscountParams {
  percentage: number;
}

interface Product {
  id: number;
  name: string;
  price: number;
}

async function applyDiscount(
  productId: number, 
  params: DiscountParams
): Promise<Product> {
  const response = await fetch(`/products/${productId}/discount`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(params)
  });
  
  return await response.json();
}
```

---

## Troubleshooting

### "Missing field: X" Error

**Cause**: Required parameter not included in request body

**Solution**: Check method signature and include all parameters without defaults

### "Invalid field 'X': ..." Error

**Cause**: Parameter type doesn't match expected type

**Solution**: Check schema for correct type (string, number, boolean, array, object)

### 404 on Instance Method

**Cause**: Resource with given ID doesn't exist

**Solution**: Verify ID exists with `GET /{resource}/{id}` first

### Custom Endpoint Not Found

**Cause**: Endpoint not registered or incorrect URL

**Solution**: Check schema (`GET /{ModelName}`) for available methods and routes

---

## Next Steps

- [Standard CRUD Endpoints](./API_CRUD_ENDPOINTS.md) - Auto-generated endpoints reference
- [Data Models Reference](./API_DATA_MODELS.md) - Schema for each model
- [API Overview](./API_OVERVIEW.md) - General conventions and setup
