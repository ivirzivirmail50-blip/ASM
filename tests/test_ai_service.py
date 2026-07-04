"""Tests for ai_service: disabled by default, opt-in behavior."""
import pytest
from unittest.mock import patch, MagicMock

from services import ai_service
from core.errors import AiDisabledError, AiProviderError


def test_ai_disabled_by_default():
    # Fresh DB has ai.enabled = false
    assert ai_service.is_enabled() is False


def test_generate_raises_when_disabled():
    with pytest.raises(AiDisabledError):
        ai_service.generate("test prompt")


def test_continue_writing_raises_when_disabled():
    with pytest.raises(AiDisabledError):
        ai_service.continue_writing("some text")


def test_summarize_raises_when_disabled():
    with pytest.raises(AiDisabledError):
        ai_service.summarize("text")


def test_rewrite_raises_when_disabled():
    with pytest.raises(AiDisabledError):
        ai_service.rewrite("text", "formal")


def test_suggest_tags_raises_when_disabled():
    with pytest.raises(AiDisabledError):
        ai_service.suggest_tags("text")


def test_generate_raises_when_no_model():
    """If enabled but no model configured, AiProviderError."""
    from core.db import write_transaction
    from models.settings import Setting
    with write_transaction() as s:
        Setting.set(s, "ai.enabled", True)
        Setting.set(s, "ai.model", "")
    with pytest.raises(AiProviderError):
        ai_service.generate("test")


def test_generate_ollama_calls_correct_url():
    from core.db import write_transaction
    from models.settings import Setting
    with write_transaction() as s:
        Setting.set(s, "ai.enabled", True)
        Setting.set(s, "ai.provider", "ollama")
        Setting.set(s, "ai.model", "llama3")
        Setting.set(s, "ai.api_base", "http://localhost:11434")

    mock_response = MagicMock()
    mock_response.json.return_value = {"response": "Generated text"}
    mock_response.raise_for_status = MagicMock()

    with patch("services.ai_service.requests.post", return_value=mock_response) as mock_post:
        result = ai_service.generate("hello", max_tokens=100, temperature=0.5)
        assert result == "Generated text"
        # Verify the URL was constructed correctly
        call_args = mock_post.call_args
        assert "localhost:11434" in call_args[0][0]
        assert "/api/generate" in call_args[0][0]


def test_generate_openai_compat_calls_chat_completions():
    from core.db import write_transaction
    from models.settings import Setting
    with write_transaction() as s:
        Setting.set(s, "ai.enabled", True)
        Setting.set(s, "ai.provider", "openai")
        Setting.set(s, "ai.model", "gpt-4o-mini")
        Setting.set(s, "ai.api_base", "https://api.openai.com")
        Setting.set(s, "ai.api_key", "sk-test")

    mock_response = MagicMock()
    mock_response.json.return_value = {
        "choices": [{"message": {"content": "OpenAI response"}}]
    }
    mock_response.raise_for_status = MagicMock()

    with patch("services.ai_service.requests.post", return_value=mock_response) as mock_post:
        result = ai_service.generate("hello")
        assert result == "OpenAI response"
        call_args = mock_post.call_args
        assert "/v1/chat/completions" in call_args[0][0]
        # API key should be in Authorization header
        assert call_args[1]["headers"]["Authorization"] == "Bearer sk-test"


def test_generate_provider_error_on_network_failure():
    from core.db import write_transaction
    from models.settings import Setting
    import requests as req
    with write_transaction() as s:
        Setting.set(s, "ai.enabled", True)
        Setting.set(s, "ai.provider", "ollama")
        Setting.set(s, "ai.model", "llama3")

    with patch("services.ai_service.requests.post",
               side_effect=req.RequestException("Network error")):
        with pytest.raises(AiProviderError):
            ai_service.generate("hello")
