const TOKEN_KEY = "access_token";

export function saveToken(token){

    localStorage.setItem(TOKEN_KEY, token);

}

export function getToken(){

    return localStorage.getItem(TOKEN_KEY);

}

export function removeToken(){

    localStorage.removeItem(TOKEN_KEY);

}

export function isLoggedIn(){

    return !!getToken();

}
const SESSION_KEY="chat_session";

export function getSessionId(){

let id=

localStorage.getItem(

SESSION_KEY

);

if(!id){

id=

crypto.randomUUID();

localStorage.setItem(

SESSION_KEY,

id

);

}

return id;

}

const LANG_KEY = "app_language";

export function getSavedLanguage() {
    return localStorage.getItem(LANG_KEY) || "en";
}

export function saveLanguage(lang) {
    if (lang) {
        localStorage.setItem(LANG_KEY, lang);
    }
}