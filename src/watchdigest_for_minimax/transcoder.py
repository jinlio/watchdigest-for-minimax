"""Video transcoding and frame extraction using ffmpeg."""

from __future__ import annotations

import base64
import json
import shutil
import subprocess
from pathlib import Path


def _get_ffmpeg() -> str:
    """Find ffmpeg executable, with fallback to imageio-ffmpeg bundled version."""
    ffmpeg = shutil.which("ffmpeg")
    if ffmpeg:
        return ffmpeg

    # Fallback to imageio-ffmpeg bundled binary
    try:
        import imageio_ffmpeg

        return str(imageio_ffmpeg.get_ffmpeg_exe())
    except ImportError:
        pass

    raise RuntimeError("未找到 ffmpeg。请安装: winget install Gyan.FFmpeg 或 pip install imageio-ffmpeg")


def _get_ffprobe() -> str:
    """Find ffprobe executable."""
    ffprobe = shutil.which("ffprobe")
    if ffprobe:
        return ffprobe

    # Try imageio-ffmpeg directory
    try:
        import imageio_ffmpeg

        ffmpeg_path = Path(imageio_ffmpeg.get_ffmpeg_exe())
        ffprobe_path = ffmpeg_path.parent / ffmpeg_path.name.replace("ffmpeg", "ffprobe")
        if ffprobe_path.exists():
            return str(ffprobe_path)
    except ImportError:
        pass

    # Fallback: use ffmpeg to get duration
    return ""


def get_video_info(video_path: Path) -> dict[str, str | int | float]:
    """Get video duration and resolution using ffprobe."""
    ffprobe = _get_ffprobe()

    if ffprobe:
        cmd = [
            ffprobe,
            "-v",
            "quiet",
            "-print_format",
            "json",
            "-show_format",
            "-show_streams",
            str(video_path),
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, check=False)
        if result.returncode == 0:
            data = json.loads(result.stdout)
            duration = float(data["format"]["duration"])
            video_stream = next((s for s in data["streams"] if s["codec_type"] == "video"), None)
            width = int(video_stream["width"]) if video_stream else 0
            height = int(video_stream["height"]) if video_stream else 0
            return {
                "duration": duration,
                "duration_str": _format_duration(duration),
                "width": width,
                "height": height,
            }

    # Fallback: use ffmpeg to probe
    ffmpeg = _get_ffmpeg()
    cmd = [
        ffmpeg,
        "-i",
        str(video_path),
        "-hide_banner",
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, check=False)
    # Parse duration from stderr
    import re

    match = re.search(r"Duration:\s*(\d+):(\d+):(\d+)\.(\d+)", result.stderr)
    if match:
        h, m, s, ms = int(match.group(1)), int(match.group(2)), int(match.group(3)), int(match.group(4))
        duration = h * 3600 + m * 60 + s + ms / 100
        return {
            "duration": duration,
            "duration_str": _format_duration(duration),
            "width": 0,
            "height": 0,
        }

    raise RuntimeError(f"无法获取视频信息: {video_path}")


def _format_duration(seconds: float) -> str:
    """Format seconds to MM:SS or HH:MM:SS."""
    total_seconds = int(seconds)
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    secs = total_seconds % 60
    if hours > 0:
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"
    return f"{minutes:02d}:{secs:02d}"


def extract_frames_base64(
    video_path: Path,
    out_dir: Path,
    fps: float = 1.0,
) -> list[str]:
    """Extract frames at given fps and return as base64-encoded strings."""
    ffmpeg = _get_ffmpeg()
    frames_dir = out_dir / "frames"
    frames_dir.mkdir(exist_ok=True)

    # Extract frames as JPEG
    cmd = [
        ffmpeg,
        "-i",
        str(video_path),
        "-vf",
        f"fps={fps},scale=1280:720:force_original_aspect_ratio=decrease,pad=1280:720:(ow-iw)/2:(oh-ih)/2",
        "-q:v",
        "3",
        "-f",
        "image2",
        str(frames_dir / "frame_%06d.jpg"),
        "-y",
    ]

    result = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if result.returncode != 0:
        raise RuntimeError(f"ffmpeg 抽帧失败:\n{result.stderr}")

    # Read and encode frames
    frames_b64: list[str] = []
    from tqdm import tqdm

    for frame_file in tqdm(sorted(frames_dir.glob("frame_*.jpg")), desc="编码帧", unit="帧"):
        with open(frame_file, "rb") as f:
            frames_b64.append(base64.b64encode(f.read()).decode("ascii"))

    # Cleanup frames directory
    shutil.rmtree(frames_dir, ignore_errors=True)

    return frames_b64
