let currentUser = null;
let currentPage = 1;
let totalPages = 1;
let chatHistoryPage = 1;
let chatHasMore = false;
let chatLoadingMore = false;
let polishAbortController = null;

const API_BASE = "";
const CHAT_PER_PAGE = 20;
const FONT_SIZE_KEY = "chatFontSize";
const FAVORITES_KEY = "favoriteRecords";
const MODE_KEY = "optimizeMode";
const FONT_SIZES = [14, 16, 18, 20, 24];

const MODE_LABELS = {
    general: "通用优化",
    writing: "写作优化",
    code: "编程场景",
    data: "数据分析",
};

function showToast(message, type = "info") {
    const container = document.getElementById("toast-container");
    if (!container) return;
    const toast = document.createElement("div");
    toast.className = `toast toast-${type}`;
    toast.textContent = message;
    container.appendChild(toast);
    requestAnimationFrame(() => toast.classList.add("show"));
    setTimeout(() => {
        toast.classList.remove("show");
        setTimeout(() => toast.remove(), 300);
    }, 2600);
}

function getFavorites() {
    return new Set(getFavoriteList().map((f) => String(f.id)));
}

function getFavoriteList() {
    try {
        const raw = JSON.parse(localStorage.getItem(FAVORITES_KEY) || "[]");
        if (!Array.isArray(raw)) return [];
        if (raw.length && typeof raw[0] === "string") {
            return raw.map((id) => ({ id: String(id), legacy: true }));
        }
        return raw;
    } catch {
        return [];
    }
}

function saveFavoriteList(list) {
    localStorage.setItem(FAVORITES_KEY, JSON.stringify(list));
}

function toggleFavoriteItem(item) {
    if (!item?.id) return false;
    const list = getFavoriteList();
    const key = String(item.id);
    const idx = list.findIndex((f) => String(f.id) === key);
    if (idx >= 0) {
        list.splice(idx, 1);
        saveFavoriteList(list);
        return false;
    }
    list.unshift({
        id: key,
        original: item.original || "",
        polished: item.polished || "",
        mode: item.mode || "general",
        mode_label: MODE_LABELS[item.mode] || item.mode || "通用优化",
        created_at: item.created_at || new Date().toISOString(),
        rating: item.rating ?? null,
    });
    saveFavoriteList(list);
    return true;
}

let refineContext = null;

function openRefineModal(item) {
    if (!item?.polished) {
        showToast("没有可继续优化的内容", "error");
        return;
    }
    refineContext = {
        polished: item.polished,
        mode: item.mode || document.getElementById("optimize-mode")?.value || "general",
        parentOriginal: item.original || "",
    };
    const modal = document.getElementById("refine-modal");
    const preview = document.getElementById("refine-preview");
    const directionEl = document.getElementById("refine-direction");
    if (preview) renderBubbleContent(preview, item.polished);
    if (directionEl) {
        directionEl.value = "";
        document.getElementById("refine-direction-count").textContent = "0";
    }
    modal?.classList.remove("hidden");
    directionEl?.focus();
}

function closeRefineModal() {
    document.getElementById("refine-modal")?.classList.add("hidden");
    refineContext = null;
}

async function submitRefineFromModal() {
    if (!refineContext) return;
    const direction = document.getElementById("refine-direction")?.value.trim();
    if (!direction) {
        showToast("请填写优化方向", "error");
        return;
    }
    const { polished, mode } = refineContext;
    if (polished.length > 3500) {
        showToast("当前提示词过长，请换一条较短记录", "error");
        return;
    }
    if (direction.length > 800) {
        showToast("优化方向过长，请精简后重试", "error");
        return;
    }

    closeRefineModal();
    switchView("polish");

    const displayOriginal = `【继续优化】\n优化方向：${direction}`;

    polishBtn.disabled = true;
    cancelBtn?.classList.remove("hidden");
    polishAbortController = new AbortController();

    originalText.value = "";
    document.getElementById("char-count").textContent = "0";

    const pendingBlock = appendPendingExchange(displayOriginal, mode);

    try {
        await streamPolish(null, mode, pendingBlock, polishAbortController.signal, {
            refine: true,
            polished,
            direction,
            displayOriginal,
        });
        scrollChatToBottom();
        showToast("已根据优化方向重新生成", "success");
    } catch (err) {
        if (err.name === "AbortError") {
            pendingBlock.remove();
            showToast("已取消", "info");
        } else {
            failPendingExchange(pendingBlock, err.message);
            showToast(err.message, "error");
        }
    } finally {
        polishBtn.disabled = false;
        cancelBtn?.classList.add("hidden");
        polishAbortController = null;
    }
}

