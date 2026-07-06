// SupportAI Production / Development API Configuration
// Set window.API_BASE_URL if backend is hosted on a different URL (e.g. Render)
if (typeof window !== "undefined" && !window.API_BASE_URL) {
    // Leave blank for automatic hostname detection (http://127.0.0.1:8000 in dev)
    // Or set your Render backend URL here:
    // window.API_BASE_URL = "https://your-backend-name.onrender.com";
}
