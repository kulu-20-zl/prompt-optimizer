import os
import time

from openai import APITimeoutError, OpenAI

MOCK_RESULT = (
    "你是一位资深内容创作专家。请撰写一篇关于气候变化的文章，"
    "要求：1) 字数800字左右；2) 包含科学依据；3) 结构为引言、现状分析、对策建议、结语；"
    "4) 语言通俗易懂。"
)

_client = None


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


def polish_text(text: str) -> str:
    """Call DeepSeek API to optimize user prompts."""
    if len(text) > 2000:
        raise ValueError("文本过长")

    if os.getenv("MOCK_AI", "0") == "1":
        delay = float(os.getenv("MOCK_AI_DELAY", "0"))
        if delay > 0:
            time.sleep(delay)
        return MOCK_RESULT

    try:
        client = _get_client()
        response = client.chat.completions.create(
            model=_get_model(),
            messages=[
                {
                    "role": "system",
                    "content": (
                        "你是一个专业的提示词优化助手，不是聊天机器人。\n\n"
                        "【任务】将用户输入的原始提示词改写成更清晰、具体、结构化、"
                        "易于 AI 理解的高质量提示词。遵循原则：1. 明确角色；"
                        "2. 给出具体任务；3. 提供输出格式要求（如列表、段落、字数）；"
                        "4. 加入必要上下文。保持与用户相同的语言（中文输入输出中文，"
                        "英文输入输出英文）。\n\n"
                        "【严禁】\n"
                        "- 禁止回答问题、闲聊或自我介绍\n"
                        "- 禁止解释优化思路，禁止前缀（如「优化结果：」）\n"
                        "- 禁止对优化效果进行评价\n\n"
                        "【输出】仅返回优化后的提示词，一段即可，别无其他。"
                    ),
                },
                {"role": "user", "content": text},
            ],
            temperature=0.2,
            timeout=30.0,
        )
        content = response.choices[0].message.content
        return content.strip() if content else ""
    except APITimeoutError:
        raise Exception("API_TIMEOUT")
    except Exception as e:
        raise Exception(f"API_ERROR: {str(e)}")