function applyChatFontSize(px) {
    const size = Math.min(24, Math.max(12, parseInt(px, 10) || 16));
    const chatWindow = document.querySelector(".chat-window");
    if (!chatWindow) return size;
    chatWindow.style.setProperty("--chat-font-size", `${size}px`);
    chatWindow.style.setProperty("--chat-label-size", `${Math.max(11, size - 4)}px`);
    const select = document.getElementById("font-size-select");
    if (select) select.value = String(size);
    localStorage.setItem(FONT_SIZE_KEY, String(size));
    return size;
}

function initFontSizeControl() {
    const saved = localStorage.getItem(FONT_SIZE_KEY) || "16";
    applyChatFontSize(saved);

    document.getElementById("font-size-select")?.addEventListener("change", (e) => {
        applyChatFontSize(e.target.value);
    });

    document.getElementById("font-smaller")?.addEventListener("click", () => {
        const current = parseInt(localStorage.getItem(FONT_SIZE_KEY) || "16", 10);
        const smaller = FONT_SIZES.filter((s) => s < current);
        applyChatFontSize(smaller.length ? smaller[smaller.length - 1] : FONT_SIZES[0]);
    });

    document.getElementById("font-larger")?.addEventListener("click", () => {
        const current = parseInt(localStorage.getItem(FONT_SIZE_KEY) || "16", 10);
        const larger = FONT_SIZES.find((s) => s > current);
        applyChatFontSize(larger || FONT_SIZES[FONT_SIZES.length - 1]);
    });
}

function initModeControl() {
    const select = document.getElementById("optimize-mode");
    if (!select) return;
    const saved = localStorage.getItem(MODE_KEY);
    if (saved && MODE_LABELS[saved]) select.value = saved;
    select.addEventListener("change", () => {
        localStorage.setItem(MODE_KEY, select.value);
    });
}

async function apiRequest(url, options = {}) {
    const response = await fetch(API_BASE + url, {
        credentials: "same-origin",
        headers: { "Content-Type": "application/json", ...options.headers },
        ...options,
    });
    const data = await response.json().catch(() => ({}));
    if (!response.ok) {
        throw new Error(data.error || "请求失败");
    }
    return data;
}

async function checkSession() {
    try {
        const data = await apiRequest("/api/me");
        currentUser = data.user_id;
        updateAuthUI(true);
        return true;
    } catch {
        currentUser = null;
        updateAuthUI(false);
        return false;
    }
}

function showMessage(el, text, type = "success") {
    el.textContent = text;
    el.className = `message ${type}`;
}

function escapeHtml(text) {
    const div = document.createElement("div");
    div.textContent = text ?? "";
    return div.innerHTML;
}

