import {
    getProfile,
    getBaseUrl,
    getConversations,
    getComplaints,
    searchConversations,
    getConversationDetail,
    getAnalyticsBookings,
    updateResolutionStatus,
    submitCallReview,
    getAdminEnrichedConversations
} from "./api.js";
import { clearAll, getToken } from "./storage.js";


// Global state
let adminProfile = null;
let currentCluster = "A1";
let particles = [];
let wavePhase = 0;
let waveAnimationFrame = null;
let flowAnimationFrame = null;

document.addEventListener("DOMContentLoaded", async () => {
    // 1. Authenticate Admin
    const token = getToken();
    if (!token) {
        location.href = "index.html";
        return;
    }

    try {
        const response = await getProfile();
        adminProfile = response.data || response;
        
        // Safety check: redirect non-admins back to user dashboard
        if (adminProfile.role !== "ADMIN") {
            location.href = "dashboard.html";
            return;
        }

        // Set name on header
        const nameEl = document.getElementById("admin-name");
        if (nameEl) {
            nameEl.textContent = adminProfile.full_name || "Admin User";
        }
    } catch (err) {
        console.error("Auth check failed:", err);
        clearAll();
        location.href = "index.html";
        return;
    }

    // 2. Initialize UI Components
    initTabNavigation();
    initCanvasAnimations();
    initLiveAlerts();
    initSettingsTab();
    
    // 3. Load Real-time Data
    await loadBookings();
    await loadConversations();
    initDriversTab();

    // 4. Set up Refresh handler
    const btnRefresh = document.getElementById("btn-refresh-bookings");
    if (btnRefresh) {
        btnRefresh.addEventListener("click", async () => {
            btnRefresh.innerHTML = `<i class="fa-solid fa-spinner fa-spin"></i> Syncing...`;
            await loadBookings();
            await loadConversations();
            btnRefresh.innerHTML = `<i class="fa-solid fa-rotate"></i> Refresh`;
        });
    }

    // 5. Handle Logout
    const logoutBtn = document.getElementById("admin-logout");
    if (logoutBtn) {
        logoutBtn.addEventListener("click", () => {
            clearAll();
            location.href = "index.html";
        });
    }

    // 6. Real-time background sync interval (every 4 seconds)
    setInterval(async () => {
        if (getToken()) {
            await loadBookings(true);
            await loadConversations(true);
        }
    }, 4000);

    // 7. Establish real-time WebSocket connection to receive call update events
    const initWebSocket = () => {
        let wsUrl;
        const baseUrl = getBaseUrl();
        if (baseUrl.startsWith("https://")) {
            wsUrl = baseUrl.replace("https://", "wss://") + "/ws/admin";
        } else if (baseUrl.startsWith("http://")) {
            wsUrl = baseUrl.replace("http://", "ws://") + "/ws/admin";
        } else {
            const loc = window.location;
            const proto = loc.protocol === "https:" ? "wss:" : "ws:";
            wsUrl = `${proto}//${loc.host}/ws/admin`;
        }

        try {
            console.log("Connecting to admin WebSocket:", wsUrl);
            const socket = new WebSocket(wsUrl);
            
            socket.onopen = () => {
                console.log("Admin WebSocket connected successfully.");
            };
            
            socket.onmessage = async (event) => {
                console.log("WebSocket event received:", event.data);
                // Trigger immediate updates on live events
                if (getToken()) {
                    await loadConversations(true);
                    await loadBookings(true);
                }
            };
            
            socket.onclose = (e) => {
                console.warn("WebSocket closed. Attempting reconnect in 3 seconds...", e);
                setTimeout(initWebSocket, 3000);
            };
            
            socket.onerror = (err) => {
                console.error("WebSocket error:", err);
                socket.close();
            };
        } catch (e) {
            console.error("Failed to initialize WebSocket:", e);
        }
    };
    initWebSocket();
});

/* ----------------- TAB NAVIGATION ----------------- */
function initTabNavigation() {
    const navItems = document.querySelectorAll(".nav-item");
    const tabPanes = document.querySelectorAll(".tab-pane");

    navItems.forEach(item => {
        item.addEventListener("click", () => {
            const targetTab = item.dataset.tab;
            if (!targetTab) return;
            switchToTab(targetTab);
        });
    });
}

function switchToTab(tabName) {
    const navItems = document.querySelectorAll(".nav-item");
    const tabPanes = document.querySelectorAll(".tab-pane");

    const targetItem = Array.from(navItems).find(item => item.dataset.tab === tabName);
    if (!targetItem) return;

    // Update active menu item
    navItems.forEach(nav => nav.classList.remove("active"));
    targetItem.classList.add("active");

    // Update active tab panel
    tabPanes.forEach(pane => {
        pane.classList.remove("active");
        if (pane.id === `tab-${tabName}`) {
            pane.classList.add("active");
        }
    });

    // Resize canvasses if showing dashboard
    if (tabName === "dashboard") {
        resizeCanvases();
    }
}

/* ----------------- REAL-TIME DATA LOGS ----------------- */
async function loadBookings(silent = false) {
    const tbody = document.getElementById("bookings-table-body");
    if (!tbody) return;

    if (!silent && !tbody.innerHTML.includes("tr")) {
        tbody.innerHTML = `<tr><td colspan="8" style="text-align: center;"><i class="fa-solid fa-spinner fa-spin"></i> Querying analytics database...</td></tr>`;
    }

    try {
        const response = await getAnalyticsBookings();
        const bookingsList = response.data || [];

        if (bookingsList.length === 0) {
            tbody.innerHTML = `<tr><td colspan="8" style="text-align: center; color: var(--text-dim);">No bookings found in analytics logs.</td></tr>`;
            return;
        }

        tbody.innerHTML = bookingsList.map(b => {
            const bStatusClass = b.booking_status === "CONFIRMED" ? "confirmed" : (b.booking_status === "CANCELLED" ? "cancelled" : "pending");
            const pStatusClass = b.payment_status === "PAID" ? "paid" : "pending";
            return `
                <tr>
                    <td style="font-family: var(--font-mono); font-weight: 700; color: white;">${b.booking_code}</td>
                    <td><i class="fa-solid fa-location-dot" style="color: var(--teal)"></i> ${b.source}</td>
                    <td><i class="fa-solid fa-location-arrow" style="color: var(--blue)"></i> ${b.destination}</td>
                    <td style="font-family: var(--font-mono);">${b.seat_number}</td>
                    <td>${b.departure_time}</td>
                    <td>${b.arrival_time}</td>
                    <td><span class="badge-status ${pStatusClass}">${b.payment_status}</span></td>
                    <td><span class="badge-status ${bStatusClass}">${b.booking_status}</span></td>
                </tr>
            `;
        }).join("");
    } catch (err) {
        console.error("Failed to load bookings list:", err);
        if (!silent) {
            tbody.innerHTML = `<tr><td colspan="8" style="text-align: center; color: var(--red);">Error loading bookings. Check backend logs.</td></tr>`;
        }
    }
}

// Master enriched conversations store
let allEnrichedConvs = [];

