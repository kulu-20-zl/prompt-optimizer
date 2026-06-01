import pytest

from backend.models import PolishRecord
from backend.services.ai_client import MOCK_RESULT


def test_polish_success(logged_in_client, mock_openai):
    original = "写一篇关于气候变化的文章"
    response = logged_in_client.post(
        "/api/polish", json={"text": original, "mode": "writing"}
    )
    assert response.status_code == 200
    data = response.get_json()
    assert data["polished"] == MOCK_RESULT
    assert data["original"] == original
    assert data["mode"] == "writing"
    assert data["status"] == "success"
    assert "record_id" in data

    record = PolishRecord.query.filter_by(original_text=original).first()
    assert record is not None
    assert record.mode == "writing"


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
    def timeout_polish(_text, mode="general"):
        raise Exception("API_TIMEOUT")

    monkeypatch.setattr("backend.routes.polish.polish_text", timeout_polish)
    response = logged_in_client.post(
        "/api/polish", json={"text": "写一篇关于 AI 的博客文章"}
    )
    assert response.status_code == 503
    assert "繁忙" in response.get_json()["error"]

    record = PolishRecord.query.order_by(PolishRecord.id.desc()).first()
    assert record.status == "failed"
    assert record.error_message


def test_polish_generic_api_error(logged_in_client, monkeypatch):
    def error_polish(_text, mode="general"):
        raise Exception("API_ERROR: something")

    monkeypatch.setattr("backend.routes.polish.polish_text", error_polish)
    response = logged_in_client.post(
        "/api/polish", json={"text": "给我一些健康饮食的建议"}
    )
    assert response.status_code == 503
    assert "异常" in response.get_json()["error"]


def test_polish_refine_stream_success(logged_in_client, mock_openai):
    polished = "请分别调研情绪识别与人格分析，输出对比表格。"
    direction = "已定 FunASR 与 PKU，只要链接和分析"
    response = logged_in_client.post(
        "/api/polish/stream",
        json={
            "refine": True,
            "polished": polished,
            "direction": direction,
            "display_original": f"【继续优化】\n优化方向：{direction}",
            "mode": "code",
        },
    )
    assert response.status_code == 200
    body = response.get_data(as_text=True)
    assert "record_id" in body
    assert "已落实优化方向" in body
    assert direction[:20] in body

    record = PolishRecord.query.order_by(PolishRecord.id.desc()).first()
    assert "继续优化" in record.original_text
    assert "已落实优化方向" in record.polished_text


def test_polish_stream_success(logged_in_client, mock_openai):
    response = logged_in_client.post(
        "/api/polish/stream",
        json={"text": "写一段 Python 爬虫提示词", "mode": "code"},
    )
    assert response.status_code == 200
    body = response.get_data(as_text=True)
    assert "data:" in body
    assert "气候变化" in body
    assert "record_id" in body


def test_list_modes(client):
    response = client.get("/api/modes")
    assert response.status_code == 200
    modes = response.get_json()["modes"]
    assert any(m["id"] == "code" for m in modes)
