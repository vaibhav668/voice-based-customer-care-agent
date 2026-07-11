import { langManager } from "./language.js";
import { getToken } from "./storage.js";
import { getBaseUrl } from "./api.js";

const token = getToken();
if (!token) {
    location.href = "../index.html";
}

const API_BASE = `${getBaseUrl()}/api/v1`;

document.addEventListener("DOMContentLoaded", () => {
    langManager.init("lang-selector-container");
    initHistoryPage();
});

let currentChannelFilter = "";
let currentSearchQuery = "";
let activeConversationId = null;

function initHistoryPage() {
    const searchInput = document.getElementById("history-search");
    const tabBtns = document.querySelectorAll(".tab-btn");

    loadConversations();

    // Tab Channel Filters
    tabBtns.forEach(btn => {
        btn.addEventListener("click", () => {
            tabBtns.forEach(b => b.classList.remove("active"));
            btn.classList.add("active");
            currentChannelFilter = btn.dataset.channel || "";
            loadConversations();
        });
    });

    // Debounced Search
    let searchTimer = null;
    if (searchInput) {
        searchInput.addEventListener("input", (e) => {
            clearTimeout(searchTimer);
            searchTimer = setTimeout(() => {
                currentSearchQuery = e.target.value.trim();
                loadConversations();
            }, 350);
        });
    }
}

async function fetchAPI(endpoint) {
    const token = getToken();
    const headers = { "Content-Type": "application/json" };
    if (token) headers["Authorization"] = `Bearer ${token}`;

    const res = await fetch(`${API_BASE}${endpoint}`, { headers });
    if (!res.ok) throw new Error(`API Error: ${res.status}`);
    const json = await res.json();
    return json.data;
}

async function loadConversations() {
    const convList = document.getElementById("conv-list");
    convList.innerHTML = `<div class="empty-state"><p>Loading conversations...</p></div>`;

    try {
        let endpoint = `/conversations?limit=100&offset=0`;
        if (currentSearchQuery) {
            endpoint = `/conversations/search?q=${encodeURIComponent(currentSearchQuery)}&limit=100&offset=0`;
        } else if (currentChannelFilter) {
            endpoint = `/conversations?channel=${currentChannelFilter}&limit=100&offset=0`;
        }

        const data = await fetchAPI(endpoint);
        const conversations = data.conversations || [];

        if (!conversations.length) {
            convList.innerHTML = `<div class="empty-state"><p data-i18n="no_conversations">No conversations found.</p></div>`;
            return;
        }

        convList.innerHTML = conversations.map(c => {
            const dateStr = c.updated_at ? new Date(c.updated_at).toLocaleString() : '';
            const channelClass = c.channel === "VOICE" ? "badge-voice" : "badge-chat";
            const isActive = c.id === activeConversationId ? "active" : "";

            return `
                <div class="conv-card ${isActive}" data-id="${c.id}">
                    <div class="conv-card-header">
                        <span class="channel-badge ${channelClass}">${c.channel}</span>
                        <span class="conv-time">${dateStr}</span>
                    </div>
                    <div class="conv-intent">${c.current_intent || "Support Conversation"}</div>
                    <div class="conv-preview">${c.last_tool ? `Tool: ${c.last_tool}` : `Messages: ${c.message_count || 0}`} | Lang: ${(c.language || 'en').toUpperCase()}</div>
                </div>
            `;
        }).join("");

        // Attach click handlers
        document.querySelectorAll(".conv-card").forEach(card => {
            card.addEventListener("click", () => {
                document.querySelectorAll(".conv-card").forEach(c => c.classList.remove("active"));
                card.classList.add("active");
                const convId = card.dataset.id;
                loadConversationDetail(convId);
            });
        });

    } catch (err) {
        console.error(err);
        convList.innerHTML = `<div class="empty-state" style="color:#ef4444;"><p>Failed to load conversations.</p></div>`;
    }
}

