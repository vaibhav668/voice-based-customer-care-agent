const TOKEN_KEY = "access_token";
const SESSION_KEY = "chat_session";
const LANG_KEY = "app_language";

export function saveToken(token) {
    localStorage.setItem(TOKEN_KEY, token);
}

export function getToken() {
    return localStorage.getItem(TOKEN_KEY);
}

export function removeToken() {
    localStorage.removeItem(TOKEN_KEY);
}

export function isLoggedIn() {
    return !!getToken();
}

export function getSessionId() {
    let id = localStorage.getItem(SESSION_KEY);
    if (!id) {
        id = crypto.randomUUID();
        localStorage.setItem(SESSION_KEY, id);
    }
    return id;
}

/** Generate and save a brand-new session ID (call on login/logout) */
export function newSession() {
    const id = crypto.randomUUID();
    localStorage.setItem(SESSION_KEY, id);
    return id;
}

/** Clear the chat session ID from localStorage */
export function clearSession() {
    localStorage.removeItem(SESSION_KEY);
}

/** Clear ALL auth + session data (full logout) */
export function clearAll() {
    localStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem(SESSION_KEY);
}

export function getSavedLanguage() {
    return localStorage.getItem(LANG_KEY) || "en";
}

export function saveLanguage(lang) {
    if (lang) {
        localStorage.setItem(LANG_KEY, lang);
    }
}