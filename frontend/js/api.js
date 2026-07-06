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

    const data = await response.json();

    if (!response.ok) {
        throw new Error(data.message || "Request Failed");
    }

    return data;
}

export function login(email, password) {

    return request("/api/v1/auth/login", {
        method: "POST",
        headers: {
            "Content-Type": "application/json",
        },
        body: JSON.stringify({
            email,
            password,
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

    return await request(

        "/api/v1/chat/",

        {

            method:"POST",

            headers:{

                "Content-Type":"application/json"

            },

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

    const data = await response.json();

    if(!response.ok){
        throw new Error(data.message || data.detail || "Voice request failed.");
    }

    return data;
}