"""轻量 schema 迁移：为已有 SQLite 库补列。"""

from sqlalchemy import inspect, text

from backend.models import db

_POLISH_COLUMNS = (
    ("status", "VARCHAR(20) DEFAULT 'success'"),
    ("error_message", "TEXT"),
    ("mode", "VARCHAR(32) DEFAULT 'general'"),
)


def ensure_schema() -> None:
    inspector = inspect(db.engine)
    if "user" not in inspector.get_table_names():
        db.create_all()
        return

    user_columns = {c["name"] for c in inspector.get_columns("user")}
    if "email" not in user_columns:
        with db.engine.begin() as conn:
            conn.execute(text("ALTER TABLE user ADD COLUMN email VARCHAR(120)"))

    if "polish_record" not in inspector.get_table_names():
        db.create_all()
        return

    polish_columns = {c["name"] for c in inspector.get_columns("polish_record")}
    with db.engine.begin() as conn:
        for name, col_type in _POLISH_COLUMNS:
            if name not in polish_columns:
                conn.execute(
                    text(f"ALTER TABLE polish_record ADD COLUMN {name} {col_type}")
                )