async function loadConversations(silent = false) {
    const chatListContainer = document.getElementById("chat-conversations-list");
    const callListContainer = document.getElementById("call-conversations-list");
    if (!chatListContainer && !callListContainer) return;

    if (!silent) {
        if (chatListContainer) chatListContainer.innerHTML = `<div style="text-align:center; padding: 20px;"><i class="fa-solid fa-spinner fa-spin"></i> Fetching active chats...</div>`;
        if (callListContainer) callListContainer.innerHTML = `<div style="text-align:center; padding: 20px;"><i class="fa-solid fa-spinner fa-spin"></i> Fetching active calls...</div>`;
    }

    try {
        const response = await getAdminEnrichedConversations(100);
        const conversations = response.data?.conversations || [];
        allEnrichedConvs = conversations;

        // Stats
        const totalCalls = conversations.length;
        const activeCalls = conversations.filter(c => c.status === "ACTIVE").length;
        const resolvedCalls = conversations.filter(c => c.resolution_status === "resolved").length;
        const escalatedCalls = conversations.filter(c => c.resolution_status === "escalated").length;
        const resRate = totalCalls > 0 ? ((resolvedCalls / totalCalls) * 100).toFixed(1) : "0.0";
        const escRate = totalCalls > 0 ? ((escalatedCalls / totalCalls) * 100).toFixed(1) : "0.0";

        const el = id => document.getElementById(id);
        if (el("stat-todays-calls")) el("stat-todays-calls").textContent = totalCalls;
        if (el("stat-active-calls")) el("stat-active-calls").textContent = activeCalls;
        if (el("stat-resolution-rate")) {
            el("stat-resolution-rate").textContent = `${resRate}%`;
            const pf = document.querySelector(".stat-card .progress-fill");
            if (pf) pf.style.width = `${resRate}%`;
        }
        if (el("stat-transfer-rate")) el("stat-transfer-rate").textContent = `${escRate}%`;

        // Split lists
        const chatConversations = conversations.filter(c => c.channel === "CHAT");
        const callConversations = conversations.filter(c => c.channel === "VOICE");

        // Active counts for the subtabs:
        const activeChatsCount = chatConversations.filter(c => c.status === "ACTIVE").length;
        const activeCallsCount = callConversations.filter(c => c.status === "ACTIVE").length;
        if (el("live-chats-count")) el("live-chats-count").textContent = activeChatsCount;
        if (el("live-calls-count")) el("live-calls-count").textContent = activeCallsCount;

        const renderList = (convList, container) => {
            if (!container) return;
            if (convList.length === 0) {
                container.innerHTML = `<div style="text-align:center; padding: 20px; color:var(--text-dim)">No sessions found.</div>`;
                return;
            }

            const activeItem = container.querySelector(".list-item.active");
            const activeId = activeItem ? activeItem.dataset.convId : null;

            container.innerHTML = convList.map((c, idx) => {
                const channelIcon = c.channel === "VOICE" ? "fa-microphone-lines" : "fa-comments";
                const channelColor = c.channel === "VOICE" ? "var(--purple)" : "var(--cyan)";
                const dateStr = c.updated_at ? new Date(c.updated_at).toLocaleTimeString() : "";
                const isSelected = activeId ? (c.id === activeId) : (idx === 0);
                const phone = c.user_phone || "Unknown";
                const name = c.user_name || "Guest";
                const resClass = c.resolution_status === "resolved" ? "badge-resolved" : (c.resolution_status === "escalated" ? "badge-escalated" : "badge-frustration");

                return `
                    <div class="list-item ${isSelected ? 'active' : ''}" data-conv-id="${c.id}">
                        <div class="item-meta">
                            <span class="channel"><i class="fa-solid ${channelIcon}" style="color:${channelColor}"></i> ${c.channel}</span>
                            <span>${dateStr}</span>
                        </div>
                        <div class="item-title">
                            <i class="fa-solid fa-phone" style="color:var(--teal); font-size:11px;"></i>
                            <strong style="font-family:var(--font-mono); color:white; font-size:13.5px;">${phone}</strong>
                            <span style="color:var(--text-dim); font-size:11px; margin-left:6px;">${name}</span>
                        </div>
                        <div class="item-subtitle">
                            ${c.booking_code ? `<i class="fa-solid fa-ticket" style="color:var(--teal)"></i> ${c.booking_code} | ` : ""}
                            Msgs: ${c.message_count} | <span class="badge ${resClass}" style="font-size:9px; padding: 2px 6px;">${c.resolution_status.toUpperCase()}</span>
                        </div>
                    </div>
                `;
            }).join("");

            const items = container.querySelectorAll(".list-item");
            items.forEach(item => {
                item.addEventListener("click", () => {
                    items.forEach(i => i.classList.remove("active"));
                    item.classList.add("active");
                    loadEnrichedConversationDetail(item.dataset.convId);
                });
            });
        };

        renderList(chatConversations, chatListContainer);
        renderList(callConversations, callListContainer);

        // Auto-load first conversation detail for both if not silent
        if (!silent) {
            if (chatListContainer) {
                const currentlyActiveChat = chatListContainer.querySelector(".list-item.active");
                if (currentlyActiveChat) {
                    loadEnrichedConversationDetail(currentlyActiveChat.dataset.convId);
                }
            }
            if (callListContainer) {
                const currentlyActiveCall = callListContainer.querySelector(".list-item.active");
                if (currentlyActiveCall) {
                    loadEnrichedConversationDetail(currentlyActiveCall.dataset.convId);
                }
            }
        }

        // Populate Support Interceptions panel on dashboard
        renderInterceptionsFromEnriched(conversations);

        // Populate Tickets tab
        renderTicketsFromEnriched(conversations);

    } catch (err) {
        console.error("Failed to load enriched conversations:", err);
        if (!silent) {
            if (chatListContainer) chatListContainer.innerHTML = `<div style="text-align:center; padding: 20px; color:var(--red)">Failed to load. Check backend connection.</div>`;
            if (callListContainer) callListContainer.innerHTML = `<div style="text-align:center; padding: 20px; color:var(--red)">Failed to load. Check backend connection.</div>`;
        }
    }
}

async function selectAndLoadConversation(convId) {
    const conv = allEnrichedConvs.find(c => c.id === convId);
    const targetTab = (conv && conv.channel === "CHAT") ? "chat-support" : "call-support";

    // 1. Switch active view to correct tab
    switchToTab(targetTab);

    // 2. Select and highlight list item
    const listId = targetTab === "chat-support" ? "chat-conversations-list" : "call-conversations-list";
    const items = document.querySelectorAll(`#${listId} .list-item`);
    items.forEach(item => {
        item.classList.remove("active");
        if (item.dataset.convId === convId) {
            item.classList.add("active");
            item.scrollIntoView({ behavior: "smooth", block: "nearest" });
        }
    });

    // 3. Load detail messages
    await loadEnrichedConversationDetail(convId);
}

async function selectAndLoadConversationByBooking(bookingCode) {
    if (!bookingCode) {
        switchToTab("chat-support");
        return;
    }

    try {
        // Search for conversation belonging to this booking code using backend search
        const response = await searchConversations(bookingCode);
        const results = response.data.conversations || [];

        if (results.length > 0) {
            const matchedConv = results[0];
            await selectAndLoadConversation(matchedConv.id);
        } else {
            switchToTab("chat-support");
            console.log(`No active conversation logs found for booking: ${bookingCode}`);
        }
    } catch (err) {
        console.error("Error searching conversation by booking code:", err);
        switchToTab("chat-support");
    }
}

// Render real ticket complaints into support interceptions
function renderInterceptions(complaints) {
    const feed = document.getElementById("dashboard-interceptions");
    if (!feed) return;

    if (!complaints || complaints.length === 0) {
        feed.innerHTML = `<div style="text-align:center; padding: 20px; color:var(--text-dim)">No active operations/tickets detected in database.</div>`;
        return;
    }

    feed.innerHTML = complaints.slice(0, 5).map(c => {
        const dateStr = c.created_at ? formatRelativeTime(c.created_at) : "recently";
        
        let badgeText = c.status;
        let badgeClass = "badge-frustration"; // open -> red
        if (c.status === "RESOLVED") {
            badgeClass = "badge-resolved"; // teal
        } else if (c.status === "IN_PROGRESS") {
            badgeClass = "badge-escalated"; // blue/yellow
        }

        const customerName = c.customer ? c.customer.name : "Guest Customer";
        const customerEmail = c.customer ? c.customer.email : "N/A";
        const tripRoute = c.trip ? `${c.trip.source} → ${c.trip.destination}` : "Route: N/A";
        
        const desc = `${c.description}<br><span style="color:var(--cyan); font-size:11px; display:inline-block; margin-top:6px;"><i class="fa-solid fa-user"></i> ${customerName} (${customerEmail}) | <i class="fa-solid fa-bus"></i> ${tripRoute}</span>`;

        return `
            <div class="interception-item clickable-card" data-booking-code="${c.booking_code || ''}" style="cursor: pointer;">
                <div class="item-header">
                    <span class="ticket-code"><i class="fa-solid fa-receipt"></i> Ticket #${c.complaint_code}</span>
                    <span class="time-stamp">${dateStr}</span>
                </div>
                <p class="item-body">${desc}</p>
                <div class="item-footer">
                    <span class="badge ${badgeClass}">${badgeText}</span>
                    <button class="btn-transcript-view" data-booking-code="${c.booking_code || ''}">View Convo</button>
                </div>
            </div>
        `;
    }).join("");

    // Attach click events
    feed.querySelectorAll(".interception-item").forEach(item => {
        item.addEventListener("click", () => {
            const bookingCode = item.dataset.bookingCode;
            selectAndLoadConversationByBooking(bookingCode);
        });
    });

    feed.querySelectorAll(".btn-transcript-view").forEach(btn => {
        btn.addEventListener("click", (e) => {
            e.stopPropagation();
            const bookingCode = btn.dataset.bookingCode;
            selectAndLoadConversationByBooking(bookingCode);
        });
    });
}

