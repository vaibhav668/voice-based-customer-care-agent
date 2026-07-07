import { login } from "./api.js";
import { saveToken, newSession } from "./storage.js";
import { langManager } from "./language.js";

document.addEventListener("DOMContentLoaded", () => {
    langManager.init("lang-selector-container");
});

const form = document.getElementById("login-form");
const message = document.getElementById("message");
const passwordInput = document.getElementById("password");
const togglePassword = document.getElementById("toggle-password");

if (togglePassword && passwordInput) {
    togglePassword.addEventListener("click", () => {
        const type = passwordInput.getAttribute("type") === "password" ? "text" : "password";
        passwordInput.setAttribute("type", type);
        togglePassword.classList.toggle("fa-eye");
        togglePassword.classList.toggle("fa-eye-slash");
    });
}

if (form) {
    form.onsubmit = async (e) => {

        e.preventDefault();

        try {

            const response = await login(

                email.value,

                password.value

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

        }

    };
}