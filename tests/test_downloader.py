"""Tests for downloader module (URL parsing only, no actual downloads)."""

from __future__ import annotations

from watchdigest_for_minimax.downloader import parse_douyin_share


class TestParseDouyinShare:
    def test_standard_share_text(self) -> None:
        text = "7.99 复制打开抖音，看看【XXX】https://v.douyin.com/abc/"
        result = parse_douyin_share(text)
        assert result == "https://v.douyin.com/abc"

    def test_url_with_trailing_text(self) -> None:
        text = "看看 https://v.douyin.com/xyz/ 你看"
        result = parse_douyin_share(text)
        assert result == "https://v.douyin.com/xyz"

    def test_no_url(self) -> None:
        assert parse_douyin_share("这里没有 URL") is None

    def test_douyin_video_url(self) -> None:
        text = "https://www.douyin.com/video/123456789"
        result = parse_douyin_share(text)
        assert result == "https://www.douyin.com/video/123456789"

    def test_share_text_no_trailing_slash(self) -> None:
        text = "7.99 复制打开抖音 https://v.douyin.com/abc"
        result = parse_douyin_share(text)
        assert result == "https://v.douyin.com/abc"