function formatRelativeTime(isoString) {
    try {
        const date = new Date(isoString);
        const now = new Date();
        const diffMs = now - date;
        const diffMins = Math.floor(diffMs / 60000);
        
        if (diffMins < 1) return "Just now";
        if (diffMins === 1) return "1m ago";
        if (diffMins < 60) return `${diffMins}m ago`;
        
        const diffHours = Math.floor(diffMins / 60);
        if (diffHours === 1) return "1h ago";
        if (diffHours < 24) return `${diffHours}h ago`;
        
        return date.toLocaleDateString();
    } catch (e) {
        return "recently";
    }
}

/* ---- ENRICHED: Support Interceptions (right panel on Dashboard) ---- */
function renderInterceptionsFromEnriched(conversations) {
    const feed = document.getElementById("dashboard-interceptions");
    if (!feed) return;

    if (!conversations || conversations.length === 0) {
        feed.innerHTML = `<div style="text-align:center; padding: 20px; color:var(--text-dim)">No active conversations in database.</div>`;
        return;
    }

    // Show top 6, prioritizing unresolved/escalated
    const prioritized = [...conversations].sort((a, b) => {
        const score = s => s === "escalated" ? 2 : s === "unresolved" ? 1 : 0;
        return score(b.resolution_status) - score(a.resolution_status);
    }).slice(0, 6);

    feed.innerHTML = prioritized.map(c => {
        const dateStr = c.updated_at ? formatRelativeTime(c.updated_at) : "recently";
        const resStatus = c.resolution_status || "unresolved";
        const badgeClass = resStatus === "resolved" ? "badge-resolved" : (resStatus === "escalated" ? "badge-escalated" : "badge-frustration");
        const phone = c.user_phone || "Unknown";
        const name = c.user_name || "Guest";
        const booking = c.booking_details;
        const route = booking ? `${booking.source || "?"} → ${booking.destination || "?"}` : (c.booking_code || "No booking");
        const problem = escapeHTML((c.possible_problem || "").substring(0, 120));
        const intents = (c.intents_detected || []).join(", ") || "—";

        return `
            <div class="interception-item clickable-card" data-conv-id="${c.id}" style="cursor: pointer;">
                <div class="item-header">
                    <span class="ticket-code">
                        <i class="fa-solid fa-phone" style="color:var(--teal)"></i>
                        <strong style="font-family:var(--font-mono); color:white;">${phone}</strong>
                        <span style="color:var(--text-dim); font-size:11px; margin-left:4px;">${name}</span>
                    </span>
                    <span class="time-stamp">${dateStr}</span>
                </div>
                <p class="item-body" style="margin: 6px 0; color: var(--text-dim); font-size: 12px; line-height:1.5;">
                    ${problem || "No user message recorded."}
                </p>
                <div style="font-size: 10.5px; color: var(--cyan); margin-bottom: 6px;">
                    <i class="fa-solid fa-route"></i> ${route} &nbsp;|&nbsp;
                    <i class="fa-solid fa-brain"></i> ${intents}
                </div>
                <div class="item-footer">
                    <span class="badge ${badgeClass}">${resStatus.toUpperCase()}</span>
                    <button class="btn-transcript-view" data-conv-id="${c.id}">View Convo</button>
                </div>
            </div>
        `;
    }).join("");

    feed.querySelectorAll(".interception-item, .btn-transcript-view").forEach(el => {
        el.addEventListener("click", (e) => {
            e.stopPropagation();
            const convId = el.dataset.convId;
            if (convId) {
                const conv = allEnrichedConvs.find(c => c.id === convId);
                const targetTab = (conv && conv.channel === "CHAT") ? "chat-support" : "call-support";
                switchToTab(targetTab);
                loadEnrichedConversationDetail(convId);
                
                // highlight in list
                const listId = targetTab === "chat-support" ? "chat-conversations-list" : "call-conversations-list";
                const items = document.querySelectorAll(`#${listId} .list-item`);
                items.forEach(item => {
                    item.classList.toggle("active", item.dataset.convId === convId);
                });
            }
        });
    });
}

/* ---- ENRICHED: Tickets tab populated from conversations ---- */
function renderTicketsFromEnriched(conversations) {
    const listContainer = document.getElementById("tickets-list");
    if (!listContainer) return;

    if (!conversations || conversations.length === 0) {
        listContainer.innerHTML = `<div style="text-align:center; padding: 20px; color:var(--text-dim)">No ticket/conversation records found.</div>`;
        return;
    }

    listContainer.innerHTML = conversations.map((c, idx) => {
        const dateStr = c.updated_at ? formatRelativeTime(c.updated_at) : "recently";
        const phone = c.user_phone || "Unknown";
        const name = c.user_name || "Guest";
        const resStatus = c.resolution_status || "unresolved";
        const resClass = resStatus === "resolved" ? "badge-resolved" : (resStatus === "escalated" ? "badge-escalated" : "badge-frustration");
        const booking = c.booking_code || "N/A";

        return `
            <div class="list-item ${idx === 0 ? 'active' : ''}" data-conv-id="${c.id}">
                <div class="item-meta">
                    <span style="font-family:var(--font-mono); color:white; font-size:12.5px;"><i class="fa-solid fa-phone" style="color:var(--teal)"></i> ${phone}</span>
                    <span>${dateStr}</span>
                </div>
                <div class="item-title">${name} &mdash; ${c.channel}</div>
                <div class="item-subtitle">
                    Booking: ${booking} | Msgs: ${c.message_count}
                    <span class="badge ${resClass}" style="font-size:9px; padding:2px 6px; margin-left:4px;">${resStatus.toUpperCase()}</span>
                </div>
            </div>
        `;
    }).join("");

    const items = listContainer.querySelectorAll(".list-item");
    items.forEach(item => {
        item.addEventListener("click", () => {
            items.forEach(i => i.classList.remove("active"));
            item.classList.add("active");
            loadEnrichedTicketDetail(item.dataset.convId);
        });
    });

    if (conversations.length > 0) {
        loadEnrichedTicketDetail(conversations[0].id);
    }
}

