"""Video downloader: Bilibili + Douyin URL parsing and yt-dlp wrapper."""

from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path


def _get_ytdlp() -> str:
    """Find yt-dlp executable."""
    ytdlp = shutil.which("yt-dlp")
    if not ytdlp:
        raise RuntimeError("未找到 yt-dlp。请安装: pip install yt-dlp")
    return ytdlp


def parse_douyin_share(text: str) -> str | None:
    """Extract Douyin URL from share text.

    Share text format: "7.99 复制打开抖音，看看【XXX】https://v.douyin.com/xxx/"
    """
    match = re.search(r"https?://v\.douyin\.com/[\w\-/]+", text)
    if match:
        return match.group(0).rstrip("/")
    match = re.search(r"https?://www\.douyin\.com/video/\d+", text)
    if match:
        return match.group(0)
    return None


def download_bilibili(url: str, out_dir: Path) -> Path:
    """Download Bilibili video using yt-dlp."""
    ytdlp = _get_ytdlp()
    output_template = str(out_dir / "%(id)s.%(ext)s")

    cmd = [
        ytdlp,
        "--add-header",
        "Referer: https://www.bilibili.com",
        "--add-header",
        "User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "-f",
        "bestvideo[height<=720]+bestaudio/best[height<=720]",
        "--merge-output-format",
        "mp4",
        "-o",
        output_template,
        url,
    ]

    result = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if result.returncode != 0:
        raise RuntimeError(f"yt-dlp 下载失败:\n{result.stderr}")

    # Find the downloaded file
    mp4_files = sorted(out_dir.glob("*.mp4"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not mp4_files:
        raise RuntimeError("下载完成但未找到输出文件")
    return mp4_files[0]


def download_douyin(url: str, out_dir: Path) -> Path:
    """Download Douyin video using yt-dlp."""
    ytdlp = _get_ytdlp()
    output_template = str(out_dir / "%(id)s.%(ext)s")

    ua = (
        "User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
        " AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    )
    cmd = [
        ytdlp,
        "--add-header",
        "Referer: https://www.douyin.com",
        "--add-header",
        ua,
        "-f",
        "best",
        "-o",
        output_template,
        url,
    ]

    result = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if result.returncode != 0:
        raise RuntimeError(f"yt-dlp 下载失败:\n{result.stderr}")

    # Find the downloaded file
    video_files = sorted(
        out_dir.glob("*.*"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    for f in video_files:
        if f.suffix.lower() in (".mp4", ".mov", ".flv", ".mkv", ".webm"):
            return f
    raise RuntimeError("下载完成但未找到输出文件")


def is_local_file(path: str) -> bool:
    """Check if the input is a local file path."""
    p = Path(path)
    return p.exists() and p.is_file() and p.suffix.lower() in (".mp4", ".mov")
