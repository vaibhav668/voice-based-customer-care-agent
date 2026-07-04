import { login } from "./api.js";
import { saveToken } from "./storage.js";
import { langManager } from "./language.js";

document.addEventListener("DOMContentLoaded", () => {
    langManager.init("lang-selector-container");
});

const form = document.getElementById("login-form");
const message = document.getElementById("message");

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

            if (authData.preferred_language) {
                await langManager.setLanguage(authData.preferred_language, false);
            }

            location.href = "dashboard.html";

        } catch (err) {

            message.innerText = err.message || langManager.getText("auth_error");

        }

    };
}