/* ---- ENRICHED: Ticket detail panel ---- */
async function loadEnrichedTicketDetail(convId) {
    const detailCol = document.getElementById("ticket-detail");
    if (!detailCol) return;

    detailCol.innerHTML = `<div class="empty-state-panel"><i class="fa-solid fa-spinner fa-spin fa-2x"></i></div>`;

    const conv = allEnrichedConvs.find(c => c.id === convId);
    if (!conv) {
        detailCol.innerHTML = `<div class="empty-state-panel"><h3>Ticket not found</h3></div>`;
        return;
    }

    const phone = conv.user_phone || "Unknown";
    const name = conv.user_name || "Guest";
    const bk = conv.booking_details;
    const resStatus = conv.resolution_status || "unresolved";
    const resClass = resStatus === "resolved" ? "badge-resolved" : (resStatus === "escalated" ? "badge-escalated" : "badge-frustration");

    // Fetch full conversation messages
    let messagesHtml = `<div style="text-align:center; color:var(--text-dim); padding:20px;">No messages recorded.</div>`;
    try {
        const detailRes = await getConversationDetail(convId);
        const detail = detailRes.data || detailRes;
        const msgs = detail.messages || [];
        if (msgs.length > 0) {
            messagesHtml = msgs.map(m => {
                const isUser = m.sender === "USER";
                const rowClass = isUser ? "user" : "ai";
                const label = isUser ? `📱 ${phone}` : "🤖 AI Agent";
                const msgTime = m.created_at ? new Date(m.created_at).toLocaleTimeString() : "";
                let tags = [];
                if (m.intent) tags.push(`<span class="meta-pill">Intent: ${m.intent}</span>`);
                if (m.tool_used) tags.push(`<span class="meta-pill">Tool: ${m.tool_used}</span>`);
                if (m.booking_code) tags.push(`<span class="meta-pill" style="color:var(--teal)">Booking: ${m.booking_code}</span>`);
                return `
                    <div class="bubble-row ${rowClass}">
                        <span class="bubble-sender">${label} • ${msgTime}</span>
                        <div class="bubble-text">${escapeHTML(m.message)}</div>
                        <div class="bubble-meta-tags">${tags.join("")}</div>
                    </div>`;
            }).join("");
        }
    } catch(e) {
        messagesHtml = `<div style="text-align:center; color:var(--red);">Failed to load transcript.</div>`;
    }

    detailCol.innerHTML = `
        <div class="detail-header">
            <div class="detail-header-info">
                <h3><i class="fa-solid fa-phone" style="color:var(--teal)"></i> ${phone} &mdash; ${name}</h3>
                <p>Channel: ${conv.channel} | Lang: ${(conv.language || 'en').toUpperCase()} | Msgs: ${conv.message_count}</p>
            </div>
            <div class="detail-actions">
                <span class="badge ${resClass}">${resStatus.toUpperCase()}</span>
            </div>
        </div>

        ${bk ? `
        <div style="padding:12px 16px; background:rgba(0,200,150,0.06); border-bottom:1px solid var(--line); display:flex; gap:24px; font-size:12px; flex-wrap:wrap;">
            <span><i class="fa-solid fa-ticket" style="color:var(--teal)"></i> <strong>${bk.booking_code}</strong></span>
            <span><i class="fa-solid fa-route" style="color:var(--blue)"></i> ${bk.source || "?"} → ${bk.destination || "?"}</span>
            <span><i class="fa-solid fa-chair" style="color:var(--purple)"></i> Seat ${bk.seat_number || "?"}</span>
            <span class="badge-status ${bk.booking_status === 'CONFIRMED' ? 'confirmed' : 'cancelled'}">${bk.booking_status}</span>
            <span class="badge-status ${bk.payment_status === 'PAID' ? 'paid' : 'pending'}">${bk.payment_status}</span>
        </div>` : ""}

        ${conv.possible_problem ? `
        <div style="padding: 10px 16px; background: rgba(255,80,80,0.06); border-bottom: 1px solid var(--line); font-size: 12px; color: var(--text-dim);">
            <i class="fa-solid fa-triangle-exclamation" style="color:var(--red)"></i>
            <strong style="color:var(--text)"> Possible Issue:</strong> ${escapeHTML(conv.possible_problem)}
        </div>` : ""}

        <div class="conversation-body" style="flex-grow:1; overflow-y:auto; padding: 12px 16px;">
            ${messagesHtml}
        </div>

        <div class="review-segment" style="padding:12px 16px; border-top:1px solid var(--line); background:rgba(0,0,0,0.2);">
            <div style="display:flex; align-items:center; gap:12px; margin-bottom:8px;">
                <span style="font-size:13px; font-weight:600; color:var(--text-dim)">Resolution:</span>
                <select id="ticket-res-select-${convId}" style="background:var(--surface-2); border:1px solid var(--line); color:white; padding:6px 10px; border-radius:6px; font-size:12.5px;">
                    <option value="unresolved" ${resStatus === 'unresolved' ? 'selected' : ''}>Unresolved</option>
                    <option value="resolved" ${resStatus === 'resolved' ? 'selected' : ''}>Resolved</option>
                    <option value="escalated" ${resStatus === 'escalated' ? 'selected' : ''}>Escalated</option>
                </select>
            </div>
        </div>
    `;

    const resSelect = document.getElementById(`ticket-res-select-${convId}`);
    if (resSelect) {
        resSelect.addEventListener("change", async (e) => {
            try {
                await updateResolutionStatus(convId, e.target.value);
                await loadConversations(true);
            } catch (err) {
                console.error("Failed to update resolution:", err);
            }
        });
    }
    const body = detailCol.querySelector(".conversation-body");
    if (body) body.scrollTop = body.scrollHeight;
}

