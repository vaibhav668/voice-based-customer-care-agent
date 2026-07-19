import {
    getProfile,
    getBaseUrl,
    getConversations,
    getComplaints,
    searchConversations,
    getConversationDetail,
    getAnalyticsBookings,
    updateResolutionStatus,
    getAdminEnrichedConversations,
    getAdminReviews
} from "./api.js";
import { clearAll, getToken } from "./storage.js";

/* =========================================================
   GLOBAL STATE
   ========================================================= */
let adminProfile      = null;
let allEnrichedConvs  = [];   // raw enriched convs from /admin/enriched
let allReviews        = [];
let allBookings       = [];
let groupedCustomers  = {};   // phone -> { phone, name, conversations[], ... }

let selectedCustomerPhone = null;
let activeLoadToken       = null;  // race-condition guard for async load

let convSearchQuery = "";

// Chart instances
let chartCallsTimelineInst   = null;
let chartResolutionRatioInst = null;
let chartLanguageDistInst    = null;
let chartRatingsTrendInst    = null;

const TWENTY_FOUR_HOURS_MS = 24 * 60 * 60 * 1000;

/* ─── Avatar helpers ──────────────────────────────────────── */
const AVATAR_COLORS = [
    "#2563eb","#7c3aed","#0891b2","#059669","#d97706",
    "#dc2626","#db2777","#65a30d","#0284c7","#6d28d9"
];
function avatarColor(str) {
    let hash = 0;
    for (const ch of (str || "")) hash = (hash * 31 + ch.charCodeAt(0)) | 0;
    return AVATAR_COLORS[Math.abs(hash) % AVATAR_COLORS.length];
}
function initials(name) {
    return (name || "CU").split(" ").map(n => n[0]).join("").substring(0, 2).toUpperCase();
}

/* =========================================================
   BOOT
   ========================================================= */
document.addEventListener("DOMContentLoaded", async () => {
    const token = getToken();
    if (!token) { location.href = "index.html"; return; }

    try {
        const response = await getProfile();
        // Backend wraps all responses: { success, message, data }
        adminProfile = response.data || response;
        if (adminProfile.role !== "ADMIN") { location.href = "dashboard.html"; return; }

        const nameEl   = document.getElementById("admin-name");
        const avatarEl = document.getElementById("admin-avatar-initials");
        if (nameEl)   nameEl.textContent   = adminProfile.full_name || "Support AI Admin";
        if (avatarEl) avatarEl.textContent = initials(adminProfile.full_name || "SA");
    } catch (err) {
        console.error("[BOOT] Auth check failed:", err);
        clearAll(); location.href = "index.html"; return;
    }

    initTabNavigation();
    initGlobalSearch();
    initConversationSearch();
    initScrollToBottom();
    wireSearchInput();

    const refreshBtn = document.getElementById("btn-refresh-data");
    if (refreshBtn) {
        refreshBtn.addEventListener("click", async () => {
            refreshBtn.innerHTML = `<i class="fa-solid fa-spinner fa-spin"></i> Syncing…`;
            await loadAllData();
            refreshBtn.innerHTML = `<i class="fa-solid fa-arrows-rotate"></i> Sync Live Data`;
        });
    }

    const logoutBtn = document.getElementById("admin-logout");
    if (logoutBtn) {
        logoutBtn.addEventListener("click", () => { clearAll(); location.href = "index.html"; });
    }

    await loadAllData();
    initWebSocket();
});

/* =========================================================
   TAB NAVIGATION
   ========================================================= */
function initTabNavigation() {
    document.querySelectorAll(".nav-item").forEach(item => {
        item.addEventListener("click", () => {
            const t = item.dataset.tab;
            if (t) switchToTab(t);
        });
    });
}

function switchToTab(tabName) {
    document.querySelectorAll(".nav-item").forEach(n =>
        n.classList.toggle("active", n.dataset.tab === tabName)
    );
    document.querySelectorAll(".tab-pane").forEach(p =>
        p.classList.toggle("active", p.id === `tab-${tabName}`)
    );
}

/* =========================================================
   DATA LOADING
   ========================================================= */
async function loadAllData() {
    try { await fetchConversations(); } catch (e) { console.error("[loadAllData] fetchConversations:", e); }
    try { await fetchReviews();       } catch (e) { console.error("[loadAllData] fetchReviews:", e); }
    try { await fetchBookings();      } catch (e) { console.error("[loadAllData] fetchBookings:", e); }

    try { renderDashboard4Metrics(); } catch (e) { console.error("[render] metrics:", e); }
    try { renderDashboardCharts();   } catch (e) { console.error("[render] charts:", e); }
    try { renderLiveCallsPanel24h(); } catch (e) { console.error("[render] livePanel:", e); }
    try { renderCustomerList();      } catch (e) { console.error("[render] customerList:", e); }
    try { renderFeedbackTab();       } catch (e) { console.error("[render] feedbackTab:", e); }
    try { renderBookingsTab();       } catch (e) { console.error("[render] bookingsTab:", e); }
}

/* ─── Fetch enriched conversations ───────────────────────── */
async function fetchConversations() {
    const res = await getAdminEnrichedConversations(200);
    // API response shape: { success: true, message: "...", data: { conversations: [...], total: N } }
    allEnrichedConvs = res?.data?.conversations || [];
    console.log("[fetchConversations] total convs from API:", allEnrichedConvs.length);
    groupCustomersByPhone();
}

async function fetchReviews() {
    const res = await getAdminReviews();
    // API response shape: { success: true, message: "...", data: { reviews: [...], total: N } }
    allReviews = res?.data?.reviews || [];
    console.log("[fetchReviews] total reviews:", allReviews.length);
}

async function fetchBookings() {
    const res = await getAnalyticsBookings();
    // API response shape: { success: true, message: "...", data: [...] }
    allBookings = res?.data || [];
    console.log("[fetchBookings] total bookings:", allBookings.length);
}

/* ─── Group conversations by unique phone ──────────────────
   Each entry in the groupedCustomers map contains:
   - phone, name, language
   - conversations[]  ← enriched conv objects, sorted oldest→newest
   - resolvedCount, openCount
   - bookingCodes: Map<convId, bookingCode>  ← per-conv, not a Set
   - lastActivity
   ───────────────────────────────────────────────────────── */
