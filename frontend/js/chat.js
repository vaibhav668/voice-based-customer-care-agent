import { sendMessage } from "./api.js";
import { langManager } from "./language.js";
import { getToken } from "./storage.js";

const token = getToken();
if (!token) {
    location.href = "../index.html";
}

function getMessagesContainer() {
    return document.getElementById("messages");
}

function getInputElem() {
    return document.getElementById("message");
}

function getSendBtn() {
    return document.getElementById("send");
}

function addMessage(sender, text, type = "user", isTyping = false) {
    const container = getMessagesContainer();
    if (!container) return null;

    const id = isTyping ? "typing-indicator" : `msg-${Date.now()}`;
    const senderName = type === "user" ? "You" : "Support AI";
    const wrapperClass = type === "user" ? "user" : (type === "error" ? "ai error" : "ai");

    let contentHtml = text;
    if (isTyping) {
        contentHtml = `
            <div class="typing-dots">
                <span></span><span></span><span></span>
            </div>
        `;
    }

    const html = `
        <div class="msg-wrapper ${wrapperClass}" id="${id}">
            <div class="msg-sender">${senderName}</div>
            <div class="msg-bubble">${contentHtml}</div>
        </div>
    `;

    container.insertAdjacentHTML("beforeend", html);
    container.scrollTop = container.scrollHeight;
    return id;
}

function removeTypingIndicator() {
    const typingEl = document.getElementById("typing-indicator");
    if (typingEl) typingEl.remove();
}

async function handleSend() {
    const input = getInputElem();
    if (!input) return;

    const text = input.value.trim();
    if (!text) return;

    addMessage("You", text, "user");
    input.value = "";

    addMessage("Support AI", "", "ai", true);

    try {
        const response = await sendMessage(text);
        removeTypingIndicator();
        
        const replyText = response.response || response.message || "I'm sorry, I couldn't process your request.";
        addMessage("Support AI", replyText, "ai");
    } catch (err) {
        removeTypingIndicator();
        addMessage("Support AI", err.message || "Network Error", "error");
    }
}

function initChat() {
    if (!token) return;
    langManager.init("lang-selector-container");

    const sendBtn = getSendBtn();
    const inputElem = getInputElem();

    if (sendBtn) {
        sendBtn.onclick = handleSend;
    }

    if (inputElem) {
        inputElem.addEventListener("keydown", (e) => {
            if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                handleSend();
            }
        });
    }
}

if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initChat);
} else {
    initChat();
}