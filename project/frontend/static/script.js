let currentUser = null;
let currentPage = 1;
let totalPages = 1;
let chatHistoryPage = 1;
let chatHasMore = false;
let chatLoadingMore = false;

const API_BASE = "";
const CHAT_PER_PAGE = 20;
const FONT_SIZE_KEY = "chatFontSize";
const FONT_SIZES = [14, 16, 18, 20, 24];

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

function showMessage(el, text, type = "success") {
    el.textContent = text;
    el.className = `message ${type}`;
}

function escapeHtml(text) {
    const div = document.createElement("div");
    div.textContent = text;
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
    switchView("polish");
    initChat();
}

function switchView(viewName) {
    document.querySelectorAll(".view").forEach((v) => v.classList.remove("active"));
    document.querySelectorAll(".nav-btn[data-view]").forEach((b) => b.classList.remove("active"));
    document.getElementById(`${viewName}-view`).classList.add("active");
    const navBtn = document.querySelector(`.nav-btn[data-view="${viewName}"]`);
    if (navBtn) navBtn.classList.add("active");
    if (viewName === "polish") {
        scrollChatToBottom();
    }
}

function updateAuthUI(loggedIn) {
    if (loggedIn) {
        showAppShell();
    } else {
        showAuthPage();
    }
}

/* ========== Chat UI ========== */

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

async function copyBubbleText(btn) {
    const bubble = btn.closest(".bubble");
    const textEl = bubble?.querySelector(".bubble-text");
    if (!textEl) return;

    const text = textEl.textContent.trim();
    if (!text || text.startsWith("AI 正在优化")) return;

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

    const original = btn.textContent;
    btn.textContent = "已复制";
    btn.classList.add("copied");
    setTimeout(() => {
        btn.textContent = original;
        btn.classList.remove("copied");
    }, 1500);
}

function bindCopyButtons(root) {
    root.querySelectorAll(".copy-btn").forEach((btn) => {
        btn.addEventListener("click", () => copyBubbleText(btn));
    });
}

function renderRatingStars(recordId, currentRating) {
    let html = '<span class="label">优化效果评分</span><div class="rating-stars">';
    for (let i = 1; i <= 5; i++) {
        const active = currentRating && i <= currentRating ? " active" : "";
        html += `<span class="rating-star${active}" data-record-id="${recordId}" data-value="${i}">★</span>`;
    }
    html += "</div>";
    return html;
}

function appendExchange(item, prepend = false) {
    const container = getChatContainer();
    const welcome = container.querySelector(".chat-welcome");
    if (welcome) welcome.remove();

    const timeHtml = item.created_at
        ? `<div class="chat-time">${formatChatTime(item.created_at)}</div>`
        : "";

    const block = document.createElement("div");
    block.className = "chat-exchange";
    block.dataset.id = item.id || "";
    block.innerHTML = `
        ${timeHtml}
        <div class="msg-row user">
            <div class="bubble">
                ${renderBubbleHeader("原始提示词")}
                <div class="bubble-text">${escapeHtml(item.original)}</div>
            </div>
        </div>
        <div class="msg-row ai">
            <div class="bubble">
                ${renderBubbleHeader("优化后提示词")}
                <div class="bubble-text">${escapeHtml(item.polished)}</div>
                <div class="bubble-rating" data-record-id="${item.id}">
                    ${renderRatingStars(item.id, item.rating)}
                </div>
            </div>
        </div>
    `;

    if (prepend) {
        const loadMore = document.getElementById("chat-load-more");
        container.insertBefore(block, loadMore.nextSibling || container.firstChild);
    } else {
        container.appendChild(block);
    }

    bindRatingStars(block);
    bindCopyButtons(block);
}

function appendPendingExchange(original) {
    const container = getChatContainer();
    const welcome = container.querySelector(".chat-welcome");
    if (welcome) welcome.remove();

    const block = document.createElement("div");
    block.className = "chat-exchange pending";
    block.innerHTML = `
        <div class="chat-time">${formatChatTime(new Date().toISOString())}</div>
        <div class="msg-row user">
            <div class="bubble">
                ${renderBubbleHeader("原始提示词")}
                <div class="bubble-text">${escapeHtml(original)}</div>
            </div>
        </div>
        <div class="msg-row ai">
            <div class="bubble bubble-pending">
                <div class="bubble-label">优化后提示词</div>
                <div class="bubble-text"><span class="typing-dots">AI 正在优化提示词</span></div>
            </div>
        </div>
    `;
    container.appendChild(block);
    bindCopyButtons(block);
    scrollChatToBottom();
    return block;
}

function completePendingExchange(block, item) {
    block.classList.remove("pending");
    block.dataset.id = item.id || "";
    const aiRow = block.querySelector(".msg-row.ai");
    aiRow.innerHTML = `
        <div class="bubble">
            ${renderBubbleHeader("优化后提示词")}
            <div class="bubble-text">${escapeHtml(item.polished)}</div>
            <div class="bubble-rating" data-record-id="${item.id}">
                ${renderRatingStars(item.id, item.rating)}
            </div>
        </div>
    `;
    bindRatingStars(block);
    bindCopyButtons(block);
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
            } catch (err) {
                alert(err.message);
            }
        });
    });
}