function groupCustomersByPhone() {
    groupedCustomers = {};

    for (const conv of allEnrichedConvs) {
        // Exact field names from backend enriched endpoint:
        // id, session_id, user_id, user_phone, user_name, channel, language,
        // status, resolution_status, current_intent, message_count, sentiment,
        // summary, booking_code, booking_details, started_at, updated_at,
        // ivr_state, rating, duration
        const phone = conv.user_phone || "Unknown";

        if (!groupedCustomers[phone]) {
            groupedCustomers[phone] = {
                phone,
                name:          conv.user_name || "Guest Customer",
                conversations: [],
                lastActivity:  conv.updated_at || conv.started_at || null,
                resolvedCount: 0,
                openCount:     0,
                // Map of convId -> bookingCode (preserves ordering; use for per-call display)
                convBookings:  {},
                language:      conv.language || "en"
            };
        }

        const g = groupedCustomers[phone];
        g.conversations.push(conv);

        // Resolution counts
        if (conv.resolution_status === "resolved") g.resolvedCount++;
        else g.openCount++;

        // Per-conversation booking code — exact field: booking_code
        if (conv.booking_code) {
            g.convBookings[conv.id] = conv.booking_code;
        }

        // Keep most-recent name / language
        if (conv.user_name && conv.user_name !== "Guest") g.name = conv.user_name;
        if (conv.language) g.language = conv.language;

        // Track latest activity
        const convTime = new Date(conv.updated_at || conv.started_at || 0);
        if (!g.lastActivity || convTime > new Date(g.lastActivity)) {
            g.lastActivity = conv.updated_at || conv.started_at;
        }
    }

    // Sort each customer's conversations oldest → newest for chat rendering
    for (const g of Object.values(groupedCustomers)) {
        g.conversations.sort((a, b) =>
            new Date(a.started_at || a.updated_at || 0) -
            new Date(b.started_at || b.updated_at || 0)
        );
    }

    console.log("[groupCustomersByPhone] unique customers:", Object.keys(groupedCustomers).length);
}

/* ─── Derive the booking reference for the SELECTED customer ─
   Uses the most recently-active conversation that has a booking code.
   This avoids showing a stale booking from an old conversation.
   ───────────────────────────────────────────────────────── */
function getMostRecentBookingCode(customer) {
    // Conversations are sorted oldest→newest; iterate in reverse for most recent
    for (let i = customer.conversations.length - 1; i >= 0; i--) {
        const conv = customer.conversations[i];
        if (conv.booking_code) return conv.booking_code;
    }
    return null;
}

/* =========================================================
   DASHBOARD — 4 METRIC CARDS
   ========================================================= */
function renderDashboard4Metrics() {
    const now = Date.now();

    const calls24h = allEnrichedConvs.filter(c => {
        if (c.status === "ACTIVE") return true;
        const t = new Date(c.started_at || c.updated_at || 0).getTime();
        return (now - t) <= TWENTY_FOUR_HOURS_MS;
    });

    const distinctActive24h = new Set(calls24h.map(c => c.user_phone).filter(Boolean));
    const activeCallsCount  = distinctActive24h.size;

    const distinctAll      = new Set(allEnrichedConvs.map(c => c.user_phone).filter(p => p && p !== "Unknown"));
    const totalUsersCount  = distinctAll.size || Object.keys(groupedCustomers).length;

    const validCalls = allEnrichedConvs.filter(c =>
        typeof c.duration === "number" && c.duration > 0 && c.duration < 14400
    );
    const sumDur = validCalls.reduce((a, c) => a + c.duration, 0);

    let avgDurFmt = "No Data Available";
    if (validCalls.length > 0 && sumDur > 0) {
        const avg = Math.round(sumDur / validCalls.length);
        const h = Math.floor(avg / 3600);
        const m = Math.floor((avg % 3600) / 60);
        const s = avg % 60;
        avgDurFmt = h > 0
            ? `${h}h ${m < 10 ? "0" : ""}${m}m ${s < 10 ? "0" : ""}${s}s`
            : `${m}m ${s < 10 ? "0" : ""}${s}s`;
    }

    const setEl = (id, v) => { const el = document.getElementById(id); if (el) el.textContent = v; };
    setEl("stat-active-calls",  activeCallsCount);
    setEl("stat-avg-duration",  avgDurFmt);
    setEl("stat-total-users",   totalUsersCount);
    setEl("stat-ai-latency",    "1.2s");

    const badge = document.getElementById("live-calls-badge");
    if (badge) badge.textContent = activeCallsCount > 0 ? `${activeCallsCount} LIVE` : "LIVE";
}

/* =========================================================
   DASHBOARD — CHARTS
   ========================================================= */
