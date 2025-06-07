// connected-engine.js - PyBend Integration Logic

// Global state
let userEntities = new Map();
let productEntities = new Map();
let subscriptions = [];
let requestCount = 0;
let isConnected = false;

// API Base URL (no /api prefix for now)
const API_BASE = 'http://localhost:8000';

// Utility functions
window.log = function(type, message, outputId = 'user-output') {
    const output = document.getElementById(outputId);
    if (!output) return;
    
    const entry = document.createElement('div');
    entry.className = `log-entry log-${type}`;
    entry.textContent = `[${new Date().toLocaleTimeString()}] ${message}`;
    output.appendChild(entry);
    output.scrollTop = output.scrollHeight;
};

function updateDisplay(data, displayId) {
    const display = document.getElementById(displayId);
    if (display) {
        display.textContent = JSON.stringify(data, null, 2);
    }
}

function incrementRequestCount() {
    requestCount++;
    document.getElementById('request-count').textContent = requestCount;
}

window.updateCounters = function() {
    const instanceCount = window.NTT ? window.NTT.getAllInstances().size : 0;
    document.getElementById('instance-count').textContent = instanceCount;

    let subscriptionCount = 0;
    if (window.NTT) {
        window.NTT.getAllInstances().forEach(instance => {
            subscriptionCount += instance._meta.subscribers.size;
            instance._meta.propertyObservers.forEach(observers => {
                subscriptionCount += observers.size;
            });
        });
    }
    document.getElementById('subscription-count').textContent = subscriptionCount;

    const factoryCount = window.Registry ?
        (window.Registry.factories ? window.Registry.factories.size : 0) : 0;
    document.getElementById('factory-count').textContent = factoryCount;
};

function updateEntitySelector() {
    const selector = document.getElementById('entity-selector');
    if (!selector) return;
    
    selector.innerHTML = '<option value="">Select entity...</option>';
    
    if (window.NTT) {
        window.NTT.getAllInstances().forEach((ntt, id) => {
            const option = document.createElement('option');
            option.value = id;
            option.textContent = `${ntt.name} (${id.substring(0, 8)}...)`;
            selector.appendChild(option);
        });
    }
}

// Connection management
async function checkPyBendConnection() {
    try {
        // Test with users schema endpoint (without /api prefix)
        const response = await fetch(`${API_BASE}/users/schema`);
        if (response.ok) {
            isConnected = true;
            updateConnectionStatus('connected', 'PyBend API Connected');
            const data = await response.json();
            document.getElementById('backend-info').textContent = 
                `PyBend Backend • Schemas Available • Ready for Integration`;
            return true;
        }
    } catch (error) {
        console.error('PyBend connection failed:', error);
    }
    
    isConnected = false;
    updateConnectionStatus('disconnected', 'PyBend API Unavailable');
    document.getElementById('backend-info').textContent = 
        'Please ensure PyBend is running on localhost:8000';
    return false;
}

function updateConnectionStatus(status, message) {
    const indicator = document.getElementById('status-indicator');
    const badge = document.getElementById('connection-status-badge');
    const text = document.getElementById('connection-text');
    
    if (indicator) indicator.className = `status-indicator ${status}`;
    if (text) text.textContent = message;
    if (badge) {
        badge.textContent = status === 'connected' ? 'Online' : 'Offline';
        badge.className = `status-value ${status}`;
    }
}

// Initialize system
async function initializeConnectedSystem() {
    window.log('info', '🔗 Initializing PyBend connection...');
    
    const connected = await checkPyBendConnection();
    
    if (connected) {
        await setupPyBendFactories();
        window.log('success', '✅ PyBend integration ready!');
        window.log('info', 'All PyBend endpoints configured');
    } else {
        window.log('warning', '⚠️ PyBend backend not available');
        window.log('info', 'Start PyBend server: python main.py');
    }
    
    window.updateCounters();
}

