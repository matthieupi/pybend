# PyBend API Documentation Index

Complete frontend-focused API documentation for PyBend applications.

## 📚 Documentation Structure

This documentation is organized into four focused sections:

### 1. [API Overview](./API_OVERVIEW.md) - **START HERE**
General conventions, setup, and concepts you need to understand before using any PyBend API.

**Topics covered:**
- Base URL and protocol
- Request/response format
- Authentication patterns
- Error handling
- HTTP status codes
- Data types and formatting
- Foreign keys and relationships
- CORS configuration
- OpenAPI/Swagger access

**Who should read this:** Everyone using a PyBend API

---

### 2. [Standard CRUD Endpoints](./API_CRUD_ENDPOINTS.md)
Complete reference for the auto-generated CRUD endpoints available for every storable model.

**Topics covered:**
- Get model schema
- Create resource (POST)
- List resources (GET)
- Get single resource (GET)
- Update resource (PUT)
- Delete resource (DELETE)
- Nested resources (many-to-many)
- Complete workflow examples
- TypeScript integration

**Who should read this:** Frontend developers implementing basic CRUD operations

---

### 3. [Custom Endpoints](./API_CUSTOM_ENDPOINTS.md)
How to use custom business logic endpoints exposed via `@expose_route`.

**Topics covered:**
- URL patterns for custom endpoints
- Request/response formats
- Static methods, class methods, instance methods
- Complex parameters (nested objects, lists)
- Common patterns (auth, search, state transitions, aggregations)
- Complete authentication flow example
- Error handling
- Best practices

**Who should read this:** Frontend developers using application-specific features

---

### 4. [Data Models Reference](./API_DATA_MODELS.md)
Detailed schema reference for example models with complete TypeScript integration.

**Topics covered:**
- User model (with login endpoint)
- Product model (with comment relationship)
- Comment model (nested resource example)
- Field-level details and constraints
- Complete request/response examples
- TypeScript interfaces and API clients
- Foreign key resolution
- Dynamic form generation from schemas

**Who should read this:** Frontend developers needing detailed schema information

---

## 🚀 Quick Start Guide

### First Time Using a PyBend API?

Follow this path:

1. **Read**: [API Overview](./API_OVERVIEW.md) - Understand the basics (15 minutes)
2. **Explore**: Open `http://localhost:8000/docs` in your browser for interactive documentation
3. **Try**: Use the interactive docs to make your first API call
4. **Reference**: Use [Standard CRUD Endpoints](./API_CRUD_ENDPOINTS.md) as you build

### Building a Feature?

1. **Discover**: `GET /{ModelName}` to get the model's schema and available endpoints
2. **Check**: [Custom Endpoints](./API_CUSTOM_ENDPOINTS.md) for any application-specific methods
3. **Implement**: Use [Data Models Reference](./API_DATA_MODELS.md) for detailed schema information
4. **Handle Errors**: Refer to error handling in [API Overview](./API_OVERVIEW.md)

---

## 🔍 Quick Reference

### Essential Endpoints

For a model called `User` with `__tablename__ = 'users'`:

