// SupportAI Production / Development API Configuration
// Set window.API_BASE_URL if your backend is hosted on Render or custom domain.
// When left unset/empty, it automatically detects localhost (http://127.0.0.1:8000) during development.
if (typeof window !== "undefined" && !window.API_BASE_URL) {
    const host = window.location.hostname;
    const isLocal = host === "localhost" || host === "127.0.0.1";
    const isFile = window.location.protocol === "file:" || !host;

    if (isLocal || isFile) {
        // Local development: file:// protocol OR localhost — always use local backend
        window.API_BASE_URL = "http://127.0.0.1:8000";
    } else {
        // Production deployment
        window.API_BASE_URL = "https://voice-based-customer-care-agent-1.onrender.com";
    }
}
