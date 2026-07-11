import {
    getProfile
} from "./api.js";

import {
    clearAll
} from "./storage.js";
import { langManager } from "./language.js";

document.addEventListener("DOMContentLoaded", () => {
    langManager.init("lang-selector-container");
});

const logout = document.getElementById("logout");
if (logout) {
    logout.onclick = () => {
        clearAll(); // Clears both access_token AND chat_session
        location.href = "index.html";
    };
}

(async()=>{

try{

const response=await getProfile();
const profile = response.data || response;

if (profile.role === "ADMIN") {
    location.href = "admin_dashboard.html";
    return;
}

if (profile.preferred_language) {
    await langManager.setLanguage(profile.preferred_language, false);
}

const welcomeHeader = document.querySelector("h1[data-i18n='dashboard_welcome']");
if (welcomeHeader) {
    welcomeHeader.innerHTML = `${langManager.getText("dashboard_welcome")}, ${profile.full_name || ''}`;
}

}catch(err){

console.warn("Profile fetch failed:", err);

}

})();