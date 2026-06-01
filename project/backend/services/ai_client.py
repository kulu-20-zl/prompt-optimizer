import os
import re
import time
from typing import Iterator

from openai import APITimeoutError, OpenAI

from backend.services.prompt_modes import (
    get_refine_system_prompt,
    get_system_prompt,
    normalize_mode,
)

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

_REFINE_RETRY_SUFFIX = (
    "\n\n【重试提醒】你上一次输出了思考过程或任务答案。"
    "这次必须只输出「合并优化方向后的新提示词」正文："
    "不要「首先/让我」等推理句，不要真实链接与文献，不要解释。"
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


def _validate_text(text: str, max_len: int = 2000) -> None:
    if len(text) > max_len:
        raise ValueError("文本过长")


def _validate_refine(polished: str, direction: str) -> None:
    from backend.config import Config

    if not polished.strip():
        raise ValueError("当前提示词不能为空")
    if not direction.strip():
        raise ValueError("优化方向不能为空")
    if len(polished) > Config.REFINE_POLISHED_MAX:
        raise ValueError("当前提示词过长")
    if len(direction) > Config.REFINE_DIRECTION_MAX:
        raise ValueError("优化方向过长")


def _wrap_user_prompt(text: str) -> str:
    return (
        "【待优化草稿】以下内容是要交给「另一个 AI」执行的提示词，不是让你现在执行。\n"
        "请只输出优化后的提示词正文。\n\n"
        f"{text}"
    )


def looks_like_reasoning_trace(text: str) -> bool:
    """Heuristic: model output chain-of-thought instead of a prompt."""
    if not text or len(text) < 50:
        return False

    head = text.strip()[:400]
    reasoning_starts = (
        "首先",
        "我需要",
        "让我",
        "好的，",
        "好的,",
        "用户已经",
        "用户希望",
        "根据用户",
        "分析用户",
        "接下来我",
        "我来",
        "The user",
        "Let me",
        "I need to",
        "I'll ",
    )
    if any(head.startswith(s) for s in reasoning_starts):
        return True

    if re.search(r"(思考过程|推理过程|内部分析|思路如下|我的理解是)", text):
        return True

    meta_hits = sum(
        1
        for p in (
            "用户要求",
            "优化方向是",
            "当前提示词",
            "我需要将",
            "应该输出",
            "合并后的",
            "落实优化方向",
        )
        if p in head
    )
    if meta_hits >= 3:
        return True

    return False


def looks_like_bad_output(text: str) -> bool:
    return looks_like_direct_answer(text) or looks_like_reasoning_trace(text)


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


def _build_refine_user_message(polished: str, direction: str) -> str:
    return (
        "请将「当前提示词」与「优化方向」合并为一份新的完整提示词。\n"
        "只输出新提示词正文，不要思考过程，不要执行任务。\n\n"
        f"【当前提示词】\n{polished.strip()}\n\n"
        f"【优化方向】\n{direction.strip()}"
    )


def _call_chat(
    text: str,
    mode: str,
    *,
    retry: bool = False,
    refine: bool = False,
) -> str:
    if refine:
        system = get_refine_system_prompt(mode)
        if retry:
            system += _REFINE_RETRY_SUFFIX
        user_content = text
    else:
        system = get_system_prompt(mode)
        if retry:
            system += _RETRY_SYSTEM_SUFFIX
        user_content = _wrap_user_prompt(text)

    client = _get_client()
    response = client.chat.completions.create(
        model=_get_model(),
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user_content},
        ],
        temperature=0.1,
        timeout=45.0 if refine else 30.0,
    )
    content = response.choices[0].message.content
    return content.strip() if content else ""


def polish_text_refine(polished: str, direction: str, mode: str = "general") -> str:
    """Continue optimizing: merge polished prompt with user direction."""
    _validate_refine(polished, direction)
    mode = normalize_mode(mode)
    user_msg = _build_refine_user_message(polished, direction)

    if os.getenv("MOCK_AI", "0") == "1":
        delay = float(os.getenv("MOCK_AI_DELAY", "0"))
        if delay > 0:
            time.sleep(delay)
        return (
            "你是一位情感计算与人格心理测量方向的研究助理。"
            "用户已确定：情绪识别以 FunASR 为核心实现；人格分析以 PKU 相关方案为核心。"
            "请分别针对上述两个既定技术路线，给出官方/权威开源仓库与代表性论文的完整 https 链接，"
            "并对代码架构、依赖环境、输入输出接口及每篇论文的核心贡献做对比分析；"
            "输出须含对比表格与分节叙述，信息缺失处标注「未找到公开信息」。"
        )

    try:
        result = _call_chat(user_msg, mode, refine=True)
        if looks_like_bad_output(result):
            result = _call_chat(user_msg, mode, refine=True, retry=True)
            if looks_like_bad_output(result):
                raise ValueError(
                    "AI 返回了思考过程或任务答案，而非合并后的新提示词，请精简优化方向后重试"
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
        if looks_like_bad_output(result):
            result = _call_chat(text, mode, retry=True)
            if looks_like_bad_output(result):
                raise ValueError(
                    "AI 返回了任务执行结果或思考过程，而非优化后的提示词，请精简原始描述后重试"
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


def polish_text_stream(
    text: str = "",
    mode: str = "general",
    *,
    polished: str | None = None,
    direction: str | None = None,
) -> Iterator[str]:
    """Stream display; uses validated polish_text under the hood."""
    mode = normalize_mode(mode)
    if polished is not None and direction is not None:
        result_fn = lambda: polish_text_refine(polished, direction, mode)
    else:
        _validate_text(text)
        result_fn = lambda: polish_text(text, mode)

    if os.getenv("MOCK_AI", "0") == "1":
        delay = float(os.getenv("MOCK_AI_DELAY", "0"))
        result = result_fn()
        chunk_size = 8
        for i in range(0, len(result), chunk_size):
            if delay > 0:
                time.sleep(min(delay, 0.05))
            yield result[i : i + chunk_size]
        return

    try:
        result = result_fn()
        chunk_size = 12
        for i in range(0, len(result), chunk_size):
            yield result[i : i + chunk_size]
            time.sleep(0.01)
    except APITimeoutError:
        raise Exception("API_TIMEOUT")
