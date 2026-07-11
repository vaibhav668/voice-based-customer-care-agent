import { register, sendOtp } from "./api.js";
import { langManager } from "./language.js";

document.addEventListener("DOMContentLoaded", () => {
    langManager.init("lang-selector-container");
});

const form = document.getElementById("register-form");
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

            message.innerText = `OTP sent! Enter ${data.otp || "123456"} to register.`;
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
            await register({
                full_name: document.getElementById("full_name").value,
                phone: cleanPhone,
                otp: otpInput.value,
                preferred_language: langManager.getLanguage(),
            });

            alert(langManager.getText("register_success"));
            location.href = "index.html";

        } catch (err) {
            message.innerText = err.message || langManager.getText("request_failed");
            message.style.color = "var(--danger)";
        }
    };
}