function renderDashboardCharts() {
    if (typeof Chart === "undefined") return;

    const totalCalls = allEnrichedConvs.length;

    // 1. Timeline
    const ctxCalls = document.getElementById("chartCallsTimeline")?.getContext("2d");
    if (ctxCalls) {
        if (chartCallsTimelineInst) chartCallsTimelineInst.destroy();
        const hoursMap = { "00:00": 0, "04:00": 0, "08:00": 0, "12:00": 0, "16:00": 0, "20:00": 0 };
        allEnrichedConvs.forEach(c => {
            if (!c.started_at) return;
            const h = new Date(c.started_at).getHours();
            if      (h < 4)  hoursMap["00:00"]++;
            else if (h < 8)  hoursMap["04:00"]++;
            else if (h < 12) hoursMap["08:00"]++;
            else if (h < 16) hoursMap["12:00"]++;
            else if (h < 20) hoursMap["16:00"]++;
            else             hoursMap["20:00"]++;
        });
        chartCallsTimelineInst = new Chart(ctxCalls, {
            type: "line",
            data: {
                labels: Object.keys(hoursMap),
                datasets: [{
                    label: "Calls Handled",
                    data: Object.values(hoursMap),
                    borderColor: "#2563eb", backgroundColor: "rgba(37,99,235,.06)",
                    borderWidth: 2.5, fill: true, tension: .3,
                    pointRadius: 4, pointBackgroundColor: "#2563eb"
                }]
            },
            options: {
                responsive: true, maintainAspectRatio: false,
                plugins: { legend: { display: false } },
                scales: {
                    x: { grid: { display: false }, ticks: { font: { size: 11 } } },
                    y: { beginAtZero: true, ticks: { precision: 0, font: { size: 11 } } }
                }
            }
        });
    }

    // 2. Resolution Doughnut
    const ctxRes = document.getElementById("chartResolutionRatio")?.getContext("2d");
    if (ctxRes) {
        if (chartResolutionRatioInst) chartResolutionRatioInst.destroy();
        const resolvedCount   = allEnrichedConvs.filter(c => c.resolution_status === "resolved").length;
        const unresolvedCount = totalCalls - resolvedCount;
        const resolvedPct     = totalCalls > 0 ? ((resolvedCount   / totalCalls) * 100).toFixed(1) : "0.0";
        const unresolvedPct   = totalCalls > 0 ? ((unresolvedCount / totalCalls) * 100).toFixed(1) : "0.0";
        const setEl = (id, v) => { const el = document.getElementById(id); if (el) el.textContent = v; };
        setEl("res-stat-resolved-pct",     `${resolvedPct}%`);
        setEl("res-stat-resolved-count",   `${resolvedCount} Calls`);
        setEl("res-stat-unresolved-pct",   `${unresolvedPct}%`);
        setEl("res-stat-unresolved-count", `${unresolvedCount} Calls`);
        chartResolutionRatioInst = new Chart(ctxRes, {
            type: "doughnut",
            data: {
                labels: ["Resolved", "Unresolved"],
                datasets: [{ data: [resolvedCount, unresolvedCount], backgroundColor: ["#16a34a","#dc2626"], borderWidth: 2, borderColor: "#fff" }]
            },
            options: {
                responsive: true, maintainAspectRatio: false,
                plugins: { legend: { display: false } }, cutout: "65%"
            }
        });
    }

    // 3. Language Pie
    const ctxLang = document.getElementById("chartLanguageDist")?.getContext("2d");
    if (ctxLang) {
        if (chartLanguageDistInst) chartLanguageDistInst.destroy();
        const langCounts = { "English": 0, "Hindi": 0, "Telugu": 0, "Tamil": 0, "Marathi": 0, "Gujarati": 0, "Kannada": 0, "Malayalam": 0, "Punjabi": 0, "Others": 0 };
        allEnrichedConvs.forEach(c => {
            const l = (c.language || "en").toLowerCase();
            if      (l.includes("en")) langCounts["English"]++;
            else if (l.includes("hi")) langCounts["Hindi"]++;
            else if (l.includes("te")) langCounts["Telugu"]++;
            else if (l.includes("ta")) langCounts["Tamil"]++;
            else if (l.includes("mr")) langCounts["Marathi"]++;
            else if (l.includes("gu")) langCounts["Gujarati"]++;
            else if (l.includes("kn")) langCounts["Kannada"]++;
            else if (l.includes("ml")) langCounts["Malayalam"]++;
            else if (l.includes("pa")) langCounts["Punjabi"]++;
            else                       langCounts["Others"]++;
        });
        const active  = Object.keys(langCounts).filter(k => langCounts[k] > 0);
        const labels  = active.length > 0 ? active : ["English"];
        const vals    = active.length > 0 ? active.map(k => langCounts[k]) : [1];
        const palette = ["#2563eb","#3b82f6","#60a5fa","#93c5fd","#16a34a","#22c55e","#d97706","#f59e0b","#7c3aed","#94a3b8"];
        chartLanguageDistInst = new Chart(ctxLang, {
            type: "pie",
            data: { labels, datasets: [{ data: vals, backgroundColor: palette.slice(0, labels.length), borderWidth: 1.5, borderColor: "#fff" }] },
            options: {
                responsive: true, maintainAspectRatio: false,
                plugins: {
                    legend: { position: "right", labels: { font: { size: 10 }, boxWidth: 12 } },
                    tooltip: { callbacks: { label: ctx => {
                        const v = ctx.raw || 0;
                        const t = ctx.dataset.data.reduce((a,b) => a+b, 0) || 1;
                        return `${ctx.label}: ${v} (${((v/t)*100).toFixed(1)}%)`;
                    }}}
                }
            }
        });
    }

    // 4. Ratings Bar
    const ctxRate = document.getElementById("chartRatingsTrend")?.getContext("2d");
    if (ctxRate) {
        if (chartRatingsTrendInst) chartRatingsTrendInst.destroy();
        const validRatings = [];
        allReviews.forEach(r => { if (r.rating >= 1 && r.rating <= 10) validRatings.push(r.rating); });
        allEnrichedConvs.forEach(c => { if (c.rating >= 1 && c.rating <= 10) validRatings.push(c.rating); });
        const total  = validRatings.length;
        const counts = new Array(10).fill(0);
        validRatings.forEach(s => { counts[s - 1]++; });
        const pcts = counts.map(c => total > 0 ? parseFloat(((c/total)*100).toFixed(1)) : 0);
        chartRatingsTrendInst = new Chart(ctxRate, {
            type: "bar",
            data: {
                labels: ["1★","2★","3★","4★","5★","6★","7★","8★","9★","10★"],
                datasets: [{ label: "Customer %", data: pcts, backgroundColor: "#f59e0b", borderRadius: 4 }]
            },
            options: {
                responsive: true, maintainAspectRatio: false,
                plugins: {
                    legend: { display: false },
                    tooltip: { callbacks: { label: ctx => `${ctx.raw}% (${counts[ctx.dataIndex]} of ${total})` }}
                },
                scales: {
                    x: { grid: { display: false }, ticks: { font: { size: 10 } } },
                    y: { beginAtZero: true, ticks: { callback: v => v + "%" } }
                }
            }
        });
    }
}

/* =========================================================
   DASHBOARD — LIVE CALLS PANEL
   ========================================================= */
function renderLiveCallsPanel24h() {
    const container = document.getElementById("dashboard-live-calls-list");
    if (!container) return;

    const now = Date.now();
    const calls24h = allEnrichedConvs.filter(c => {
        if (c.status === "ACTIVE") return true;
        const d = c.started_at || c.updated_at;
        if (!d) return false;
        return (now - new Date(d).getTime()) <= TWENTY_FOUR_HOURS_MS;
    });

    const display = calls24h.length > 0 ? calls24h : allEnrichedConvs.slice(0, 10);

    if (display.length === 0) {
        container.innerHTML = `<div class="empty-state-box"><i class="fa-solid fa-phone-slash"></i><p>No call sessions recorded in PostgreSQL.</p></div>`;
        return;
    }

    container.innerHTML = display.map(c => {
        const phone = c.user_phone   || "Unknown";
        const name  = c.user_name    || "Guest Customer";
        const bk    = c.booking_code || "Not Verified";
        const lang  = (c.language    || "EN").toUpperCase();
        const durSec = c.duration    || 0;
        const dur   = `${Math.floor(durSec/60)}m ${durSec%60}s`;

        let badgeClass = "badge-completed", statusLabel = "COMPLETED";
        if (c.status === "ACTIVE") {
            badgeClass = "badge-live"; statusLabel = "LIVE NOW";
        } else if (c.resolution_status === "unresolved" || c.resolution_status === "escalated") {
            badgeClass = "badge-ongoing"; statusLabel = "ONGOING";
        }

        return `
        <div class="live-call-card">
            <div class="live-call-header">
                <span class="live-customer-name">${escapeHtml(name)}</span>
                <span class="live-call-status ${badgeClass}">${statusLabel}</span>
            </div>
            <div class="live-call-details">
                <div><i class="fa-solid fa-phone"></i> ${escapeHtml(phone)}</div>
                <div><i class="fa-solid fa-ticket"></i> ${escapeHtml(bk)}</div>
                <div><i class="fa-solid fa-language"></i> ${lang}</div>
                <div><i class="fa-solid fa-clock"></i> ${dur}</div>
                <div><i class="fa-solid fa-robot"></i> ${escapeHtml(c.ivr_state || "AI_AGENT")}</div>
                <div><i class="fa-solid fa-shield"></i> Verified</div>
            </div>
            <button class="btn-view-conv" onclick="openConversationInCallSupport('${escapeAttr(phone)}')">
                <i class="fa-solid fa-eye"></i> View Conversation
            </button>
        </div>`;
    }).join("");
}

window.openConversationInCallSupport = (phone) => {
    switchToTab("call-support");
    selectCustomer(phone);
};

/* =========================================================
   CALL SUPPORT — LEFT PANEL (UNIQUE CUSTOMERS)
   ========================================================= */
function wireSearchInput() {
    const searchEl = document.getElementById("cs-search-input");
    if (searchEl) {
        searchEl.addEventListener("input", e => renderCustomerList(e.target.value));
    }
}

