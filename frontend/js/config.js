// SupportAI Production / Development API Configuration
// Set window.API_BASE_URL if your backend is hosted on Render or custom domain.
// When left unset/empty, it automatically detects localhost (http://127.0.0.1:8000) during development.
if (typeof window !== "undefined" && !window.API_BASE_URL) {
    const host = window.location.hostname || "127.0.0.1";
    if (host === "localhost" || host === "127.0.0.1") {
        window.API_BASE_URL = "http://127.0.0.1:8000";
    } else {
        window.API_BASE_URL = "https://voice-based-customer-care-agent-1.onrender.com";
    }
}
