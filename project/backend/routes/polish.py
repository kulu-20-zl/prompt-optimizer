import json

from flask import Blueprint, Response, current_app, jsonify, request, session, stream_with_context

from backend.config import Config
from backend.models import PolishRecord, db
from backend.services.ai_client import polish_text, polish_text_refine, polish_text_stream
from backend.services.image_analyzer import (
    analyze_images,
    merge_image_context,
    normalize_images,
    storage_label_with_images,
)
from backend.services.prompt_modes import MODE_LABELS, normalize_mode
from backend.utils.auth import login_required

polish_bp = Blueprint("polish", __name__)


def _map_ai_error(exc: Exception, *, stage: str = "") -> tuple[str, int]:
    msg = str(exc)
    if "VISION_ERROR:" in msg:
        detail = msg.split("VISION_ERROR:", 1)[1].strip()
        return f"图片分析失败：{detail}", 503
    if "API_TIMEOUT" in msg:
        return "AI服务繁忙，请稍后重试", 503
    if "未设置 DEEPSEEK_API_KEY" in msg or "未设置 OPENAI_API_KEY" in msg:
        return f"提示词优化失败：{msg.replace('API_ERROR: ', '')}", 503
    if "未设置 VISION_API_KEY" in msg:
        return msg.replace("API_ERROR: ", ""), 503
    if msg.startswith("API_ERROR: "):
        detail = msg.replace("API_ERROR: ", "", 1)
        prefix = "提示词优化失败" if stage == "polish" else "AI 服务异常"
        return f"{prefix}：{detail}", 503
    if "does not accept input types: image" in msg.lower():
        return (
            "图片分析失败：当前模型不支持图片，请检查 VISION_MODEL（如 gpt-5.4）"
            " 与 VISION_BASE_URL 后重启服务",
            503,
        )
    if stage == "vision":
        return (
            "图片分析失败：请检查 VISION_API_KEY、VISION_BASE_URL、VISION_MODEL 后重启 Flask",
            503,
        )
    if stage == "polish":
        return (
            "提示词优化失败：请检查 DEEPSEEK_API_KEY、DEEPSEEK_BASE_URL、DEEPSEEK_MODEL",
            503,
        )
    return (
        "请求失败：带图片时请检查 VISION_* 配置；纯文字时请检查 DEEPSEEK_* 配置，并重启 Flask",
        503,
    )


def _save_record(
    user_id: int,
    original: str,
    polished: str,
    mode: str,
    status: str = "success",
    error_message: str | None = None,
) -> PolishRecord:
    record = PolishRecord(
        user_id=user_id,
        original_text=original,
        polished_text=polished or "",
        mode=mode,
        status=status,
        error_message=error_message,
    )
    db.session.add(record)
    db.session.commit()
    print(
        f"  [数据库] 已写入 polish_record #{record.id} "
        f"（用户 {user_id}，状态 {status}，库: {Config.DB_FILE}）"
    )
    return record


def _parse_polish_body(data: dict) -> tuple[str, str, str, bool, str | None, list[dict]]:
    """Returns text, mode, storage_original, is_refine, refine_direction, images."""
    mode = normalize_mode(data.get("mode"))
    is_refine = bool(data.get("refine"))
    images = data.get("images") or []

    if is_refine:
        polished_base = (data.get("polished") or "").strip()
        direction = (data.get("direction") or "").strip()
        storage = (data.get("display_original") or "").strip()
        if not storage:
            storage = f"【继续优化】\n优化方向：{direction}"
        return polished_base, mode, storage, True, direction, images

    text = (data.get("text") or "").strip()
    return text, mode, text, False, None, images


def _prepare_polish_inputs(
    text: str,
    storage_original: str,
    is_refine: bool,
    direction: str | None,
    images_raw: list,
) -> tuple[str, str]:
    """解析图片、调用视觉模型，返回用于 AI 的文本与展示用 storage_original。"""
    images = normalize_images(
        images_raw,
        max_count=current_app.config["MAX_IMAGES"],
        max_bytes=current_app.config["MAX_IMAGE_BYTES"],
    )

    if images and is_refine:
        raise ValueError("延续上一轮/继续优化暂不支持附带图片，请移除图片后重试")

    if not text and not images:
        raise ValueError("请输入提示词或添加参考图片")

    if images:
        analysis = analyze_images(images)
        merged_text = merge_image_context(text, analysis)
        storage = storage_label_with_images(storage_original, len(images))
        return merged_text, storage

    return text, storage_original


