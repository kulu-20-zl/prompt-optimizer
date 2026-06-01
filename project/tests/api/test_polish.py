from backend.models import PolishRecord
from backend.services.ai_client import MOCK_RESULT


def test_polish_success(logged_in_client, mock_openai):
    original = "写一篇关于气候变化的文章"
    response = logged_in_client.post(
        "/api/polish", json={"text": original}
    )
    assert response.status_code == 200
    data = response.get_json()
    assert data["polished"] == MOCK_RESULT
    assert data["original"] == original
    assert "record_id" in data

    record = PolishRecord.query.filter_by(original_text=original).first()
    assert record is not None


def test_polish_not_logged_in(client, mock_openai):
    response = client.post("/api/polish", json={"text": "给我一些营销点子"})
    assert response.status_code == 401


def test_polish_empty_text(logged_in_client, mock_openai):
    response = logged_in_client.post("/api/polish", json={"text": ""})
    assert response.status_code == 400


def test_polish_text_too_long(logged_in_client, mock_openai):
    response = logged_in_client.post(
        "/api/polish", json={"text": "x" * 2001}
    )
    assert response.status_code == 400


def test_polish_ai_timeout(logged_in_client, monkeypatch):
    def timeout_polish(_text):
        raise Exception("API_TIMEOUT")

    monkeypatch.setattr("backend.app.polish_text", timeout_polish)
    response = logged_in_client.post(
        "/api/polish", json={"text": "写一篇关于 AI 的博客文章"}
    )
    assert response.status_code == 503
    assert "繁忙" in response.get_json()["error"]


def test_polish_generic_api_error(logged_in_client, monkeypatch):
    def error_polish(_text):
        raise Exception("API_ERROR: something")

    monkeypatch.setattr("backend.app.polish_text", error_polish)
    response = logged_in_client.post(
        "/api/polish", json={"text": "给我一些健康饮食的建议"}
    )
    assert response.status_code == 503
    assert "异常" in response.get_json()["error"]