| Purpose | Method | Endpoint | Documentation |
|---------|--------|----------|---------------|
| Get schema | GET | `/User` | [Overview](./API_OVERVIEW.md#openapi--swagger-documentation) |
| Create | POST | `/users` | [CRUD](./API_CRUD_ENDPOINTS.md#create-resource) |
| List all | GET | `/users` | [CRUD](./API_CRUD_ENDPOINTS.md#list-resources) |
| Get one | GET | `/users/{id}` | [CRUD](./API_CRUD_ENDPOINTS.md#get-single-resource) |
| Update | PUT | `/users/{id}` | [CRUD](./API_CRUD_ENDPOINTS.md#update-resource) |
| Delete | DELETE | `/users/{id}` | [CRUD](./API_CRUD_ENDPOINTS.md#delete-resource) |

### Custom Endpoint Patterns

| Method Type | Pattern | Example | Documentation |
|-------------|---------|---------|---------------|
| Static | `/{resource}{path}` | `POST /users/login` | [Custom](./API_CUSTOM_ENDPOINTS.md#static-method) |
| Class | `/{resource}{path}` | `GET /users/search` | [Custom](./API_CUSTOM_ENDPOINTS.md#class-method) |
| Instance | `/{resource}/{id}{path}` | `POST /products/1/discount` | [Custom](./API_CUSTOM_ENDPOINTS.md#instance-method) |

### HTTP Status Codes

| Code | Meaning | When | How to Handle |
|------|---------|------|---------------|
| 200 | OK | Successful GET/PUT/DELETE | Process response data |
| 201 | Created | Successful POST | Process new resource |
| 400 | Bad Request | Validation error | Show error to user |
| 404 | Not Found | Resource doesn't exist | Show not found message |
| 422 | Unprocessable | Invalid data type | Show field error |
| 500 | Server Error | Backend error | Log and show generic error |

See [API Overview - Status Codes](./API_OVERVIEW.md#status-codes) for details.

---

## 📋 Common Tasks

### Create a Resource

```javascript
const user = await fetch('http://localhost:8000/users', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    name: 'Alice',
    email: 'alice@example.com'
  })
}).then(r => r.json());
```

See: [CRUD - Create Resource](./API_CRUD_ENDPOINTS.md#create-resource)

### Get All Resources

```javascript
const users = await fetch('http://localhost:8000/users')
  .then(r => r.json());
```

See: [CRUD - List Resources](./API_CRUD_ENDPOINTS.md#list-resources)

### Update a Resource

```javascript
const updated = await fetch('http://localhost:8000/users/1', {
  method: 'PUT',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ age: 29 })
}).then(r => r.json());
```

See: [CRUD - Update Resource](./API_CRUD_ENDPOINTS.md#update-resource)

### Call a Custom Endpoint

```javascript
const result = await fetch('http://localhost:8000/users/login', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    email: 'alice@example.com',
    password: 'secret'
  })
}).then(r => r.json());
```

See: [Custom Endpoints](./API_CUSTOM_ENDPOINTS.md#static-method)

### Handle Errors

```javascript
try {
  const response = await fetch('/users', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(userData)
  });
  
  if (!response.ok) {
    const error = await response.json();
    const message = error.detail?.[0]?.error || 'Unknown error';
    console.error('API Error:', message);
    return null;
  }
  
  return await response.json();
  
} catch (err) {
  console.error('Network error:', err);
  return null;
}
```

See: [Overview - Error Handling](./API_OVERVIEW.md#error-handling)

### Work with Relationships

```javascript
// Create a comment on a product (nested resource)
const comment = await fetch('http://localhost:8000/products/1/comments', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    text: 'Great product!',
    user: 1  // Foreign key - send ID
  })
}).then(r => r.json());

// Get the full user object
const user = await fetch(`http://localhost:8000/users/${comment.user}`)
  .then(r => r.json());
```

See: [Overview - Foreign Keys](./API_OVERVIEW.md#foreign-keys--relationships)

---

## 🎯 By Use Case

### Building a Login Form

1. Read: [Custom Endpoints - Authentication Pattern](./API_CUSTOM_ENDPOINTS.md#1-authentication)
2. Check: Does your User model have a `/login` endpoint? `GET /User` to see schema
3. Implement: Use the pattern from [Complete Authentication Flow](./API_CUSTOM_ENDPOINTS.md#example-complete-authentication-flow)

### Building a Product Listing

1. Read: [CRUD - List Resources](./API_CRUD_ENDPOINTS.md#list-resources)
2. If filtering needed: Check for custom search endpoint in [Custom Endpoints](./API_CUSTOM_ENDPOINTS.md#2-searchfilter)
3. For details: See [Data Models - Product](./API_DATA_MODELS.md#product-model)

### Building a Comment System

1. Read: [CRUD - Nested Resources](./API_CRUD_ENDPOINTS.md#nested-resource-endpoints)
2. For schema: See [Data Models - Comment](./API_DATA_MODELS.md#comment-model)
3. Complete example: [Data Models - React Component](./API_DATA_MODELS.md#complete-frontend-integration-example)

### Dynamic Form Generation

1. Read: [Data Models - Schema Discovery](./API_DATA_MODELS.md#schema-discovery)
2. Fetch schema: `GET /{ModelName}`
3. Generate fields based on `properties` and `required` arrays

### TypeScript Integration

1. Define interfaces: See [Data Models - TypeScript Interfaces](./API_DATA_MODELS.md#typescript-interface)
2. Build type-safe clients: See examples in each model section
3. Reference: [CRUD - TypeScript Integration](./API_CRUD_ENDPOINTS.md#typescript-integration)

---

## 🔧 Tools & Resources

### Interactive API Explorer

Visit `http://localhost:8000/docs` (FastAPI backend) for:
- Complete endpoint listing
- Request/response examples
- Try-it-out functionality
- Automatic schema documentation

### Schema Endpoint

For any model: `GET /{ModelName}` returns complete JSON schema including:
- All fields with types
- Required fields
- Custom methods and parameters
- Validation rules

Example:
```bash
curl http://localhost:8000/User
```

### OpenAPI Specification

The entire API is documented using OpenAPI 3.0 standard, accessible at:
- `http://localhost:8000/openapi.json` (FastAPI)

---

## 💡 Best Practices

### Always Check Schemas First

```javascript
// Get schema to understand available fields and methods
const schema = await fetch('/User').then(r => r.json());
console.log('Available methods:', Object.keys(schema.methods));
console.log('Required fields:', schema.required);
```

### Handle All Error Cases

```javascript
async function apiCall(url, options) {
  try {
    const response = await fetch(url, options);
    
    if (!response.ok) {
      const error = await response.json();
      
      switch (response.status) {
        case 400: // Validation
          showValidationError(error.detail[0].error);
          break;
        case 404: // Not found
          showNotFound();
          break;
        case 422: // Invalid format
          showFieldError(error.detail);
          break;
        default:
          showGenericError();
      }
      return null;
    }
    
    return await response.json();
  } catch (err) {
    console.error('Network error:', err);
    showNetworkError();
    return null;
  }
}
```

See: [Overview - Error Handling](./API_OVERVIEW.md#error-handling)

### Use TypeScript for Type Safety

```typescript
interface User {
  id: number;
  name: string;
  email: string;
}

async function getUser(id: number): Promise<User> {
  return await fetch(`/users/${id}`).then(r => r.json());
}
```

See: [Data Models - TypeScript](./API_DATA_MODELS.md#typescript-interface)

### Cache Schema Information

```javascript
const schemaCache = new Map();

async function getSchema(modelName) {
  if (!schemaCache.has(modelName)) {
    const schema = await fetch(`/${modelName}`).then(r => r.json());
    schemaCache.set(modelName, schema);
  }
  return schemaCache.get(modelName);
}
```

---

## 🆘 Troubleshooting

### "Not found" on Custom Endpoint

1. Check schema: `GET /{ModelName}` → Look in `methods` object
2. Verify URL pattern matches method type (static/class/instance)
3. See: [Custom Endpoints - URL Patterns](./API_CUSTOM_ENDPOINTS.md#endpoint-url-patterns)

### "Missing field: X"

1. Check schema for required fields: `GET /{ModelName}` → Look in `required` array
2. Ensure all required fields are in request body
3. See: [CRUD - Create Resource](./API_CRUD_ENDPOINTS.md#create-resource)

### "Invalid field 'X': ..."

1. Check field type in schema: `GET /{ModelName}` → Look in `properties.X.type`
2. Ensure request value matches expected type
3. See: [Overview - Data Types](./API_OVERVIEW.md#data-types)

### Foreign Key Not Resolving

Remember: Foreign keys are stored as IDs, not full objects.

```javascript
// Response contains ID
const comment = await fetch('/comments/1').then(r => r.json());
// { user: 1 } ← This is an ID, not a user object

// Fetch full object separately
const user = await fetch(`/users/${comment.user}`).then(r => r.json());
// { id: 1, name: "Alice", ... } ← Full object
```

See: [Overview - Foreign Keys](./API_OVERVIEW.md#foreign-keys--relationships)

---

## 📞 Getting Help

1. **Check the docs** - Use this index to find relevant sections
2. **Try interactive docs** - Visit `/docs` endpoint
3. **Inspect schemas** - `GET /{ModelName}` for model details
4. **Check examples** - Each doc section includes working code examples
5. **Read error messages** - Error responses include detailed stack traces

---

## 📖 Complete Documentation Set

- **[API Overview](./API_OVERVIEW.md)** - Conventions, setup, and general concepts
- **[Standard CRUD Endpoints](./API_CRUD_ENDPOINTS.md)** - Auto-generated REST endpoints
- **[Custom Endpoints](./API_CUSTOM_ENDPOINTS.md)** - Application-specific business logic
- **[Data Models Reference](./API_DATA_MODELS.md)** - Detailed schema and examples

---

## 🎓 Additional Resources

- [PyBend README](./README.md) - Project overview and setup
- [Getting Started Guide](./GETTING_STARTED.md) - Tutorial for building your first API
- [Examples](./EXAMPLES.md) - Real-world application patterns
- [Architecture Guide](./ARCHITECTURE.md) - Backend implementation details (for backend devs)

---

*Last Updated: 2025-01-15*  
*PyBend Version: 0.5.0*