def _record_payload(record: PolishRecord, original: str, polished: str) -> dict:
    return {
        "original": original,
        "polished": polished,
        "record_id": record.id,
        "mode": record.mode,
        "status": record.status,
    }


@polish_bp.get("/api/modes")
def list_modes():
    return jsonify(
        {
            "modes": [
                {"id": key, "label": label}
                for key, label in MODE_LABELS.items()
            ]
        }
    )


@polish_bp.post("/api/polish")
@login_required
def polish():
    data = request.get_json(silent=True) or {}
    text, mode, storage_original, is_refine, direction, images_raw = _parse_polish_body(data)

    try:
        ai_text, storage_original = _prepare_polish_inputs(
            text, storage_original, is_refine, direction, images_raw
        )
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        error_msg, status_code = _map_ai_error(e, stage="vision" if images_raw else "")
        return jsonify({"error": error_msg}), status_code

    if is_refine:
        if not ai_text:
            return jsonify({"error": "当前提示词不能为空"}), 400
        if not direction:
            return jsonify({"error": "优化方向不能为空"}), 400
        if len(ai_text) > current_app.config["REFINE_POLISHED_MAX"]:
            return jsonify({"error": "当前提示词过长"}), 400
        if len(direction) > current_app.config["REFINE_DIRECTION_MAX"]:
            return jsonify({"error": "优化方向过长"}), 400
    else:
        if len(ai_text) > current_app.config["MAX_TEXT_LENGTH"] * 3:
            return jsonify({"error": "合并图片分析后文本过长，请减少图片或缩短描述"}), 400

    try:
        if is_refine:
            polished = polish_text_refine(ai_text, direction, mode=mode)
        else:
            polished = polish_text(ai_text, mode=mode)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        error_msg, status_code = _map_ai_error(e, stage="polish")
        _save_record(
            session["user_id"],
            storage_original,
            "",
            mode,
            status="failed",
            error_message=error_msg,
        )
        return jsonify({"error": error_msg}), status_code

    record = _save_record(session["user_id"], storage_original, polished, mode)
    return jsonify(_record_payload(record, storage_original, polished))


@polish_bp.post("/api/polish/stream")
@login_required
def polish_stream():
    data = request.get_json(silent=True) or {}
    text, mode, storage_original, is_refine, direction, images_raw = _parse_polish_body(data)

    try:
        ai_text, storage_original = _prepare_polish_inputs(
            text, storage_original, is_refine, direction, images_raw
        )
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        error_msg, status_code = _map_ai_error(e, stage="vision" if images_raw else "")
        return jsonify({"error": error_msg}), status_code

    if is_refine:
        if not ai_text:
            return jsonify({"error": "当前提示词不能为空"}), 400
        if not direction:
            return jsonify({"error": "优化方向不能为空"}), 400
        if len(ai_text) > current_app.config["REFINE_POLISHED_MAX"]:
            return jsonify({"error": "当前提示词过长"}), 400
        if len(direction) > current_app.config["REFINE_DIRECTION_MAX"]:
            return jsonify({"error": "优化方向过长"}), 400
    else:
        if len(ai_text) > current_app.config["MAX_TEXT_LENGTH"] * 3:
            return jsonify({"error": "合并图片分析后文本过长，请减少图片或缩短描述"}), 400

    user_id = session["user_id"]

    def generate():
        parts: list[str] = []
        try:
            if is_refine:
                stream_iter = polish_text_stream(
                    mode=mode, polished=ai_text, direction=direction
                )
            else:
                stream_iter = polish_text_stream(ai_text, mode=mode)
            for chunk in stream_iter:
                parts.append(chunk)
                yield f"data: {json.dumps({'chunk': chunk}, ensure_ascii=False)}\n\n"
            polished = "".join(parts)
            record = _save_record(user_id, storage_original, polished, mode)
            yield f"data: {json.dumps(_record_payload(record, storage_original, polished), ensure_ascii=False)}\n\n"
        except ValueError as e:
            yield f"data: {json.dumps({'error': str(e)}, ensure_ascii=False)}\n\n"
        except Exception as e:
            error_msg, _ = _map_ai_error(e, stage="polish")
            record = _save_record(
                user_id,
                storage_original,
                "",
                mode,
                status="failed",
                error_message=error_msg,
            )
            payload = {
                "error": error_msg,
                "record_id": record.id,
                "status": "failed",
            }
            yield f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"

    return Response(
        stream_with_context(generate()),
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
