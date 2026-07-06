import { register } from "./api.js";
import { langManager } from "./language.js";

document.addEventListener("DOMContentLoaded", () => {
    langManager.init("lang-selector-container");
});

const form = document.getElementById("register-form");
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

            await register({

                full_name: full_name.value,

                email: email.value,

                phone: phone.value,

                password: password.value,

                preferred_language: langManager.getLanguage(),

            });

            alert(langManager.getText("register_success"));

            location.href = "login.html";

        }

        catch(err){

            message.innerText = err.message || langManager.getText("request_failed");

        }

    };
}