function renderCustomerList(filterQuery = "") {
    const container = document.getElementById("cs-customer-list");
    const skeletons  = document.getElementById("cs-skeleton-list");
    const countEl    = document.getElementById("cs-customer-count");

    if (!container) return;

    // Remove skeleton loaders
    if (skeletons) skeletons.remove();

    let customers = Object.values(groupedCustomers);

    if (filterQuery.trim()) {
        const q = filterQuery.toLowerCase();
        customers = customers.filter(c => {
            if (c.name.toLowerCase().includes(q)) return true;
            if (c.phone.toLowerCase().includes(q)) return true;
            if ((c.language || "").toLowerCase().includes(q)) return true;
            // Search across all booking codes for this customer
            return Object.values(c.convBookings).some(bk => bk.toLowerCase().includes(q));
        });
    }

    // Sort: most recently active first
    customers.sort((a, b) => new Date(b.lastActivity || 0) - new Date(a.lastActivity || 0));

    if (countEl) countEl.textContent = customers.length;

    if (customers.length === 0) {
        container.innerHTML = `
        <div class="cs-empty">
            <i class="fa-solid fa-user-slash"></i>
            <p>${filterQuery ? "No customers match your search." : "No unique customers available."}</p>
        </div>`;
        return;
    }

    container.innerHTML = customers.map(cust => buildCustomerCard(cust)).join("");

    // Auto-select first customer if none selected yet
    if (!selectedCustomerPhone && customers.length > 0) {
        selectCustomer(customers[0].phone);
    } else if (selectedCustomerPhone) {
        highlightSelectedCard();
    }
}

function buildCustomerCard(cust) {
    const isSelected  = cust.phone === selectedCustomerPhone;
    const ini         = initials(cust.name);
    const color       = avatarColor(cust.phone);
    // Total calls = exactly the number of conversations for this phone number
    const totalCalls  = cust.conversations.length;
    const lastDate    = cust.lastActivity ? formatRelativeTime(new Date(cust.lastActivity)) : "";
    // Most-recent booking code from the most recently active conversation
    const recentBooking = getMostRecentBookingCode(cust);
    const langCode    = (cust.language || "en").toUpperCase().substring(0, 2);

    const now    = Date.now();
    const lastMs = cust.lastActivity ? new Date(cust.lastActivity).getTime() : 0;
    const isRecent = (now - lastMs) < TWENTY_FOUR_HOURS_MS;
    const statusClass = isRecent ? "status-recent" : "";

    // Last message summary from the enriched data (enriched endpoint: summary field)
    const latestConv   = cust.conversations.at(-1);
    const latestPreview = latestConv?.summary || "";

    return `
    <div class="cs-customer-card ${isSelected ? "selected" : ""}"
         data-phone="${escapeAttr(cust.phone)}"
         onclick="selectCustomer('${escapeAttr(cust.phone)}')">
        <div class="cs-card-avatar ${statusClass}" style="background:${color};">${ini}</div>
        <div class="cs-card-body">
            <div class="cs-card-row1">
                <span class="cs-card-name">${escapeHtml(cust.name)}</span>
                <span class="cs-card-time">${lastDate}</span>
            </div>
            <div class="cs-card-phone">${escapeHtml(cust.phone)}</div>
            <div class="cs-card-row3">
                <span class="cs-mini-badge">${totalCalls} call${totalCalls !== 1 ? "s" : ""}</span>
                ${cust.resolvedCount > 0  ? `<span class="cs-mini-badge resolved">✓ ${cust.resolvedCount} resolved</span>` : ""}
                ${cust.openCount > 0      ? `<span class="cs-mini-badge unresolved">✕ ${cust.openCount} open</span>`      : ""}
                ${recentBooking           ? `<span class="cs-mini-badge booking">${escapeHtml(recentBooking)}</span>`      : ""}
                <span class="cs-mini-badge lang">${langCode}</span>
            </div>
            ${latestPreview ? `<div class="cs-card-preview">${escapeHtml(latestPreview)}</div>` : ""}
        </div>
    </div>`;
}

function highlightSelectedCard() {
    document.querySelectorAll(".cs-customer-card").forEach(card => {
        card.classList.toggle("selected", card.dataset.phone === selectedCustomerPhone);
    });
}

/* =========================================================
   CALL SUPPORT — SELECT CUSTOMER → LOAD CONVERSATION
   ========================================================= */
window.selectCustomer = function(phone) {
    // Bug Fix #7: Clear stale state before loading new customer
    selectedCustomerPhone = phone;
    highlightSelectedCard();
    loadCustomerConversation(phone);
};

async function loadCustomerConversation(phone) {
    const customer = groupedCustomers[phone];
    if (!customer) {
        console.error("[loadCustomerConversation] No customer found for phone:", phone);
        return;
    }

    // Bug Fix #7: Race-condition guard — if user clicks another customer before
    // this async load finishes, abandon this stale load.
    const token = Symbol();
    activeLoadToken = token;

    console.log("[loadCustomerConversation] Selected customer:", phone,
        "| Total calls:", customer.conversations.length,
        "| Name:", customer.name);

    // ── Show workspace, hide no-selection ──
    const noSel    = document.getElementById("cs-no-selection");
    const convView = document.getElementById("cs-conversation-view");
    if (noSel)    noSel.style.display = "none";
    if (convView) { convView.classList.add("active"); convView.style.display = "flex"; }

    // ── Populate Sticky Header immediately from enriched data ──
    populateConvHeader(customer);

    // ── Show skeleton in chat area while loading ──
    const chatScroll = document.getElementById("conv-chat-scroll");
    if (chatScroll) chatScroll.innerHTML = buildChatSkeleton(6);

    // ── Load INDIVIDUAL conversation details for each conv ──
    // BUG FIX #2: We fetch each conv detail separately to get per-call messages
    // and per-call recording_url. We do NOT rely on the admin aggregated view
    // because the backend returns ALL user messages merged under one conv_id
    // (when admin + user_id exists). Instead we fetch per-conv detail, which
    // returns messages for that specific conversation only (non-admin path for
    // guests, or if user_id is null). For admin+user_id convs, backend returns
    // all user messages merged — so we need to de-dup using conversation_id.
    const convIds = customer.conversations.map(c => c.id);
    console.log("[loadCustomerConversation] Fetching", convIds.length, "conversation details...");

    const details = await loadConvDetailsWithDedup(convIds, customer.conversations);

    // Abandon if another customer was selected while we were fetching
    if (activeLoadToken !== token) {
        console.log("[loadCustomerConversation] Stale load abandoned for phone:", phone);
        return;
    }

    console.log("[loadCustomerConversation] Loaded", details.length, "conversations with details");

    renderContinuousConversation(details, chatScroll, customer);
}

/* ─── Load per-conversation details with message de-duplication ──────────
   The backend GET /api/v1/conversations/{id} for ADMIN+user_id returns
   ALL messages for all conversations of that user merged into messages[].
   We need only the messages belonging to each specific conversation.
   Solution: filter messages by conversation_id to isolate per-call transcript.
   ───────────────────────────────────────────────────────────────────────── */
