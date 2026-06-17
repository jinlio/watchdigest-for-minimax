"""Tests for video_splitter module."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from watchdigest_for_minimax.video_splitter import (
    COMPRESS_VIDEO_FILTER,
    get_video_duration,
    split_video,
)


class TestGetVideoDuration:
    @patch("watchdigest_for_minimax.video_splitter.subprocess.run")
    @patch("watchdigest_for_minimax.video_splitter.shutil.which", return_value="/usr/bin/ffprobe")
    def test_returns_float(self, mock_which: object, mock_run: object) -> None:
        from unittest.mock import MagicMock

        mock_result = MagicMock()
        mock_result.stdout = "120.5\n"
        mock_run.return_value = mock_result  # type: ignore[union-attr]

        duration = get_video_duration(Path("test.mp4"))
        assert duration == 120.5


class TestSplitVideo:
    @patch("watchdigest_for_minimax.video_splitter.subprocess.run")
    @patch("watchdigest_for_minimax.video_splitter.get_video_duration", return_value=10.0)
    @patch("watchdigest_for_minimax.video_splitter.shutil.which", return_value="/usr/bin/ffmpeg")
    def test_split_into_chunks(self, mock_which: object, mock_dur: object, mock_run: object) -> None:
        from unittest.mock import MagicMock

        mock_run.return_value = MagicMock(returncode=0)  # type: ignore[union-attr]

        with patch("watchdigest_for_minimax.video_splitter.Path.mkdir"):
            chunks = split_video(Path("test.mp4"), Path("/tmp/chunks"), chunk_seconds=5)
        assert len(chunks) == 2


class TestConstants:
    def test_compress_filter(self) -> None:
        assert "480" in COMPRESS_VIDEO_FILTER