function formatChatTime(iso) {
    if (!iso) return "";
    const d = new Date(iso);
    const pad = (n) => String(n).padStart(2, "0");
    return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

function switchAuthPanel(panelName) {
    document.querySelectorAll(".auth-panel").forEach((p) => p.classList.remove("active"));
    document.getElementById(`${panelName}-panel`).classList.add("active");
    document.querySelectorAll(".auth-panel .message").forEach((m) => {
        m.textContent = "";
        m.className = "message";
    });
}

function showAuthPage() {
    document.getElementById("auth-page").classList.remove("hidden");
    document.getElementById("app-shell").classList.add("hidden");
    switchAuthPanel("login");
}

function showAppShell() {
    document.getElementById("auth-page").classList.add("hidden");
    document.getElementById("app-shell").classList.remove("hidden");
    initFontSizeControl();
    initModeControl();
    switchView("polish");
    initChat();
}

function switchView(viewName) {
    document.querySelectorAll(".view").forEach((v) => v.classList.remove("active"));
    document.querySelectorAll(".nav-btn[data-view]").forEach((b) => b.classList.remove("active"));
    document.getElementById(`${viewName}-view`).classList.add("active");
    const navBtn = document.querySelector(`.nav-btn[data-view="${viewName}"]`);
    if (navBtn) navBtn.classList.add("active");
    if (viewName === "polish") scrollChatToBottom();
}

function updateAuthUI(loggedIn) {
    if (loggedIn) showAppShell();
    else showAuthPage();
}

function getChatContainer() {
    return document.getElementById("chat-messages");
}

function scrollChatToBottom() {
    const el = getChatContainer();
    if (el) {
        requestAnimationFrame(() => {
            el.scrollTop = el.scrollHeight;
        });
    }
}

function renderBubbleHeader(label) {
    return `
        <div class="bubble-header">
            <div class="bubble-label">${escapeHtml(label)}</div>
            <button type="button" class="bubble-action-btn copy-btn" title="复制到剪贴板">复制</button>
        </div>
    `;
}

async function copyText(text, btn) {
    if (!text) return;
    try {
        await navigator.clipboard.writeText(text);
    } catch {
        const ta = document.createElement("textarea");
        ta.value = text;
        ta.style.position = "fixed";
        ta.style.left = "-9999px";
        document.body.appendChild(ta);
        ta.select();
        document.execCommand("copy");
        document.body.removeChild(ta);
    }
    if (btn) {
        const original = btn.textContent;
        btn.textContent = "已复制";
        btn.classList.add("copied");
        setTimeout(() => {
            btn.textContent = original;
            btn.classList.remove("copied");
        }, 1500);
    } else {
        showToast("已复制到剪贴板", "success");
    }
}

async function copyBubbleText(btn) {
    const bubble = btn.closest(".bubble");
    const textEl = bubble?.querySelector(".bubble-text");
    if (!textEl) return;
    const text = getBubblePlainText(textEl);
    if (!text || text.startsWith("AI 正在优化")) return;
    await copyText(text, btn);
}

function bindCopyButtons(root) {
    root.querySelectorAll(".copy-btn").forEach((btn) => {
        btn.addEventListener("click", () => copyBubbleText(btn));
    });
}

function renderRatingStars(recordId, currentRating) {
    if (!recordId) return "";
    let html = '<span class="label">优化效果评分</span><div class="rating-stars">';
    for (let i = 1; i <= 5; i++) {
        const active = currentRating && i <= currentRating ? " active" : "";
        html += `<span class="rating-star${active}" data-record-id="${recordId}" data-value="${i}">★</span>`;
    }
    html += "</div>";
    return html;
}

function renderModeBadge(mode) {
    const label = MODE_LABELS[mode] || mode || "通用优化";
    return `<span class="mode-badge">${escapeHtml(label)}</span>`;
}

function renderAiExtras(item) {
    if (item.status === "failed") return "";
    const favorited = item.id && getFavorites().has(String(item.id));
    return `
        <div class="bubble-actions">
            <button type="button" class="bubble-action-btn reuse-btn">继续优化</button>
            <button type="button" class="bubble-action-btn compare-btn">对比</button>
            <button type="button" class="bubble-action-btn favorite-btn${favorited ? " active" : ""}">${favorited ? "已收藏" : "收藏"}</button>
        </div>
        <div class="compare-panel hidden">
            <div class="compare-col">
                <div class="compare-title">原始</div>
                <div class="compare-body compare-body-original"></div>
            </div>
            <div class="compare-col">
                <div class="compare-title">优化后</div>
                <div class="compare-body compare-body-polished"></div>
            </div>
        </div>
    `;
}

function bindAiExtras(block, item) {
    block.querySelector(".reuse-btn")?.addEventListener("click", () => {
        openRefineModal(item);
    });

    block.querySelector(".compare-btn")?.addEventListener("click", () => {
        const panel = block.querySelector(".compare-panel");
        panel?.classList.toggle("hidden");
        if (panel && !panel.classList.contains("hidden")) {
            const originalCol = panel.querySelector(".compare-col:first-child .compare-body");
            const polishedCol = panel.querySelector(".compare-col:last-child .compare-body");
            if (originalCol && item.original && !originalCol.dataset.mdDone) {
                renderBubbleContent(originalCol, item.original);
                originalCol.dataset.mdDone = "1";
            }
            if (polishedCol && item.polished && !polishedCol.dataset.mdDone) {
                applyMarkdownToElement(polishedCol, item.polished);
                polishedCol.classList.add("md-content");
                polishedCol.dataset.mdDone = "1";
            }
        }
    });

    block.querySelector(".favorite-btn")?.addEventListener("click", (e) => {
        if (!item.id) return;
        const active = toggleFavoriteItem(item);
        e.target.textContent = active ? "已收藏" : "收藏";
        e.target.classList.toggle("active", active);
        showToast(active ? "已收藏，可在「我的收藏」查看" : "已取消收藏", "success");
        if (document.getElementById("favorites-view")?.classList.contains("active")) {
            loadFavorites();
        }
    });
}

function renderAiBubble(item) {
    if (item.status === "failed") {
        return `
            <div class="bubble bubble-error">
                ${renderModeBadge(item.mode)}
                <div class="bubble-label">优化失败</div>
                <div class="bubble-text">${escapeHtml(item.error_message || item.polished || "未知错误")}</div>
            </div>
        `;
    }
    return `
        <div class="bubble">
            ${renderBubbleHeader("优化后提示词")}
            ${renderModeBadge(item.mode)}
            <div class="bubble-text bubble-text-md"></div>
            <div class="bubble-rating" data-record-id="${item.id}">
                ${renderRatingStars(item.id, item.rating)}
            </div>
            ${renderAiExtras(item)}
        </div>
    `;
}

function hydrateAiMarkdown(block, item) {
    const el = block.querySelector(".msg-row.ai .bubble-text-md");
    if (el && item.polished) {
        applyMarkdownToElement(el, item.polished);
        el.classList.remove("bubble-text-md");
    }
}

function hydrateUserMarkdown(block, text) {
    const el = block.querySelector(".msg-row.user .bubble-text-user");
    if (el && text) {
        renderBubbleContent(el, text);
        el.classList.remove("bubble-text-user");
    }
}

function appendExchange(item, prepend = false) {
    const container = getChatContainer();
    container.querySelector(".chat-welcome")?.remove();

    const block = document.createElement("div");
    block.className = "chat-exchange";
    block.dataset.id = item.id || "";
    block.innerHTML = `
        ${item.created_at ? `<div class="chat-time">${formatChatTime(item.created_at)}</div>` : ""}
        <div class="msg-row user">
            <div class="bubble">
                ${renderBubbleHeader("原始提示词")}
                <div class="bubble-text bubble-text-user"></div>
            </div>
        </div>
        <div class="msg-row ai">${renderAiBubble(item)}</div>
    `;

    if (prepend) {
        const loadMore = document.getElementById("chat-load-more");
        container.insertBefore(block, loadMore.nextSibling || container.firstChild);
    } else {
        container.appendChild(block);
    }

    bindRatingStars(block);
    bindCopyButtons(block);
    bindAiExtras(block, item);
    hydrateUserMarkdown(block, item.original);
    hydrateAiMarkdown(block, item);
}

function appendPendingExchange(original, mode) {
    const container = getChatContainer();
    container.querySelector(".chat-welcome")?.remove();

    const block = document.createElement("div");
    block.className = "chat-exchange pending";
    block.dataset.original = original;
    block.dataset.mode = mode;
    block.innerHTML = `
        <div class="chat-time">${formatChatTime(new Date().toISOString())}</div>
        <div class="msg-row user">
            <div class="bubble">
                ${renderBubbleHeader("原始提示词")}
                ${renderModeBadge(mode)}
                <div class="bubble-text bubble-text-user"></div>
            </div>
        </div>
        <div class="msg-row ai">
            <div class="bubble bubble-pending">
                <div class="bubble-label">优化后提示词</div>
                <div class="bubble-text streaming"><span class="typing-dots">AI 正在优化提示词</span></div>
            </div>
        </div>
    `;
    container.appendChild(block);
    bindCopyButtons(block);
    hydrateUserMarkdown(block, original);
    scrollChatToBottom();
    return block;
}

function finalizeExchange(block, item) {
    block.classList.remove("pending");
    block.dataset.id = item.id || "";
    const aiRow = block.querySelector(".msg-row.ai");
    aiRow.innerHTML = renderAiBubble(item);
    bindRatingStars(block);
    bindCopyButtons(block);
    bindAiExtras(block, item);
    hydrateAiMarkdown(block, item);
}

function failPendingExchange(block, message) {
    block.classList.remove("pending");
    const aiRow = block.querySelector(".msg-row.ai");
    aiRow.innerHTML = `
        <div class="bubble bubble-error">
            <div class="bubble-label">优化失败</div>
            <div class="bubble-text">${escapeHtml(message)}</div>
        </div>
    `;
}

function bindRatingStars(root) {
    root.querySelectorAll(".rating-star").forEach((star) => {
        star.addEventListener("click", async () => {
            const recordId = star.dataset.recordId;
            const value = parseInt(star.dataset.value, 10);
            if (!recordId) return;
            try {
                const data = await apiRequest(`/api/record/${recordId}/rate`, {
                    method: "POST",
                    body: JSON.stringify({ rating: value }),
                });
                const ratingEl = root.querySelector(".bubble-rating");
                ratingEl.querySelectorAll(".rating-star").forEach((s) => {
                    s.classList.toggle("active", parseInt(s.dataset.value, 10) <= value);
                });
                let hint = ratingEl.querySelector(".rate-hint");
                if (!hint) {
                    hint = document.createElement("span");
                    hint.className = "rate-hint";
                    ratingEl.appendChild(hint);
                }
                hint.textContent = `已评分，您的平均分：${data.new_avg_rating}`;
                showToast("评分成功", "success");
            } catch (err) {
                showToast(err.message, "error");
            }
        });
    });
}

async function loadChatHistory(page = 1, prepend = false) {
    if (chatLoadingMore) return;
    chatLoadingMore = true;

    try {
        const data = await apiRequest(`/api/history?page=${page}&per_page=${CHAT_PER_PAGE}`);
        chatHistoryPage = data.page;
        totalPages = data.pages;
        chatHasMore = data.page < data.pages;

        const items = [...data.items].reverse();
        if (items.length === 0 && page === 1) return;

        const container = getChatContainer();
        const scrollHeightBefore = container.scrollHeight;

        items.forEach((item) => {
            appendExchange(
                {
                    id: item.id,
                    original: item.original,
                    polished: item.polished,
                    rating: item.rating,
                    created_at: item.created_at,
                    mode: item.mode,
                    status: item.status,
                    error_message: item.error_message,
                },
                prepend
            );
        });

        document.getElementById("chat-load-more").classList.toggle("hidden", !chatHasMore);

        if (prepend) container.scrollTop = container.scrollHeight - scrollHeightBefore;
        else scrollChatToBottom();
    } catch (err) {
        if (page === 1) {
            getChatContainer().innerHTML += `<p class="message error">${escapeHtml(err.message)}</p>`;
        }
    } finally {
        chatLoadingMore = false;
    }
}

function initChat() {
    getChatContainer().innerHTML = `
        <div class="chat-welcome">
            <p>👋 欢迎使用 AI 提示词优化助手</p>
            <p>选择优化模式，输入原始提示词，AI 将流式输出优化结果。</p>
            <p class="chat-example">示例：写一篇关于气候变化的文章</p>
        </div>
    `;
    chatHistoryPage = 1;
    chatHasMore = false;
    loadChatHistory(1, false);
}

async function streamPolish(text, mode, pendingBlock, signal, options = {}) {
    const aiTextEl = pendingBlock.querySelector(".msg-row.ai .bubble-text");
    const aiBubble = pendingBlock.querySelector(".msg-row.ai .bubble");
    aiBubble.classList.remove("bubble-pending");
    aiTextEl.classList.add("streaming");
    aiTextEl.textContent = "";

    const body = options.refine
        ? {
              refine: true,
              polished: options.polished,
              direction: options.direction,
              display_original: options.displayOriginal,
              mode,
          }
        : { text, mode };

    const originalForRecord = options.refine
        ? options.displayOriginal || `【继续优化】\n优化方向：${options.direction}`
        : text;

    const response = await fetch("/api/polish/stream", {
        method: "POST",
        credentials: "same-origin",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
        signal,
    });

    if (!response.ok) {
        const data = await response.json().catch(() => ({}));
        throw new Error(data.error || "请求失败");
    }

    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";
    let polished = "";
    let finalPayload = null;

    while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const parts = buffer.split("\n\n");
        buffer = parts.pop() || "";

        for (const part of parts) {
            const line = part.trim();
            if (!line.startsWith("data:")) continue;
            const payload = JSON.parse(line.slice(5).trim());
            if (payload.error) throw new Error(payload.error);
            if (payload.chunk) {
                polished += payload.chunk;
                aiTextEl.textContent = polished;
                scrollChatToBottom();
            }
            if (payload.record_id !== undefined) {
                finalPayload = payload;
            }
        }
    }

    if (!finalPayload) {
        throw new Error("未收到完整响应");
    }

    finalizeExchange(pendingBlock, {
        id: finalPayload.record_id,
        original: originalForRecord,
        polished: finalPayload.polished || polished,
        rating: null,
        mode: finalPayload.mode || mode,
        status: finalPayload.status || "success",
        error_message: finalPayload.error_message,
    });
}

