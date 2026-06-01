import json

from flask import Blueprint, Response, current_app, jsonify, request, session, stream_with_context

from backend.config import Config
from backend.models import PolishRecord, db
from backend.services.ai_client import polish_text, polish_text_refine, polish_text_stream
from backend.services.prompt_modes import MODE_LABELS, normalize_mode
from backend.utils.auth import login_required

polish_bp = Blueprint("polish", __name__)


def _map_ai_error(exc: Exception) -> tuple[str, int]:
    msg = str(exc)
    if "API_TIMEOUT" in msg:
        return "AI服务繁忙，请稍后重试", 503
    if "未设置 DEEPSEEK_API_KEY" in msg or "未设置 OPENAI_API_KEY" in msg:
        return msg.replace("API_ERROR: ", ""), 503
    return "AI 服务异常，请检查 DeepSeek 代理配置（Key、地址、模型名）", 503


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


def _parse_polish_body(data: dict) -> tuple[str, str, str, bool, str | None]:
    """Returns text, mode, storage_original, is_refine, refine_direction."""
    mode = normalize_mode(data.get("mode"))
    is_refine = bool(data.get("refine"))

    if is_refine:
        polished_base = (data.get("polished") or "").strip()
        direction = (data.get("direction") or "").strip()
        storage = (data.get("display_original") or "").strip()
        if not storage:
            storage = f"【继续优化】\n优化方向：{direction}"
        return polished_base, mode, storage, True, direction

    text = (data.get("text") or "").strip()
    return text, mode, text, False, None


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
    text, mode, storage_original, is_refine, direction = _parse_polish_body(data)

    if is_refine:
        if not text:
            return jsonify({"error": "当前提示词不能为空"}), 400
        if not direction:
            return jsonify({"error": "优化方向不能为空"}), 400
        if len(text) > current_app.config["REFINE_POLISHED_MAX"]:
            return jsonify({"error": "当前提示词过长"}), 400
        if len(direction) > current_app.config["REFINE_DIRECTION_MAX"]:
            return jsonify({"error": "优化方向过长"}), 400
    else:
        if not text:
            return jsonify({"error": "文本不能为空"}), 400
        if len(text) > current_app.config["MAX_TEXT_LENGTH"]:
            return jsonify({"error": "文本过长，最多2000字符"}), 400

    try:
        if is_refine:
            polished = polish_text_refine(text, direction, mode=mode)
        else:
            polished = polish_text(text, mode=mode)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        error_msg, status_code = _map_ai_error(e)
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
    text, mode, storage_original, is_refine, direction = _parse_polish_body(data)

    if is_refine:
        if not text:
            return jsonify({"error": "当前提示词不能为空"}), 400
        if not direction:
            return jsonify({"error": "优化方向不能为空"}), 400
        if len(text) > current_app.config["REFINE_POLISHED_MAX"]:
            return jsonify({"error": "当前提示词过长"}), 400
        if len(direction) > current_app.config["REFINE_DIRECTION_MAX"]:
            return jsonify({"error": "优化方向过长"}), 400
    else:
        if not text:
            return jsonify({"error": "文本不能为空"}), 400
        if len(text) > current_app.config["MAX_TEXT_LENGTH"]:
            return jsonify({"error": "文本过长，最多2000字符"}), 400

    user_id = session["user_id"]

    def generate():
        parts: list[str] = []
        try:
            if is_refine:
                stream_iter = polish_text_stream(
                    mode=mode, polished=text, direction=direction
                )
            else:
                stream_iter = polish_text_stream(text, mode=mode)
            for chunk in stream_iter:
                parts.append(chunk)
                yield f"data: {json.dumps({'chunk': chunk}, ensure_ascii=False)}\n\n"
            polished = "".join(parts)
            record = _save_record(user_id, storage_original, polished, mode)
            yield f"data: {json.dumps(_record_payload(record, storage_original, polished), ensure_ascii=False)}\n\n"
        except ValueError as e:
            yield f"data: {json.dumps({'error': str(e)}, ensure_ascii=False)}\n\n"
        except Exception as e:
            error_msg, _ = _map_ai_error(e)
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