/* ---- ENRICHED: Live call detail panel ---- */
async function loadEnrichedConversationDetail(convId) {
    const enriched = allEnrichedConvs.find(c => c.id === convId);
    const channel = enriched?.channel || "VOICE";
    const detailContainerId = channel === "CHAT" ? "chat-support-detail" : "call-support-detail";
    const detailCol = document.getElementById(detailContainerId);
    if (!detailCol) return;

    detailCol.innerHTML = `<div class="empty-state-panel"><i class="fa-solid fa-spinner fa-spin fa-2x"></i></div>`;

    const phone = enriched?.user_phone || "Unknown";
    const name = enriched?.user_name || "Guest";

    try {
        const response = await getConversationDetail(convId);
        const c = response.data || response;

        if (!c) {
            detailCol.innerHTML = `<div class="empty-state-panel"><h3>Conversation not found</h3></div>`;
            return;
        }

        const dateStr = c.updated_at ? new Date(c.updated_at).toLocaleString() : "";
        const messages = c.messages || [];
        const bk = enriched?.booking_details;

        let messagesHtml = `<div class="empty-state-panel"><p>No messages recorded.</p></div>`;
        if (messages.length > 0) {
            messagesHtml = messages.map(m => {
                const isUser = m.sender === "USER";
                const rowClass = isUser ? "user" : "ai";
                const label = isUser ? `📱 ${phone}` : "🤖 AI Agent";
                const msgTime = m.created_at ? new Date(m.created_at).toLocaleTimeString() : "";
                let metaTags = [];
                if (m.intent) metaTags.push(`<span class="meta-pill">NLU: ${m.intent}</span>`);
                if (m.tool_used) metaTags.push(`<span class="meta-pill">Tool: ${m.tool_used}</span>`);
                if (m.booking_code) metaTags.push(`<span class="meta-pill" style="border-color:var(--teal);color:var(--teal)">Booking: ${m.booking_code}</span>`);
                if (m.response_time_ms) metaTags.push(`<span class="meta-pill">${m.response_time_ms}ms</span>`);
                let audioWidget = "";
                if (m.audio_path) {
                    let cleanPath = m.audio_path.replace(/\\/g, "/");
                    if (!cleanPath.startsWith("http")) {
                        const tempIdx = cleanPath.indexOf("temp/");
                        const genIdx = cleanPath.indexOf("generated_audio/");
                        if (tempIdx !== -1) cleanPath = cleanPath.substring(tempIdx);
                        else if (genIdx !== -1) cleanPath = cleanPath.substring(genIdx);
                        else cleanPath = `generated_audio/${cleanPath}`;
                    }
                    const audioUrl = cleanPath.startsWith("http") ? cleanPath : `${getBaseUrl()}/${cleanPath}`;
                    audioWidget = `<div style="margin-top:8px;"><audio controls style="width:100%;max-width:280px;height:32px;"><source src="${audioUrl}" type="audio/webm"></audio></div>`;
                }
                return `
                    <div class="bubble-row ${rowClass}">
                        <span class="bubble-sender">${label} • ${msgTime}</span>
                        <div class="bubble-text">${escapeHTML(m.message)} ${audioWidget}</div>
                        <div class="bubble-meta-tags">${metaTags.join("")}</div>
                    </div>`;
            }).join("");
        }

        const resStatus = c.resolution_status || "unresolved";

        // Setup Layout with Tabs
        detailCol.innerHTML = `
            <div class="detail-header">
                <div class="detail-header-info">
                    <h3>
                        <i class="fa-solid ${channel === 'CHAT' ? 'fa-comments' : 'fa-phone'}" style="color:var(--teal)"></i>
                        <span style="font-family:var(--font-mono); color:white;">${phone}</span>
                        <span style="font-size:14px; color:var(--text-dim); margin-left:8px;">${name}</span>
                    </h3>
                    <p>Channel: ${c.channel} | Lang: ${(c.language||'en').toUpperCase()} | Last Updated: ${dateStr}</p>
                </div>
                <div class="detail-actions">
                    <span class="live-badge" style="background:rgba(53,216,182,0.1); color:var(--teal); border:1px solid var(--teal);">${c.status}</span>
                </div>
            </div>

            <!-- Detail Tabs Nav -->
            <div class="detail-tabs-nav">
                <button class="detail-tab-btn active" data-tab-target="transcript-${c.id}">
                    <i class="fa-solid fa-file-invoice"></i> Transcript
                </button>
                <button class="detail-tab-btn" data-tab-target="qa-review-${c.id}">
                    <i class="fa-solid fa-clipboard-check"></i> QA Review
                </button>
            </div>

            <!-- TAB 1: TRANSCRIPT CONTENT -->
            <div id="transcript-container-${c.id}" class="detail-tab-content" style="display:flex; flex-direction:column; flex-grow:1; overflow:hidden;">
                ${bk ? `
                <div style="padding:10px 16px; background:rgba(0,200,150,0.06); border-bottom:1px solid var(--line); display:flex; gap:20px; font-size:12px; flex-wrap:wrap; align-items:center;">
                    <span><i class="fa-solid fa-ticket" style="color:var(--teal)"></i> <strong>${bk.booking_code}</strong></span>
                    <span><i class="fa-solid fa-route" style="color:var(--blue)"></i> ${bk.source||"?"} → ${bk.destination||"?"}</span>
                    <span><i class="fa-solid fa-chair" style="color:var(--purple)"></i> Seat ${bk.seat_number||"?"}</span>
                    <span class="badge-status ${bk.booking_status==='CONFIRMED'?'confirmed':'cancelled'}">${bk.booking_status}</span>
                    <span class="badge-status ${bk.payment_status==='PAID'?'paid':'pending'}">${bk.payment_status}</span>
                    ${bk.departure_time ? `<span style="color:var(--text-dim)"><i class="fa-solid fa-clock"></i> ${new Date(bk.departure_time).toLocaleString()}</span>` : ""}
                </div>` : ""}

                ${enriched?.possible_problem ? `
                <div style="padding:8px 16px; background:rgba(255,80,80,0.05); border-bottom:1px solid var(--line); font-size:12px; color:var(--text-dim);">
                    <i class="fa-solid fa-triangle-exclamation" style="color:var(--red)"></i>
                    <strong style="color:var(--text)"> Possible Issue:</strong> ${escapeHTML(enriched.possible_problem)}
                </div>` : ""}

                <div class="conversation-body" style="flex-grow:1; overflow-y:auto; padding: 12px 16px;">
                    ${messagesHtml}
                </div>

                <div class="resolution-bar" style="padding:16px; border-top:1px solid var(--line); background:rgba(0,0,0,0.25); display:flex; align-items:center; justify-content:space-between; gap:12px;">
                    <div style="font-size:13px; font-weight:600; color:var(--text-dim);"><i class="fa-solid fa-square-check"></i> Resolution status:</div>
                    <select class="resolution-select" id="res-select-${c.id}" style="background:var(--surface-2); border:1px solid var(--line); color:white; padding:6px 10px; border-radius:6px; font-size:12.5px; outline:none; cursor:pointer;">
                        <option value="unresolved" ${resStatus==='unresolved'?'selected':''}>Unresolved</option>
                        <option value="resolved" ${resStatus==='resolved'?'selected':''}>Resolved</option>
                        <option value="escalated" ${resStatus==='escalated'?'selected':''}>Escalated</option>
                    </select>
                </div>
            </div>

            <!-- TAB 2: QA REVIEW CONTENT -->
            <div id="qa-review-container-${c.id}" class="detail-tab-content" style="display:none; flex-direction:column; flex-grow:1; overflow-y:auto; padding:16px; gap:12px; background:rgba(0,0,0,0.1);">
                <div style="font-size:13px; font-weight:700; color:var(--text-dim); text-transform:uppercase;"><i class="fa-solid fa-list-check"></i> QA Reviews Trail</div>
                <div class="qa-reviews-list" id="qa-reviews-${c.id}" style="font-size:12px; display:flex; flex-direction:column; gap:6px; min-height:80px; max-height:160px; overflow-y:auto; background:rgba(0,0,0,0.15); padding:8px; border-radius:6px; border:1px solid rgba(255,255,255,0.03);">Loading QA trail...</div>
                
                <div style="font-size:11.5px; font-weight:700; color:var(--text-dim); text-transform:uppercase; margin-top:8px;"><i class="fa-solid fa-pen-to-square"></i> Submit QA Review</div>
                <form class="qa-review-form" id="qa-form-${c.id}" style="display:flex; flex-direction:column; gap:10px;">
                    <div style="display:flex; flex-direction:column; gap:4px;">
                        <input type="text" placeholder="Outcome tag (e.g. Helpful)" id="qa-tag-${c.id}" required style="padding:10px; font-size:12px; border:1px solid var(--line); background:var(--surface-2); border-radius:6px; color:white;">
                    </div>
                    <div style="display:flex; flex-direction:column; gap:4px;">
                        <textarea placeholder="QA review notes..." id="qa-notes-${c.id}" style="padding:10px; font-size:12px; border:1px solid var(--line); background:var(--surface-2); border-radius:6px; color:white; min-height:60px; resize:vertical; font-family:inherit;"></textarea>
                    </div>
                    <button type="submit" style="margin-top:4px; padding:10px 14px; font-size:12.5px; cursor:pointer; background:linear-gradient(135deg, var(--teal), var(--blue)); border:none; color:white; border-radius:6px; font-weight:600;">Submit QA</button>
                </form>
            </div>
        `;

        const body = detailCol.querySelector(".conversation-body");
        if (body) body.scrollTop = body.scrollHeight;

        // Tab Switching Logic
        const tabBtns = detailCol.querySelectorAll(".detail-tab-btn");
        const transcriptTab = detailCol.querySelector(`#transcript-container-${c.id}`);
        const qaTab = detailCol.querySelector(`#qa-review-container-${c.id}`);

        tabBtns.forEach(btn => {
            btn.addEventListener("click", () => {
                const target = btn.dataset.tabTarget;
                tabBtns.forEach(b => {
                    b.classList.remove("active");
                });
                btn.classList.add("active");

                if (target.startsWith("transcript-")) {
                    transcriptTab.style.display = "flex";
                    qaTab.style.display = "none";
                    if (body) body.scrollTop = body.scrollHeight;
                } else {
                    transcriptTab.style.display = "none";
                    qaTab.style.display = "flex";
                    loadQaReviews();
                }
            });
        });

        // Resolution select listener
        const resSelect = document.getElementById(`res-select-${c.id}`);
        if (resSelect) {
            resSelect.addEventListener("change", async (e) => {
                try {
                    await updateResolutionStatus(c.id, e.target.value);
                    await loadConversations(true);
                } catch (err) { console.error("Failed to update resolution:", err); }
            });
        }

        // QA Reviews load helper
        const loadQaReviews = async () => {
            const listDiv = document.getElementById(`qa-reviews-${c.id}`);
            if (!listDiv) return;
            try {
                const reviewsRes = await fetch(`${getBaseUrl()}/api/v1/conversations/${c.id}/reviews`, {
                    headers: { "Authorization": `Bearer ${getToken()}` }
                });
                const reviewsJson = await reviewsRes.json();
                const reviews = reviewsJson.data || [];
                if (reviews.length === 0) {
                    listDiv.innerHTML = `<span style="color:var(--text-dim); font-style:italic;">No QA reviews logged.</span>`;
                } else {
                    listDiv.innerHTML = reviews.map(r => {
                        const rDate = new Date(r.reviewed_at).toLocaleTimeString();
                        return `<div style="padding:6px 4px; border-bottom:1px solid rgba(255,255,255,0.03); line-height:1.4;">
                            <strong style="color:var(--teal)">[${escapeHTML(r.outcome_tag)}]</strong>
                            <span style="color:var(--text)">${escapeHTML(r.notes||'')}</span>
                            <span style="color:var(--text-dim); font-size:10px; float:right;">${rDate}</span>
                        </div>`;
                    }).join("");
                }
            } catch (err) {
                listDiv.innerHTML = `<span style="color:var(--red)">Failed to load QA trail.</span>`;
            }
        };

        // QA form submit listener
        const qaForm = document.getElementById(`qa-form-${c.id}`);
        if (qaForm) {
            qaForm.addEventListener("submit", async (e) => {
                e.preventDefault();
                const tagInput = document.getElementById(`qa-tag-${c.id}`);
                const notesInput = document.getElementById(`qa-notes-${c.id}`);
                if (!tagInput) return;
                try {
                    await submitCallReview(c.id, tagInput.value, notesInput?.value || "");
                    tagInput.value = "";
                    if (notesInput) notesInput.value = "";
                    await loadQaReviews();
                } catch (err) {
                    console.error("Failed to submit QA review:", err);
                    alert("Error: " + err.message);
                }
            });
        }

        // Initially load QA reviews in background
        loadQaReviews();

    } catch (err) {
        console.error("Failed to load conversation details:", err);
        detailCol.innerHTML = `<div class="empty-state-panel"><p style="color:var(--red)">Failed to load details.</p></div>`;
    }
}

