
export const config = {
    API_URL: 'http://localhost:8000',
    WS_URL: 'ws://localhost:8765',
    DEFAULT_HEADERS: {
        'Content-Type': 'application/json',
        'Accept': 'application/json'
    },
    TIMEOUT: 5000,
    RETRY_LIMIT: 3,
    DEBUG: true,
    E : {
        // CRUD operations
        create: "CREATE",
        read: "READ",
        update: "UPDATE",
        delete: "DELETE",
       // UI Events
        enable: "ENABLE",
        disable: "DISABLE",
        describe: "DESCRIBE",
        // State management
        evolve: "EVOLVE",
        commit: "COMMIT",
        rollback: "ROLLBACK",
        subscribe: "SUBSCRIBE",
        observe: "OBSERVE",
        // Connection events
        connected: "CONNECTED",
        disconnected: "DISCONNECTED",
        // Other events
        get: "GET",
        load: "LOAD",
        schema: "SCHEMA",
        // Custom events
        custom: "CUSTOM",
        // Error handling
        error: "ERROR",
        // Miscellaneous
        ping: "PING",
        pong: "PONG",
        heartbeat: "HEARTBEAT",
        // Authentication
        login: "LOGIN",
        logout: "LOGOUT",
        register: "REGISTER",
        // Notifications
        notify: "NOTIFY",
        alert: "ALERT",
    },
   
}