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