// Setup PyBend factories
async function setupPyBendFactories() {
    // Register User factory (without /api prefix)
    window.NTT.register(
        'users',
        'User',
        (ntt) => {
            userEntities.set(ntt.id, ntt);
            window.log('success', `✅ User operation: ${ntt.data.name}`, 'user-output');
            updateEntitySelector();
            window.updateCounters();
        },
        (error) => {
            window.log('error', `❌ User error: ${error}`, 'user-output');
        },
        `${API_BASE}/users`
    );

    // Register Product factory (replacing bots)
    window.NTT.register(
        'products',
        'Product',
        (ntt) => {
            productEntities.set(ntt.id, ntt);
            window.log('success', `✅ Product operation: ${ntt.data.name}`, 'product-output');
            updateEntitySelector();
            window.updateCounters();
        },
        (error) => {
            window.log('error', `❌ Product error: ${error}`, 'product-output');
        },
        `${API_BASE}/products`
    );

    window.log('success', 'PyBend factories registered');
}

// PyBend User Management
function createPyBendUser() {
    const name = document.getElementById('user-name').value;
    const email = document.getElementById('user-email').value;
    const age = parseInt(document.getElementById('user-age').value) || null;
    
    if (!name || !email) {
        window.log('error', 'Name and email are required', 'user-output');
        return;
    }

    if (!isConnected) {
        window.log('error', 'PyBend backend not connected', 'user-output');
        return;
    }

    const userData = { name, email };
    if (age) userData.age = age;

    window.log('info', 'Creating user via PyBend API...', 'user-output');
    incrementRequestCount();
    
    window.NTT.create('users', userData);
    
    // Clear inputs
    document.getElementById('user-name').value = '';
    document.getElementById('user-email').value = '';
    document.getElementById('user-age').value = '';
}

function loadPyBendUsers() {
    if (!isConnected) {
        window.log('error', 'PyBend backend not connected', 'user-output');
        return;
    }

    window.log('info', 'Loading users from PyBend...', 'user-output');
    incrementRequestCount();

    window.HTTP.get(`${API_BASE}/users`, (response) => {
        window.log('success', `Loaded ${response.length} users`, 'user-output');
        
        // Create NTT instances for each user
        response.forEach((userData) => {
            const ntt = new window.NTT({
                name: `User_${userData.name}`,
                addr: `${API_BASE}/users/${userData.id}`,
                data: userData
            });
            ntt._meta.remoteState = { ...userData };
            ntt._meta.isDirty = false;
            userEntities.set(ntt.id, ntt);
        });
        
        updateDisplay(response, 'user-data');
        updateEntitySelector();
        window.updateCounters();
    }, (error) => {
        window.log('error', `Failed to load users: ${error}`, 'user-output');
    });
}

// PyBend Product Management (replacing bots)
function createPyBendProduct() {
    const name = document.getElementById('product-name').value;
    const price = parseFloat(document.getElementById('product-price').value);
    const description = document.getElementById('product-description').value || '';
    
    if (!name || !price) {
        window.log('error', 'Name and price are required', 'product-output');
        return;
    }

    if (!isConnected) {
        window.log('error', 'PyBend backend not connected', 'product-output');
        return;
    }

    const productData = {
        name,
        price,
        description
    };

    window.log('info', 'Creating product via PyBend API...', 'product-output');
    incrementRequestCount();
    
    window.NTT.create('products', productData);
    
    // Clear inputs
    document.getElementById('product-name').value = '';
    document.getElementById('product-price').value = '';
    document.getElementById('product-description').value = '';
}