async function loadConvDetailsWithDedup(convIds, enrichedConvs) {
    const results = [];

    for (let i = 0; i < convIds.length; i++) {
        const convId      = convIds[i];
        const enrichedMeta = enrichedConvs[i]; // enriched metadata for this conv

        try {
            const res  = await getConversationDetail(convId);
            // API response shape: { success: true, message: "...", data: { ...ConversationDetailSchema, messages: [...], recording_url, ivr_state, rating, duration } }
            const data = res?.data;

            if (!data) {
                console.warn("[loadConvDetailsWithDedup] No data for conv:", convId);
                // Fallback: use enriched metadata with empty messages
                results.push({ ...enrichedMeta, messages: [], recording_url: null });
                continue;
            }

            console.log("[loadConvDetailsWithDedup] Conv", convId,
                "| Raw messages from API:", data.messages?.length || 0,
                "| recording_url:", data.recording_url || "null");

            // BUG FIX #2/#3: Filter messages by conversation_id to get only THIS call's messages
            // This handles the backend's admin behavior of merging all user messages.
            const allMsgs = data.messages || [];
            const filteredMsgs = allMsgs.filter(m =>
                !m.conversation_id || m.conversation_id === convId
            );

            console.log("[loadConvDetailsWithDedup] Conv", convId,
                "| Filtered messages:", filteredMsgs.length,
                "| recording_url:", data.recording_url || "null");

            results.push({
                // Use detail API fields (more complete than enriched)
                id:                convId,
                session_id:        data.session_id || enrichedMeta.session_id,
                user_id:           data.user_id    || enrichedMeta.user_id,
                // Exact field names from ConversationDetailSchema:
                started_at:        data.started_at  || enrichedMeta.started_at,
                ended_at:          data.ended_at,
                status:            data.status       || enrichedMeta.status,
                language:          data.language     || enrichedMeta.language,
                channel:           data.channel      || enrichedMeta.channel,
                resolution_status: data.resolution_status || enrichedMeta.resolution_status || "unresolved",
                // recording_url is returned by detail endpoint for ADMIN role
                recording_url:     data.recording_url || null,
                current_intent:    data.current_intent,
                last_tool:         data.last_tool,
                message_count:     data.message_count,
                summary:           data.summary,
                sentiment:         data.sentiment,
                // Extended fields added by the backend route:
                ivr_state:         data.ivr_state,
                rating:            data.rating,
                duration:          data.duration || enrichedMeta.duration || 0,
                // Enriched fields not in schema (from /admin/enriched):
                user_phone:        enrichedMeta.user_phone,
                user_name:         enrichedMeta.user_name,
                booking_code:      enrichedMeta.booking_code,
                // Messages: filtered to only this conversation
                messages:          filteredMsgs,
            });
        } catch (err) {
            console.error("[loadConvDetailsWithDedup] Failed to load conv", convId, ":", err.message);
            // On error: use enriched metadata with empty messages so conversation still renders
            results.push({
                ...enrichedMeta,
                messages:      [],
                recording_url: null,
                _loadError:    true,
            });
        }
    }

    return results;
}

/* ─── Populate sticky header from enriched customer data ──── */
function populateConvHeader(customer) {
    const phone         = customer.phone;
    const color         = avatarColor(phone);
    const ini           = initials(customer.name);
    // Bug Fix #5: Total calls = count of conversations for THIS phone only
    const totalCalls    = customer.conversations.length;
    // Bug Fix #4: Most recent booking = from most recently active conversation
    const recentBooking = getMostRecentBookingCode(customer);
    const langCode      = (customer.language || "en").toUpperCase().substring(0, 2);

    const hdrAvatar = document.getElementById("conv-hdr-avatar");
    const hdrName   = document.getElementById("conv-hdr-name");
    const hdrPhone  = document.getElementById("conv-hdr-phone");
    const hdrBadges = document.getElementById("conv-hdr-badges");
    const metaGrid  = document.getElementById("conv-meta-grid");

    if (hdrAvatar) { hdrAvatar.style.background = color; hdrAvatar.textContent = ini; }
    if (hdrName)   hdrName.textContent  = customer.name;
    if (hdrPhone)  hdrPhone.textContent = phone;

    if (hdrBadges) {
        hdrBadges.innerHTML = `
            ${customer.resolvedCount > 0 ? `<span class="badge-status-sm badge-resolved">✓ ${customer.resolvedCount} Resolved</span>` : ""}
            ${customer.openCount > 0     ? `<span class="badge-status-sm badge-pending">✕ ${customer.openCount} Open</span>`         : ""}
            ${recentBooking ? `<span class="badge-status-sm badge-active" style="font-family:var(--font-mono);">${escapeHtml(recentBooking)}</span>` : ""}
            <span class="badge-status-sm badge-active">${langCode}</span>
            <span class="badge-status-sm" style="background:#e2e8f0;color:var(--text-secondary);">${totalCalls} Call${totalCalls !== 1 ? "s" : ""}</span>
        `;
    }

    if (metaGrid) {
        const lastAct    = customer.lastActivity ? new Date(customer.lastActivity).toLocaleString() : "—";
        const totalDurSec = customer.conversations.reduce((a, c) => a + (c.duration || 0), 0);
        const totalDurFmt = totalDurSec > 0
            ? `${Math.floor(totalDurSec / 60)}m ${totalDurSec % 60}s`
            : "—";

        metaGrid.innerHTML = `
            <div class="conv-meta-item">
                <span class="conv-meta-label">Last Activity</span>
                <span class="conv-meta-value">${escapeHtml(lastAct)}</span>
            </div>
            <div class="conv-meta-item">
                <span class="conv-meta-label">Total Calls</span>
                <span class="conv-meta-value">${totalCalls}</span>
            </div>
            <div class="conv-meta-item">
                <span class="conv-meta-label">Total Talk Time</span>
                <span class="conv-meta-value">${totalDurFmt}</span>
            </div>
            <div class="conv-meta-item">
                <span class="conv-meta-label">Language</span>
                <span class="conv-meta-value">${escapeHtml((customer.language || "en").toUpperCase())}</span>
            </div>
            ${recentBooking ? `
            <div class="conv-meta-item">
                <span class="conv-meta-label">Booking Ref</span>
                <span class="conv-meta-value mono">${escapeHtml(recentBooking)}</span>
            </div>` : ""}
        `;
    }
}

/* =========================================================
   RENDER CONTINUOUS CONVERSATION (ChatGPT / WhatsApp style)
   ========================================================= */