const originalText = document.getElementById("original-text");
const polishBtn = document.getElementById("polish-btn");
const cancelBtn = document.getElementById("cancel-polish-btn");

async function sendPolish() {
    const text = originalText.value.trim();
    const mode = document.getElementById("optimize-mode")?.value || "general";

    if (!text) {
        showToast("请输入原始提示词", "error");
        return;
    }

    polishBtn.disabled = true;
    cancelBtn?.classList.remove("hidden");
    polishAbortController = new AbortController();

    originalText.value = "";
    originalText.style.height = "auto";
    document.getElementById("char-count").textContent = "0";

    const pendingBlock = appendPendingExchange(text, mode);

    try {
        await streamPolish(text, mode, pendingBlock, polishAbortController.signal);
        scrollChatToBottom();
    } catch (err) {
        if (err.name === "AbortError") {
            pendingBlock.remove();
            showToast("已取消优化", "info");
        } else {
            failPendingExchange(pendingBlock, err.message);
            scrollChatToBottom();
            showToast(err.message, "error");
        }
    } finally {
        polishBtn.disabled = false;
        cancelBtn?.classList.add("hidden");
        polishAbortController = null;
    }
}

document.getElementById("load-more-btn")?.addEventListener("click", () => {
    if (chatHasMore) loadChatHistory(chatHistoryPage + 1, true);
});

