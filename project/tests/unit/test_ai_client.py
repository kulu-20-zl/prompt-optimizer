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
        create_kwargs = mock_client.chat.completions.create.call_args.kwargs
        assert create_kwargs.get("stream") is not True
        assert create_kwargs["max_tokens"] == 1200


class TestPolishTextStream:
    def test_stream_yields_incremental_chunks(self, monkeypatch):
        monkeypatch.delenv("MOCK_AI", raising=False)

        class FakeDelta:
            def __init__(self, content):
                self.content = content

        class FakeChoice:
            def __init__(self, content):
                self.delta = FakeDelta(content)

        class FakeChunk:
            def __init__(self, content):
                self.choices = [FakeChoice(content)]

        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = [
            FakeChunk("你"),
            FakeChunk("是"),
            FakeChunk("一位"),
        ]
        monkeypatch.setattr(ai_client, "_client", mock_client)

        chunks = list(ai_client.polish_text_stream("写小说", mode="writing"))
        assert chunks == ["你", "是", "一位"]
        create_kwargs = mock_client.chat.completions.create.call_args.kwargs
        assert create_kwargs["stream"] is True


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


class TestLooksLikeReasoningTrace:
    def test_detects_chain_of_thought(self):
        sample = (
            "首先，我需要理解用户的优化方向。用户已经确定 FunASR 和 PKU，"
            "接下来我将分析如何在提示词中落实这些要求。"
        )
        assert ai_client.looks_like_reasoning_trace(sample) is True

    def test_prompt_style_not_detected(self):
        sample = (
            "你是一位研究助理。请针对 FunASR（情绪识别）与 PKU 人格分析方案，"
            "分别给出完整 https 链接，并分析代码与论文。输出须含对比表格。"
        )
        assert ai_client.looks_like_reasoning_trace(sample) is False


class TestPolishTextRefineMock:
    def test_refine_mock_returns_prompt(self, monkeypatch):
        monkeypatch.setenv("MOCK_AI", "1")
        result = ai_client.polish_text_refine(
            "请调研情绪与人格两个方向。",
            "已定 FunASR 与 PKU，要链接和分析",
            mode="code",
        )
        assert "FunASR" in result
        assert "https" in result
        assert result.startswith("你是一位")

    def test_refine_empty_direction_raises(self, monkeypatch):
        monkeypatch.setenv("MOCK_AI", "1")
        with pytest.raises(ValueError, match="优化方向"):
            ai_client.polish_text_refine("已有提示词", "  ", mode="general")
