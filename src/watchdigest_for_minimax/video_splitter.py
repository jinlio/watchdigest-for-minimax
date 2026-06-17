"""视频压缩 + 切分模块。

ffmpeg 流程：
1. 压缩原始视频到 480p + 700k 码率（保识别 + 小文件）
2. 估算压缩后大小
3. 按 N 段切分（每段 45s / ≤ 5MB）
4. 用 -c copy 不重编码（保留压缩后的质量）
"""

from __future__ import annotations

import math
import shutil
import subprocess
from pathlib import Path

COMPRESS_VIDEO_FILTER = "scale=-2:480"
COMPRESS_VIDEO_CRF = "28"
COMPRESS_VIDEO_BITRATE = "700k"
COMPRESS_AUDIO_BITRATE = "32k"
COMPRESS_PRESET = "medium"


def get_video_duration(video_path: Path) -> float:
    """用 ffprobe 获取视频时长（秒）。"""
    ffprobe = shutil.which("ffprobe")
    if not ffprobe:
        ffmpeg = shutil.which("ffmpeg")
        if ffmpeg:
            ffprobe = ffmpeg.replace("ffmpeg", "ffprobe")
    if not ffprobe:
        raise RuntimeError("未找到 ffprobe")

    result = subprocess.run(
        [
            ffprobe,
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            str(video_path),
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    return float(result.stdout.strip())


def compress_video(
    input_path: Path,
    output_path: Path,
) -> Path:
    """压缩视频到 480p + 700k 码率。"""
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise RuntimeError("未找到 ffmpeg")

    subprocess.run(
        [
            ffmpeg,
            "-y",
            "-i",
            str(input_path),
            "-vf",
            COMPRESS_VIDEO_FILTER,
            "-c:v",
            "libx264",
            "-crf",
            COMPRESS_VIDEO_CRF,
            "-b:v",
            COMPRESS_VIDEO_BITRATE,
            "-preset",
            COMPRESS_PRESET,
            "-c:a",
            "aac",
            "-b:a",
            COMPRESS_AUDIO_BITRATE,
            "-movflags",
            "+faststart",
            str(output_path),
        ],
        check=True,
        capture_output=True,
    )
    return output_path


def split_video(
    input_path: Path,
    output_dir: Path,
    chunk_seconds: int = 45,
) -> list[Path]:
    """按 N 秒切分视频（用 -c copy 不重编码）。"""
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise RuntimeError("未找到 ffmpeg")

    duration = get_video_duration(input_path)
    n_chunks = max(1, math.ceil(duration / chunk_seconds))

    output_dir.mkdir(parents=True, exist_ok=True)
    chunks: list[Path] = []

    for i in range(n_chunks):
        start_s = i * chunk_seconds
        chunk_path = output_dir / f"chunk_{i:03d}.mp4"
        subprocess.run(
            [
                ffmpeg,
                "-y",
                "-i",
                str(input_path),
                "-ss",
                str(start_s),
                "-t",
                str(chunk_seconds),
                "-c",
                "copy",
                "-movflags",
                "+faststart",
                str(chunk_path),
            ],
            check=True,
            capture_output=True,
        )
        chunks.append(chunk_path)

    return chunks


def split_long_video(
    input_path: Path,
    work_dir: Path,
    chunk_seconds: int = 45,
    chunk_target_size_mb: int = 5,
) -> list[Path]:
    """完整流程：压缩 + 切分。"""
    work_dir.mkdir(parents=True, exist_ok=True)
    compressed = work_dir / "compressed.mp4"

    compress_video(input_path, compressed)

    duration = get_video_duration(compressed)
    size_mb = compressed.stat().st_size / 1024 / 1024
    n_chunks = max(1, math.ceil(duration / chunk_seconds))
    avg_chunk_size = size_mb / n_chunks

    if avg_chunk_size > chunk_target_size_mb:
        n_chunks = max(1, math.ceil(size_mb / chunk_target_size_mb))
        chunk_seconds = max(1, int(duration / n_chunks))

    chunks = split_video(compressed, work_dir / "chunks", chunk_seconds)

    for c in chunks:
        size = c.stat().st_size / 1024 / 1024
        if size > chunk_target_size_mb * 1.5:
            raise ValueError(f"Chunk {c.name} is {size:.1f}MB, exceeds {chunk_target_size_mb}MB target")

    return chunks
