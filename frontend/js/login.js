import { login, sendOtp } from "./api.js";
import { saveToken, newSession } from "./storage.js";
import { langManager } from "./language.js";

document.addEventListener("DOMContentLoaded", () => {
    langManager.init("lang-selector-container");
});

const form = document.getElementById("login-form");
const message = document.getElementById("message");
const phoneInput = document.getElementById("phone");
const otpInput = document.getElementById("otp");
const sendOtpBtn = document.getElementById("send-otp-btn");

if (sendOtpBtn) {
    sendOtpBtn.addEventListener("click", async () => {
        if (!phoneInput.value.trim()) {
            message.innerText = "Please enter your phone number first.";
            message.style.color = "var(--danger)";
            return;
        }

        sendOtpBtn.disabled = true;
        sendOtpBtn.innerText = "Sending...";
        message.innerText = "";

        try {
            const cleanPhone = phoneInput.value.replace(/\D/g, "");
            const res = await sendOtp(cleanPhone);
            const data = res.data || res;
            
            // Auto fill OTP in UI for mock/test convenience
            if (data.otp) {
                otpInput.value = data.otp;
            }

            message.innerText = `OTP sent! Enter ${data.otp || "123456"} to login.`;
            message.style.color = "var(--teal)";
        } catch (err) {
            message.innerText = err.message || "Failed to send OTP.";
            message.style.color = "var(--danger)";
        } finally {
            sendOtpBtn.disabled = false;
            sendOtpBtn.innerText = "Send OTP";
        }
    });
}

if (form) {
    form.onsubmit = async (e) => {
        e.preventDefault();

        try {
            const cleanPhone = phoneInput.value.replace(/\D/g, "");
            const response = await login(
                cleanPhone,
                otpInput.value
            );

            const authData = response.data || response;
            saveToken(authData.access_token);
            newSession(); // Start a brand-new chat session for this login

            if (authData.preferred_language) {
                await langManager.setLanguage(authData.preferred_language, false);
            }

            location.href = "dashboard.html";

        } catch (err) {
            message.innerText = err.message || langManager.getText("auth_error");
            message.style.color = "var(--danger)";
        }
    };
}