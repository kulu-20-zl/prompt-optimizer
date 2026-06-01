import os
import sys

from flask import Flask, jsonify, request, session, send_from_directory

# Ensure project root is on path when running as script
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

import re

from sqlalchemy import inspect, text

from backend.config import Config
from backend.models import PolishRecord, User, db
from backend.services.ai_client import polish_text
from backend.services.pagination import paginate_records
from backend.services.rating import calculate_avg_rating, validate_rating

FRONTEND_DIR = os.path.join(PROJECT_ROOT, "frontend")


def create_app(config_class=Config):
    app = Flask(
        __name__,
        static_folder=os.path.join(FRONTEND_DIR, "static"),
        static_url_path="/static",
    )
    app.config.from_object(config_class)
    app.config["MOCK_AI"] = os.getenv("MOCK_AI", "0") == "1"
    app.config["MOCK_AI_DELAY"] = float(os.getenv("MOCK_AI_DELAY", "0"))

    db.init_app(app)

    def _init_database():
        db.create_all()
        _ensure_user_email_column()

    with app.app_context():
        _init_database()

    @app.before_request
    def _ensure_database_tables():
        """热重载后若表缺失则自动建表，避免 500。"""
        from sqlalchemy import inspect

        inspector = inspect(db.engine)
        if "user" not in inspector.get_table_names():
            _init_database()

    def login_required(f):
        from functools import wraps

        @wraps(f)
        def decorated(*args, **kwargs):
            if "user_id" not in session:
                return jsonify({"error": "未登录"}), 401
            return f(*args, **kwargs)

        return decorated

    @app.route("/")
    def index():
        return send_from_directory(FRONTEND_DIR, "index.html")

    @app.route("/register")
    def register_page():
        return send_from_directory(FRONTEND_DIR, "index.html")

    @app.route("/history")
    def history_page():
        return send_from_directory(FRONTEND_DIR, "index.html")

    @app.errorhandler(404)
    def not_found(_e):
        return jsonify({"error": "资源不存在"}), 404

    @app.errorhandler(500)
    def internal_error(_e):
        return jsonify({"error": "服务器内部错误"}), 500

    @app.post("/api/register")
    def register():
        data = request.get_json(silent=True) or {}
        username = (data.get("username") or "").strip()
        email = (data.get("email") or "").strip().lower()
        password = data.get("password") or ""
        confirm_password = data.get("confirm_password") or password

        error = _validate_registration(username, email, password, confirm_password)
        if error:
            return jsonify({"error": error}), 400
        if User.query.filter_by(username=username).first():
            return jsonify({"error": "用户名已存在"}), 409
        if User.query.filter_by(email=email).first():
            return jsonify({"error": "邮箱已被注册"}), 409

        user = User(username=username, email=email)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        print(
            f"  [数据库] 已注册用户 #{user.id}（{username}，库: {Config.DB_FILE}）"
        )
        return jsonify({"user_id": user.id, "message": "注册成功"}), 201

    @app.post("/api/forgot-password")
    def forgot_password():
        data = request.get_json(silent=True) or {}
        username = (data.get("username") or "").strip()
        email = (data.get("email") or "").strip().lower()
        new_password = data.get("new_password") or ""
        confirm_password = data.get("confirm_password") or ""

        if not username or not email:
            return jsonify({"error": "用户名和邮箱不能为空"}), 400
        if not _is_valid_email(email):
            return jsonify({"error": "邮箱格式不正确"}), 400
        if not new_password:
            return jsonify({"error": "新密码不能为空"}), 400
        if len(new_password) < 6:
            return jsonify({"error": "密码长度至少6位"}), 400
        if new_password != confirm_password:
            return jsonify({"error": "两次输入的密码不一致"}), 400

        user = User.query.filter_by(username=username).first()
        if not user or not user.email or user.email.lower() != email:
            return jsonify({"error": "用户名与邮箱不匹配"}), 404

        user.set_password(new_password)
        db.session.commit()
        return jsonify({"message": "密码重置成功，请使用新密码登录"})

    @app.post("/api/login")
    def login():
        data = request.get_json(silent=True) or {}
        username = (data.get("username") or "").strip()
        password = data.get("password") or ""

        if not password:
            return jsonify({"error": "密码不能为空"}), 400

        user = User.query.filter_by(username=username).first()
        if not user or not user.check_password(password):
            return jsonify({"error": "用户名或密码错误"}), 401

        session["user_id"] = user.id
        session["username"] = user.username
        return jsonify({"user_id": user.id, "message": "登录成功"})

    @app.post("/api/logout")
    def logout():
        session.clear()
        return jsonify({"message": "已登出"})

    @app.post("/api/polish")
    @login_required
    def polish():
        data = request.get_json(silent=True) or {}
        text = (data.get("text") or "").strip()

        if not text:
            return jsonify({"error": "文本不能为空"}), 400
        if len(text) > app.config["MAX_TEXT_LENGTH"]:
            return jsonify({"error": "文本过长，最多2000字符"}), 400

        try:
            polished = polish_text(text)
        except ValueError as e:
            return jsonify({"error": str(e)}), 400
        except Exception as e:
            msg = str(e)
            if "API_TIMEOUT" in msg:
                return jsonify({"error": "AI服务繁忙，请稍后重试"}), 503
            if "未设置 DEEPSEEK_API_KEY" in msg or "未设置 OPENAI_API_KEY" in msg:
                return jsonify({"error": msg.replace("API_ERROR: ", "")}), 503
            return jsonify({"error": "AI 服务异常，请检查 DeepSeek 代理配置（Key、地址、模型名）"}), 503

        record = PolishRecord(
            user_id=session["user_id"],
            original_text=text,
            polished_text=polished,
        )
        db.session.add(record)
        db.session.commit()
        print(
            f"  [数据库] 已写入 polish_record #{record.id} "
            f"（用户 {session['user_id']}，库: {app.config.get('DB_FILE', Config.DB_FILE)}）"
        )

        return jsonify(
            {
                "original": text,
                "polished": polished,
                "record_id": record.id,
            }
        )

    @app.get("/api/history")
    @login_required
    def history():
        try:
            page = int(request.args.get("page", 1))
            per_page = int(request.args.get("per_page", app.config["DEFAULT_PER_PAGE"]))
        except ValueError:
            return jsonify({"error": "分页参数无效"}), 400

        if page < 1:
            return jsonify({"error": "页码必须大于0"}), 400

        per_page = min(per_page, app.config["MAX_PER_PAGE"])
        items, total, pages = paginate_records(session["user_id"], page, per_page)

        return jsonify(
            {
                "items": [
                    {
                        "id": r.id,
                        "original": r.original_text,
                        "polished": r.polished_text,
                        "rating": r.rating,
                        "created_at": r.created_at.isoformat() if r.created_at else None,
                    }
                    for r in items
                ],
                "total": total,
                "page": page,
                "pages": pages,
            }
        )

    @app.delete("/api/record/<int:record_id>")
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

    @app.post("/api/record/<int:record_id>/rate")
    @login_required
    def rate_record(record_id):
        record = PolishRecord.query.get(record_id)
        if not record:
            return jsonify({"error": "记录不存在"}), 404
        if record.user_id != session["user_id"]:
            return jsonify({"error": "无权评分此记录"}), 403

        data = request.get_json(silent=True) or {}
        rating = data.get("rating")

        if not validate_rating(rating):
            return jsonify({"error": "评分必须在1-5之间"}), 400

        record.rating = int(rating)
        db.session.commit()

        new_avg = calculate_avg_rating(session["user_id"])
        return jsonify({"new_avg_rating": new_avg})

    return app


