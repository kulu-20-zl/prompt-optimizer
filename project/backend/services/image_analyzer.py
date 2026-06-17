"""图片理解：调用 Vision 兼容 API 描述图片，供提示词优化参考。"""
import base64
import os
import re

from openai import APITimeoutError, OpenAI

_ALLOWED_MIMES = frozenset(
    {"image/jpeg", "image/png", "image/webp", "image/gif"}
)
_MIME_BY_EXT = {
    "jpg": "image/jpeg",
    "jpeg": "image/jpeg",
    "png": "image/png",
    "webp": "image/webp",
    "gif": "image/gif",
}

_VISION_PROMPT = (
    "你是图片内容分析助手。用户会上传一张或多张参考图（可能是界面截图、文档、流程图、需求说明等）。\n"
    "请用中文简洁描述每张图的关键信息：界面元素、文字要点、结构关系、用户可能想达成的任务。\n"
    "不要编造图中没有的内容；看不清处标注「不清晰」。\n"
    "多张图请按「图片1」「图片2」分段输出，总字数控制在 600 字以内。"
)

_MOCK_ANALYSIS = (
    "【图片1】界面截图：顶部为「AI 提示词优化助手」标题，中部为对话区域，"
    "底部有模式选择与文本输入框，适合作为产品原型参考。\n"
    "【图片2】文档截图：包含项目需求条目与功能列表，重点为登录、优化对话与历史记录模块。"
)

_vision_client = None


def _get_vision_api_key() -> str:
    return (
        os.getenv("VISION_API_KEY", "").strip()
        or os.getenv("OPENAI_API_KEY", "").strip()
    )


def _get_vision_base_url() -> str | None:
    url = (
        os.getenv("VISION_BASE_URL", "").strip()
        or os.getenv("OPENAI_BASE_URL", "").strip()
    )
    return url or "https://api.openai.com/v1"


def _get_vision_model() -> str:
    return (
        os.getenv("VISION_MODEL", "").strip()
        or os.getenv("OPENAI_VISION_MODEL", "").strip()
        or "gpt-5.4"
    )


def _get_vision_client() -> OpenAI:
    global _vision_client
    if _vision_client is None:
        api_key = _get_vision_api_key()
        if not api_key:
            raise Exception(
                "VISION_ERROR: 未设置 VISION_API_KEY，图片分析需要单独的 GPT API Key。"
            )
        _vision_client = OpenAI(api_key=api_key, base_url=_get_vision_base_url())
    return _vision_client


def vision_enabled() -> bool:
    return os.getenv("VISION_ENABLED", "1") == "1"


def _decode_image_payload(data: str) -> bytes:
    raw = (data or "").strip()
    if not raw:
        raise ValueError("图片数据为空")
    if raw.startswith("data:"):
        match = re.match(r"^data:([^;]+);base64,(.+)$", raw, re.DOTALL)
        if not match:
            raise ValueError("图片 data URL 格式无效")
        raw = match.group(2)
    try:
        return base64.b64decode(raw, validate=True)
    except Exception as exc:
        raise ValueError("图片 Base64 解码失败") from exc


def normalize_image_item(item: dict, *, max_bytes: int) -> dict:
    if not isinstance(item, dict):
        raise ValueError("图片项格式无效")

    mime = (item.get("mime") or item.get("mime_type") or "").strip().lower()
    data = item.get("data") or item.get("base64") or ""
    if isinstance(data, str) and data.startswith("data:"):
        match = re.match(r"^data:([^;]+);base64,(.+)$", data, re.DOTALL)
        if match:
            if not mime:
                mime = match.group(1).lower()
            data = match.group(2)

    binary = _decode_image_payload(data if isinstance(data, str) else "")
    if len(binary) > max_bytes:
        raise ValueError(f"单张图片不能超过 {max_bytes // 1024 // 1024}MB")

    if not mime:
        name = (item.get("name") or "").lower()
        ext = name.rsplit(".", 1)[-1] if "." in name else ""
        mime = _MIME_BY_EXT.get(ext, "")

    if mime not in _ALLOWED_MIMES:
        raise ValueError("仅支持 JPEG、PNG、WebP、GIF 图片")

    return {
        "mime": mime,
        "data": base64.b64encode(binary).decode("ascii"),
        "name": (item.get("name") or "image").strip()[:120],
    }


def normalize_images(raw_images, *, max_count: int, max_bytes: int) -> list[dict]:
    if not raw_images:
        return []
    if not isinstance(raw_images, list):
        raise ValueError("images 必须是数组")
    if len(raw_images) > max_count:
        raise ValueError(f"最多上传 {max_count} 张图片")
    return [normalize_image_item(item, max_bytes=max_bytes) for item in raw_images]


def merge_image_context(user_text: str, image_analysis: str) -> str:
    text = (user_text or "").strip()
    analysis = (image_analysis or "").strip()
    if not analysis:
        return text
    if not text:
        text = "请根据参考图片中的信息，生成一段清晰、可执行的 AI 提示词。"
    return (
        "【参考图片内容（视觉模型自动描述，请融入优化后的提示词，勿当作最终答案输出）】\n"
        f"{analysis}\n\n"
        f"【用户原始描述】\n{text}"
    )


def storage_label_with_images(user_text: str, image_count: int) -> str:
    text = (user_text or "").strip()
    if image_count <= 0:
        return text
    prefix = f"【含参考图 ×{image_count}】\n"
    if not text:
        return prefix + "（请根据图片优化提示词）"
    return prefix + text


def analyze_images(images: list[dict]) -> str:
    """调用 Vision 模型描述图片内容。"""
    if not images:
        return ""

    if not vision_enabled():
        raise ValueError("图片分析功能已关闭（VISION_ENABLED=0）")

    if os.getenv("MOCK_AI", "0") == "1":
        return _MOCK_ANALYSIS[: 200 + 80 * len(images)]

    content: list[dict] = [{"type": "text", "text": _VISION_PROMPT}]
    for idx, img in enumerate(images, start=1):
        content.append(
            {
                "type": "text",
                "text": f"--- 图片{idx}（{img.get('name', 'image')}）---",
            }
        )
        content.append(
            {
                "type": "image_url",
                "image_url": {
                    "url": f"data:{img['mime']};base64,{img['data']}",
                },
            }
        )

    try:
        client = _get_vision_client()
        response = client.chat.completions.create(
            model=_get_vision_model(),
            messages=[{"role": "user", "content": content}],
            temperature=0.2,
            max_tokens=int(os.getenv("VISION_MAX_TOKENS", "800")),
            timeout=float(os.getenv("VISION_TIMEOUT", "60")),
        )
        result = response.choices[0].message.content
        if not result or not result.strip():
            raise ValueError("视觉模型未返回有效描述")
        return result.strip()
    except ValueError:
        raise
    except APITimeoutError:
        raise Exception("VISION_ERROR: 图片分析超时，请稍后重试") from None
    except Exception as e:
        if "VISION_ERROR:" in str(e):
            raise
        msg = str(e).lower()
        if "image" in msg or "vision" in msg or "multimodal" in msg:
            raise ValueError(
                "当前视觉模型不支持图片，请检查 VISION_MODEL、VISION_API_KEY、VISION_BASE_URL 后重启服务"
            ) from e
        raise Exception(f"VISION_ERROR: {str(e)}") from e
