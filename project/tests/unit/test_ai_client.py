import os
import time
from unittest.mock import MagicMock, patch

import pytest

from backend.services import ai_client


class TestPolishTextMock:
    def test_mock_ai_returns_fixed_text(self, monkeypatch):
        monkeypatch.setenv("MOCK_AI", "1")
        monkeypatch.setenv("MOCK_AI_DELAY", "0")
        result = ai_client.polish_text("Hello world")
        assert result == ai_client.MOCK_RESULT

    def test_mock_ai_with_delay(self, monkeypatch):
        monkeypatch.setenv("MOCK_AI", "1")
        monkeypatch.setenv("MOCK_AI_DELAY", "0.1")
        start = time.time()
        ai_client.polish_text("Hello")
        elapsed = time.time() - start
        assert elapsed >= 0.09

    def test_text_too_long_raises(self, monkeypatch):
        monkeypatch.setenv("MOCK_AI", "1")
        with pytest.raises(ValueError, match="文本过长"):
            ai_client.polish_text("x" * 2001)

    def test_boundary_2000_chars_ok(self, monkeypatch):
        monkeypatch.setenv("MOCK_AI", "1")
        result = ai_client.polish_text("a" * 2000)
        assert result == ai_client.MOCK_RESULT

    def test_boundary_2001_chars_fails(self, monkeypatch):
        monkeypatch.setenv("MOCK_AI", "1")
        with pytest.raises(ValueError):
            ai_client.polish_text("a" * 2001)


class TestPolishTextRealApiMocked:
    def test_api_timeout_raises(self, monkeypatch):
        monkeypatch.delenv("MOCK_AI", raising=False)

        mock_client = MagicMock()
        mock_client.chat.completions.create.side_effect = ai_client.APITimeoutError(
            request=MagicMock()
        )
        monkeypatch.setattr(ai_client, "_client", mock_client)

        with pytest.raises(Exception, match="API_TIMEOUT"):
            ai_client.polish_text("test text")

    def test_api_error_raises(self, monkeypatch):
        monkeypatch.delenv("MOCK_AI", raising=False)

        mock_client = MagicMock()
        mock_client.chat.completions.create.side_effect = RuntimeError("network fail")
        monkeypatch.setattr(ai_client, "_client", mock_client)

        with pytest.raises(Exception, match="API_ERROR"):
            ai_client.polish_text("test text")

    def test_strips_whitespace_from_response(self, monkeypatch):
        monkeypatch.delenv("MOCK_AI", raising=False)

        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "  Polished text  \n"

        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = mock_response
        monkeypatch.setattr(ai_client, "_client", mock_client)

        result = ai_client.polish_text("input")
        assert result == "Polished text"


class TestLooksLikeDirectAnswer:
    def test_detects_research_answer(self):
        sample = (
            "- **情绪识别**\n"
            "  - **研究方向**\n"
            "  - **关键论文**\n"
            "    - Poria et al., 2019\n"
            "  - **开源代码**\n"
            "    - https://github.com/huggingface/transformers\n"
            "    - https://github.com/speechbrain/speechbrain\n"
        )
        assert ai_client.looks_like_direct_answer(sample) is True

    def test_prompt_style_not_detected(self):
        sample = (
            "你是一位研究助理。请梳理情绪与人格相关研究，"
            "输出分情绪识别与人格分析两节，每节说明研究方向与文献检索要点。"
        )
        assert ai_client.looks_like_direct_answer(sample) is False