document.querySelectorAll(".nav-btn[data-view]").forEach((btn) => {
    btn.addEventListener("click", () => switchView(btn.dataset.view));
});

document.querySelectorAll("[data-switch]").forEach((btn) => {
    btn.addEventListener("click", () => switchAuthPanel(btn.dataset.switch));
});

document.getElementById("show-forgot-btn").addEventListener("click", () => {
    const username = document.getElementById("login-username").value.trim();
    if (username) document.getElementById("forgot-username").value = username;
    switchAuthPanel("forgot");
});

document.getElementById("login-form").addEventListener("submit", async (e) => {
    e.preventDefault();
    const msgEl = document.getElementById("login-message");
    try {
        const data = await apiRequest("/api/login", {
            method: "POST",
            body: JSON.stringify({
                username: document.getElementById("login-username").value.trim(),
                password: document.getElementById("login-password").value,
            }),
        });
        currentUser = data.user_id;
        showMessage(msgEl, data.message, "success");
        setTimeout(() => updateAuthUI(true), 400);
    } catch (err) {
        showMessage(msgEl, err.message, "error");
    }
});

document.getElementById("register-form").addEventListener("submit", async (e) => {
    e.preventDefault();
    const msgEl = document.getElementById("register-message");
    const password = document.getElementById("register-password").value;
    const confirm = document.getElementById("register-confirm").value;
    if (password !== confirm) {
        showMessage(msgEl, "两次输入的密码不一致", "error");
        return;
    }
    try {
        await apiRequest("/api/register", {
            method: "POST",
            body: JSON.stringify({
                username: document.getElementById("register-username").value.trim(),
                email: document.getElementById("register-email").value.trim(),
                password,
                confirm_password: confirm,
            }),
        });
        showMessage(msgEl, "注册成功，请登录", "success");
        setTimeout(() => {
            switchAuthPanel("login");
            document.getElementById("login-username").value =
                document.getElementById("register-username").value.trim();
        }, 800);
    } catch (err) {
        showMessage(msgEl, err.message, "error");
    }
});