function renderContinuousConversation(convDataArray, chatScroll, customer) {
    if (!chatScroll) return;

    if (!convDataArray || convDataArray.length === 0) {
        chatScroll.innerHTML = `
        <div class="cs-empty" style="flex:1;">
            <i class="fa-solid fa-comment-slash"></i>
            <p>No conversation history found for this customer.</p>
        </div>`;
        return;
    }

    // Sort conversations oldest → newest for chronological chat display
    const sorted = [...convDataArray].sort((a, b) =>
        new Date(a.started_at || a.created_at || 0) -
        new Date(b.started_at || b.created_at || 0)
    );

    let html = "";

    sorted.forEach((conv, idx) => {
        // Messages are already filtered to this conversation only
        const messages = conv.messages || [];

        // ─── Call Divider ────────────────────────────────────
        const callDate = conv.started_at
            ? new Date(conv.started_at).toLocaleDateString("en-IN", { day: "2-digit", month: "short", year: "numeric" })
            : `Call ${idx + 1}`;
        const callTime = conv.started_at
            ? new Date(conv.started_at).toLocaleTimeString("en-IN", { hour: "2-digit", minute: "2-digit" })
            : "";
        // Exact field: resolution_status
        const resStatus = conv.resolution_status || "unresolved";
        const resClass  = resStatus === "resolved" ? "badge-resolved" : (resStatus === "escalated" ? "badge-escalated" : "badge-pending");
        // Exact field: duration (in seconds)
        const durSec    = conv.duration || 0;
        const durFmt    = `${Math.floor(durSec / 60)}m ${durSec % 60}s`;

        html += `
        <div class="call-divider" data-conv-id="${escapeAttr(conv.id || "")}">
            <div class="call-divider-line"></div>
            <div class="call-divider-label">
                <i class="fa-solid fa-phone"></i>
                <span class="call-divider-text">Call ${idx + 1}</span>
                <span class="call-divider-date">${escapeHtml(callDate)} ${escapeHtml(callTime)} · ${durFmt}</span>
                <span class="badge-status-sm ${resClass}" style="margin-left:4px;">${resStatus.toUpperCase()}</span>
            </div>
            <div class="call-divider-line"></div>
        </div>`;

        // ─── Per-call Audio Player ───────────────────────────
        // Bug Fix #3: recording_url comes from the DETAIL endpoint for each conv.
        // Each conv object here already has the correct recording_url from its own detail fetch.
        html += buildRecordingPlayer(conv, idx);

        // ─── Messages (filtered to this call only) ───────────
        if (conv._loadError) {
            html += `<div class="cs-empty" style="padding:16px;"><i class="fa-solid fa-triangle-exclamation" style="color:var(--amber-warning);"></i><p>Failed to load transcript for this call. Please refresh.</p></div>`;
        } else if (messages.length === 0) {
            html += `<div class="cs-empty" style="padding:16px 0;"><i class="fa-solid fa-comment-slash"></i><p>No transcript available for this call.</p></div>`;
        } else {
            // Sort messages by created_at to ensure correct order
            const sortedMsgs = [...messages].sort((a, b) =>
                new Date(a.created_at || 0) - new Date(b.created_at || 0)
            );
            sortedMsgs.forEach(msg => { html += buildChatMessage(msg); });
        }
    });

    chatScroll.innerHTML = html;

    // Bug Fix #3: Set up audio players after DOM is updated
    sorted.forEach((conv, idx) => {
        const playerId = `crp-${conv.id || idx}`;
        if (conv.recording_url) {
            console.log("[audio] Setting up player for conv", conv.id, "url:", conv.recording_url);
            setupRecordingPlayer(playerId, conv.recording_url);
        }
    });

    // Auto-scroll to bottom (most recent message)
    requestAnimationFrame(() => {
        chatScroll.scrollTop = chatScroll.scrollHeight;
    });

    // Re-apply any active search highlight
    if (convSearchQuery) applyConvSearch(convSearchQuery);
}

/* ─── Audio Recording Player HTML ────────────────────────── */
function buildRecordingPlayer(conv, idx) {
    const playerId = `crp-${conv.id || idx}`;

    // Bug Fix #3: Only show "No recording" if recording_url is truly null/undefined/empty
    if (!conv.recording_url) {
        return `
        <div class="chat-recording-player no-recording">
            <i class="fa-regular fa-circle-xmark"></i>
            <span>No recording available for this call.</span>
        </div>`;
    }

    return `
    <div class="chat-recording-player" id="player-wrap-${escapeAttr(playerId)}">
        <button class="crp-play-btn" id="${escapeAttr(playerId)}-btn" title="Play/Pause">
            <i class="fa-solid fa-play"></i>
        </button>
        <div class="crp-info">
            <div class="crp-title"><i class="fa-solid fa-microphone" style="margin-right:5px;color:var(--blue-primary);"></i>Call Recording</div>
            <input type="range" class="crp-seekbar" id="${escapeAttr(playerId)}-seek" value="0" min="0" max="100" step="0.1">
            <div class="crp-times">
                <span id="${escapeAttr(playerId)}-cur">0:00</span>
                <span id="${escapeAttr(playerId)}-tot">0:00</span>
            </div>
        </div>
        <button class="crp-speed" id="${escapeAttr(playerId)}-speed" title="Playback Speed">1×</button>
        <div class="crp-vol">
            <i class="fa-solid fa-volume-high" id="${escapeAttr(playerId)}-vol-icon" title="Mute/Unmute"></i>
        </div>
        <audio id="${escapeAttr(playerId)}-audio" style="display:none;" preload="metadata"
               src="${escapeAttr(conv.recording_url)}"></audio>
    </div>`;
}

function setupRecordingPlayer(playerId, url) {
    const audioEl  = document.getElementById(`${playerId}-audio`);
    const playBtn  = document.getElementById(`${playerId}-btn`);
    const seekbar  = document.getElementById(`${playerId}-seek`);
    const curEl    = document.getElementById(`${playerId}-cur`);
    const totEl    = document.getElementById(`${playerId}-tot`);
    const speedBtn = document.getElementById(`${playerId}-speed`);
    const volIcon  = document.getElementById(`${playerId}-vol-icon`);

    if (!audioEl || !playBtn) {
        console.warn("[setupRecordingPlayer] Missing DOM elements for player:", playerId);
        return;
    }

    const SPEEDS = [1, 1.25, 1.5, 2, 0.75];
    let speedIdx  = 0;

    playBtn.onclick = () => {
        if (audioEl.paused) {
            // Pause all other players first
            document.querySelectorAll("audio").forEach(a => { if (a !== audioEl) a.pause(); });
            document.querySelectorAll(".crp-play-btn").forEach(b => { if (b !== playBtn) b.innerHTML = `<i class="fa-solid fa-play"></i>`; });
            audioEl.play().catch(err => console.error("[audio] Play error:", err));
            playBtn.innerHTML = `<i class="fa-solid fa-pause"></i>`;
        } else {
            audioEl.pause();
            playBtn.innerHTML = `<i class="fa-solid fa-play"></i>`;
        }
    };

    audioEl.addEventListener("ended", () => {
        playBtn.innerHTML = `<i class="fa-solid fa-play"></i>`;
        if (seekbar) seekbar.value = 0;
    });

    audioEl.addEventListener("timeupdate", () => {
        if (!isNaN(audioEl.duration)) {
            if (seekbar) seekbar.value = (audioEl.currentTime / audioEl.duration) * 100;
            if (curEl)   curEl.textContent = fmtTime(audioEl.currentTime);
            if (totEl)   totEl.textContent = fmtTime(audioEl.duration);
        }
    });

    audioEl.addEventListener("loadedmetadata", () => {
        if (totEl && !isNaN(audioEl.duration)) totEl.textContent = fmtTime(audioEl.duration);
    });

    if (seekbar) {
        seekbar.oninput = () => {
            if (!isNaN(audioEl.duration)) {
                audioEl.currentTime = (seekbar.value / 100) * audioEl.duration;
            }
        };
    }

    if (speedBtn) {
        speedBtn.onclick = () => {
            speedIdx = (speedIdx + 1) % SPEEDS.length;
            audioEl.playbackRate = SPEEDS[speedIdx];
            speedBtn.textContent = `${SPEEDS[speedIdx]}×`;
        };
    }

    if (volIcon) {
        volIcon.onclick = () => {
            audioEl.muted = !audioEl.muted;
            volIcon.className = audioEl.muted ? "fa-solid fa-volume-xmark" : "fa-solid fa-volume-high";
        };
    }
}

