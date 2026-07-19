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
let adminProfile     = null;
let allEnrichedConvs = [];
let allReviews       = [];
let allBookings      = [];
let groupedCustomers = {};

let selectedCustomerPhone = null;
let activeLoadToken       = null;  // race-condition guard

let convSearchQuery = "";

// WebSocket throttling to prevent latency/API floods during active streams
let wsUpdateTimeout = null;
let wsPendingUpdate = false;
const WS_THROTTLE_MS = 2000; // minimum 2 seconds between UI/API syncs during live events

// Chart instances
let chartCallsTimelineInst   = null;
let chartResolutionRatioInst = null;
let chartLanguageDistInst    = null;
let chartRatingsTrendInst    = null;

const TWENTY_FOUR_HOURS_MS = 24 * 60 * 60 * 1000;

/* =========================================================
   LAZY LOADER STATE
   Kept as a plain object; reset on every customer switch.
   ========================================================= */
const MSGS_PER_CHUNK    = 50;   // messages shown per incremental reveal
const PREFETCH_AHEAD    = 2;    // number of older convs to silently prefetch

const lazy = {
    phone:          null,   // which phone this state belongs to
    convQueue:      [],     // enriched conv objects sorted newest→oldest, not yet fetched
    prefetchCache:  {},     // convId → full detail data (pre-fetched in background)
    loadedBlocks:   [],     // ordered oldest→newest; each block = { meta, detail, renderedMsgCount }
    allConvsLoaded: false,  // true when convQueue is empty and all fetched
    isLoadingOlder: false,  // prevent concurrent prepend loads
    topObserver:    null,   // IntersectionObserver watching top sentinel
    audioObserver:  null,   // IntersectionObserver watching audio players
};

function resetLazy() {
    if (lazy.topObserver)   { lazy.topObserver.disconnect();   lazy.topObserver   = null; }
    if (lazy.audioObserver) { lazy.audioObserver.disconnect(); lazy.audioObserver = null; }
    lazy.phone          = null;
    lazy.convQueue      = [];
    lazy.prefetchCache  = {};
    lazy.loadedBlocks   = [];
    lazy.allConvsLoaded = false;
    lazy.isLoadingOlder = false;
}

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
   DATA LOADING (enriched list + reviews + bookings)
   ========================================================= */
async function loadAllData() {
    try { await fetchConversations(); } catch (e) { console.error("[loadAllData]", e); }
    try { await fetchReviews();       } catch (e) { console.error("[loadAllData]", e); }
    try { await fetchBookings();      } catch (e) { console.error("[loadAllData]", e); }

    try { renderDashboard4Metrics(); } catch (e) { console.error(e); }
    try { renderDashboardCharts();   } catch (e) { console.error(e); }
    try { renderLiveCallsPanel24h(); } catch (e) { console.error(e); }
    try { renderCustomerList();      } catch (e) { console.error(e); }
    try { renderFeedbackTab();       } catch (e) { console.error(e); }
    try { renderBookingsTab();       } catch (e) { console.error(e); }
}

async function fetchConversations() {
    const res = await getAdminEnrichedConversations(200);
    allEnrichedConvs = res?.data?.conversations || [];
    groupCustomersByPhone();
}

async function fetchReviews() {
    const res = await getAdminReviews();
    allReviews = res?.data?.reviews || [];
}

async function fetchBookings() {
    const res = await getAnalyticsBookings();
    allBookings = res?.data || [];
}

function groupCustomersByPhone() {
    groupedCustomers = {};

    for (const conv of allEnrichedConvs) {
        const phone = conv.user_phone || "Unknown";

        if (!groupedCustomers[phone]) {
            groupedCustomers[phone] = {
                phone,
                name:          conv.user_name || "Guest Customer",
                conversations: [],
                lastActivity:  conv.updated_at || conv.started_at || null,
                resolvedCount: 0,
                openCount:     0,
                convBookings:  {},
                language:      conv.language || "en"
            };
        }

        const g = groupedCustomers[phone];
        g.conversations.push(conv);

        if (conv.resolution_status === "resolved") g.resolvedCount++;
        else g.openCount++;

        if (conv.booking_code) g.convBookings[conv.id] = conv.booking_code;
        if (conv.user_name && conv.user_name !== "Guest") g.name = conv.user_name;
        if (conv.language) g.language = conv.language;

        const convTime = new Date(conv.updated_at || conv.started_at || 0);
        if (!g.lastActivity || convTime > new Date(g.lastActivity)) {
            g.lastActivity = conv.updated_at || conv.started_at;
        }
    }

    for (const g of Object.values(groupedCustomers)) {
        g.conversations.sort((a, b) =>
            new Date(a.started_at || a.updated_at || 0) -
            new Date(b.started_at || b.updated_at || 0)
        );
    }
}

