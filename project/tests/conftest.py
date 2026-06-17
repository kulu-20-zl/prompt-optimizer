import os
import sys

import pytest

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

os.environ["MOCK_AI"] = "1"
os.environ["MOCK_AI_DELAY"] = "0"

from backend.app import create_app
from backend.models import User, db


@pytest.fixture
def app():
    app = create_app(
        config_overrides={
            "TESTING": True,
            "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
            "SECRET_KEY": "test-secret",
            "WTF_CSRF_ENABLED": False,
        }
    )
    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def db_session(app):
    with app.app_context():
        yield db.session
        db.session.rollback()


@pytest.fixture
def mock_openai(monkeypatch):
    mock_result = (
        "你是一位资深内容创作专家。请撰写一篇关于气候变化的文章，"
        "要求：1) 字数800字左右；2) 包含科学依据；3) 结构为引言、现状分析、对策建议、结语；"
        "4) 语言通俗易懂。"
    )

    def fake_polish(text, mode="general"):
        if len(text) > 2000:
            raise ValueError("文本过长")
        return mock_result

    def fake_polish_refine(polished, direction, mode="general"):
        if not polished.strip():
            raise ValueError("当前提示词不能为空")
        if not direction.strip():
            raise ValueError("优化方向不能为空")
        return (
            f"{mock_result}\n\n"
            f"【已落实优化方向】{direction.strip()[:120]}"
        )

    def fake_polish_stream(text="", mode="general", *, polished=None, direction=None):
        if polished is not None and direction is not None:
            full = fake_polish_refine(polished, direction, mode)
        else:
            full = fake_polish(text, mode)
        for i in range(0, len(full), 16):
            yield full[i : i + 16]

    from backend.services import ai_client

    monkeypatch.setattr(ai_client, "polish_text", fake_polish)
    monkeypatch.setattr(ai_client, "polish_text_refine", fake_polish_refine)
    monkeypatch.setattr(ai_client, "polish_text_stream", fake_polish_stream)

    def fake_analyze_images(images):
        return "【图片1】模拟界面截图：含登录表单与优化对话区域。"

    from backend.services import image_analyzer

    monkeypatch.setattr(image_analyzer, "analyze_images", fake_analyze_images)
    return fake_polish


@pytest.fixture
def logged_in_user(app, db_session):
    user = User(username="testuser", email="testuser@example.com")
    user.set_password("password123")
    db_session.add(user)
    db_session.commit()
    return user


@pytest.fixture
def logged_in_client(client, logged_in_user):
    client.post(
        "/api/login",
        json={"username": "testuser", "password": "password123"},
    )
    return client


@pytest.fixture
def logged_in_headers(logged_in_client):
    return {}