function fmtTime(sec) {
    if (isNaN(sec) || sec < 0) return "0:00";
    const m = Math.floor(sec / 60);
    const s = Math.floor(sec % 60);
    return `${m}:${s < 10 ? "0" : ""}${s}`;
}

/* ─── Build individual chat message bubble ────────────────── */
function buildChatMessage(msg) {
    // Exact field names from ConversationMessageSchema:
    // id, conversation_id, sender, message_type, message, translated_message,
    // intent, confidence, entities, tool_used, response_time_ms, audio_path,
    // booking_code, created_at
    const isCustomer = msg.sender === "USER";
    const side  = isCustomer ? "customer" : "ai";
    const color = isCustomer ? "#64748b" : "#2563eb";
    const avi   = isCustomer ? "👤" : "⚡";

    const timeStr = msg.created_at
        ? new Date(msg.created_at).toLocaleTimeString("en-IN", { hour: "2-digit", minute: "2-digit" })
        : "";

    const msgText = msg.message || "";

    let badges = "";
    if (timeStr)       badges += `<span class="bubble-time">${timeStr}</span>`;
    if (msg.intent)    badges += `<span class="bubble-badge intent">${escapeHtml(msg.intent)}</span>`;
    if (msg.tool_used) badges += `<span class="bubble-badge tool"><i class="fa-solid fa-wrench" style="font-size:8px;"></i> ${escapeHtml(msg.tool_used)}</span>`;

    return `
    <div class="chat-msg-group ${side}" data-msg-id="${escapeAttr(String(msg.id || ""))}">
        <div class="chat-bubble-wrap">
            <div class="chat-avatar" style="background:${color};">${avi}</div>
            <div class="chat-bubble" data-text="${escapeAttr(msgText)}">
                <div class="bubble-text">${escapeHtml(msgText)}</div>
                ${badges ? `<div class="bubble-footer">${badges}</div>` : ""}
            </div>
        </div>
    </div>`;
}

/* ─── Chat skeleton loader ────────────────────────────────── */
function buildChatSkeleton(count = 5) {
    let html = "";
    for (let i = 0; i < count; i++) {
        const side = i % 2 === 0 ? "flex-start" : "flex-end";
        html += `
        <div class="skel-msg" style="justify-content:${side};">
            <div class="skel-msg-avatar"></div>
            <div class="skel-msg-bubble" style="max-width:55%;">
                <div class="skel-line" style="width:${60 + (i * 7) % 35}%;"></div>
                ${i % 3 === 0 ? `<div class="skel-line" style="width:${40 + (i * 11) % 40}%;"></div>` : ""}
            </div>
        </div>`;
    }
    return html;
}

/* =========================================================
   CONVERSATION SEARCH (inside right panel)
   ========================================================= */
function initConversationSearch() {
    const searchInput = document.getElementById("conv-search-input");
    const clearBtn    = document.getElementById("conv-search-clear");

    if (searchInput) {
        searchInput.addEventListener("input", e => {
            convSearchQuery = e.target.value.trim();
            applyConvSearch(convSearchQuery);
        });
    }

    if (clearBtn) {
        clearBtn.addEventListener("click", () => {
            convSearchQuery = "";
            if (searchInput) searchInput.value = "";
            applyConvSearch("");
        });
    }
}

function applyConvSearch(query) {
    const chatScroll = document.getElementById("conv-chat-scroll");
    if (!chatScroll) return;

    // Remove existing highlights
    chatScroll.querySelectorAll("mark.search-hl").forEach(m => {
        m.outerHTML = m.textContent;
    });
    chatScroll.querySelectorAll(".chat-bubble.highlighted").forEach(b => {
        b.classList.remove("highlighted");
    });

    if (!query) return;

    const q = query.toLowerCase();
    let firstMatch = null;

    chatScroll.querySelectorAll(".chat-bubble").forEach(bubble => {
        const textDiv = bubble.querySelector(".bubble-text");
        if (!textDiv) return;

        const text = textDiv.textContent || "";
        if (text.toLowerCase().includes(q)) {
            bubble.classList.add("highlighted");
            textDiv.innerHTML = escapeHtml(text).replace(
                new RegExp(escapeRegex(escapeHtml(query)), "gi"),
                m => `<mark class="search-hl">${m}</mark>`
            );
            if (!firstMatch) firstMatch = bubble;
        }
    });

    if (firstMatch) {
        firstMatch.scrollIntoView({ behavior: "smooth", block: "center" });
    }
}