async function loadConversationDetail(convId) {
    return loadEnrichedConversationDetail(convId);
}

function escapeHTML(str) {
    if (!str) return "";
    return str.replace(/[&<>'"]/g, tag => ({
        "&": "&amp;", "<": "&lt;", ">": "&gt;", "'": "&#39;", '"': "&quot;"
    }[tag] || tag));
}

/* ----------------- TICKETS TAB COMPONENT ----------------- */
function renderTickets(complaints) {
    const listContainer = document.getElementById("tickets-list");
    if (!listContainer) return;

    if (!complaints || complaints.length === 0) {
        listContainer.innerHTML = `<div style="text-align:center; padding: 20px; color:var(--text-dim)">No ticket logs found in database.</div>`;
        return;
    }

    listContainer.innerHTML = complaints.map((c, idx) => {
        const dateStr = c.created_at ? formatRelativeTime(c.created_at) : "recently";
        const customerName = c.customer ? c.customer.name : "Guest Customer";
        
        return `
            <div class="list-item ${idx === 0 ? 'active' : ''}" data-complaint-id="${c.id}">
                <div class="item-meta">
                    <span>Ticket #${c.complaint_code}</span>
                    <span>${dateStr}</span>
                </div>
                <div class="item-title">${c.title}</div>
                <div class="item-subtitle">Customer: ${customerName} | Code: ${c.booking_code || 'N/A'}</div>
            </div>
        `;
    }).join("");

    const items = listContainer.querySelectorAll(".list-item");
    items.forEach(item => {
        item.addEventListener("click", () => {
            items.forEach(i => i.classList.remove("active"));
            item.classList.add("active");
            loadTicketDetail(item.dataset.complaintId);
        });
    });

    if (complaints.length > 0) {
        loadTicketDetail(complaints[0].id);
    }
}