function loadPyBendProducts() {
    if (!isConnected) {
        window.log('error', 'PyBend backend not connected', 'product-output');
        return;
    }

    window.log('info', 'Loading products from PyBend...', 'product-output');
    incrementRequestCount();

    window.HTTP.get(`${API_BASE}/products`, (response) => {
        window.log('success', `Loaded ${response.length} products`, 'product-output');
        
        // Create NTT instances for each product
        response.forEach((productData) => {
            const ntt = new window.NTT({
                name: `Product_${productData.name}`,
                addr: `${API_BASE}/products/${productData.id}`,
                data: productData
            });
            ntt._meta.remoteState = { ...productData };
            ntt._meta.isDirty = false;
            productEntities.set(ntt.id, ntt);
        });
        
        updateDisplay(response, 'product-data');
        updateEntitySelector();
        window.updateCounters();
    }, (error) => {
        window.log('error', `Failed to load products: ${error}`, 'product-output');
    });
}

// Real-time State Management
function evolveSelectedEntity() {
    const selector = document.getElementById('entity-selector');
    const selectedId = selector.value;
    
    if (!selectedId) {
        window.log('error', 'Please select an entity first', 'state-output');
        return;
    }

    const entity = window.NTT.get(selectedId);
    if (!entity) {
        window.log('error', 'Entity not found', 'state-output');
        return;
    }

    // Apply random evolution based on entity type
    let evolution = {};
    if (entity.data.email) { // User entity
        evolution = {
            lastModified: new Date().toISOString(),
            age: (entity.data.age || 25) + Math.floor(Math.random() * 5)
        };
    } else if (entity.data.price !== undefined) { // Product entity
        evolution = {
            price: parseFloat((entity.data.price * (0.9 + Math.random() * 0.2)).toFixed(2)),
            description: entity.data.description + ' (Updated)',
            lastModified: new Date().toISOString()
        };
    }

    const oldVersion = entity.version;
    const oldHash = entity.hash;
    
    window.NTT.evolve(selectedId, evolution);
    
    window.log('success', `Evolved ${entity.name}`, 'state-output');
    window.log('info', `Version: ${oldVersion} → ${entity.version}`, 'state-output');
    window.log('info', `Hash: ${oldHash} → ${entity.hash}`, 'state-output');
    
    updateDisplay({
        name: entity.name,
        data: entity.data,
        version: entity.version,
        hash: entity.hash,
        isDirty: entity.isDirty
    }, 'state-data');
}

function commitSelectedEntity() {
    const selector = document.getElementById('entity-selector');
    const selectedId = selector.value;
    
    if (!selectedId) {
        window.log('error', 'Please select an entity first', 'state-output');
        return;
    }

    const entity = window.NTT.get(selectedId);
    if (!entity || !entity.isDirty) {
        window.log('warning', 'No changes to commit', 'state-output');
        return;
    }

    window.log('info', 'Committing to PyBend...', 'state-output');
    incrementRequestCount();
    
    window.NTT.commit(selectedId).then(() => {
        window.log('success', 'Successfully committed to PyBend!', 'state-output');
        updateDisplay({
            name: entity.name,
            data: entity.data,
            isDirty: entity.isDirty,
            hash: entity.hash
        }, 'state-data');
    }).catch(err => {
        window.log('error', `Commit failed: ${err.message}`, 'state-output');
    });
}

function rollbackSelectedEntity() {
    const selector = document.getElementById('entity-selector');
    const selectedId = selector.value;
    
    if (!selectedId) {
        window.log('error', 'Please select an entity first', 'state-output');
        return;
    }

    const entity = window.NTT.get(selectedId);
    if (!entity || !entity.isDirty) {
        window.log('warning', 'No changes to rollback', 'state-output');
        return;
    }

    window.NTT.rollback(selectedId);
    window.log('success', 'Rolled back changes', 'state-output');
    
    updateDisplay({
        name: entity.name,
        data: entity.data,
        isDirty: entity.isDirty,
        hash: entity.hash
    }, 'state-data');
}

