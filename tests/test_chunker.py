"""Tests for chunker module."""

from __future__ import annotations

from watchdigest_for_minimax.chunker import chunk_frames, estimate_tokens


class TestEstimateTokens:
    def test_basic_estimate(self) -> None:
        assert estimate_tokens(100) == 25600

    def test_zero_frames(self) -> None:
        assert estimate_tokens(0) == 0


class TestChunkFrames:
    def test_small_video_single_chunk(self) -> None:
        frames = ["f"] * 10
        result = chunk_frames(frames, fps=1.0)
        assert len(result) == 1
        chunk, start_s, end_s = result[0]
        assert len(chunk) == 10
        assert start_s == 0.0
        assert end_s == 10.0

    def test_exact_one_chunk_boundary(self) -> None:
        frames = ["f"] * 600
        result = chunk_frames(frames, fps=1.0)
        assert len(result) == 1
        chunk, start_s, end_s = result[0]
        assert len(chunk) == 600
        assert start_s == 0.0
        assert end_s == 600.0

    def test_two_chunks(self) -> None:
        frames = ["f"] * 1200
        result = chunk_frames(frames, fps=1.0)
        assert len(result) == 2

        chunk0, start0, end0 = result[0]
        assert len(chunk0) == 600
        assert start0 == 0.0
        assert end0 == 600.0

        chunk1, start1, end1 = result[1]
        assert len(chunk1) == 600
        assert start1 == 600.0
        assert end1 == 1200.0

    def test_custom_fps(self) -> None:
        frames = ["f"] * 300
        result = chunk_frames(frames, fps=0.5)
        # 0.5 fps → 300 frames_per_chunk (600*0.5)
        assert len(result) == 1
        _, start_s, end_s = result[0]
        assert start_s == 0.0
        assert end_s == 600.0
