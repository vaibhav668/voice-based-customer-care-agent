import { getProfile } from "./api.js";
import { langManager } from "./language.js";
import { getToken } from "./storage.js";

document.addEventListener("DOMContentLoaded", () => {
    langManager.init("lang-selector-container");
});

const profileContainer = document.getElementById("profile");

async function load() {
    const token = getToken();
    if (!token) {
        profileContainer.innerHTML = `
            <div style="text-align: center; padding: 20px 0;">
                <h3 style="font-family:'Space Grotesk', sans-serif; font-size:18px; margin-bottom:12px;">You are not logged in</h3>
                <p style="color:var(--text-dim); margin-bottom:20px;">Please sign in to view your profile and account details.</p>
                <button onclick="location.href='../login.html'" style="background:var(--teal); color:#0b1220; border:none; font-weight:700; padding:10px 24px; border-radius:999px; cursor:pointer;">
                    Sign In Now
                </button>
            </div>
        `;
        return;
    }

    try {
        const response = await getProfile();
        const user = response.data || response;

        if (user.preferred_language) {
            await langManager.setLanguage(user.preferred_language, false);
        }

        profileContainer.innerHTML = `
            <h2 style="font-family:'Space Grotesk', sans-serif; font-size:22px; margin-bottom:16px; color:var(--teal);">${user.full_name || 'Customer'}</h2>
            <div style="display:flex; flex-direction:column; gap:10px;">
                <p><strong>Email:</strong> ${user.email || 'N/A'}</p>
                <p><strong>Phone:</strong> ${user.phone || 'N/A'}</p>
                <p><strong>Role:</strong> <span style="background:rgba(53,216,182,0.15); color:var(--teal); padding:2px 8px; border-radius:4px; font-weight:600; font-size:12px;">${user.role || 'CUSTOMER'}</span></p>
                <p><strong>${langManager.getText("pref_lang_label")}:</strong> ${(user.preferred_language || 'en').toUpperCase()}</p>
            </div>
        `;
    } catch(err) {
        profileContainer.innerHTML = `
            <div style="text-align: center; padding: 20px 0;">
                <p style="color:#ef4444; margin-bottom:16px;">Session expired or unauthenticated.</p>
                <button onclick="location.href='../login.html'" style="background:var(--teal); color:#0b1220; border:none; font-weight:700; padding:10px 24px; border-radius:999px; cursor:pointer;">
                    Sign In
                </button>
            </div>
        `;
    }
}

load();