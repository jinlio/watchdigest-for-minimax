"""Tests for config module."""

from __future__ import annotations

import pytest

from watchdigest_for_minimax.config import get_api_key, get_pricing


class TestGetApiKey:
    def test_reads_anthropic_api_key(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key-123")
        monkeypatch.delenv("ANTHROPIC_AUTH_TOKEN", raising=False)
        assert get_api_key() == "test-key-123"

    def test_fallback_to_auth_token(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        monkeypatch.setenv("ANTHROPIC_AUTH_TOKEN", "fallback-token")
        assert get_api_key() == "fallback-token"

    def test_raises_when_no_key(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        monkeypatch.delenv("ANTHROPIC_AUTH_TOKEN", raising=False)
        with pytest.raises(RuntimeError, match="ANTHROPIC_API_KEY"):
            get_api_key()


class TestGetPricing:
    def test_default_pricing(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("WATCHDIGEST_INPUT_PRICE", raising=False)
        monkeypatch.delenv("WATCHDIGEST_OUTPUT_PRICE", raising=False)
        pricing = get_pricing()
        assert pricing["input_per_million"] == pytest.approx(2.10)
        assert pricing["output_per_million"] == pytest.approx(8.40)

    def test_custom_pricing(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("WATCHDIGEST_INPUT_PRICE", "3.00")
        monkeypatch.setenv("WATCHDIGEST_OUTPUT_PRICE", "10.00")
        pricing = get_pricing()
        assert pricing["input_per_million"] == pytest.approx(3.00)
        assert pricing["output_per_million"] == pytest.approx(10.00)
