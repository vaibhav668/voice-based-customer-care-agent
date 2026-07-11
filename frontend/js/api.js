import "./config.js";
import {
    getToken,
    getSessionId,
    removeToken
} from "./storage.js";
import { langManager } from "./language.js";

export const getBaseUrl = () => {
    if (window.API_BASE_URL) {
        return window.API_BASE_URL.replace(/\/$/, "");
    }
    const host = window.location.hostname || "127.0.0.1";
    const protocol = window.location.protocol === "https:" ? "https:" : "http:";
    if (host === "localhost" || host === "127.0.0.1") {
        return `http://${host}:8000`;
    }
    return `${protocol}//${host}:8000`;
};

export const BASE_URL = getBaseUrl();

async function safeJson(response) {
    const text = await response.text();
    try {
        return JSON.parse(text);
    } catch (e) {
        // Handle non-JSON HTML error pages from Render/Cloudflare/etc.
        const cleanText = text.replace(/<[^>]*>/g, '').trim().substring(0, 150);
        return { 
            success: false, 
            message: cleanText || `Server returned HTTP ${response.status}` 
        };
    }
}

async function request(url, options = {}) {

    const headers = {
        ...(options.headers || {})
    };

    const token = getToken();

    if (token) {
        headers.Authorization = `Bearer ${token}`;
    }

    const response = await fetch(BASE_URL + url, {
        ...options,
        headers,
    });

    // If unauthorized / token expired, automatically sign out and redirect
    if (response.status === 401) {
        removeToken();
        const path = window.location.pathname;
        if (!path.includes("login.html") && !path.includes("register.html") && path !== "/" && !path.endsWith("/index.html")) {
            window.location.href = path.includes("/pages/") ? "../login.html" : "login.html";
        }
    }

    const data = await safeJson(response);

    if (!response.ok) {
        throw new Error(data.message || data.detail || "Request Failed");
    }

    return data;
}

export function sendOtp(phone) {
    return request("/api/v1/auth/send-otp", {
        method: "POST",
        headers: {
            "Content-Type": "application/json",
        },
        body: JSON.stringify({ phone }),
    });
}

export function login(phone, otp) {
    return request("/api/v1/auth/login", {
        method: "POST",
        headers: {
            "Content-Type": "application/json",
        },
        body: JSON.stringify({
            phone,
            otp,
        }),
    });
}

export function register(user) {
    const payload = {
        ...user,
        preferred_language: user.preferred_language || langManager.getLanguage(),
    };

    return request("/api/v1/auth/register", {
        method: "POST",
        headers: {
            "Content-Type": "application/json",
        },
        body: JSON.stringify(payload),
    });
}

export function getProfile() {

    return request("/api/v1/users/me");

}

export function getBookings() {

    return request("/api/v1/bookings");

}

export function getBooking(bookingCode) {

    return request(`/api/v1/bookings/${bookingCode}`);

}

export async function getTrip(bookingCode){

    const response = await request(

        `/api/v1/trips/${bookingCode}`

    );

    return response.data;

}

export async function sendMessage(message){
    const headers = {
        "Content-Type":"application/json"
    };
    const token = getToken();
    if (token) {
        headers.Authorization = `Bearer ${token}`;
    }

    return await request(
        "/api/v1/chat/",
        {
            method:"POST",
            headers,
            body:JSON.stringify({
                session_id:getSessionId(),
                message,
                language: langManager.getLanguage(),
            })
        }
    );
}


export async function sendVoice(audio){

    const formData = new FormData();

    const filename =
        audio.name ??
        `recording.webm`;

    formData.append(
        "audio",
        audio,
        filename
    );

    formData.append(
        "session_id",
        getSessionId()
    );

    formData.append(
        "language",
        langManager.getLanguage()
    );

    const headers = {};
    const token = getToken();
    if (token) {
        headers.Authorization = `Bearer ${token}`;
    }

    const response = await fetch(
        `${BASE_URL}/voice/chat`,
        {
            method: "POST",
            headers: headers,
            body: formData,
        }
    );

    const data = await safeJson(response);

    if(!response.ok){
        throw new Error(data.message || data.detail || "Voice request failed.");
    }

    return data;
}

export function getConversations() {
    return request("/api/v1/conversations?limit=25&offset=0");
}

export function getComplaints() {
    return request("/api/v1/complaints");
}

export function searchConversations(bookingCode) {
    return request(`/api/v1/conversations/search?booking_code=${bookingCode}&limit=1`);
}

export function getConversationDetail(id) {
    return request(`/api/v1/conversations/${id}`);
}

export function getAnalyticsBookings() {
    return request("/api/v1/conversations/analytics/bookings");
}

export function updateResolutionStatus(id, status) {
    return request(`/api/v1/conversations/${id}/resolution?status=${status}`, {
        method: "PUT"
    });
}

export function submitCallReview(id, outcome, notes) {
    return request(`/api/v1/conversations/${id}/reviews`, {
        method: "POST",
        headers: {
            "Content-Type": "application/json"
        },
        body: JSON.stringify({
            outcome_tag: outcome,
            notes: notes
        })
    });
}

export function getAdminEnrichedConversations(limit = 100) {
    return request(`/api/v1/conversations/admin/enriched?limit=${limit}`);
}