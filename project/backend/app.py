import os
import sys

from flask import Flask, jsonify, send_from_directory

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from backend.config import Config
from backend.routes.auth import auth_bp
from backend.routes.history import history_bp
from backend.routes.polish import polish_bp
from backend.services.backup import backup_database
from backend.services.db_migrate import ensure_schema

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

    from backend.models import db

    db.init_app(app)

    with app.app_context():
        ensure_schema()

    @app.before_request
    def _ensure_database_tables():
        from sqlalchemy import inspect

        from backend.models import db

        inspector = inspect(db.engine)
        if "user" not in inspector.get_table_names():
            ensure_schema()

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

    app.register_blueprint(auth_bp)
    app.register_blueprint(polish_bp)
    app.register_blueprint(history_bp)

    return app


app = create_app()

if __name__ == "__main__":
    from backend.models import PolishRecord, User, db

    with app.app_context():
        if Config.ENABLE_DB_BACKUP:
            backup_path = backup_database(max_keep=Config.DB_BACKUP_KEEP)
            if backup_path:
                print(f"  数据库已备份: {backup_path}")

        users = User.query.count()
        records = PolishRecord.query.count()
        print("=" * 52)
        print("  AI 提示词优化助手已启动")
        print(f"  数据库: {Config.DB_FILE}")
        print(f"  已有用户: {users} 人 | 优化记录: {records} 条")
        print(f"  Debug: {'开' if Config.DEBUG else '关'}")
        print("  访问: http://127.0.0.1:5000")
        print("=" * 52)

    app.run(debug=Config.DEBUG, port=5000, use_reloader=Config.DEBUG)