function refreshSelectedEntity() {
    const selector = document.getElementById('entity-selector');
    const selectedId = selector.value;
    
    if (!selectedId) {
        window.log('error', 'Please select an entity first', 'state-output');
        return;
    }

    window.log('info', 'Refreshing from PyBend API...', 'state-output');
    incrementRequestCount();
    
    window.NTT.pull(selectedId);
    
    setTimeout(() => {
        const entity = window.NTT.get(selectedId);
        if (entity) {
            window.log('success', 'Entity refreshed from PyBend', 'state-output');
            updateDisplay({
                name: entity.name,
                data: entity.data,
                remoteState: entity.remoteState,
                hash: entity.hash
            }, 'state-data');
        }
    }, 1000);
}

// Schema Discovery
function discoverPyBendSchemas() {
    if (!isConnected) {
        window.log('error', 'PyBend backend not connected', 'schema-output');
        return;
    }

    window.log('info', 'Discovering PyBend schemas...', 'schema-output');
    incrementRequestCount();

    // Discover User schema (without /api prefix)
    window.HTTP.get(`${API_BASE}/users/schema`, (userSchema) => {
        window.Registry.registerPrototype('user', userSchema);
        window.log('success', 'User schema discovered', 'schema-output');
        
        // Discover Product schema
        window.HTTP.get(`${API_BASE}/products/schema`, (productSchema) => {
            window.Registry.registerPrototype('product', productSchema);
            window.log('success', 'Product schema discovered', 'schema-output');
            window.log('info', 'All PyBend schemas loaded!', 'schema-output');
        }, (error) => {
            window.log('warning', `Product schema not available: ${error}`, 'schema-output');
        });
    }, (error) => {
        window.log('error', `Schema discovery failed: ${error}`, 'schema-output');
    });
}

function showUserSchema() {
    const schema = window.Registry.getPrototype('user');
    if (schema) {
        window.log('info', '📋 User Schema from PyBend:', 'schema-output');
        window.log('info', JSON.stringify(schema, null, 2), 'schema-output');
    } else {
        window.log('warning', 'User schema not loaded. Run discovery first.', 'schema-output');
    }
}

function showProductSchema() {
    const schema = window.Registry.getPrototype('product');
    if (schema) {
        window.log('info', '📋 Product Schema from PyBend:', 'schema-output');
        window.log('info', JSON.stringify(schema, null, 2), 'schema-output');
    } else {
        window.log('warning', 'Product schema not loaded. Run discovery first.', 'schema-output');
    }
}

function testDynamicPromotion() {
    if (!isConnected) {
        window.log('error', 'PyBend backend not connected', 'schema-output');
        return;
    }

    window.log('info', 'Testing dynamic schema promotion...', 'schema-output');
    
    // Create a new user with schema promotion (without /api prefix)
    const testUser = new window.NTT({
        name: 'DynamicUser',
        addr: `${API_BASE}/users/999`,
        data: { name: 'Test User', email: 'test@example.com', age: 30 },
        prototype: `${API_BASE}/users/schema`
    });

    setTimeout(() => {
        window.log('success', 'Dynamic promotion test completed', 'schema-output');
        window.log('info', `Created: ${testUser.name} with schema validation`, 'schema-output');
    }, 500);
}

// Custom PyBend Endpoints
function testUserLogin() {
    if (!isConnected) {
        window.log('error', 'PyBend backend not connected', 'custom-output');
        return;
    }

    const testEmail = 'test@example.com';
    window.log('info', `Testing user login with ${testEmail}...`, 'custom-output');
    incrementRequestCount();

    // Test the custom login endpoint (without /api prefix)
    window.HTTP.post(`${API_BASE}/users/login`, { email: testEmail }, (response) => {
        window.log('success', `Login test result: ${JSON.stringify(response)}`, 'custom-output');
    }, (error) => {
        window.log('warning', `Login failed (expected): ${error}`, 'custom-output');
    });
}