async function loadTicketDetail(complaintId) {
    const detailCol = document.getElementById("ticket-detail");
    if (!detailCol) return;

    detailCol.innerHTML = `<div class="empty-state-panel"><i class="fa-solid fa-spinner fa-spin fa-2x"></i></div>`;

    try {
        // Fetch complaints to find current selection
        const response = await getComplaints();
        const list = response.data || response;
        const c = list.find(item => item.id === complaintId);

        if (!c) {
            detailCol.innerHTML = `<div class="empty-state-panel"><h3>Ticket not found</h3></div>`;
            return;
        }

        const customerName = c.customer ? c.customer.name : "Guest Customer";
        const customerEmail = c.customer ? c.customer.email : "N/A";
        const customerPhone = c.customer ? c.customer.phone : "N/A";
        const tripRoute = c.trip ? `${c.trip.source} → ${c.trip.destination}` : "Route: N/A";
        
        let badgeText = c.status;
        let badgeClass = "badge-frustration";
        if (c.status === "RESOLVED") {
            badgeClass = "badge-resolved";
        } else if (c.status === "IN_PROGRESS") {
            badgeClass = "badge-escalated";
        }

        // Search for associated chat transcript in db
        let convoHtml = `<div style="text-align: center; color: var(--text-dim); padding: 20px;"><i class="fa-solid fa-circle-info"></i> No active support chat transcript recorded for this ticket.</div>`;
        
        if (c.booking_code) {
            try {
                const searchRes = await searchConversations(c.booking_code);
                const results = searchRes.data.conversations || [];
                if (results.length > 0) {
                    const detailRes = await getConversationDetail(results[0].id);
                    const conv = detailRes.data || detailRes;
                    const messages = conv.messages || [];
                    
                    if (messages.length > 0) {
                        convoHtml = messages.map(m => {
                            const isUser = m.sender === "USER";
                            const rowClass = isUser ? "user" : "ai";
                            const label = isUser ? "User" : "AI Agent";
                            const msgTime = m.created_at ? new Date(m.created_at).toLocaleTimeString() : "";

                            let metaTags = [];
                            if (m.intent) metaTags.push(`<span class="meta-pill">NLU: ${m.intent}</span>`);
                            if (m.tool_used) metaTags.push(`<span class="meta-pill">Tool: ${m.tool_used}</span>`);
                            if (m.response_time_ms) metaTags.push(`<span class="meta-pill">${m.response_time_ms} ms</span>`);

                            return `
                                <div class="bubble-row ${rowClass}">
                                    <span class="bubble-sender">${label} • ${msgTime}</span>
                                    <div class="bubble-text">${escapeHTML(m.message)}</div>
                                    <div class="bubble-meta-tags">
                                        ${metaTags.join("")}
                                    </div>
                                </div>
                            `;
                        }).join("");
                    }
                }
            } catch (err) {
                console.warn("Failed to load associated conversation:", err);
            }
        }

        let associatedConversation = null;
        if (c.booking_code) {
            try {
                const searchRes = await searchConversations(c.booking_code);
                const results = searchRes.data.conversations || [];
                if (results.length > 0) {
                    const detailRes = await getConversationDetail(results[0].id);
                    associatedConversation = detailRes.data || detailRes;
                    const messages = associatedConversation.messages || [];
                    
                    if (messages.length > 0) {
                        convoHtml = messages.map(m => {
                            const isUser = m.sender === "USER";
                            const rowClass = isUser ? "user" : "ai";
                            const label = isUser ? "User" : "AI Agent";
                            const msgTime = m.created_at ? new Date(m.created_at).toLocaleTimeString() : "";

                            let metaTags = [];
                            if (m.intent) metaTags.push(`<span class="meta-pill">NLU: ${m.intent}</span>`);
                            if (m.tool_used) metaTags.push(`<span class="meta-pill">Tool: ${m.tool_used}</span>`);
                            if (m.response_time_ms) metaTags.push(`<span class="meta-pill">${m.response_time_ms} ms</span>`);

                            return `
                                <div class="bubble-row ${rowClass}">
                                    <span class="bubble-sender">${label} • ${msgTime}</span>
                                    <div class="bubble-text">${escapeHTML(m.message)}</div>
                                    <div class="bubble-meta-tags">
                                        ${metaTags.join("")}
                                    </div>
                                </div>
                            `;
                        }).join("");
                    }
                }
            } catch (err) {
                console.warn("Failed to load associated conversation:", err);
            }
        }

        let reviewSectionHtml = "";
        if (associatedConversation) {
            reviewSectionHtml = `
                <div class="review-segment" style="padding: 16px; border-top: 1px solid var(--line); background: rgba(0,0,0,0.25); display: flex; flex-direction: column; gap: 12px; margin-top: 12px; border-radius: 8px;">
                    <div style="display: flex; align-items: center; justify-content: space-between; gap: 12px;">
                        <div style="font-size: 13px; font-weight: 600; color: var(--text-dim);"><i class="fa-solid fa-square-check"></i> Resolution status:</div>
                        <select class="resolution-select" id="ticket-res-select-${associatedConversation.id}" style="background: var(--surface-2); border: 1px solid var(--line); color: white; padding: 6px 10px; border-radius: 6px; font-size: 12.5px; outline: none; cursor: pointer;">
                            <option value="unresolved" ${associatedConversation.resolution_status === 'unresolved' ? 'selected' : ''}>Unresolved</option>
                            <option value="resolved" ${associatedConversation.resolution_status === 'resolved' ? 'selected' : ''}>Resolved</option>
                            <option value="escalated" ${associatedConversation.resolution_status === 'escalated' ? 'selected' : ''}>Escalated</option>
                        </select>
                    </div>

                    <!-- Call QA Reviews list -->
                    <div style="font-size: 11px; font-weight: 700; color: var(--text-dim); text-transform: uppercase; margin-top: 4px;"><i class="fa-solid fa-list-check"></i> QA Reviews Trail</div>
                    <div class="qa-reviews-list" id="ticket-qa-reviews-${associatedConversation.id}" style="font-size: 12px; display: flex; flex-direction: column; gap: 6px; max-height: 90px; overflow-y: auto; background: rgba(0,0,0,0.15); padding: 8px; border-radius: 6px; border: 1px solid rgba(255,255,255,0.03);">
                        Loading QA trail...
                    </div>

                    <!-- Add Call Review Form -->
                    <form class="qa-review-form" id="ticket-qa-form-${associatedConversation.id}" style="display: flex; gap: 8px; align-items: center; margin-top: 4px;">
                        <input type="text" placeholder="Outcome tag" id="ticket-qa-tag-${associatedConversation.id}" required style="padding: 10px; font-size: 12px; border: 1px solid var(--line); background: var(--surface-2); border-radius: 6px; flex: 1;">
                        <input type="text" placeholder="QA notes..." id="ticket-qa-notes-${associatedConversation.id}" style="padding: 10px; font-size: 12px; border: 1px solid var(--line); background: var(--surface-2); border-radius: 6px; flex: 2;">
                        <button type="submit" style="margin-top: 0; padding: 10px 14px; width: auto; font-size: 12.5px; white-space: nowrap;">Submit QA</button>
                    </form>
                </div>
            `;
        }

        detailCol.innerHTML = `
            <div class="detail-header">
                <div class="detail-header-info">
                    <h3>Ticket #${c.complaint_code} Details</h3>
                    <p>Booking Reference: <strong>${c.booking_code || 'N/A'}</strong></p>
                </div>
                <div class="detail-actions">
                    <span class="live-badge ${badgeClass}">${badgeText}</span>
                </div>
            </div>
            
            <!-- Ticket Details Meta -->
            <div style="background: rgba(255,255,255,0.015); border-bottom: 1px solid var(--line); padding: 18px 24px; display:flex; flex-direction:column; gap:10px;">
                <div style="display:grid; grid-template-columns: 1fr 1fr; gap:10px; font-size:12px;">
                    <div><span style="color:var(--text-dim)">Customer:</span> <strong style="color:white">${customerName}</strong></div>
                    <div><span style="color:var(--text-dim)">Route:</span> <strong style="color:white">${tripRoute}</strong></div>
                    <div><span style="color:var(--text-dim)">Email:</span> <strong style="color:white">${customerEmail}</strong></div>
                    <div><span style="color:var(--text-dim)">Phone:</span> <strong style="color:white">${customerPhone}</strong></div>
                </div>
                <div style="margin-top:6px; font-size:13px; line-height:1.45; color:var(--text-secondary); background:rgba(0,0,0,0.15); padding:10px 14px; border-radius:6px; border:1px solid rgba(255,255,255,0.02);">
                    <div style="font-size:10px; font-weight:700; color:var(--text-dim); margin-bottom:4px; text-transform:uppercase;">Complaint Description</div>
                    ${escapeHTML(c.description)}
                </div>
            </div>

            <!-- Associated Conversation History -->
            <div style="padding: 18px 24px 8px; font-family: var(--font-display); font-size: 13px; font-weight: 700; color: var(--text-dim); border-bottom: 1px solid rgba(255,255,255,0.04);">
                <i class="fa-solid fa-comments"></i> Associated Chat Transcript
            </div>
            
            <div class="conversation-body" style="height: 180px; overflow-y: auto; padding: 20px; border-bottom: 1px solid var(--line);">
                ${convoHtml}
            </div>

            ${reviewSectionHtml}
        `;

        const body = detailCol.querySelector(".conversation-body");
        if (body) body.scrollTop = body.scrollHeight;

        if (associatedConversation) {
            const ticketConvId = associatedConversation.id;

            // Resolution handler
            const ticketResSelect = document.getElementById(`ticket-res-select-${ticketConvId}`);
            if (ticketResSelect) {
                ticketResSelect.addEventListener("change", async (e) => {
                    try {
                        await updateResolutionStatus(ticketConvId, e.target.value);
                        console.log("Ticket resolution updated:", e.target.value);
                        await loadConversations(true);
                    } catch (err) {
                        console.error(err);
                    }
                });
            }

            // QA load helper
            const loadTicketQaReviews = async () => {
                const listDiv = document.getElementById(`ticket-qa-reviews-${ticketConvId}`);
                if (!listDiv) return;
                try {
                    const reviewsRes = await fetch(`${getBaseUrl()}/api/v1/conversations/${ticketConvId}/reviews`, {
                        headers: { "Authorization": `Bearer ${getToken()}` }
                    });
                    const reviewsJson = await reviewsRes.json();
                    const reviews = reviewsJson.data || [];
                    
                    if (reviews.length === 0) {
                        listDiv.innerHTML = `<span style="color:var(--text-dim); font-style:italic;">No QA reviews logged.</span>`;
                    } else {
                        listDiv.innerHTML = reviews.map(r => {
                            const rDate = new Date(r.reviewed_at).toLocaleTimeString();
                            return `<div style="padding: 6px 4px; border-bottom: 1px solid rgba(255,255,255,0.03);">
                                <strong style="color:var(--teal)">[${escapeHTML(r.outcome_tag)}]</strong> 
                                <span style="color:var(--text)">${escapeHTML(r.notes || '')}</span>
                                <span style="color:var(--text-dim); font-size: 10px; float: right;">${rDate}</span>
                            </div>`;
                        }).join("");
                    }
                } catch (err) {
                    listDiv.innerHTML = `<span style="color:var(--red)">Error.</span>`;
                }
            };

            // QA submit handler
            const ticketQaForm = document.getElementById(`ticket-qa-form-${ticketConvId}`);
            if (ticketQaForm) {
                ticketQaForm.addEventListener("submit", async (e) => {
                    e.preventDefault();
                    const tagInput = document.getElementById(`ticket-qa-tag-${ticketConvId}`);
                    const notesInput = document.getElementById(`ticket-qa-notes-${ticketConvId}`);
                    try {
                        await submitCallReview(ticketConvId, tagInput.value, notesInput.value);
                        tagInput.value = "";
                        notesInput.value = "";
                        await loadTicketQaReviews();
                    } catch (err) {
                        console.error(err);
                    }
                });
            }

            loadTicketQaReviews();
        }

    } catch (err) {
        console.error("Failed to load ticket details:", err);
        detailCol.innerHTML = `<div class="empty-state-panel"><p style="color:var(--red)">Failed to load ticket details.</p></div>`;
    }
}

/* ----------------- DRIVERS TAB COMPONENT ----------------- */
function initDriversTab() {
    const driversGrid = document.getElementById("drivers-grid");
    if (!driversGrid) return;

    const mockDrivers = [
        { name: "Rajesh Kumar", id: "DR-4091", route: "Delhi -> Jaipur", speed: "78 km/h", status: "In Transit", active: true, avatar: "https://images.unsplash.com/photo-1500648767791-00dcc994a43e?auto=format&fit=crop&q=80&w=100" },
        { name: "Amit Singh", id: "DR-2391", route: "Mumbai -> Pune", speed: "0 km/h", status: "On Break", active: false, avatar: "https://images.unsplash.com/photo-1472099645785-5658abf4ff4e?auto=format&fit=crop&q=80&w=100" },
        { name: "Vijay Sharma", id: "DR-9011", route: "Bengaluru -> Chennai", speed: "65 km/h", status: "In Transit", active: true, avatar: "https://images.unsplash.com/photo-1519085360753-af0119f7cbe7?auto=format&fit=crop&q=80&w=100" },
        { name: "Suresh Patil", id: "DR-5612", route: "None", speed: "0 km/h", status: "Off Duty", active: false, avatar: "https://images.unsplash.com/photo-1507003211169-0a1dd7228f2d?auto=format&fit=crop&q=80&w=100" }
    ];

    driversGrid.innerHTML = mockDrivers.map(d => {
        const statClass = d.status === "In Transit" ? "style='color: var(--teal)'" : "style='color: var(--text-dim)'";
        return `
            <div class="driver-card">
                <div class="driver-profile">
                    <img src="${d.avatar}" alt="${d.name}">
                    <div class="driver-info">
                        <h4>${d.name}</h4>
                        <p>ID: ${d.id}</p>
                    </div>
                    <span class="live-badge" style="margin-left:auto; background:${d.active ? 'rgba(53, 216, 182, 0.08)' : 'rgba(255,255,255,0.03)'}; color:${d.active ? 'var(--teal)' : 'var(--text-dim)'}">${d.status}</span>
                </div>
                <div class="driver-stats">
                    <div class="driver-stat-item">
                        <span class="label">ACTIVE ROUTE</span>
                        <span class="val">${d.route}</span>
                    </div>
                    <div class="driver-stat-item">
                        <span class="label">SPEED</span>
                        <span class="val" ${statClass}>${d.speed}</span>
                    </div>
                </div>
            </div>
        `;
    }).join("");
}

