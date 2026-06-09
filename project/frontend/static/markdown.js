/**
 * 轻量 Markdown 渲染（无外部依赖），用于聊天气泡展示。
 */

function escapeHtml(text) {
    const div = document.createElement("div");
    div.textContent = text ?? "";
    return div.innerHTML;
}

/** 让「1. **xxx** 2. **yyy**」等同一段里的多条列表能正确换行 */
function normalizeMarkdown(text) {
    return text
        .replace(/\r\n/g, "\n")
        .replace(/([。；！？\s])\s*(\d+)\.\s+/g, "$1\n\n$2. ")
        .replace(/(\*\*[^*]+\*\*[^。\n]*?)\s+(\d+)\.\s+/g, "$1\n\n$2. ");
}

function renderMarkdownHtml(text) {
    if (!text) return "";

    if (typeof marked !== "undefined") {
        marked.setOptions({
            breaks: true,
            gfm: true,
            headerIds: false,
            mangle: false,
        });
        const html = marked.parse(normalizeMarkdown(text));
        if (typeof DOMPurify !== "undefined") {
            return DOMPurify.sanitize(html, { USE_PROFILES: { html: true } });
        }
        return html;
    }

    return renderMarkdownFallback(normalizeMarkdown(text));
}

function renderMarkdownFallback(text) {
    const lines = text.split("\n");
    const out = [];
    let inOl = false;
    let inUl = false;

    const closeLists = () => {
        if (inOl) {
            out.push("</ol>");
            inOl = false;
        }
        if (inUl) {
            out.push("</ul>");
            inUl = false;
        }
    };

    const inline = (s) =>
        escapeHtml(s)
            .replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>")
            .replace(/\*([^*]+)\*/g, "<em>$1</em>")
            .replace(/`([^`]+)`/g, "<code>$1</code>");

    for (const raw of lines) {
        const line = raw.trim();
        if (!line) {
            closeLists();
            continue;
        }

        const ol = line.match(/^(\d+)\.\s+(.+)$/);
        if (ol) {
            if (!inOl) {
                closeLists();
                out.push("<ol>");
                inOl = true;
            }
            out.push(`<li>${inline(ol[2])}</li>`);
            continue;
        }

        const ul = line.match(/^[-*]\s+(.+)$/);
        if (ul) {
            if (!inUl) {
                closeLists();
                out.push("<ul>");
                inUl = true;
            }
            out.push(`<li>${inline(ul[1])}</li>`);
            continue;
        }

        const h = line.match(/^(#{1,3})\s+(.+)$/);
        if (h) {
            closeLists();
            const level = h[1].length;
            out.push(`<h${level}>${inline(h[2])}</h${level}>`);
            continue;
        }

        closeLists();
        out.push(`<p>${inline(line)}</p>`);
    }

    closeLists();
    return out.join("");
}

function applyMarkdownToElement(el, text) {
    if (!el || !text) return;
    el.classList.add("md-content");
    el.dataset.rawText = text;
    el.innerHTML = renderMarkdownHtml(text);
}

function getBubblePlainText(el) {
    if (!el) return "";
    return (el.dataset.rawText || el.textContent || "").trim();
}

/** 是否像 Markdown（含 **、列表、标题、代码块等） */
function looksLikeMarkdown(text) {
    if (!text || !text.trim()) return false;
    return /(\*\*|__|`[^`]+`|```|^#{1,6}\s|^\s*[-*+]\s+\S|^\s*\d+\.\s+\S|\[[^\]]+\]\([^)]+\))/m.test(
        text
    );
}

/** 聊天气泡：纯文本或 Markdown 展示 */
function renderBubbleContent(el, text) {
    if (!el) return;
    if (looksLikeMarkdown(text)) {
        applyMarkdownToElement(el, text);
    } else {
        el.classList.remove("md-content");
        delete el.dataset.rawText;
        el.textContent = text;
    }
}
