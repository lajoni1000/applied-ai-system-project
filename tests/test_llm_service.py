"""Tests for src/llm_service.py.

The Gemini client is always mocked, so these tests never touch the network or
require a real GEMINI_API_KEY.
"""

from unittest.mock import MagicMock

import pytest

from src import llm_service
from src.llm_service import LLMServiceError, generate_explanation

SAMPLE_CONTEXT = (
    "User Preferences:\n- Favorite Genre: lofi\n\n"
    'Retrieved Songs:\n1. "Library Rain" by Paper Lanterns'
)


def install_fake_client(monkeypatch, *, text=None, raise_exc=None) -> MagicMock:
    """Patch genai.Client so generate_content returns `text` or raises `raise_exc`."""
    client = MagicMock()
    if raise_exc is not None:
        client.models.generate_content.side_effect = raise_exc
    else:
        response = MagicMock()
        response.text = text
        client.models.generate_content.return_value = response

    # _build_client calls genai.Client(api_key=...); return our fake instead.
    monkeypatch.setattr(llm_service.genai, "Client", lambda api_key=None: client)
    return client


def test_empty_context_raises():
    with pytest.raises(LLMServiceError):
        generate_explanation("   ")


def test_non_string_context_raises():
    with pytest.raises(LLMServiceError):
        generate_explanation(None)  # type: ignore[arg-type]


def test_missing_api_key_raises(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    # Even with a client patched in, the missing key must fail before any call.
    client = install_fake_client(monkeypatch, text="should not be used")

    with pytest.raises(LLMServiceError):
        generate_explanation(SAMPLE_CONTEXT)

    client.models.generate_content.assert_not_called()


def test_successful_generation_returns_text(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "fake-key")
    client = install_fake_client(monkeypatch, text="  Library Rain is a cozy lofi pick for you.  ")

    result = generate_explanation(SAMPLE_CONTEXT)

    assert result == "Library Rain is a cozy lofi pick for you."
    # The grounded context must actually be sent to the model.
    _, kwargs = client.models.generate_content.call_args
    assert SAMPLE_CONTEXT in kwargs["contents"]


def test_empty_gemini_response_raises(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "fake-key")
    install_fake_client(monkeypatch, text="")

    with pytest.raises(LLMServiceError):
        generate_explanation(SAMPLE_CONTEXT)


def test_none_gemini_response_raises(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "fake-key")
    install_fake_client(monkeypatch, text=None)

    with pytest.raises(LLMServiceError):
        generate_explanation(SAMPLE_CONTEXT)


def test_gemini_exception_becomes_llm_service_error(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "fake-key")
    install_fake_client(monkeypatch, raise_exc=RuntimeError("boom"))

    with pytest.raises(LLMServiceError) as excinfo:
        generate_explanation(SAMPLE_CONTEXT)

    # The original SDK error should be preserved as the cause.
    assert isinstance(excinfo.value.__cause__, RuntimeError)


def test_whitespace_only_gemini_response_raises(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "fake-key")
    install_fake_client(monkeypatch, text="   \n   ")

    with pytest.raises(LLMServiceError):
        generate_explanation(SAMPLE_CONTEXT)