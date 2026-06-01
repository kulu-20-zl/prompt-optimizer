from flask import Blueprint, current_app, jsonify, request, session

from backend.models import PolishRecord, db
from backend.services.pagination import paginate_records
from backend.services.prompt_modes import MODE_LABELS
from backend.services.rating import calculate_avg_rating, validate_rating
from backend.utils.auth import login_required

history_bp = Blueprint("history", __name__)


def _serialize_record(record: PolishRecord) -> dict:
    return {
        "id": record.id,
        "original": record.original_text,
        "polished": record.polished_text,
        "rating": record.rating,
        "status": record.status,
        "error_message": record.error_message,
        "mode": record.mode,
        "mode_label": MODE_LABELS.get(record.mode, record.mode),
        "created_at": record.created_at.isoformat() if record.created_at else None,
    }


@history_bp.get("/api/history")
@login_required
def history():
    try:
        page = int(request.args.get("page", 1))
        per_page = int(request.args.get("per_page", 10))
    except ValueError:
        return jsonify({"error": "分页参数无效"}), 400

    if page < 1:
        return jsonify({"error": "页码必须大于0"}), 400

    per_page = min(per_page, current_app.config["MAX_PER_PAGE"])
    items, total, pages = paginate_records(session["user_id"], page, per_page)

    return jsonify(
        {
            "items": [_serialize_record(r) for r in items],
            "total": total,
            "page": page,
            "pages": pages,
        }
    )


@history_bp.delete("/api/record/<int:record_id>")
@login_required
def delete_record(record_id):
    record = PolishRecord.query.get(record_id)
    if not record:
        return jsonify({"error": "记录不存在"}), 404
    if record.user_id != session["user_id"]:
        return jsonify({"error": "无权删除此记录"}), 403

    db.session.delete(record)
    db.session.commit()
    return jsonify({"message": "删除成功"})


@history_bp.post("/api/record/<int:record_id>/rate")
@login_required
def rate_record(record_id):
    record = PolishRecord.query.get(record_id)
    if not record:
        return jsonify({"error": "记录不存在"}), 404
    if record.user_id != session["user_id"]:
        return jsonify({"error": "无权评分此记录"}), 403
    if record.status != "success":
        return jsonify({"error": "失败记录无法评分"}), 400

    data = request.get_json(silent=True) or {}
    rating = data.get("rating")

    if not validate_rating(rating):
        return jsonify({"error": "评分必须在1-5之间"}), 400

    record.rating = int(rating)
    db.session.commit()

    new_avg = calculate_avg_rating(session["user_id"])
    return jsonify({"new_avg_rating": new_avg})