document.getElementById("forgot-form").addEventListener("submit", async (e) => {
    e.preventDefault();
    const msgEl = document.getElementById("forgot-message");
    const newPassword = document.getElementById("forgot-password").value;
    const confirm = document.getElementById("forgot-confirm").value;
    if (newPassword !== confirm) {
        showMessage(msgEl, "两次输入的密码不一致", "error");
        return;
    }
    try {
        const data = await apiRequest("/api/forgot-password", {
            method: "POST",
            body: JSON.stringify({
                username: document.getElementById("forgot-username").value.trim(),
                email: document.getElementById("forgot-email").value.trim(),
                new_password: newPassword,
                confirm_password: confirm,
            }),
        });
        showMessage(msgEl, data.message, "success");
        setTimeout(() => switchAuthPanel("login"), 1200);
    } catch (err) {
        showMessage(msgEl, err.message, "error");
    }
});

document.getElementById("logout-btn").addEventListener("click", async () => {
    await apiRequest("/api/logout", { method: "POST" });
    currentUser = null;
    updateAuthUI(false);
});

originalText.addEventListener("input", () => {
    document.getElementById("char-count").textContent = originalText.value.length;
    originalText.style.height = "auto";
    originalText.style.height = Math.min(originalText.scrollHeight, 120) + "px";
});

