"""Tests for analyzer module."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from watchdigest_for_minimax.analyzer import get_public_url


class TestGetPublicUrl:
    def test_default_host(self) -> None:
        url = get_public_url("chunk_000.mp4")
        assert "8.136.148.185" in url
        assert "41234" in url
        assert "chunk_000.mp4" in url

    def test_custom_host_port(self) -> None:
        url = get_public_url("test.mp4", host="1.2.3.4", port=8080)
        assert url == "http://1.2.3.4:8080/test.mp4"

    def test_url_encoding(self) -> None:
        url = get_public_url("my file.mp4")
        assert "my%20file.mp4" in url


class TestCallMinimaxNative:
    @patch("watchdigest_for_minimax.analyzer.get_api_key", return_value="test-key")
    @patch("watchdigest_for_minimax.analyzer.get_base_url", return_value="https://api.minimaxi.com/anthropic")
    @patch("watchdigest_for_minimax.analyzer.urllib.request.urlopen")
    def test_success(self, mock_urlopen: MagicMock, mock_base: object, mock_key: object) -> None:
        import json

        response_data = {
            "base_resp": {"status_code": 0, "status_msg": "success"},
            "choices": [{"message": {"content": "test summary"}}],
        }
        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps(response_data).encode("utf-8")
        mock_resp.__enter__ = MagicMock(return_value=mock_resp)
        mock_resp.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_resp

        from watchdigest_for_minimax.analyzer import call_minimax_native

        result = call_minimax_native(messages=[{"role": "user", "content": "test"}])
        assert result["choices"][0]["message"]["content"] == "test summary"  # type: ignore[index]
