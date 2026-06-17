"""Tests for prompt module."""

from __future__ import annotations

from watchdigest_for_minimax.prompt import SYSTEM_PROMPT, build_chunk_prompt, build_merge_prompt


class TestSystemPrompt:
    def test_exists(self) -> None:
        assert isinstance(SYSTEM_PROMPT, str)
        assert len(SYSTEM_PROMPT) > 0


class TestBuildChunkPrompt:
    def test_contains_time_range(self) -> None:
        result = build_chunk_prompt(
            chunk_index=1,
            total_chunks=3,
            chunk_start_s=0,
            chunk_end_s=600,
        )
        assert "1/3" in result
        assert "00:00" in result
        assert "10:00" in result

    def test_contains_output_format(self) -> None:
        result = build_chunk_prompt(2, 6, 600, 1200)
        assert "时间线" in result
        assert "关键人物" in result


class TestBuildMergePrompt:
    def test_basic_merge(self) -> None:
        result = build_merge_prompt(
            chunk_summaries=["总结1", "总结2"],
            video_title="测试视频",
            uploader="UP主",
            duration_s=1200,
        )
        assert "测试视频" in result
        assert "UP主" in result
        assert "20:00" in result
        assert "总结1" in result
        assert "总结2" in result

    def test_single_chunk(self) -> None:
        result = build_merge_prompt(
            chunk_summaries=["唯一总结"],
            video_title="短视频",
            uploader="",
            duration_s=60,
        )
        assert "1" in result
        assert "唯一总结" in result
