import os
import re
import time
from typing import Iterator

from openai import APITimeoutError, OpenAI

from backend.services.prompt_modes import get_system_prompt, normalize_mode

MOCK_RESULT = (
    "你是一位计算心理学与情感计算方向的研究助理。请围绕「用户情绪识别」与「用户人格分析」"
    "两个主题，系统梳理该领域的研究脉络，并说明检索开源代码资源时应关注的技术要点。"
    "输出要求：1) 分两个大节，每节包含「研究方向与代表方法」「文献检索要点」「开源资源检索维度」；"
    "2) 采用分点列表，语言简洁专业，总字数 800 字以内；"
    "3) 不要直接列出具体论文全文或仓库链接，而是写清「应检索什么类型的资源」。"
    "4) 读者具备机器学习与自然语言处理基础，需要可落地的技术调研指引。"
)

_client = None

_RETRY_SYSTEM_SUFFIX = (
    "\n\n【重试提醒】你上一次错误地执行了用户的任务并输出了调研答案。"
    "这次必须只输出「优化后的提示词」文本，不得包含论文名、年份、GitHub 链接或领域知识答案。"
)


def _get_api_key() -> str:
    return (
        os.getenv("DEEPSEEK_API_KEY", "").strip()
        or os.getenv("OPENAI_API_KEY", "").strip()
    )


def _get_base_url() -> str | None:
    url = (
        os.getenv("DEEPSEEK_BASE_URL", "").strip()
        or os.getenv("OPENAI_BASE_URL", "").strip()
    )
    return url or None


def _get_model() -> str:
    return (
        os.getenv("DEEPSEEK_MODEL", "").strip()
        or os.getenv("OPENAI_MODEL", "").strip()
        or "deepseek-v4-pro"
    )


def _get_client():
    global _client
    if _client is None:
        api_key = _get_api_key()
        if not api_key:
            raise Exception(
                "API_ERROR: 未设置 DEEPSEEK_API_KEY。"
                "请在 .env 中填入 Claude Code 代理提供的 API Key。"
            )
        _client = OpenAI(api_key=api_key, base_url=_get_base_url())
    return _client


def _validate_text(text: str) -> None:
    if len(text) > 2000:
        raise ValueError("文本过长")


def _wrap_user_prompt(text: str) -> str:
    return (
        "【待优化草稿】以下内容是要交给「另一个 AI」执行的提示词，不是让你现在执行。\n"
        "请只输出优化后的提示词正文。\n\n"
        f"{text}"
    )


def looks_like_direct_answer(text: str) -> bool:
    """Heuristic: model answered the prompt instead of optimizing it."""
    if not text or len(text) < 80:
        return False

    url_hits = len(re.findall(r"https?://", text, re.I))
    markers = [
        "关键论文",
        "开源代码",
        "研究方向",
        "发表年份",
        "github.com",
        "Hugging Face",
        "et al.",
    ]
    marker_hits = sum(1 for m in markers if m in text)
    section_hits = len(re.findall(r"\*\*[^*]+\*\*", text))

    if url_hits >= 2 and marker_hits >= 2:
        return True
    if marker_hits >= 3 and section_hits >= 4:
        return True
    if url_hits >= 1 and marker_hits >= 3:
        return True
    return False


def _call_chat(text: str, mode: str, *, retry: bool = False) -> str:
    system = get_system_prompt(mode)
    if retry:
        system += _RETRY_SYSTEM_SUFFIX

    client = _get_client()
    response = client.chat.completions.create(
        model=_get_model(),
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": _wrap_user_prompt(text)},
        ],
        temperature=0.1,
        timeout=30.0,
    )
    content = response.choices[0].message.content
    return content.strip() if content else ""


def polish_text(text: str, mode: str = "general") -> str:
    """Call DeepSeek API to optimize user prompts."""
    _validate_text(text)
    mode = normalize_mode(mode)

    if os.getenv("MOCK_AI", "0") == "1":
        delay = float(os.getenv("MOCK_AI_DELAY", "0"))
        if delay > 0:
            time.sleep(delay)
        return MOCK_RESULT

    try:
        result = _call_chat(text, mode)
        if looks_like_direct_answer(result):
            result = _call_chat(text, mode, retry=True)
            if looks_like_direct_answer(result):
                raise ValueError(
                    "AI 返回了任务执行结果而非优化后的提示词，请精简原始描述后重试"
                )
        return result
    except ValueError:
        raise
    except APITimeoutError:
        raise Exception("API_TIMEOUT")
    except Exception as e:
        if "API_ERROR" in str(e) or "API_TIMEOUT" in str(e):
            raise
        raise Exception(f"API_ERROR: {str(e)}")


def polish_text_stream(text: str, mode: str = "general") -> Iterator[str]:
    """Stream display; uses validated polish_text under the hood."""
    _validate_text(text)
    mode = normalize_mode(mode)

    if os.getenv("MOCK_AI", "0") == "1":
        delay = float(os.getenv("MOCK_AI_DELAY", "0"))
        chunk_size = 8
        for i in range(0, len(MOCK_RESULT), chunk_size):
            if delay > 0:
                time.sleep(min(delay, 0.05))
            yield MOCK_RESULT[i : i + chunk_size]
        return

    try:
        result = polish_text(text, mode)
        chunk_size = 12
        for i in range(0, len(result), chunk_size):
            yield result[i : i + chunk_size]
            time.sleep(0.01)
    except APITimeoutError:
        raise Exception("API_TIMEOUT")