function getUserSchema() {
    if (!isConnected) {
        window.log('error', 'PyBend backend not connected', 'custom-output');
        return;
    }

    window.log('info', 'Getting user schema via @expose_route...', 'custom-output');
    incrementRequestCount();

    window.HTTP.get(`${API_BASE}/users/schema`, (schema) => {
        window.log('success', 'Schema retrieved via custom endpoint:', 'custom-output');
        window.log('info', JSON.stringify(schema, null, 2), 'custom-output');
    }, (error) => {
        window.log('error', `Schema retrieval failed: ${error}`, 'custom-output');
    });
}

function testRPCCall() {
    if (!isConnected) {
        window.log('error', 'PyBend backend not connected', 'custom-output');
        return;
    }

    window.log('info', 'Testing RPC call to PyBend...', 'custom-output');
    incrementRequestCount();

    // Use the HTTP RPC method
    window.HTTP.rpc('test_method', ['arg1', 'arg2'], { param1: 'value1' }, (response) => {
        window.log('success', `RPC call result: ${JSON.stringify(response)}`, 'custom-output');
    });
}

function testCustomEndpoints() {
    window.log('info', 'Testing all custom PyBend endpoints...', 'custom-output');
    
    setTimeout(() => testUserLogin(), 0);
    setTimeout(() => getUserSchema(), 1000);
    setTimeout(() => testRPCCall(), 2000);
}

// Reactive Subscriptions
function subscribeToAllEntities() {
    if (window.NTT.getAllInstances().size === 0) {
        window.log('warning', 'No entities available. Create some first.', 'reactive-output');
        return;
    }

    window.NTT.getAllInstances().forEach((ntt, id) => {
        const unsubscribe = window.NTT.subscribe(id, (newData, oldData, entity) => {
            window.log('info', `🔔 ${entity.name} changed!`, 'reactive-output');
            window.log('success', `Hash: ${entity.hash}, Version: ${entity.version}`, 'reactive-output');
        });
        subscriptions.push(unsubscribe);
    });

    window.log('success', 'Subscribed to all entities', 'reactive-output');
    window.updateCounters();
}

function observeUserEmails() {
    let emailObservers = 0;
    userEntities.forEach((ntt, id) => {
        if (ntt.data.email) {
            const unsubscribe = window.NTT.observe(id, 'email', (newValue, oldValue, property, entity) => {
                window.log('info', `📧 ${entity.name} email: ${oldValue} → ${newValue}`, 'reactive-output');
                
                // Email validation
                if (newValue && !newValue.includes('@')) {
                    window.log('warning', '⚠️ Invalid email format detected!', 'reactive-output');
                } else if (newValue) {
                    window.log('success', '✅ Valid email format', 'reactive-output');
                }
            });
            subscriptions.push(unsubscribe);
            emailObservers++;
        }
    });

    if (emailObservers > 0) {
        window.log('success', `Observing ${emailObservers} user emails`, 'reactive-output');
    } else {
        window.log('warning', 'No users with emails found', 'reactive-output');
    }
    window.updateCounters();
}

function observeProductPrices() {
    let priceObservers = 0;
    productEntities.forEach((ntt, id) => {
        if (ntt.data.price !== undefined) {
            const unsubscribe = window.NTT.observe(id, 'price', (newValue, oldValue, property, entity) => {
                window.log('info', `💰 ${entity.name} price: $${oldValue} → $${newValue}`, 'reactive-output');
                
                // Price validation
                if (newValue > oldValue) {
                    window.log('success', '📈 Price increased', 'reactive-output');
                } else if (newValue < oldValue) {
                    window.log('warning', '📉 Price decreased', 'reactive-output');
                }
            });
            subscriptions.push(unsubscribe);
            priceObservers++;
        }
    });

    if (priceObservers > 0) {
        window.log('success', `Observing ${priceObservers} product prices`, 'reactive-output');
    } else {
        window.log('warning', 'No products with prices found', 'reactive-output');
    }
    window.updateCounters();
}