def _is_valid_email(email: str) -> bool:
    return bool(re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email))


def _validate_registration(username, email, password, confirm_password):
    if not username:
        return "用户名不能为空"
    if len(username) < 3:
        return "用户名至少3个字符"
    if not email:
        return "邮箱不能为空"
    if not _is_valid_email(email):
        return "邮箱格式不正确"
    if not password:
        return "密码不能为空"
    if len(password) < 6:
        return "密码长度至少6位"
    if password != confirm_password:
        return "两次输入的密码不一致"
    return None


def _ensure_user_email_column():
    inspector = inspect(db.engine)
    if "user" not in inspector.get_table_names():
        return
    columns = {column["name"] for column in inspector.get_columns("user")}
    if "email" not in columns:
        with db.engine.begin() as conn:
            conn.execute(text("ALTER TABLE user ADD COLUMN email VARCHAR(120)"))


app = create_app()

if __name__ == "__main__":
    from backend.config import Config as AppConfig

    with app.app_context():
        users = User.query.count()
        records = PolishRecord.query.count()
        print("=" * 52)
        print("  AI 提示词优化助手已启动")
        print(f"  数据库: {AppConfig.DB_FILE}")
        print(f"  已有用户: {users} 人 | 优化记录: {records} 条")
        print("  访问: http://127.0.0.1:5000")
        print("=" * 52)
    app.run(debug=True, port=5000)
