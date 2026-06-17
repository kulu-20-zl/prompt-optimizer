import base64

import pytest

from backend.services import image_analyzer

PNG_1X1 = (
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
)


def test_polish_with_image_stream(logged_in_client, mock_openai):
    resp = logged_in_client.post(
        "/api/polish/stream",
        json={
            "text": "根据截图写一段生成类似界面的提示词",
            "mode": "general",
            "images": [
                {
                    "name": "ui.png",
                    "mime": "image/png",
                    "data": PNG_1X1,
                }
            ],
        },
    )
    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert "record_id" in body
    assert "error" not in body or body.count("error") == 0


def test_polish_image_only(logged_in_client, mock_openai):
    resp = logged_in_client.post(
        "/api/polish",
        json={
            "text": "",
            "mode": "general",
            "images": [{"mime": "image/png", "data": PNG_1X1}],
        },
    )
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["record_id"]
    assert "含参考图" in data["original"] or "参考图" in data["original"]


def test_refine_with_image_rejected(logged_in_client, mock_openai):
    resp = logged_in_client.post(
        "/api/polish",
        json={
            "refine": True,
            "polished": "你是一位助手。请完成任务。",
            "direction": "更简短",
            "images": [{"mime": "image/png", "data": PNG_1X1}],
        },
    )
    assert resp.status_code == 400
    assert "不支持" in resp.get_json()["error"]


def test_normalize_image_rejects_oversize():
    big = base64.b64encode(b"x" * (5 * 1024 * 1024)).decode()
    with pytest.raises(ValueError, match="不能超过"):
        image_analyzer.normalize_image_item(
            {"mime": "image/png", "data": big},
            max_bytes=4 * 1024 * 1024,
        )