function triggerRandomChange() {
    const allEntities = Array.from(window.NTT.getAllInstances().values());
    if (allEntities.length === 0) {
        window.log('warning', 'No entities available to modify', 'reactive-output');
        return;
    }

    const randomEntity = allEntities[Math.floor(Math.random() * allEntities.length)];
    
    // Apply random change based on entity type
    if (randomEntity.data.email) { // User entity
        const changes = [
            { email: `updated.${Date.now()}@example.com` },
            { age: Math.floor(Math.random() * 50) + 20 },
            { email: 'invalid-email' }, // Will trigger validation
            { name: `${randomEntity.data.name} (Updated)` }
        ];
        const randomChange = changes[Math.floor(Math.random() * changes.length)];
        window.NTT.evolve(randomEntity.id, randomChange);
        window.log('info', `Triggered user change: ${JSON.stringify(randomChange)}`, 'reactive-output');
    } else if (randomEntity.data.price !== undefined) { // Product entity
        const changes = [
            { price: parseFloat((Math.random() * 100 + 10).toFixed(2)) },
            { description: `${randomEntity.data.description} (Modified)` },
            { name: `${randomEntity.data.name} v2.0` }
        ];
        const randomChange = changes[Math.floor(Math.random() * changes.length)];
        window.NTT.evolve(randomEntity.id, randomChange);
        window.log('info', `Triggered product change: ${JSON.stringify(randomChange)}`, 'reactive-output');
    }
}

function unsubscribeAllEntities() {
    subscriptions.forEach(unsubscribe => unsubscribe());
    subscriptions = [];
    
    window.NTT.getAllInstances().forEach((ntt, id) => {
        window.NTT.unsubscribeAll(id);
    });
    
    window.log('success', 'Unsubscribed from all entities', 'reactive-output');
    window.updateCounters();
}

// Clear log functions
function clearUserLog() {
    document.getElementById('user-output').innerHTML = '';
    document.getElementById('user-data').textContent = '';
}

function clearProductLog() {
    document.getElementById('product-output').innerHTML = '';
    document.getElementById('product-data').textContent = '';
}

// Make functions globally available
window.initializeConnectedSystem = initializeConnectedSystem;
window.checkPyBendConnection = checkPyBendConnection;
window.createPyBendUser = createPyBendUser;
window.loadPyBendUsers = loadPyBendUsers;
window.createPyBendProduct = createPyBendProduct;
window.loadPyBendProducts = loadPyBendProducts;
window.evolveSelectedEntity = evolveSelectedEntity;
window.commitSelectedEntity = commitSelectedEntity;
window.rollbackSelectedEntity = rollbackSelectedEntity;
window.refreshSelectedEntity = refreshSelectedEntity;
window.discoverPyBendSchemas = discoverPyBendSchemas;
window.showUserSchema = showUserSchema;
window.showProductSchema = showProductSchema;
window.testDynamicPromotion = testDynamicPromotion;
window.testUserLogin = testUserLogin;
window.getUserSchema = getUserSchema;
window.testRPCCall = testRPCCall;
window.testCustomEndpoints = testCustomEndpoints;
window.subscribeToAllEntities = subscribeToAllEntities;
window.observeUserEmails = observeUserEmails;
window.observeProductPrices = observeProductPrices;
window.triggerRandomChange = triggerRandomChange;
window.unsubscribeAllEntities = unsubscribeAllEntities;
window.clearUserLog = clearUserLog;
window.clearProductLog = clearProductLog;

// Auto-refresh connection status and counters
setInterval(() => {
    if (window.NTT) {
        window.updateCounters();
        updateEntitySelector();
    }
}, 3000);

// Check connection periodically
setInterval(() => {
    checkPyBendConnection();
}, 10000);

// Initialize when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    setTimeout(() => {
        if (window.NTT) {
            initializeConnectedSystem();
            window.log('info', '🔗 PyBend Integration Ready!');
            window.log('info', 'Connect to real PyBend backend for full functionality');
        } else {
            window.log('error', '❌ Framework failed to load properly');
        }
    }, 1000);
});