function escapeRegex(str) {
    return str.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

/* =========================================================
   SCROLL-TO-BOTTOM BUTTON
   ========================================================= */
function initScrollToBottom() {
    const chatScroll = document.getElementById("conv-chat-scroll");
    const scrollBtn  = document.getElementById("scroll-bottom-btn");

    if (chatScroll && scrollBtn) {
        chatScroll.addEventListener("scroll", () => {
            const distFromBottom = chatScroll.scrollHeight - chatScroll.scrollTop - chatScroll.clientHeight;
            scrollBtn.classList.toggle("visible", distFromBottom > 200);
        });

        scrollBtn.addEventListener("click", () => {
            chatScroll.scrollTo({ top: chatScroll.scrollHeight, behavior: "smooth" });
        });
    }
}

/* =========================================================
   CUSTOMER FEEDBACK TAB
   ========================================================= */
function renderFeedbackTab() {
    const setEl = (id, v) => { const el = document.getElementById(id); if (el) el.textContent = v; };

    const total = allReviews.length;
    if (total === 0) {
        setEl("fb-avg-rating",       "No Data Available");
        setEl("fb-total-reviews",    "0");
        setEl("fb-csat-score",       "N/A");
        setEl("fb-resolution-ratio", "N/A");
        setEl("fb-sentiment-split",  "N/A");
    } else {
        const avg    = (allReviews.reduce((a, r) => a + r.rating, 0) / total).toFixed(1);
        const pos    = allReviews.filter(r => r.rating >= 7).length;
        const csat   = ((pos / total) * 100).toFixed(0);
        const res    = allReviews.filter(r => r.resolution_status === "resolved").length;
        const resPct = ((res / total) * 100).toFixed(0);
        setEl("fb-avg-rating",       `${avg} / 10`);
        setEl("fb-total-reviews",    total);
        setEl("fb-csat-score",       `${csat}%`);
        setEl("fb-resolution-ratio", `${resPct}%`);
        setEl("fb-sentiment-split",  `${csat}% Pos / ${100 - Number(csat)}% Neg`);
    }

    const distContainer = document.getElementById("rating-distribution-bars");
    if (distContainer) {
        const ratings = [];
        allReviews.forEach(r => { if (r.rating >= 1 && r.rating <= 10) ratings.push(r.rating); });
        allEnrichedConvs.forEach(c => { if (c.rating >= 1 && c.rating <= 10) ratings.push(c.rating); });
        const totalR = ratings.length;
        const counts = new Array(11).fill(0);
        ratings.forEach(s => { if (s >= 1 && s <= 10) counts[s]++; });
        const maxC = Math.max(...counts, 1);

        let barsHtml = "";
        for (let star = 10; star >= 1; star--) {
            const count  = counts[star];
            const pct    = totalR > 0 ? Math.round((count / totalR) * 100) : 0;
            const barPct = Math.round((count / maxC) * 100);
            barsHtml += `
            <div class="dist-bar-row">
                <div class="dist-label">${star} ★</div>
                <div class="dist-bar-track"><div class="dist-bar-fill" style="width:${barPct}%;"></div></div>
                <div class="dist-value">${count} (${pct}%)</div>
            </div>`;
        }
        distContainer.innerHTML = barsHtml;
    }

    const tbody = document.getElementById("reviews-table-body");
    if (!tbody) return;

    if (allReviews.length === 0) {
        tbody.innerHTML = `<tr><td colspan="7" class="empty-state-box"><i class="fa-solid fa-inbox"></i><p>No customer reviews logged in PostgreSQL.</p></td></tr>`;
        return;
    }

    tbody.innerHTML = allReviews.map(r => {
        // Exact fields from /admin/reviews endpoint:
        // id, conversation_id, rating, created_at, user_name, user_phone, resolution_status
        const name      = r.user_name  || "Guest Customer";
        const phone     = r.user_phone || "Unknown";
        const dateStr   = r.created_at ? new Date(r.created_at).toLocaleDateString() : "Recent";
        const statusClass = r.resolution_status === "resolved" ? "badge-resolved" : "badge-pending";
        return `
        <tr>
            <td style="font-weight:600;">${escapeHtml(name)}</td>
            <td style="font-family:var(--font-mono);">${escapeHtml(phone)}</td>
            <td>N/A</td>
            <td><span class="badge-status-sm" style="background:#fef3c7;color:#b45309;">${r.rating} ★</span></td>
            <td>${dateStr}</td>
            <td><span class="badge-status-sm ${statusClass}">${(r.resolution_status || "unresolved").toUpperCase()}</span></td>
            <td>
                <button class="btn-view-conv" style="padding:4px 8px;" onclick="openConversationInCallSupport('${escapeAttr(phone)}')">
                    Open Call
                </button>
            </td>
        </tr>`;
    }).join("");
}

/* =========================================================
   BOOKINGS TAB
   ========================================================= */
function renderBookingsTab() {
    const tbody = document.getElementById("bookings-table-body");
    if (!tbody) return;

    if (allBookings.length === 0) {
        tbody.innerHTML = `<tr><td colspan="8" class="empty-state-box"><i class="fa-solid fa-ticket-simple"></i><p>No verified travel bookings found in database.</p></td></tr>`;
        return;
    }

    tbody.innerHTML = allBookings.map(b => {
        // Exact fields from /analytics/bookings:
        // booking_code, source, destination, seat_number, departure_time, arrival_time,
        // payment_status, booking_status
        const pClass = b.payment_status === "PAID" ? "badge-resolved" : "badge-pending";
        const bClass = b.booking_status === "CONFIRMED" ? "badge-resolved" : (b.booking_status === "CANCELLED" ? "badge-escalated" : "badge-pending");
        return `
        <tr>
            <td style="font-family:var(--font-mono);font-weight:700;">${escapeHtml(b.booking_code || "")}</td>
            <td><i class="fa-solid fa-location-dot" style="color:var(--blue-primary);"></i> ${escapeHtml(b.source || "—")}</td>
            <td><i class="fa-solid fa-location-arrow" style="color:var(--green-text);"></i> ${escapeHtml(b.destination || "—")}</td>
            <td style="font-family:var(--font-mono);">${escapeHtml(b.seat_number || "—")}</td>
            <td>${escapeHtml(b.departure_time || "—")}</td>
            <td>${escapeHtml(b.arrival_time || "—")}</td>
            <td><span class="badge-status-sm ${pClass}">${escapeHtml(b.payment_status || "—")}</span></td>
            <td><span class="badge-status-sm ${bClass}">${escapeHtml(b.booking_status || "—")}</span></td>
        </tr>`;
    }).join("");
}

/* =========================================================
   GLOBAL SEARCH (header search bar)
   ========================================================= */
function initGlobalSearch() {
    const searchInput = document.getElementById("global-search");
    if (!searchInput) return;

    searchInput.addEventListener("input", e => {
        const query = e.target.value.trim();
        if (!query) return;

        switchToTab("call-support");

        const csSearch = document.getElementById("cs-search-input");
        if (csSearch) {
            csSearch.value = query;
            renderCustomerList(query);
        }
    });
}

/* =========================================================
   WEBSOCKET REALTIME SYNC
   ========================================================= */
function initWebSocket() {
    const baseUrl = getBaseUrl();
    let wsUrl;
    if      (baseUrl.startsWith("https://")) wsUrl = baseUrl.replace("https://", "wss://") + "/ws/admin";
    else if (baseUrl.startsWith("http://"))  wsUrl = baseUrl.replace("http://",  "ws://")  + "/ws/admin";
    else {
        const loc = window.location;
        wsUrl = `${loc.protocol === "https:" ? "wss:" : "ws:"}//${loc.host}/ws/admin`;
    }

    try {
        const socket = new WebSocket(wsUrl);

        socket.onopen = () => console.log("[WS] Admin WebSocket connected.");
        socket.onclose = () => {
            console.log("[WS] Admin WebSocket disconnected. Reconnecting in 4s...");
            setTimeout(initWebSocket, 4000);
        };
        socket.onerror = (e) => console.warn("[WS] Admin WebSocket error:", e);

        socket.onmessage = async (event) => {
            let parsed = null;
            try { parsed = JSON.parse(event.data); } catch (_) {}
            console.log("[WS] Realtime event:", parsed?.event || "unknown");

            // Re-fetch data on any realtime event
            await loadAllData();

            // Refresh the currently open customer's conversation
            if (selectedCustomerPhone && groupedCustomers[selectedCustomerPhone]) {
                await loadCustomerConversation(selectedCustomerPhone);
            }
        };
    } catch (e) {
        console.error("[WS] WebSocket connection failed:", e);
    }
}

/* =========================================================
   UTILITY FUNCTIONS
   ========================================================= */
function escapeHtml(str) {
    return String(str || "")
        .replace(/&/g,  "&amp;")
        .replace(/</g,  "&lt;")
        .replace(/>/g,  "&gt;")
        .replace(/"/g,  "&quot;")
        .replace(/'/g,  "&#039;");
}

function escapeAttr(str) {
    return String(str || "").replace(/'/g, "\\'").replace(/"/g, "&quot;");
}

function formatRelativeTime(date) {
    if (!date) return "";
    const now  = Date.now();
    const diff = now - date.getTime();
    if (diff < 60_000)     return "Just now";
    if (diff < 3_600_000)  return `${Math.floor(diff / 60_000)}m ago`;
    if (diff < 86_400_000) return `${Math.floor(diff / 3_600_000)}h ago`;
    if (diff < 604_800_000)return `${Math.floor(diff / 86_400_000)}d ago`;
    return date.toLocaleDateString("en-IN", { day: "2-digit", month: "short" });
}
