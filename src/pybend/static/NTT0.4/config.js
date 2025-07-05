
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
        create: "CREATE",
        read: "READ",
        update: "UPDATE",
        delete: "DELETE",
        enable: "ENABLE",
        disable: "DISABLE",
        describe: "DESCRIBE",
        error: "ERROR",
    }
}