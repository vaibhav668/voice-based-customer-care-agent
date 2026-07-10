import { register } from "./api.js";
import { langManager } from "./language.js";

document.addEventListener("DOMContentLoaded", () => {
    langManager.init("lang-selector-container");
});

const form = document.getElementById("register-form");
const message = document.getElementById("message");

if (form) {
    form.onsubmit = async (e) => {
        e.preventDefault();

        try {
            const cleanPhone = phone.value.replace(/\D/g, "");
            await register({
                full_name: full_name.value,
                phone: cleanPhone,
                preferred_language: langManager.getLanguage(),
            });

            alert(langManager.getText("register_success"));
            location.href = "login.html";

        } catch (err) {
            message.innerText = err.message || langManager.getText("request_failed");
        }
    };
}