originalText.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
        e.preventDefault();
        polishBtn.click();
    }
});

cancelBtn?.addEventListener("click", () => {
    polishAbortController?.abort();
});

polishBtn.addEventListener("click", sendPolish);

async function loadHistory(page = 1) {
    const listEl = document.getElementById("history-list");
    const favorites = getFavorites();
    try {
        const data = await apiRequest(`/api/history?page=${page}&per_page=10`);
        currentPage = data.page;
        totalPages = data.pages;
        document.getElementById("page-info").textContent =
            `第 ${currentPage} / ${totalPages} 页（共 ${data.total} 条）`;
        document.getElementById("prev-page").disabled = currentPage <= 1;
        document.getElementById("next-page").disabled = currentPage >= totalPages;

        if (data.items.length === 0) {
            listEl.innerHTML = "<p>暂无历史记录</p>";
            return;
        }

        listEl.innerHTML = data.items
            .map((item) => {
                const failed = item.status === "failed";
                const star = favorites.has(String(item.id)) ? " ★" : "";
                return `
            <div class="history-item${failed ? " history-failed" : ""}" data-id="${item.id}">
                <div class="meta">${item.created_at || ""} · ${escapeHtml(item.mode_label || "")}${star}</div>
                <div class="original">
                    <div class="polished-label">原始提示词</div>
                    <div class="history-original-md"></div>
                </div>
                <div class="history-polished-wrap">
                    <div class="polished-label">${failed ? "失败原因" : "优化后"}</div>
                    <div class="history-polished-md"></div>
                </div>
                <div class="rating-display">${item.rating ? "★".repeat(item.rating) + " (" + item.rating + "星)" : failed ? "优化失败" : "未评分"}</div>
                <div class="history-actions">
                    <button type="button" class="history-copy-btn" data-target="original">复制原始</button>
                    ${failed ? "" : '<button type="button" class="history-copy-btn" data-target="polished">复制优化</button>'}
                    ${failed ? "" : '<button type="button" class="history-reuse-btn">继续优化</button>'}
                    <button class="delete-btn" data-id="${item.id}">删除</button>
                </div>
            </div>`;
            })
            .join("");

        data.items.forEach((item, index) => {
            const row = listEl.children[index];
            const body = row?.querySelector(".history-polished-md");
            const origBody = row?.querySelector(".history-original-md");
            if (origBody && item.original) {
                renderBubbleContent(origBody, item.original);
            }
            if (!body) return;
            const text = item.status === "failed" ? item.error_message : item.polished;
            if (item.status === "failed") {
                body.textContent = text || "";
            } else if (text) {
                applyMarkdownToElement(body, text);
            }
        });

        listEl.querySelectorAll(".history-copy-btn").forEach((btn) => {
            btn.addEventListener("click", async () => {
                const itemEl = btn.closest(".history-item");
                const target = btn.dataset.target;
                if (target === "polished") {
                    const el = itemEl.querySelector(".history-polished-md");
                    const text = getBubblePlainText(el);
                    if (text) await copyText(text);
                    return;
                }
                const el = itemEl.querySelector(".original");
                if (!el) return;
                const mdEl = el.querySelector(".history-original-md");
                let text = mdEl ? getBubblePlainText(mdEl) : el.textContent.trim();
                if (!text) text = el.textContent.replace(/^原始提示词\s*/, "").trim();
                await copyText(text);
            });
        });

        listEl.querySelectorAll(".history-reuse-btn").forEach((btn) => {
            btn.addEventListener("click", () => {
                const itemEl = btn.closest(".history-item");
                const id = itemEl?.dataset.id;
                const mdEl = itemEl.querySelector(".history-polished-md");
                const origMd = itemEl.querySelector(".history-original-md");
                const record = data.items.find((i) => String(i.id) === String(id));
                if (!record) return;
                openRefineModal({
                    id: record.id,
                    original: origMd ? getBubblePlainText(origMd) : record.original,
                    polished: getBubblePlainText(mdEl) || record.polished,
                    mode: record.mode,
                    created_at: record.created_at,
                });
            });
        });

        listEl.querySelectorAll(".delete-btn").forEach((btn) => {
            btn.addEventListener("click", async () => {
                if (!confirm("确定删除此记录？")) return;
                try {
                    await apiRequest(`/api/record/${btn.dataset.id}`, { method: "DELETE" });
                    loadHistory(currentPage);
                    initChat();
                    showToast("已删除", "success");
                } catch (err) {
                    showToast(err.message, "error");
                }
            });
        });
    } catch (err) {
        listEl.innerHTML = `<p class="message error">${err.message}</p>`;
    }
}