function getMostRecentBookingCode(customer) {
    for (let i = customer.conversations.length - 1; i >= 0; i--) {
        if (customer.conversations[i].booking_code) return customer.conversations[i].booking_code;
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
    const distinctAll       = new Set(allEnrichedConvs.map(c => c.user_phone).filter(p => p && p !== "Unknown"));
    const totalUsersCount   = distinctAll.size || Object.keys(groupedCustomers).length;

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
    setEl("stat-active-calls", distinctActive24h.size);
    setEl("stat-avg-duration", avgDurFmt);
    setEl("stat-total-users",  totalUsersCount);
    setEl("stat-ai-latency",   "1.2s");

    const badge = document.getElementById("live-calls-badge");
    if (badge) badge.textContent = distinctActive24h.size > 0 ? `${distinctActive24h.size} LIVE` : "LIVE";
}

/* =========================================================
   DASHBOARD — CHARTS
   ========================================================= */
function renderDashboardCharts() {
    if (typeof Chart === "undefined") return;

    const totalCalls = allEnrichedConvs.length;

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
                datasets: [{ label: "Calls Handled", data: Object.values(hoursMap), borderColor: "#2563eb", backgroundColor: "rgba(37,99,235,.06)", borderWidth: 2.5, fill: true, tension: .3, pointRadius: 4, pointBackgroundColor: "#2563eb" }]
            },
            options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { display: false } }, scales: { x: { grid: { display: false }, ticks: { font: { size: 11 } } }, y: { beginAtZero: true, ticks: { precision: 0, font: { size: 11 } } } } }
        });
    }

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
            data: { labels: ["Resolved", "Unresolved"], datasets: [{ data: [resolvedCount, unresolvedCount], backgroundColor: ["#16a34a","#dc2626"], borderWidth: 2, borderColor: "#fff" }] },
            options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { display: false } }, cutout: "65%" }
        });
    }

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
            options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { position: "right", labels: { font: { size: 10 }, boxWidth: 12 } }, tooltip: { callbacks: { label: ctx => { const v = ctx.raw||0; const t = ctx.dataset.data.reduce((a,b)=>a+b,0)||1; return `${ctx.label}: ${v} (${((v/t)*100).toFixed(1)}%)`; } } } } }
        });
    }

    const ctxRate = document.getElementById("chartRatingsTrend")?.getContext("2d");
    if (ctxRate) {
        if (chartRatingsTrendInst) chartRatingsTrendInst.destroy();
        const validRatings = [];
        allReviews.forEach(r => { if (r.rating >= 1 && r.rating <= 10) validRatings.push(r.rating); });
        allEnrichedConvs.forEach(c => { if (c.rating >= 1 && c.rating <= 10) validRatings.push(c.rating); });
        const total  = validRatings.length;
        const counts = new Array(10).fill(0);
        validRatings.forEach(s => { counts[s - 1]++; });
        const pcts = counts.map(c => total > 0 ? parseFloat(((c / total) * 100).toFixed(1)) : 0);
        chartRatingsTrendInst = new Chart(ctxRate, {
            type: "bar",
            data: { labels: ["1★","2★","3★","4★","5★","6★","7★","8★","9★","10★"], datasets: [{ label: "Customer %", data: pcts, backgroundColor: "#f59e0b", borderRadius: 4 }] },
            options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { display: false }, tooltip: { callbacks: { label: ctx => `${ctx.raw}% (${counts[ctx.dataIndex]} of ${total})` } } }, scales: { x: { grid: { display: false }, ticks: { font: { size: 10 } } }, y: { beginAtZero: true, ticks: { callback: v => v + "%" } } } }
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
        return d && (now - new Date(d).getTime()) <= TWENTY_FOUR_HOURS_MS;
    });

    const display = calls24h.length > 0 ? calls24h : allEnrichedConvs.slice(0, 10);

    if (display.length === 0) {
        container.innerHTML = `<div class="empty-state-box"><i class="fa-solid fa-phone-slash"></i><p>No call sessions recorded in PostgreSQL.</p></div>`;
        return;
    }

    container.innerHTML = display.map(c => {
        const phone  = c.user_phone   || "Unknown";
        const name   = c.user_name    || "Guest Customer";
        const bk     = c.booking_code || "Not Verified";
        const lang   = (c.language    || "EN").toUpperCase();
        const durSec = c.duration     || 0;
        const dur    = `${Math.floor(durSec / 60)}m ${durSec % 60}s`;

        let badgeClass = "badge-completed", statusLabel = "COMPLETED";
        if (c.status === "ACTIVE") { badgeClass = "badge-live"; statusLabel = "LIVE NOW"; }
        else if (c.resolution_status === "unresolved" || c.resolution_status === "escalated") { badgeClass = "badge-ongoing"; statusLabel = "ONGOING"; }

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
   CALL SUPPORT — LEFT PANEL
   ========================================================= */
function wireSearchInput() {
    const searchEl = document.getElementById("cs-search-input");
    if (searchEl) searchEl.addEventListener("input", e => renderCustomerList(e.target.value));
}

function renderCustomerList(filterQuery = "") {
    const container = document.getElementById("cs-customer-list");
    const skeletons  = document.getElementById("cs-skeleton-list");
    const countEl    = document.getElementById("cs-customer-count");
    if (!container) return;

    if (skeletons) skeletons.remove();

    let customers = Object.values(groupedCustomers);

    if (filterQuery.trim()) {
        const q = filterQuery.toLowerCase();
        customers = customers.filter(c =>
            c.name.toLowerCase().includes(q) ||
            c.phone.toLowerCase().includes(q) ||
            (c.language || "").toLowerCase().includes(q) ||
            Object.values(c.convBookings).some(bk => bk.toLowerCase().includes(q))
        );
    }

    customers.sort((a, b) => new Date(b.lastActivity || 0) - new Date(a.lastActivity || 0));
    if (countEl) countEl.textContent = customers.length;

    if (customers.length === 0) {
        container.innerHTML = `<div class="cs-empty"><i class="fa-solid fa-user-slash"></i><p>${filterQuery ? "No customers match your search." : "No unique customers available."}</p></div>`;
        return;
    }

    container.innerHTML = customers.map(cust => buildCustomerCard(cust)).join("");

    if (!selectedCustomerPhone && customers.length > 0) {
        selectCustomer(customers[0].phone);
    } else if (selectedCustomerPhone) {
        highlightSelectedCard();
    }
}

function buildCustomerCard(cust) {
    const isSelected    = cust.phone === selectedCustomerPhone;
    const color         = avatarColor(cust.phone);
    const totalCalls    = cust.conversations.length;
    const lastDate      = cust.lastActivity ? formatRelativeTime(new Date(cust.lastActivity)) : "";
    const recentBooking = getMostRecentBookingCode(cust);
    const langCode      = (cust.language || "en").toUpperCase().substring(0, 2);
    const isRecent      = (Date.now() - new Date(cust.lastActivity || 0).getTime()) < TWENTY_FOUR_HOURS_MS;
    const latestPreview = cust.conversations.at(-1)?.summary || "";

    return `
    <div class="cs-customer-card ${isSelected ? "selected" : ""}"
         data-phone="${escapeAttr(cust.phone)}"
         onclick="selectCustomer('${escapeAttr(cust.phone)}')">
        <div class="cs-card-avatar ${isRecent ? "status-recent" : ""}" style="background:${color};">${initials(cust.name)}</div>
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
    document.querySelectorAll(".cs-customer-card").forEach(card =>
        card.classList.toggle("selected", card.dataset.phone === selectedCustomerPhone)
    );
}

/* =========================================================
   SELECT CUSTOMER — ENTRY POINT
   ========================================================= */
window.selectCustomer = function(phone) {
    selectedCustomerPhone = phone;
    highlightSelectedCard();
    loadCustomerConversation(phone);
};

/* =========================================================
   LAZY CONVERSATION LOADER
   ─────────────────────────────────────────────────────────
   STRATEGY
   ─────────────────────────────────────────────────────────
   1. Reset all lazy state.
   2. Sort this customer's convs newest → oldest → convQueue.
   3. Fetch ONLY the latest conv (1 API call).
   4. Render latest MSGS_PER_CHUNK messages immediately.
   5. Install IntersectionObserver on a top-sentinel div.
   6. When sentinel enters viewport:
        a. If the latest conv has more messages → prepend older chunk.
        b. Else if convQueue not empty → fetch next older conv and prepend.
        c. Else → show "beginning of history" label.
   7. Background-prefetch next PREFETCH_AHEAD convs silently.
   8. Audio players use preload="none"; src set lazily via observer.
   ========================================================= */
async function loadCustomerConversation(phone) {
    const customer = groupedCustomers[phone];
    if (!customer) return;

    // Race-condition guard
    const token = Symbol();
    activeLoadToken = token;

    // ── Reset lazy state ──
    resetLazy();
    lazy.phone = phone;

    // ── Sort convs newest → oldest ──
    // customer.conversations is sorted oldest→newest; reverse for the queue
    lazy.convQueue = [...customer.conversations].reverse(); // index 0 = newest

    // ── Show workspace ──
    const noSel    = document.getElementById("cs-no-selection");
    const convView = document.getElementById("cs-conversation-view");
    if (noSel)    noSel.style.display = "none";
    if (convView) { convView.classList.add("active"); convView.style.display = "flex"; }

    // ── Populate header immediately (no API call needed) ──
    populateConvHeader(customer);

    // ── Show skeleton in chat while we fetch ──
    const chatScroll = document.getElementById("conv-chat-scroll");
    if (chatScroll) chatScroll.innerHTML = buildChatSkeleton(6);

    // ── Fetch latest conversation only ──
    const latestEnriched = lazy.convQueue.shift(); // pop newest
    if (!latestEnriched) {
        if (chatScroll) chatScroll.innerHTML = buildEmptyState("No conversations found.");
        return;
    }

    const latestDetail = await fetchConvDetail(latestEnriched);

    // Abandoned? (user clicked another customer)
    if (activeLoadToken !== token) return;

    // ── Render the latest conversation immediately ──
    if (chatScroll) chatScroll.innerHTML = ""; // clear skeletons

    appendConversationBlock(latestDetail, latestEnriched, chatScroll, "append");

    // ── Scroll to bottom (newest messages) ──
    requestAnimationFrame(() => { chatScroll.scrollTop = chatScroll.scrollHeight; });

    // ── Install IntersectionObserver on top sentinel ──
    installTopSentinel(chatScroll, customer, token);

    // ── Install lazy audio observer ──
    installAudioObserver(chatScroll);

    // ── Background prefetch next PREFETCH_AHEAD conversations ──
    prefetchOlderConvs(PREFETCH_AHEAD);
}

/* ─── Fetch a single conversation detail ──────────────────── */
async function fetchConvDetail(enrichedMeta) {
    // Check prefetch cache first
    if (lazy.prefetchCache[enrichedMeta.id]) {
        const cached = lazy.prefetchCache[enrichedMeta.id];
        delete lazy.prefetchCache[enrichedMeta.id]; // consume
        return cached;
    }

    try {
        const res  = await getConversationDetail(enrichedMeta.id);
        const data = res?.data;
        if (!data) return buildFallbackDetail(enrichedMeta);

        // Filter messages by conversation_id (backend merges all user messages for admin+user_id)
        const allMsgs      = data.messages || [];
        const filteredMsgs = allMsgs.filter(m =>
            !m.conversation_id || m.conversation_id === enrichedMeta.id
        );

        // Sort messages oldest → newest
        filteredMsgs.sort((a, b) => new Date(a.created_at || 0) - new Date(b.created_at || 0));

        return {
            id:                enrichedMeta.id,
            session_id:        data.session_id        || enrichedMeta.session_id,
            started_at:        data.started_at        || enrichedMeta.started_at,
            ended_at:          data.ended_at,
            status:            data.status            || enrichedMeta.status,
            language:          data.language          || enrichedMeta.language,
            resolution_status: data.resolution_status || enrichedMeta.resolution_status || "unresolved",
            recording_url:     data.recording_url     || null, // only returned for ADMIN
            duration:          data.duration          || enrichedMeta.duration || 0,
            ivr_state:         data.ivr_state,
            rating:            data.rating,
            summary:           data.summary,
            // Per-conversation enriched fields
            user_phone:        enrichedMeta.user_phone,
            user_name:         enrichedMeta.user_name,
            booking_code:      enrichedMeta.booking_code,
            // All messages for this conversation, sorted oldest→newest
            messages:          filteredMsgs,
        };
    } catch (err) {
        console.error("[fetchConvDetail] Failed:", enrichedMeta.id, err.message);
        return buildFallbackDetail(enrichedMeta);
    }
}

function buildFallbackDetail(enrichedMeta) {
    return { ...enrichedMeta, messages: [], recording_url: null, _loadError: true };
}

/* ─── Background prefetch ─────────────────────────────────── */
async function prefetchOlderConvs(count) {
    // Peek at next `count` items in the queue without removing them
    const toPrefetch = lazy.convQueue.slice(0, count);
    for (const meta of toPrefetch) {
        if (lazy.prefetchCache[meta.id]) continue; // already cached
        // Fire-and-forget; errors are silently ignored
        fetchConvDetail(meta).then(detail => {
            lazy.prefetchCache[meta.id] = detail;
        }).catch(() => {});
    }
}

/* =========================================================
   INCREMENTAL RENDERING — APPEND / PREPEND CONVERSATION BLOCK
   ─────────────────────────────────────────────────────────
   Each conversation is rendered as a "block" containing:
    - call-divider header
    - audio player
    - message chunk (last MSGS_PER_CHUNK messages initially)
   ========================================================= */
function appendConversationBlock(detail, enrichedMeta, chatScroll, direction) {
    // Track state for this block so we can reveal older message chunks
    const block = {
        meta:            enrichedMeta,
        detail:          detail,
        allMsgs:         detail.messages || [],        // all messages oldest→newest
        renderedUpTo:    0,                             // index into allMsgs we've rendered so far
    };

    // Determine which slice to render initially: last MSGS_PER_CHUNK messages
    const totalMsgs    = block.allMsgs.length;
    const startIdx     = Math.max(0, totalMsgs - MSGS_PER_CHUNK);
    block.renderedUpTo = startIdx; // msgs before this index are not yet rendered

    if (direction === "append") {
        lazy.loadedBlocks.push(block);
        const el = buildConvBlockElement(block, startIdx);
        chatScroll.appendChild(el);
    } else {
        // Prepending: preserve scroll position
        const prevScrollHeight = chatScroll.scrollHeight;
        const prevScrollTop    = chatScroll.scrollTop;

        lazy.loadedBlocks.unshift(block);
        const el = buildConvBlockElement(block, startIdx);
        
        // Find top sentinel and insert after it, to keep sentinel at the very top of scroll container
        const sentinel = chatScroll.querySelector(".lazy-top-sentinel");
        if (sentinel) {
            chatScroll.insertBefore(el, sentinel.nextSibling);
        } else {
            chatScroll.insertBefore(el, chatScroll.firstChild);
        }

        // Restore scroll position (prevent jump)
        requestAnimationFrame(() => {
            chatScroll.scrollTop = chatScroll.scrollHeight - prevScrollHeight + prevScrollTop;
        });
    }
}

/* ─── Build the DOM element for one conversation block ──────── */
function buildConvBlockElement(block, startIdx) {
    const detail      = block.detail;
    const totalMsgs   = block.allMsgs.length;
    const msgsToShow  = block.allMsgs.slice(startIdx);

    const wrapper = document.createElement("div");
    wrapper.className   = "conv-block";
    wrapper.dataset.convId = detail.id || "";

    // ── Call divider ──
    const callIdx   = lazy.loadedBlocks.indexOf(block); // position among all loaded blocks
    const callDate  = detail.started_at
        ? new Date(detail.started_at).toLocaleDateString("en-IN", { day: "2-digit", month: "short", year: "numeric" })
        : "Unknown Date";
    const callTime  = detail.started_at
        ? new Date(detail.started_at).toLocaleTimeString("en-IN", { hour: "2-digit", minute: "2-digit" })
        : "";
    const resStatus = detail.resolution_status || "unresolved";
    const resClass  = resStatus === "resolved" ? "badge-resolved" : (resStatus === "escalated" ? "badge-escalated" : "badge-pending");
    const durSec    = detail.duration || 0;
    const durFmt    = `${Math.floor(durSec / 60)}m ${durSec % 60}s`;

    let html = `
    <div class="call-divider">
        <div class="call-divider-line"></div>
        <div class="call-divider-label">
            <i class="fa-solid fa-phone"></i>
            <span class="call-divider-text">Call — ${escapeHtml(callDate)} ${escapeHtml(callTime)}</span>
            <span class="call-divider-date">· ${durFmt}</span>
            <span class="badge-status-sm ${resClass}" style="margin-left:4px;">${resStatus.toUpperCase()}</span>
        </div>
        <div class="call-divider-line"></div>
    </div>`;

    // ── "Older messages within this call" indicator (if we didn't show all) ──
    if (startIdx > 0) {
        html += `<div class="older-msgs-hint" data-block-conv-id="${escapeAttr(detail.id || "")}">
            <button class="load-older-msgs-btn" onclick="revealOlderMessages('${escapeAttr(detail.id || "")}')">
                <i class="fa-solid fa-chevron-up"></i>
                Show ${startIdx} older message${startIdx !== 1 ? "s" : ""} from this call
            </button>
        </div>`;
    }

    // ── Audio player (lazy: preload="none", src set by observer) ──
    html += buildRecordingPlayer(detail, detail.id || "");

    // ── Messages ──
    if (detail._loadError) {
        html += `<div class="cs-empty" style="padding:16px;"><i class="fa-solid fa-triangle-exclamation" style="color:var(--amber-warning);"></i><p>Failed to load transcript. Please refresh.</p></div>`;
    } else if (totalMsgs === 0) {
        html += `<div class="cs-empty" style="padding:12px 0;"><i class="fa-solid fa-comment-slash"></i><p>No transcript for this call.</p></div>`;
    } else {
        msgsToShow.forEach(msg => { html += buildChatMessage(msg); });
    }

    wrapper.innerHTML = html;

    // Setup audio player JS (now in DOM)
    if (detail.recording_url) {
        setupRecordingPlayer(`crp-${detail.id || ""}`, detail.recording_url);
    }

    return wrapper;
}

/* ─── Reveal older messages within the same call ─────────────
   Called when user clicks "Show N older messages from this call"
   ──────────────────────────────────────────────────────────── */
window.revealOlderMessages = function(convId) {
    const block = lazy.loadedBlocks.find(b => (b.detail.id || b.meta.id) === convId);
    if (!block) return;

    const chatScroll   = document.getElementById("conv-chat-scroll");
    const blockEl      = chatScroll?.querySelector(`[data-conv-id="${escapeAttr(convId)}"]`);
    if (!blockEl) return;

    const prevScrollHeight = chatScroll.scrollHeight;
    const prevScrollTop    = chatScroll.scrollTop;

    // Determine next slice to reveal
    const endIdx   = block.renderedUpTo;                          // currently rendered from here
    const startIdx = Math.max(0, endIdx - MSGS_PER_CHUNK);        // reveal this many more
    const newMsgs  = block.allMsgs.slice(startIdx, endIdx);
    block.renderedUpTo = startIdx;

    // Build and insert HTML before the existing messages in this block
    const hintEl = blockEl.querySelector(`[data-block-conv-id="${escapeAttr(convId)}"]`);

    let insertHtml = "";
    newMsgs.forEach(msg => { insertHtml += buildChatMessage(msg); });

    if (insertHtml) {
        const tempDiv = document.createElement("div");
        tempDiv.innerHTML = insertHtml;
        if (hintEl) {
            while (tempDiv.firstChild) blockEl.insertBefore(tempDiv.firstChild, hintEl);
        }
    }

    // Update or remove the hint button
    if (hintEl) {
        if (startIdx > 0) {
            hintEl.querySelector("button").textContent =
                `↑ Show ${startIdx} older message${startIdx !== 1 ? "s" : ""} from this call`;
            hintEl.querySelector("button").innerHTML = `<i class="fa-solid fa-chevron-up"></i> Show ${startIdx} older message${startIdx !== 1 ? "s" : ""} from this call`;
        } else {
            hintEl.remove(); // all messages in this call are now visible
        }
    }

    // Restore scroll position
    requestAnimationFrame(() => {
        chatScroll.scrollTop = chatScroll.scrollHeight - prevScrollHeight + prevScrollTop;
    });
};

/* =========================================================
   TOP SENTINEL — INFINITE SCROLL (REVERSE)
   ─────────────────────────────────────────────────────────
   A sentinel div is prepended at the very top of the chat.
   When it enters the viewport, load the next older conversation.
   ========================================================= */
function installTopSentinel(chatScroll, customer, token) {
    // Remove any existing sentinel
    chatScroll.querySelector(".lazy-top-sentinel")?.remove();

    // If nothing left to load, don't install
    if (lazy.convQueue.length === 0) {
        prependBeginningLabel(chatScroll);
        lazy.allConvsLoaded = true;
        return;
    }

    const sentinel = document.createElement("div");
    sentinel.className = "lazy-top-sentinel";
    sentinel.innerHTML = `
    <div class="lazy-loading-top" id="lazy-loading-indicator" style="display:none;">
        <div class="lazy-spinner"><i class="fa-solid fa-spinner fa-spin"></i></div>
        <span>Loading earlier calls…</span>
    </div>`;

    chatScroll.insertBefore(sentinel, chatScroll.firstChild);

    lazy.topObserver = new IntersectionObserver(
        (entries) => {
            if (entries[0].isIntersecting) {
                loadNextOlderConversation(chatScroll, customer, token);
            }
        },
        { root: chatScroll, threshold: 0, rootMargin: "100px 0px 0px 0px" }
    );
    lazy.topObserver.observe(sentinel);
}

async function loadNextOlderConversation(chatScroll, customer, token) {
    // Guard: prevent concurrent loads and stale loads
    if (lazy.isLoadingOlder) return;
    if (activeLoadToken !== token) return;
    if (lazy.convQueue.length === 0) {
        lazy.allConvsLoaded = true;
        removeSentinel(chatScroll);
        prependBeginningLabel(chatScroll);
        return;
    }

    lazy.isLoadingOlder = true;

    // Show inline loading indicator
    const indicator = document.getElementById("lazy-loading-indicator");
    if (indicator) indicator.style.display = "flex";

    const nextEnriched = lazy.convQueue.shift();
    const detail       = await fetchConvDetail(nextEnriched);

    // Check not abandoned
    if (activeLoadToken !== token) {
        lazy.isLoadingOlder = false;
        return;
    }

    // Hide loading indicator
    if (indicator) indicator.style.display = "none";

    // Prepend this conversation block
    appendConversationBlock(detail, nextEnriched, chatScroll, "prepend");

    // Install audio observer for new players
    installAudioObserver(chatScroll);

    lazy.isLoadingOlder = false;

    // If no more convs left, swap sentinel for "beginning" label
    if (lazy.convQueue.length === 0) {
        lazy.allConvsLoaded = true;
        removeSentinel(chatScroll);
        prependBeginningLabel(chatScroll);
        lazy.topObserver?.disconnect();
    } else {
        // Prefetch next batch in background
        prefetchOlderConvs(PREFETCH_AHEAD);
    }
}

function removeSentinel(chatScroll) {
    chatScroll.querySelector(".lazy-top-sentinel")?.remove();
}

function prependBeginningLabel(chatScroll) {
    chatScroll.querySelector(".conv-beginning-label")?.remove();
    const label = document.createElement("div");
    label.className = "conv-beginning-label";
    label.innerHTML = `<i class="fa-solid fa-flag-checkered"></i> Beginning of conversation history`;
    chatScroll.insertBefore(label, chatScroll.firstChild);
}

/* =========================================================
   LAZY AUDIO OBSERVER
   ─────────────────────────────────────────────────────────
   Audio elements have preload="none" and no src initially.
   When the player enters the viewport, the src is set and
   metadata is loaded. This avoids loading every recording.
   ========================================================= */
function installAudioObserver(chatScroll) {
    if (lazy.audioObserver) lazy.audioObserver.disconnect();

    lazy.audioObserver = new IntersectionObserver(
        (entries) => {
            entries.forEach(entry => {
                if (entry.isIntersecting) {
                    const playerWrap = entry.target;
                    const audioEl    = playerWrap.querySelector("audio[data-lazy-src]");
                    if (audioEl && !audioEl.src) {
                        audioEl.src = audioEl.dataset.lazySrc;
                        audioEl.preload = "metadata";
                        audioEl.load();
                    }
                    lazy.audioObserver.unobserve(playerWrap);
                }
            });
        },
        { root: chatScroll, threshold: 0.1, rootMargin: "200px 0px" }
    );

    chatScroll.querySelectorAll(".chat-recording-player[data-has-recording='true']").forEach(el => {
        lazy.audioObserver.observe(el);
    });
}

/* ─── Audio Player HTML — uses data-lazy-src for lazy loading ─ */
function buildRecordingPlayer(detail, idx) {
    const playerId = `crp-${idx}`;

    if (!detail.recording_url) {
        return `
        <div class="chat-recording-player no-recording">
            <i class="fa-regular fa-circle-xmark"></i>
            <span>No recording available for this call.</span>
        </div>`;
    }

    // Use data-lazy-src; actual src will be set by IntersectionObserver when visible
    return `
    <div class="chat-recording-player" id="player-wrap-${escapeAttr(playerId)}"
         data-has-recording="true">
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
        <!-- preload=none; src set lazily when player enters viewport -->
        <audio id="${escapeAttr(playerId)}-audio"
               data-lazy-src="${escapeAttr(detail.recording_url)}"
               preload="none"
               style="display:none;"></audio>
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

    if (!audioEl || !playBtn) return;

    const SPEEDS = [1, 1.25, 1.5, 2, 0.75];
    let speedIdx = 0;

    playBtn.onclick = () => {
        // If src not yet loaded (lazy), load it now on play click
        if (!audioEl.src && audioEl.dataset.lazySrc) {
            audioEl.src = audioEl.dataset.lazySrc;
            audioEl.preload = "auto";
            audioEl.load();
        }
        if (audioEl.paused) {
            document.querySelectorAll("audio").forEach(a => { if (a !== audioEl) a.pause(); });
            document.querySelectorAll(".crp-play-btn").forEach(b => { if (b !== playBtn) b.innerHTML = `<i class="fa-solid fa-play"></i>`; });
            audioEl.play().catch(err => console.error("[audio] play error:", err));
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
            if (!audioEl.src && audioEl.dataset.lazySrc) {
                audioEl.src = audioEl.dataset.lazySrc;
                audioEl.preload = "auto";
                audioEl.load();
            }
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
    return `${Math.floor(sec / 60)}:${String(Math.floor(sec % 60)).padStart(2, "0")}`;
}

/* ─── Build chat message bubble ───────────────────────────── */
function buildChatMessage(msg) {
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

/* ─── Skeleton loader ──────────────────────────────────────── */
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

function buildEmptyState(msg) {
    return `<div class="cs-empty" style="flex:1;"><i class="fa-solid fa-comment-slash"></i><p>${escapeHtml(msg)}</p></div>`;
}

/* =========================================================
   POPULATE STICKY HEADER
   ========================================================= */
function populateConvHeader(customer) {
    const phone         = customer.phone;
    const color         = avatarColor(phone);
    const totalCalls    = customer.conversations.length;
    const recentBooking = getMostRecentBookingCode(customer);
    const langCode      = (customer.language || "en").toUpperCase().substring(0, 2);

    const hdrAvatar = document.getElementById("conv-hdr-avatar");
    const hdrName   = document.getElementById("conv-hdr-name");
    const hdrPhone  = document.getElementById("conv-hdr-phone");
    const hdrBadges = document.getElementById("conv-hdr-badges");
    const metaGrid  = document.getElementById("conv-meta-grid");

    if (hdrAvatar) { hdrAvatar.style.background = color; hdrAvatar.textContent = initials(customer.name); }
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
        const lastAct     = customer.lastActivity ? new Date(customer.lastActivity).toLocaleString() : "—";
        const totalDurSec = customer.conversations.reduce((a, c) => a + (c.duration || 0), 0);
        const totalDurFmt = totalDurSec > 0 ? `${Math.floor(totalDurSec / 60)}m ${totalDurSec % 60}s` : "—";

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
   CONVERSATION SEARCH
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

    chatScroll.querySelectorAll("mark.search-hl").forEach(m => { m.outerHTML = m.textContent; });
    chatScroll.querySelectorAll(".chat-bubble.highlighted").forEach(b => b.classList.remove("highlighted"));

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

    if (firstMatch) firstMatch.scrollIntoView({ behavior: "smooth", block: "center" });
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
            const dist = chatScroll.scrollHeight - chatScroll.scrollTop - chatScroll.clientHeight;
            scrollBtn.classList.toggle("visible", dist > 200);
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
        setEl("fb-avg-rating", "No Data Available"); setEl("fb-total-reviews", "0");
        setEl("fb-csat-score", "N/A"); setEl("fb-resolution-ratio", "N/A"); setEl("fb-sentiment-split", "N/A");
    } else {
        const avg    = (allReviews.reduce((a, r) => a + r.rating, 0) / total).toFixed(1);
        const pos    = allReviews.filter(r => r.rating >= 7).length;
        const csat   = ((pos / total) * 100).toFixed(0);
        const res    = allReviews.filter(r => r.resolution_status === "resolved").length;
        const resPct = ((res / total) * 100).toFixed(0);
        setEl("fb-avg-rating", `${avg} / 10`); setEl("fb-total-reviews", total);
        setEl("fb-csat-score", `${csat}%`); setEl("fb-resolution-ratio", `${resPct}%`);
        setEl("fb-sentiment-split", `${csat}% Pos / ${100 - Number(csat)}% Neg`);
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
            const count = counts[star];
            barsHtml += `
            <div class="dist-bar-row">
                <div class="dist-label">${star} ★</div>
                <div class="dist-bar-track"><div class="dist-bar-fill" style="width:${Math.round((count/maxC)*100)}%;"></div></div>
                <div class="dist-value">${count} (${totalR > 0 ? Math.round((count/totalR)*100) : 0}%)</div>
            </div>`;
        }
        distContainer.innerHTML = barsHtml;
    }

    const tbody = document.getElementById("reviews-table-body");
    if (!tbody) return;
    if (allReviews.length === 0) {
        tbody.innerHTML = `<tr><td colspan="7" class="empty-state-box"><i class="fa-solid fa-inbox"></i><p>No customer reviews logged.</p></td></tr>`;
        return;
    }
    tbody.innerHTML = allReviews.map(r => {
        const statusClass = r.resolution_status === "resolved" ? "badge-resolved" : "badge-pending";
        return `
        <tr>
            <td style="font-weight:600;">${escapeHtml(r.user_name || "Guest Customer")}</td>
            <td style="font-family:var(--font-mono);">${escapeHtml(r.user_phone || "Unknown")}</td>
            <td>N/A</td>
            <td><span class="badge-status-sm" style="background:#fef3c7;color:#b45309;">${r.rating} ★</span></td>
            <td>${r.created_at ? new Date(r.created_at).toLocaleDateString() : "Recent"}</td>
            <td><span class="badge-status-sm ${statusClass}">${(r.resolution_status || "unresolved").toUpperCase()}</span></td>
            <td><button class="btn-view-conv" style="padding:4px 8px;" onclick="openConversationInCallSupport('${escapeAttr(r.user_phone || "")}')">Open Call</button></td>
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
        tbody.innerHTML = `<tr><td colspan="8" class="empty-state-box"><i class="fa-solid fa-ticket-simple"></i><p>No verified travel bookings found.</p></td></tr>`;
        return;
    }
    tbody.innerHTML = allBookings.map(b => {
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
   GLOBAL SEARCH
   ========================================================= */
function initGlobalSearch() {
    const searchInput = document.getElementById("global-search");
    if (!searchInput) return;
    searchInput.addEventListener("input", e => {
        const query = e.target.value.trim();
        if (!query) return;
        switchToTab("call-support");
        const csSearch = document.getElementById("cs-search-input");
        if (csSearch) { csSearch.value = query; renderCustomerList(query); }
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
    else { const loc = window.location; wsUrl = `${loc.protocol === "https:" ? "wss:" : "ws:"}//${loc.host}/ws/admin`; }

    try {
        const socket = new WebSocket(wsUrl);
        socket.onopen  = () => console.log("[WS] Admin WebSocket connected.");
        socket.onclose = () => setTimeout(initWebSocket, 4000);
        socket.onerror = (e) => console.warn("[WS] error:", e);

        socket.onmessage = () => {
            triggerWSUpdate();
        };
    } catch (e) {
        console.error("[WS] Connection failed:", e);
    }
}

/* ─── Throttled Update Trigger to prevent API flooding and browser lag during streams ─── */
function triggerWSUpdate() {
    if (wsUpdateTimeout) {
        wsPendingUpdate = true;
        return;
    }

    performWSUpdate();

    wsUpdateTimeout = setTimeout(() => {
        wsUpdateTimeout = null;
        if (wsPendingUpdate) {
            wsPendingUpdate = false;
            triggerWSUpdate();
        }
    }, WS_THROTTLE_MS);
}

async function performWSUpdate() {
    console.log("[WS] Performing throttled update...");
    try {
        await loadAllData();
        if (selectedCustomerPhone) {
            await refreshCustomerConversation(selectedCustomerPhone);
        }
    } catch (err) {
        console.error("[WS] throttled update failed:", err);
    }
}

/* ─── Quietly Refresh Conversation (append new messages without resetting lazy state/scroll) ─── */
async function refreshCustomerConversation(phone) {
    const customer = groupedCustomers[phone];
    if (!customer) return;

    if (selectedCustomerPhone !== phone) return;

    const newestEnriched = customer.conversations.at(-1); // sorted oldest -> newest
    if (!newestEnriched) return;

    const detail = await fetchConvDetail(newestEnriched);

    if (selectedCustomerPhone !== phone) return;

    const chatScroll = document.getElementById("conv-chat-scroll");
    if (!chatScroll) return;

    const newestBlockEl = chatScroll.querySelector(`[data-conv-id="${escapeAttr(newestEnriched.id)}"]`);
    if (newestBlockEl) {
        const blockState = lazy.loadedBlocks.find(b => (b.detail.id || b.meta.id) === newestEnriched.id);
        if (blockState) {
            blockState.detail = detail;
            blockState.allMsgs = detail.messages || [];

            const existingMsgGroupEls = newestBlockEl.querySelectorAll(".chat-msg-group");
            const existingMsgIds = new Set(Array.from(existingMsgGroupEls).map(el => el.dataset.msgId));

            const startIdx = blockState.renderedUpTo;
            const msgsToShow = blockState.allMsgs.slice(startIdx);

            let newHtml = "";
            let addedAny = false;
            msgsToShow.forEach(msg => {
                const msgIdStr = String(msg.id || "");
                if (!existingMsgIds.has(msgIdStr)) {
                    newHtml += buildChatMessage(msg);
                    addedAny = true;
                }
            });

            if (addedAny) {
                // Check if user is scrolled near the bottom (within 120px)
                const isNearBottom = (chatScroll.scrollHeight - chatScroll.scrollTop - chatScroll.clientHeight) < 120;

                const tempDiv = document.createElement("div");
                tempDiv.innerHTML = newHtml;
                while (tempDiv.firstChild) {
                    newestBlockEl.appendChild(tempDiv.firstChild);
                }

                if (isNearBottom) {
                    requestAnimationFrame(() => {
                        chatScroll.scrollTop = chatScroll.scrollHeight;
                    });
                }
            }

            // Update call header/divider metadata
            const labelEl = newestBlockEl.querySelector(".call-divider-label");
            if (labelEl) {
                const callDate = detail.started_at
                    ? new Date(detail.started_at).toLocaleDateString("en-IN", { day: "2-digit", month: "short", year: "numeric" })
                    : "Unknown Date";
                const callTime = detail.started_at
                    ? new Date(detail.started_at).toLocaleTimeString("en-IN", { hour: "2-digit", minute: "2-digit" })
                    : "";
                const resStatus = detail.resolution_status || "unresolved";
                const resClass  = resStatus === "resolved" ? "badge-resolved" : (resStatus === "escalated" ? "badge-escalated" : "badge-pending");
                const durSec    = detail.duration || 0;
                const durFmt    = `${Math.floor(durSec / 60)}m ${durSec % 60}s`;

                labelEl.innerHTML = `
                    <i class="fa-solid fa-phone"></i>
                    <span class="call-divider-text">Call — ${escapeHtml(callDate)} ${escapeHtml(callTime)}</span>
                    <span class="call-divider-date">· ${durFmt}</span>
                    <span class="badge-status-sm ${resClass}" style="margin-left:4px;">${resStatus.toUpperCase()}</span>
                `;
            }

            populateConvHeader(customer);
        }
    } else {
        // Entirely new call started
        appendConversationBlock(detail, newestEnriched, chatScroll, "append");
        installAudioObserver(chatScroll);
        requestAnimationFrame(() => {
            chatScroll.scrollTop = chatScroll.scrollHeight;
        });
    }
}

/* =========================================================
   UTILITY
   ========================================================= */
function escapeHtml(str) {
    return String(str || "").replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;").replace(/"/g,"&quot;").replace(/'/g,"&#039;");
}
function escapeAttr(str) {
    return String(str || "").replace(/'/g, "\\'").replace(/"/g, "&quot;");
}
function formatRelativeTime(date) {
    if (!date) return "";
    const diff = Date.now() - date.getTime();
    if (diff < 60_000)     return "Just now";
    if (diff < 3_600_000)  return `${Math.floor(diff / 60_000)}m ago`;
    if (diff < 86_400_000) return `${Math.floor(diff / 3_600_000)}h ago`;
    if (diff < 604_800_000)return `${Math.floor(diff / 86_400_000)}d ago`;
    return date.toLocaleDateString("en-IN", { day: "2-digit", month: "short" });
}