async function loadChatHistory(page = 1, prepend = false) {
    if (chatLoadingMore) return;
    chatLoadingMore = true;

    try {
        const data = await apiRequest(
            `/api/history?page=${page}&per_page=${CHAT_PER_PAGE}`
        );
        chatHistoryPage = data.page;
        totalPages = data.pages;
        chatHasMore = data.page < data.pages;

        const items = [...data.items].reverse();
        if (items.length === 0 && page === 1) {
            return;
        }

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
                },
                prepend
            );
        });

        document.getElementById("chat-load-more").classList.toggle("hidden", !chatHasMore);

        if (prepend) {
            container.scrollTop = container.scrollHeight - scrollHeightBefore;
        } else {
            scrollChatToBottom();
        }
    } catch (err) {
        if (page === 1) {
            getChatContainer().innerHTML +=
                `<p class="message error">${escapeHtml(err.message)}</p>`;
        }
    } finally {
        chatLoadingMore = false;
    }
}

function initChat() {
    const container = getChatContainer();
    container.innerHTML = `
        <div class="chat-welcome">
            <p>👋 欢迎使用 AI 提示词优化助手</p>
            <p>在下方输入你的原始提示词，点击发送即可获得优化后的版本。</p>
            <p class="chat-example">示例：写一篇关于气候变化的文章</p>
        </div>
    `;
    chatHistoryPage = 1;
    chatHasMore = false;
    loadChatHistory(1, false);
}

document.getElementById("load-more-btn")?.addEventListener("click", () => {
    if (chatHasMore) {
        loadChatHistory(chatHistoryPage + 1, true);
    }
});

document.querySelectorAll(".nav-btn[data-view]").forEach((btn) => {
    btn.addEventListener("click", () => {
        switchView(btn.dataset.view);
        if (btn.dataset.view === "polish") {
            scrollChatToBottom();
        }
    });
});

document.querySelectorAll("[data-switch]").forEach((btn) => {
    btn.addEventListener("click", () => switchAuthPanel(btn.dataset.switch));
});

document.getElementById("show-forgot-btn").addEventListener("click", () => {
    const username = document.getElementById("login-username").value.trim();
    if (username) {
        document.getElementById("forgot-username").value = username;
    }
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

const originalText = document.getElementById("original-text");
const polishBtn = document.getElementById("polish-btn");
const chatLoading = document.getElementById("chat-loading");

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

document.getElementById("paste-btn").addEventListener("click", async () => {
    try {
        const text = await navigator.clipboard.readText();
        if (!text) return;
        originalText.value = text.slice(0, 2000);
        document.getElementById("char-count").textContent = originalText.value.length;
        originalText.style.height = "auto";
        originalText.style.height = Math.min(originalText.scrollHeight, 120) + "px";
        originalText.focus();
    } catch {
        alert("无法读取剪贴板，请使用 Ctrl+V 粘贴");
    }
});

async function sendPolish() {
    const text = originalText.value.trim();
    if (!text) {
        alert("请输入原始提示词");
        return;
    }

    polishBtn.disabled = true;
    originalText.value = "";
    originalText.style.height = "auto";
    document.getElementById("char-count").textContent = "0";

    const pendingBlock = appendPendingExchange(text);

    try {
        const data = await apiRequest("/api/polish", {
            method: "POST",
            body: JSON.stringify({ text }),
        });

        completePendingExchange(pendingBlock, {
            id: data.record_id,
            polished: data.polished,
            rating: null,
        });
        scrollChatToBottom();
    } catch (err) {
        failPendingExchange(pendingBlock, err.message);
        scrollChatToBottom();
    } finally {
        polishBtn.disabled = false;
    }
}

polishBtn.addEventListener("click", sendPolish);

/* ========== History management tab ========== */

async function loadHistory(page = 1) {
    const listEl = document.getElementById("history-list");
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
            .map(
                (item) => `
            <div class="history-item" data-id="${item.id}">
                <div class="meta">${item.created_at || ""}</div>
                <div class="original">原始提示词：${escapeHtml(item.original)}</div>
                <div class="polished">优化后：${escapeHtml(item.polished)}</div>
                <div class="rating-display">${item.rating ? "★".repeat(item.rating) + " (" + item.rating + "星)" : "未评分"}</div>
                <div class="history-actions">
                    <button type="button" class="history-copy-btn" data-target="original">复制原始</button>
                    <button type="button" class="history-copy-btn" data-target="polished">复制优化</button>
                    <button class="delete-btn" data-id="${item.id}">删除</button>
                </div>
            </div>`
            )
            .join("");

        listEl.querySelectorAll(".history-copy-btn").forEach((btn) => {
            btn.addEventListener("click", async () => {
                const itemEl = btn.closest(".history-item");
                const target = btn.dataset.target;
                const el = itemEl.querySelector(target === "polished" ? ".polished" : ".original");
                if (!el) return;
                let text = el.textContent.trim();
                if (target === "original") text = text.replace(/^原始提示词：/, "").trim();
                if (target === "polished") text = text.replace(/^优化后：/, "").trim();
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
                const original = btn.textContent;
                btn.textContent = "已复制";
                setTimeout(() => {
                    btn.textContent = original;
                }, 1500);
            });
        });

        listEl.querySelectorAll(".delete-btn").forEach((btn) => {
            btn.addEventListener("click", async () => {
                if (!confirm("确定删除此记录？")) return;
                try {
                    await apiRequest(`/api/record/${btn.dataset.id}`, { method: "DELETE" });
                    loadHistory(currentPage);
                    initChat();
                } catch (err) {
                    alert(err.message);
                }
            });
        });
    } catch (err) {
        listEl.innerHTML = `<p class="message error">${err.message}</p>`;
    }
}

document.querySelector('.nav-btn[data-view="history"]').addEventListener("click", () => {
    loadHistory(1);
});

document.getElementById("prev-page").addEventListener("click", () => {
    if (currentPage > 1) loadHistory(currentPage - 1);
});

document.getElementById("next-page").addEventListener("click", () => {
    if (currentPage < totalPages) loadHistory(currentPage + 1);
});
