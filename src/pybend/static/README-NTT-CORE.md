# NTT.js - Named Thing Transaction

**A functional, reactive state management system for frontend applications with seamless backend integration.**

## Overview

NTT (Named Thing Transaction) is the core class of the NTTTX framework that provides functional state management, reactive subscriptions, and automatic backend synchronization. It creates virtual representations of backend entities with optimistic updates, conflict resolution, and real-time data binding.

## Table of Contents

- [Installation](#installation)
- [Quick Start](#quick-start)
- [Core Concepts](#core-concepts)
- [API Reference](#api-reference)
- [Advanced Usage](#advanced-usage)
- [Integration Patterns](#integration-patterns)
- [Best Practices](#best-practices)
- [Troubleshooting](#troubleshooting)

## Installation

```javascript
import { NTT } from './NTT.js';
import { EntityRegistry } from './EntityRegistry.js';
import { NTTFunctional } from './NTTFunctional.js';
import { NTTReactive } from './NTTReactive.js';
```

**Dependencies:**
- `NTTUtils.js` - Utility functions
- `EntityRegistry.js` - Instance management
- `NTTFunctional.js` - State operations
- `NTTReactive.js` - Subscription management
- `Event.js` - Event system

## Quick Start

### Basic Instance Creation

```javascript
// Create a new NTT instance
const user = new NTT({
  name: 'UserProfile',
  addr: '/api/users/123',
  data: {
    name: 'John Doe',
    email: 'john@example.com',
    age: 30
  }
});

console.log(user.id);       // Auto-generated unique ID
console.log(user.data);     // Current state data
console.log(user.isDirty);  // false (no changes yet)
```

### Functional State Management

```javascript
// Apply state transformations
NTT.evolve(user.id, { age: 31, status: 'active' });

// Functional transformation
NTT.evolve(user.id, (state) => ({
  ...state,
  email: state.email.toLowerCase(),
  lastModified: Date.now()
}));

// Commit changes to backend
await NTT.commit(user.id);

// Rollback uncommitted changes
NTT.rollback(user.id);
```

### Reactive Subscriptions

```javascript
// Subscribe to all changes
const unsubscribe = NTT.subscribe(user.id, (newData, oldData, ntt) => {
  console.log('User changed:', newData);
});

// Observe specific property
const unsubscribeEmail = NTT.observe(user.id, 'email', (newValue, oldValue) => {
  console.log(`Email changed: ${oldValue} → ${newValue}`);
});

// Clean up
unsubscribe();
unsubscribeEmail();
```

## Core Concepts

### State Architecture

NTT uses a **functional state management** approach with three key state layers:

```javascript
const ntt = new NTT({ data: { name: 'John' } });

// Three state layers:
ntt.data         // Current working state (localState)
ntt.remoteState  // Last known server state
ntt.pendingOps   // Array of uncommitted operations
```

### State Lifecycle

1. **Creation** → Initial state set as both local and remote
2. **Evolution** → Local state changes, marked as dirty
3. **Commit** → Sync to backend, update remote state
4. **Rollback** → Revert to remote state if needed

### Hash-Based Integrity

Every NTT instance maintains a hash of its data for integrity checking:

```javascript
console.log(ntt.hash);    // e.g., "a1b2c3d4"
NTT.evolve(ntt.id, { age: 31 });
console.log(ntt.hash);    // Changed: "e5f6g7h8"
```

## API Reference

### Constructor

```javascript
new NTT(config)
```

**Parameters:**
- `config.name` (string) - Entity name identifier
- `config.addr` (string) - Backend endpoint address
- `config.href` (string, optional) - View URL (defaults to addr)
- `config.data` (object, optional) - Initial state data
- `config.prototype` (object|string, optional) - Schema or schema URL
- `config.meta` (object, optional) - Additional metadata
- `config.id` (string, optional) - Custom ID (auto-generated if not provided)

**Example:**
```javascript
const product = new NTT({
  name: 'Product_Widget',
  addr: '/api/products/456',
  data: { name: 'Widget', price: 19.99 },
  prototype: '/api/products/schema'
});
```

### Instance Properties

#### Read-Only Properties

```javascript
ntt.id              // string - Unique instance identifier
ntt.name            // string - Entity name
ntt.addr            // string - Backend address
ntt.href            // string - View URL
ntt.data            // object - Current state (localState)
ntt.remoteState     // object - Last known server state
ntt.pendingOps      // array - Uncommitted operations
ntt.version         // number - Optimistic locking version
ntt.isDirty         // boolean - Has uncommitted changes
ntt.isCommitting    // boolean - Currently syncing
ntt.hash            // string - Data integrity hash
```

#### Writable Properties

```javascript
ntt.name = 'NewName';           // Update entity name
ntt.data = { newField: 'value' }; // Merge new data (triggers change notification)
```

### Static Methods - Entity Registry

#### NTT.register(factoryId, model, onSuccess, onError, url)

Register a factory for creating NTT instances via API.

**Parameters:**
- `factoryId` (string) - Unique factory identifier
- `model` (string) - Model type name
- `onSuccess` (function) - Success callback `(ntt) => {}`
- `onError` (function) - Error callback `(error) => {}`
- `url` (string) - API base URL

**Example:**
```javascript
NTT.register('users', 'User',
  (ntt) => console.log('User created:', ntt.data),
  (error) => console.error('Error:', error),
  'http://localhost:8000/users'
);
```

#### NTT.create(factoryId, data)

Create a new NTT instance via registered factory.

**Example:**
```javascript
NTT.create('users', {
  name: 'Jane Smith',
  email: 'jane@example.com'
});
```

#### NTT.get(instanceId)

Retrieve an NTT instance by ID.

**Returns:** `NTT | null`

```javascript
const user = NTT.get('user-instance-id');
if (user) {
  console.log(user.data);
}
```

#### NTT.getAllInstances()

Get all registered NTT instances.

**Returns:** `Map<string, NTT>`

```javascript
const allInstances = NTT.getAllInstances();
console.log(`Total instances: ${allInstances.size}`);
```

#### NTT.remove(instanceId)

Remove an NTT instance from registry.

**Returns:** `boolean`

#### NTT.clear()

Clear all instances and factories.

#### NTT.discover(url)

Discover API schemas from backend.

```javascript
NTT.discover('http://localhost:8000/api/schema');
```

### Static Methods - Functional Operations

#### NTT.evolve(instanceId, transformation, metadata?)

Apply a pure transformation to an NTT instance's state.

**Parameters:**
- `instanceId` (string) - NTT instance ID
- `transformation` (function|object) - State transformation
- `metadata` (object, optional) - Operation metadata

**Returns:** `NTT` - The updated instance

**Examples:**
```javascript
// Object merge
NTT.evolve(user.id, { age: 31, status: 'active' });

// Functional transformation
NTT.evolve(user.id, (state) => ({
  ...state,
  fullName: `${state.firstName} ${state.lastName}`
}));

// With metadata
NTT.evolve(user.id, { age: 32 }, { source: 'birthday' });
```

#### NTT.commit(instanceId)

Commit pending changes to the server.

**Returns:** `Promise<NTT>`

```javascript
try {
  const ntt = await NTT.commit(user.id);
  console.log('Committed successfully:', ntt.hash);
} catch (error) {
  console.error('Commit failed:', error);
}
```

#### NTT.rollback(instanceId)

Discard pending changes and revert to remote state.

**Returns:** `NTT`

```javascript
if (user.isDirty) {
  NTT.rollback(user.id);
  console.log('Changes rolled back');
}
```

#### NTT.merge(instanceId, otherInstanceId, conflictResolver?)

Merge two NTT instances with conflict resolution.

**Parameters:**
- `instanceId` (string) - Target instance ID
- `otherInstanceId` (string) - Source instance ID
- `conflictResolver` (function, optional) - Custom conflict resolver

**Example:**
```javascript
// Default conflict resolution
NTT.merge(userA.id, userB.id);

// Custom conflict resolver
NTT.merge(userA.id, userB.id, (conflict, localNTT, otherNTT) => {
  if (conflict.property === 'email') {
    return conflict.otherValue; // Always prefer other email
  }
  return conflict.localValue; // Default to local
});
```

#### NTT.pull(instanceId)

Refresh data from server without overwriting local changes.

```javascript
NTT.pull(user.id); // Fetches latest server state
```

#### NTT.setConflictResolver(instanceId, resolver)

Set a custom conflict resolver for an instance.

```javascript
NTT.setConflictResolver(user.id, (conflict, localNTT, otherNTT) => {
  // Custom resolution logic
  return otherNTT.version > localNTT.version ? 
    conflict.otherValue : conflict.localValue;
});
```

### Static Methods - Reactive Subscriptions

#### NTT.subscribe(instanceId, callback)

Subscribe to all changes on an NTT instance.

**Parameters:**
- `instanceId` (string) - NTT instance ID
- `callback` (function) - `(newData, oldData, ntt) => {}`

**Returns:** `function` - Unsubscribe function

```javascript
const unsubscribe = NTT.subscribe(user.id, (newData, oldData, ntt) => {
  console.log('User changed:', {
    changes: Object.keys(newData).filter(k => newData[k] !== oldData[k]),
    version: ntt.version,
    isDirty: ntt.isDirty
  });
});

// Later...
unsubscribe();
```

#### NTT.observe(instanceId, property, callback)

Observe changes to a specific property.

**Parameters:**
- `instanceId` (string) - NTT instance ID
- `property` (string) - Property name to observe
- `callback` (function) - `(newValue, oldValue, property, ntt) => {}`

**Returns:** `function` - Unsubscribe function

```javascript
const unsubscribeEmail = NTT.observe(user.id, 'email', (newVal, oldVal) => {
  if (newVal && !newVal.includes('@')) {
    console.warn('Invalid email format!');
  }
});
```

#### NTT.unsubscribeAll(instanceId)

Remove all subscriptions from an NTT instance.

```javascript
NTT.unsubscribeAll(user.id);
```

### Instance Methods

#### resolveAndPromote(url)

Resolve and apply a schema from a URL.

**Returns:** `Promise<NTT>`

```javascript
await user.resolveAndPromote('/api/users/schema');
// User now has dynamic properties based on schema
```

#### toJSON()

Serialize the NTT instance to JSON.

**Returns:** `object`

```javascript
const serialized = user.toJSON();
// Safe for JSON.stringify() - excludes non-serializable items
```

#### clone()

Create a deep copy of the NTT instance.

**Returns:** `NTT`

```javascript
const userCopy = user.clone();
// Fresh instance with same data but no subscriptions
```

## Advanced Usage

### Dynamic Schema Promotion

NTT instances can dynamically promote themselves based on backend schemas:

```javascript
const user = new NTT({
  name: 'DynamicUser',
  addr: '/api/users/123',
  prototype: '/api/users/schema' // Fetches schema and applies
});

// After promotion, dynamic properties are available:
setTimeout(() => {
  user.email = 'new@example.com'; // Type-checked against schema
  user.age = 25;                  // Validated as number
}, 1000);
```

### Complex State Transformations

```javascript
// Multi-step transformation with metadata
NTT.evolve(user.id, (state) => {
  const updates = { ...state };
  
  // Calculate derived fields
  updates.fullName = `${state.firstName} ${state.lastName}`;
  updates.ageGroup = state.age < 18 ? 'minor' : 'adult';
  updates.lastModified = Date.now();
  
  return updates;
}, { operation: 'profile-update', timestamp: Date.now() });
```

### Batch Operations

```javascript
// Create multiple instances
const userIds = [];
const userData = [
  { name: 'Alice', email: 'alice@example.com' },
  { name: 'Bob', email: 'bob@example.com' },
  { name: 'Charlie', email: 'charlie@example.com' }
];

userData.forEach(data => {
  NTT.create('users', data);
});

// Subscribe to all at once
const allUsers = NTT.getAllInstances();
allUsers.forEach((ntt, id) => {
  if (ntt.data.email) {
    NTT.subscribe(id, (newData) => {
      console.log(`User ${newData.name} updated`);
    });
  }
});
```

### Error Handling and Recovery

```javascript
// Robust commit with error handling
async function safeCommit(instanceId) {
  const ntt = NTT.get(instanceId);
  if (!ntt || !ntt.isDirty) return;
  
  const backupData = { ...ntt.data };
  
  try {
    await NTT.commit(instanceId);
    console.log('✅ Commit successful');
  } catch (error) {
    console.error('❌ Commit failed:', error);
    
    // Option 1: Rollback
    NTT.rollback(instanceId);
    
    // Option 2: Retry with exponential backoff
    setTimeout(() => safeCommit(instanceId), 2000);
    
    // Option 3: Store for later sync
    localStorage.setItem(`pending_${instanceId}`, JSON.stringify(backupData));
  }
}
```

## Integration Patterns

### React Integration

```javascript
// Custom React hook for NTT instances
function useNTT(instanceId) {
  const [data, setData] = useState(null);
  const [isDirty, setIsDirty] = useState(false);
  
  useEffect(() => {
    const ntt = NTT.get(instanceId);
    if (!ntt) return;
    
    setData(ntt.data);
    setIsDirty(ntt.isDirty);
    
    const unsubscribe = NTT.subscribe(instanceId, (newData, _, ntt) => {
      setData(newData);
      setIsDirty(ntt.isDirty);
    });
    
    return unsubscribe;
  }, [instanceId]);
  
  return { data, isDirty };
}

// Usage in component
function UserProfile({ userId }) {
  const { data, isDirty } = useNTT(userId);
  
  return (
    <div>
      <h1>{data?.name}</h1>
      {isDirty && <span>Unsaved changes</span>}
    </div>
  );
}
```

### Vue.js Integration

```javascript
// Vue composable
function useNTT(instanceId) {
  const data = ref(null);
  const isDirty = ref(false);
  
  onMounted(() => {
    const ntt = NTT.get(instanceId);
    if (!ntt) return;
    
    data.value = ntt.data;
    isDirty.value = ntt.isDirty;
    
    const unsubscribe = NTT.subscribe(instanceId, (newData, _, ntt) => {
      data.value = newData;
      isDirty.value = ntt.isDirty;
    });
    
    onUnmounted(unsubscribe);
  });
  
  return { data, isDirty };
}
```

### Web Components Integration

```javascript
class NTTComponent extends HTMLElement {
  connectedCallback() {
    const nttId = this.getAttribute('ntt-id');
    if (nttId) {
      this.unsubscribe = NTT.subscribe(nttId, (data) => {
        this.render(data);
      });
    }
  }
  
  disconnectedCallback() {
    if (this.unsubscribe) {
      this.unsubscribe();
    }
  }
}
```

## Best Practices

### 1. Factory Registration

Always register factories at application startup:

```javascript
// At app initialization
const factories = [
  { id: 'users', model: 'User', url: '/api/users' },
  { id: 'products', model: 'Product', url: '/api/products' },
  { id: 'orders', model: 'Order', url: '/api/orders' }
];

factories.forEach(({ id, model, url }) => {
  NTT.register(id, model,
    (ntt) => console.log(`${model} operation success`),
    (error) => console.error(`${model} error:`, error),
    url
  );
});
```

### 2. State Management

Use functional transformations for complex state changes:

```javascript
// Good: Functional transformation
NTT.evolve(user.id, (state) => ({
  ...state,
  profile: {
    ...state.profile,
    lastSeen: Date.now()
  },
  metrics: calculateMetrics(state)
}));

// Bad: Direct mutation
const user = NTT.get(userId);
user.data.profile.lastSeen = Date.now(); // Don't do this!
```

### 3. Subscription Management

Always clean up subscriptions:

```javascript
class UserManager {
  constructor() {
    this.subscriptions = [];
  }
  
  watchUser(userId) {
    const unsubscribe = NTT.subscribe(userId, this.handleUserChange);
    this.subscriptions.push(unsubscribe);
  }
  
  destroy() {
    this.subscriptions.forEach(unsubscribe => unsubscribe());
    this.subscriptions = [];
  }
}
```

### 4. Error Handling

Implement comprehensive error handling:

```javascript
// Wrapper for safe NTT operations
class SafeNTT {
  static async safeCommit(instanceId) {
    try {
      return await NTT.commit(instanceId);
    } catch (error) {
      if (error.status === 409) {
        // Conflict - refresh and try merge
        NTT.pull(instanceId);
        throw new ConflictError('Data was modified by another user');
      } else if (error.status >= 500) {
        // Server error - queue for retry
        this.queueForRetry(instanceId);
        throw new ServerError('Server temporarily unavailable');
      }
      throw error;
    }
  }
}
```

### 5. Performance Optimization

Batch operations when possible:

```javascript
// Batch subscription setup
function setupUserSubscriptions(userIds) {
  const subscriptions = userIds.map(id => 
    NTT.subscribe(id, (data) => updateUserUI(id, data))
  );
  
  return () => subscriptions.forEach(unsub => unsub());
}
```

## Troubleshooting

### Common Issues

#### 1. Instance Not Found

```javascript
const user = NTT.get('invalid-id');
if (!user) {
  console.error('User instance not found');
  // Handle gracefully
}
```

#### 2. Subscription Memory Leaks

```javascript
// Always store unsubscribe functions
const subscriptions = new Set();

function addSubscription(instanceId, callback) {
  const unsubscribe = NTT.subscribe(instanceId, callback);
  subscriptions.add(unsubscribe);
  return unsubscribe;
}

function cleanup() {
  subscriptions.forEach(unsubscribe => unsubscribe());
  subscriptions.clear();
}
```

#### 3. Commit Failures

```javascript
// Handle commit failures gracefully
NTT.commit(user.id).catch(error => {
  if (error.status === 409) {
    // Conflict - show merge dialog
    showMergeConflictDialog(user.id);
  } else {
    // Other error - show retry option
    showRetryDialog(user.id);
  }
});
```

### Debug Mode

Enable debug logging for troubleshooting:

```javascript
// Enable debug mode (if implemented)
NTT.debug = true;

// Or check internal state
const user = NTT.get(userId);
console.log('Debug info:', {
  id: user.id,
  version: user.version,
  isDirty: user.isDirty,
  pendingOps: user.pendingOps.length,
  hash: user.hash
});
```

## Performance Considerations

- **Memory Usage**: NTT instances are kept in memory. Use `NTT.remove()` for cleanup
- **Subscription Overhead**: Each subscription adds overhead. Unsubscribe when not needed
- **Network Requests**: `commit()` and `pull()` make HTTP requests. Use judiciously
- **State Size**: Large state objects increase hash computation time

## Version History

- **v1.0.0** - Initial release with functional state management
- **v1.1.0** - Added reactive subscriptions
- **v1.2.0** - Dynamic schema promotion
- **v1.3.0** - Conflict resolution and merge operations
- **v1.4.0** - Web Components integration

---

**License:** MIT  
**Maintainers:** NTTTX Framework Team  
**Issues:** [GitHub Issues](https://github.com/your-repo/ntttx/issues)