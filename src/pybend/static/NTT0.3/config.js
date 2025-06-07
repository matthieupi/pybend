
export const config = {
    API_URL: 'http://localhost:8000',
    WS_URL: 'ws://localhost:8765',
    DEFAULT_HEADERS: {
        'Content-Type': 'application/json',
        'Accept': 'application/json'
    },
    TIMEOUT: 5000, // Default timeout for HTTP requests in milliseconds
    RETRY_LIMIT: 3, // Number of retries for failed requests
    DEBUG: true // Enable debug mode for logging
}