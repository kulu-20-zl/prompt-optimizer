from flask import Blueprint, current_app, jsonify, request, session

from backend.config import Config
from backend.models import User, db
from backend.services.rate_limit import is_rate_limited, reset_rate_limit
from backend.utils.auth import login_required
from backend.utils.validators import validate_registration

auth_bp = Blueprint("auth", __name__)


@auth_bp.get("/api/me")
def me():
    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"logged_in": False}), 401
    user = User.query.get(user_id)
    if not user:
        session.clear()
        return jsonify({"logged_in": False}), 401
    return jsonify(
        {
            "logged_in": True,
            "user_id": user.id,
            "username": user.username,
        }
    )


@auth_bp.post("/api/register")
def register():
    data = request.get_json(silent=True) or {}
    username = (data.get("username") or "").strip()
    email = (data.get("email") or "").strip().lower()
    password = data.get("password") or ""
    confirm_password = data.get("confirm_password") or password

    error = validate_registration(username, email, password, confirm_password)
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
    print(f"  [数据库] 已注册用户 #{user.id}（{username}，库: {Config.DB_FILE}）")
    return jsonify({"user_id": user.id, "message": "注册成功"}), 201


@auth_bp.post("/api/forgot-password")
def forgot_password():
    data = request.get_json(silent=True) or {}
    username = (data.get("username") or "").strip()
    email = (data.get("email") or "").strip().lower()
    new_password = data.get("new_password") or ""
    confirm_password = data.get("confirm_password") or ""

    if not username or not email:
        return jsonify({"error": "用户名和邮箱不能为空"}), 400
    from backend.utils.validators import is_valid_email

    if not is_valid_email(email):
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


@auth_bp.post("/api/login")
def login():
    ip = request.remote_addr or "unknown"
    limit_key = f"login:{ip}"
    if is_rate_limited(
        limit_key,
        current_app.config["LOGIN_RATE_LIMIT"],
        current_app.config["LOGIN_RATE_WINDOW"],
    ):
        return jsonify({"error": "登录尝试过于频繁，请稍后再试"}), 429

    data = request.get_json(silent=True) or {}
    username = (data.get("username") or "").strip()
    password = data.get("password") or ""

    if not password:
        return jsonify({"error": "密码不能为空"}), 400

    user = User.query.filter_by(username=username).first()
    if not user or not user.check_password(password):
        return jsonify({"error": "用户名或密码错误"}), 401

    reset_rate_limit(limit_key)
    session["user_id"] = user.id
    session["username"] = user.username
    return jsonify({"user_id": user.id, "username": user.username, "message": "登录成功"})


@auth_bp.post("/api/logout")
def logout():
    session.clear()
    return jsonify({"message": "已登出"})
