import {
    getToken,
    getSessionId
} from "./storage.js";
import { langManager } from "./language.js";

const BASE_URL = "http://127.0.0.1:8000";

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

    const response = await fetch(

        `${BASE_URL}/voice/chat`,

        {

            method:"POST",

            body:formData,

        }

    );

    if(!response.ok){

        throw new Error("Voice request failed.");

    }

    return await response.json();

}