async function loadConversationDetail(convId) {
    activeConversationId = convId;
    const detailHeader = document.getElementById("detail-header");
    const sessionTitle = document.getElementById("detail-session-id");
    const metaText = document.getElementById("detail-meta-text");
    const msgContainer = document.getElementById("messages-container");

    msgContainer.innerHTML = `<div class="empty-state"><p>Loading chat transcript...</p></div>`;

    try {
        const detail = await fetchAPI(`/conversations/${convId}`);
        if (!detail) {
            msgContainer.innerHTML = `<div class="empty-state"><p>Conversation not found.</p></div>`;
            return;
        }

        detailHeader.style.display = "flex";
        sessionTitle.textContent = `Session: ${detail.session_id || convId.slice(0, 8)}`;
        metaText.textContent = `Channel: ${detail.channel} | Language: ${(detail.language || 'en').toUpperCase()} | Intent: ${detail.current_intent || 'General'}`;

        const messages = detail.messages || [];

        if (!messages.length) {
            msgContainer.innerHTML = `<div class="empty-state"><p>No messages recorded in this conversation.</p></div>`;
            return;
        }

        msgContainer.innerHTML = messages.map(m => {
            const isUser = m.sender === "USER";
            const senderClass = isUser ? "msg-user" : "msg-ai";
            const senderLabel = isUser ? langManager.getText("user_sender") : langManager.getText("ai_sender");
            const timeStr = m.created_at ? new Date(m.created_at).toLocaleTimeString() : '';

            let audioWidget = "";
            if (m.audio_path) {
                let cleanPath = m.audio_path.replace(/\\/g, "/");
                if (!cleanPath.startsWith("http")) {
                    const tempIdx = cleanPath.indexOf("temp/");
                    const genIdx = cleanPath.indexOf("generated_audio/");
                    if (tempIdx !== -1) {
                        cleanPath = cleanPath.substring(tempIdx);
                    } else if (genIdx !== -1) {
                        cleanPath = cleanPath.substring(genIdx);
                    } else {
                        cleanPath = `generated_audio/${cleanPath}`;
                    }
                }
                const audioUrl = cleanPath.startsWith("http") ? cleanPath : `${getBaseUrl()}/${cleanPath}`;
                const mimeType = cleanPath.endsWith(".webm") ? "audio/webm" : "audio/mpeg";
                audioWidget = `<div><audio controls style="width:100%; margin-top:8px;"><source src="${audioUrl}" type="${mimeType}">Your browser does not support audio playback.</audio></div>`;
            }

            let metaTags = [];
            if (m.intent) metaTags.push(`<span class="meta-tag">Intent: ${m.intent}</span>`);
            if (m.tool_used) metaTags.push(`<span class="meta-tag">Tool: ${m.tool_used}</span>`);
            if (m.booking_code) metaTags.push(`<span class="meta-tag" style="border-color:#35d8b6; color:#35d8b6;">Code: ${m.booking_code}</span>`);
            if (m.response_time_ms) metaTags.push(`<span class="meta-tag">${m.response_time_ms} ms</span>`);

            return `
                <div class="msg-bubble-wrap ${senderClass}">
                    <div class="msg-sender-label">${senderLabel} • ${timeStr}</div>
                    <div class="msg-bubble">
                        ${escapeHTML(m.message)}
                        ${audioWidget}
                    </div>
                    <div class="msg-meta">
                        ${metaTags.join("")}
                    </div>
                </div>
            `;
        }).join("");

        msgContainer.scrollTop = msgContainer.scrollHeight;

    } catch (err) {
        console.error(err);
        msgContainer.innerHTML = `<div class="empty-state" style="color:#ef4444;"><p>Error loading conversation transcript.</p></div>`;
    }
}

function escapeHTML(str) {
    if (!str) return '';
    return str.replace(/[&<>'"]/g, 
        tag => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', "'": '&#39;', '"': '&quot;' }[tag] || tag)
    );
}