function loadFavorites() {
    const listEl = document.getElementById("favorites-list");
    if (!listEl) return;

    const items = getFavoriteList();
    if (items.length === 0) {
        listEl.innerHTML =
            '<p class="favorites-empty">暂无收藏。在优化对话中点击某条结果的「收藏」即可保存到这里。</p>';
        return;
    }

    listEl.innerHTML = items
        .map((item) => {
            if (item.legacy) {
                return `
            <div class="favorite-item favorite-legacy" data-id="${escapeHtml(item.id)}">
                <p>收藏 #${escapeHtml(item.id)}（旧版收藏，缺少内容）</p>
                <p class="favorites-legacy-hint">请取消后重新收藏该条记录，或从历史记录中再次收藏。</p>
                <button type="button" class="favorite-unfav-btn" data-id="${escapeHtml(item.id)}">取消收藏</button>
            </div>`;
            }
            return `
            <div class="favorite-item" data-id="${escapeHtml(item.id)}">
                <div class="meta">${formatChatTime(item.created_at)} · ${escapeHtml(item.mode_label || "")}</div>
                <div class="favorite-block">
                    <div class="favorite-label">原始提示词</div>
                    <div class="favorite-original-md"></div>
                </div>
                <div class="favorite-block">
                    <div class="favorite-label">优化后提示词</div>
                    <div class="favorite-polished-md"></div>
                </div>
                <div class="favorite-actions">
                    <button type="button" class="history-copy-btn" data-copy="original">复制原始</button>
                    <button type="button" class="history-copy-btn" data-copy="polished">复制优化</button>
                    <button type="button" class="favorite-refine-btn">继续优化</button>
                    <button type="button" class="favorite-unfav-btn" data-id="${escapeHtml(item.id)}">取消收藏</button>
                </div>
            </div>`;
        })
        .join("");

    items.forEach((item, index) => {
        const row = listEl.children[index];
        if (item.legacy || !row) return;
        const origEl = row.querySelector(".favorite-original-md");
        const polEl = row.querySelector(".favorite-polished-md");
        if (origEl && item.original) renderBubbleContent(origEl, item.original);
        if (polEl && item.polished) applyMarkdownToElement(polEl, item.polished);
    });

    listEl.querySelectorAll(".history-copy-btn").forEach((btn) => {
        btn.addEventListener("click", async () => {
            const row = btn.closest(".favorite-item");
            const target = btn.dataset.copy;
            const el =
                target === "polished"
                    ? row.querySelector(".favorite-polished-md")
                    : row.querySelector(".favorite-original-md");
            const text = getBubblePlainText(el);
            if (text) await copyText(text);
        });
    });

    listEl.querySelectorAll(".favorite-refine-btn").forEach((btn) => {
        btn.addEventListener("click", () => {
            const row = btn.closest(".favorite-item");
            const id = row?.dataset.id;
            const item = getFavoriteList().find((f) => String(f.id) === String(id));
            if (item && !item.legacy) openRefineModal(item);
        });
    });

    listEl.querySelectorAll(".favorite-unfav-btn").forEach((btn) => {
        btn.addEventListener("click", () => {
            const id = btn.dataset.id;
            const list = getFavoriteList().filter((f) => String(f.id) !== String(id));
            saveFavoriteList(list);
            loadFavorites();
            showToast("已取消收藏", "info");
        });
    });
}

document.querySelector('.nav-btn[data-view="history"]').addEventListener("click", () => {
    loadHistory(1);
});

document.querySelector('.nav-btn[data-view="favorites"]')?.addEventListener("click", () => {
    loadFavorites();
});

document.getElementById("refine-direction")?.addEventListener("input", (e) => {
    document.getElementById("refine-direction-count").textContent = e.target.value.length;
});

document.querySelectorAll("[data-close-refine]").forEach((el) => {
    el.addEventListener("click", closeRefineModal);
});

document.getElementById("refine-submit-btn")?.addEventListener("click", submitRefineFromModal);

document.getElementById("prev-page").addEventListener("click", () => {
    if (currentPage > 1) loadHistory(currentPage - 1);
});

document.getElementById("next-page").addEventListener("click", () => {
    if (currentPage < totalPages) loadHistory(currentPage + 1);
});

checkSession();
