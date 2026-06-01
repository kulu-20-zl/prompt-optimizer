from functools import wraps

from flask import jsonify, session


def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if "user_id" not in session:
            return jsonify({"error": "未登录"}), 401
        return f(*args, **kwargs)

    return decorated