/* ----------------- CANVAS VISUALIZATIONS ----------------- */
function initCanvasAnimations() {
    const flowCanvas = document.getElementById("flowCanvas");
    const waveCanvas = document.getElementById("waveCanvas");

    if (flowCanvas) {
        resizeCanvas(flowCanvas);
        setupFlowParticles();
        animateFlow();
    }

    if (waveCanvas) {
        resizeCanvas(waveCanvas);
        animateWave();
    }

    window.addEventListener("resize", resizeCanvases);
}

function resizeCanvas(canvas) {
    const rect = canvas.parentNode.getBoundingClientRect();
    canvas.width = rect.width * window.devicePixelRatio;
    canvas.height = rect.height * window.devicePixelRatio;
    
    const ctx = canvas.getContext("2d");
    ctx.scale(window.devicePixelRatio, window.devicePixelRatio);
}

function resizeCanvases() {
    const flowCanvas = document.getElementById("flowCanvas");
    const waveCanvas = document.getElementById("waveCanvas");
    if (flowCanvas) resizeCanvas(flowCanvas);
    if (waveCanvas) resizeCanvas(waveCanvas);
}

// Flow Particles setup
function setupFlowParticles() {
    particles = [];
    const count = 45;
    for (let i = 0; i < count; i++) {
        particles.push({
            x: Math.random() * 500,
            y: Math.random() * 280,
            vx: (Math.random() - 0.5) * 0.8,
            vy: (Math.random() - 0.5) * 0.8,
            radius: Math.random() * 3 + 1,
            // Types map to Synthesizing (purple), Context (cyan), NLP (teal)
            type: Math.random() < 0.33 ? "synth" : (Math.random() < 0.66 ? "context" : "nlp"),
            pulse: Math.random() * Math.PI
        });
    }
}

function animateFlow() {
    const canvas = document.getElementById("flowCanvas");
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    const w = canvas.width / window.devicePixelRatio;
    const h = canvas.height / window.devicePixelRatio;

    ctx.clearRect(0, 0, w, h);

    // Dynamic speed based on Cluster toggle
    const speedMultiplier = currentCluster === "A1" ? 1.0 : 1.6;

    // Draw grid mesh behind
    ctx.strokeStyle = "rgba(255,255,255,0.015)";
    ctx.lineWidth = 1;
    const gridSize = 25;
    for (let x = 0; x < w; x += gridSize) {
        ctx.beginPath();
        ctx.moveTo(x, 0);
        ctx.lineTo(x, h);
        ctx.stroke();
    }
    for (let y = 0; y < h; y += gridSize) {
        ctx.beginPath();
        ctx.moveTo(0, y);
        ctx.lineTo(w, y);
        ctx.stroke();
    }

    // Move & draw particles
    particles.forEach(p => {
        p.x += p.vx * speedMultiplier;
        p.y += p.vy * speedMultiplier;

        // Boundaries
        if (p.x < 0 || p.x > w) p.vx *= -1;
        if (p.y < 0 || p.y > h) p.vy *= -1;

        p.pulse += 0.02;
        const alpha = 0.3 + Math.sin(p.pulse) * 0.2;

        let color = "rgba(6, 182, 212, " + alpha + ")"; // Cyan default
        if (p.type === "synth") color = "rgba(139, 92, 246, " + alpha + ")"; // Purple
        if (p.type === "nlp") color = "rgba(53, 216, 182, " + alpha + ")"; // Teal

        ctx.beginPath();
        ctx.arc(p.x, p.y, p.radius + Math.sin(p.pulse) * 0.5, 0, Math.PI * 2);
        ctx.fillStyle = color;
        ctx.shadowBlur = 6;
        ctx.shadowColor = color.replace(/[\d\.]+\)$/, "0.5)");
        ctx.fill();
        ctx.shadowBlur = 0; // reset
    });

    // Draw links between nearby particles
    ctx.lineWidth = 0.5;
    for (let i = 0; i < particles.length; i++) {
        for (let j = i + 1; j < particles.length; j++) {
            const p1 = particles[i];
            const p2 = particles[j];
            const dx = p1.x - p2.x;
            const dy = p1.y - p2.y;
            const dist = Math.sqrt(dx * dx + dy * dy);

            if (dist < 65) {
                const alpha = (1 - dist / 65) * 0.12;
                ctx.strokeStyle = `rgba(255, 255, 255, ${alpha})`;
                ctx.beginPath();
                ctx.moveTo(p1.x, p1.y);
                ctx.lineTo(p2.x, p2.y);
                ctx.stroke();
            }
        }
    }

    flowAnimationFrame = requestAnimationFrame(animateFlow);
}

// Bouncing speech synth waveform
function animateWave() {
    const canvas = document.getElementById("waveCanvas");
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    const w = canvas.width / window.devicePixelRatio;
    const h = canvas.height / window.devicePixelRatio;

    ctx.clearRect(0, 0, w, h);

    ctx.strokeStyle = "rgba(6, 182, 212, 0.4)";
    ctx.lineWidth = 1.5;

    // Draw central grid line
    ctx.beginPath();
    ctx.strokeStyle = "rgba(255, 255, 255, 0.03)";
    ctx.moveTo(0, h/2);
    ctx.lineTo(w, h/2);
    ctx.stroke();

    wavePhase += 0.07;

    // We draw 3 overlapping waves with different phases
    const waves = [
        { color: "rgba(53, 216, 182, 0.75)", amp: 20, freq: 0.015, phase: wavePhase },
        { color: "rgba(37, 99, 235, 0.5)", amp: 14, freq: 0.025, phase: wavePhase + 1.5 },
        { color: "rgba(139, 92, 246, 0.4)", amp: 8, freq: 0.035, phase: wavePhase - 1.0 }
    ];

    waves.forEach(wave => {
        ctx.strokeStyle = wave.color;
        ctx.beginPath();
        ctx.moveTo(0, h / 2);

        for (let x = 0; x < w; x++) {
            // Envelope to pinch waves at the start and end edges
            const envelope = Math.sin((x / w) * Math.PI);
            const y = h / 2 + Math.sin(x * wave.freq + wave.phase) * wave.amp * envelope;
            ctx.lineTo(x, y);
        }
        ctx.stroke();
    });

    waveAnimationFrame = requestAnimationFrame(animateWave);
}

// Attach cluster toggles logic
function initLiveAlerts() {
    const toggles = document.querySelectorAll(".btn-toggle");
    toggles.forEach(toggle => {
        toggle.addEventListener("click", () => {
            toggles.forEach(t => t.classList.remove("active"));
            toggle.classList.add("active");
            currentCluster = toggle.dataset.cluster;
        });
    });
}

/* ----------------- SETTINGS & THRESHOLDS ----------------- */
function initSettingsTab() {
    const slider = document.getElementById("threshold-slider");
    const valSpan = document.querySelector(".threshold-val");
    if (slider && valSpan) {
        slider.addEventListener("input", (e) => {
            valSpan.textContent = `${e.target.value}%`;
        });
    }
}
