"""Tests for prompt module."""

from __future__ import annotations

from watchdigest_for_minimax.prompt import SYSTEM_PROMPT, build_user_prompt


class TestSystemPrompt:
    def test_exists(self) -> None:
        assert isinstance(SYSTEM_PROMPT, str)
        assert len(SYSTEM_PROMPT) > 0


class TestBuildUserPrompt:
    def test_full_video_prompt(self) -> None:
        result = build_user_prompt("23:45")
        assert "23:45" in result
        assert "一句话总览" in result

    def test_chunk_prompt_contains_time_range(self) -> None:
        result = build_user_prompt(
            "30:00",
            is_chunk=True,
            chunk_index=1,
            total_chunks=3,
            chunk_start_s=0,
            chunk_end_s=600,
        )
        assert "1/3" in result
        assert "00:00" in result
        assert "10:00" in result

    def test_chunk_prompt_with_offset(self) -> None:
        result = build_user_prompt(
            "1:00:00",
            is_chunk=True,
            chunk_index=2,
            total_chunks=6,
            chunk_start_s=600,
            chunk_end_s=1200,
        )
        assert "2/6" in result
        assert "10:00" in result
        assert "20:00" in result
