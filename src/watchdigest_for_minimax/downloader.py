"""Video downloader: Bilibili + Douyin with anti-crawl measures."""

from __future__ import annotations

import logging
import re
import shutil
import subprocess
import time
from pathlib import Path

logger = logging.getLogger(__name__)

_COMMON_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)

_MOBILE_UA = (
    "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) "
    "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 Mobile/15E148 Safari/604.1"
)

_DOUYIN_UA = (
    "Mozilla/5.0 (Linux; Android 13; Pixel 7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36"
)


def _get_ytdlp() -> str:
    """Find yt-dlp executable."""
    ytdlp = shutil.which("yt-dlp")
    if not ytdlp:
        raise RuntimeError("未找到 yt-dlp。请安装: pip install yt-dlp")
    return ytdlp


def _run_ytdlp(cmd: list[str], retries: int = 2) -> subprocess.CompletedProcess[str]:
    """Run yt-dlp with retry logic."""
    for attempt in range(retries + 1):
        result = subprocess.run(cmd, capture_output=True, text=True, check=False)
        if result.returncode == 0:
            return result
        if attempt < retries:
            wait = 2**attempt
            logger.warning("yt-dlp 失败 (attempt %d/%d)，%ds 后重试...", attempt + 1, retries + 1, wait)
            time.sleep(wait)
    raise RuntimeError(f"yt-dlp 下载失败 (重试 {retries} 次):\n{result.stderr}")


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
    match = re.search(r"https?://www\.iesdouyin\.com/share/video/\d+", text)
    if match:
        return match.group(0)
    return None


def download_bilibili(url: str, out_dir: Path) -> Path:
    """Download Bilibili video using yt-dlp with anti-crawl measures.

    Strategy:
    1. Standard download with browser-like headers
    2. Fallback: try --cookies-from-browser if available
    3. Fallback: use lower quality
    """
    ytdlp = _get_ytdlp()
    output_template = str(out_dir / "%(id)s.%(ext)s")

    # Attempt 1: standard with proper headers
    cmd = [
        ytdlp,
        "--add-header",
        "Referer: https://www.bilibili.com",
        "--add-header",
        f"User-Agent: {_COMMON_UA}",
        "--add-header",
        "Accept-Language: zh-CN,zh;q=0.9,en;q=0.8",
        "--no-check-certificates",
        "-f",
        "bestvideo[height<=720]+bestaudio/best[height<=720]",
        "--merge-output-format",
        "mp4",
        "--extractor-args",
        "bilibili:enable_bv_transcode",
        "-o",
        output_template,
        "--retries",
        "3",
        "--fragment-retries",
        "3",
        url,
    ]

    try:
        _run_ytdlp(cmd)
    except RuntimeError:
        # Attempt 2: try lower quality as fallback
        logger.warning("标准下载失败，尝试降级画质...")
        cmd_fallback = [
            ytdlp,
            "--add-header",
            "Referer: https://www.bilibili.com",
            "--add-header",
            f"User-Agent: {_COMMON_UA}",
            "--no-check-certificates",
            "-f",
            "best[height<=480]",
            "--merge-output-format",
            "mp4",
            "-o",
            output_template,
            "--retries",
            "3",
            url,
        ]
        _run_ytdlp(cmd_fallback)

    mp4_files = sorted(out_dir.glob("*.mp4"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not mp4_files:
        raise RuntimeError("下载完成但未找到输出文件")
    return mp4_files[0]


def download_douyin(url: str, out_dir: Path) -> Path:
    """Download Douyin video using yt-dlp with anti-crawl measures.

    Strategy:
    1. Use mobile UA (Douyin serves better content to mobile)
    2. Retry with exponential backoff
    3. Fallback: try different extractor args
    """
    ytdlp = _get_ytdlp()
    output_template = str(out_dir / "%(id)s.%(ext)s")

    # Attempt 1: mobile UA (Douyin prefers mobile clients)
    cmd = [
        ytdlp,
        "--add-header",
        "Referer: https://www.douyin.com",
        "--add-header",
        f"User-Agent: {_DOUYIN_UA}",
        "--add-header",
        "Accept-Language: zh-CN,zh;q=0.9",
        "--no-check-certificates",
        "-f",
        "best",
        "-o",
        output_template,
        "--retries",
        "3",
        "--fragment-retries",
        "3",
        url,
    ]

    try:
        _run_ytdlp(cmd)
    except RuntimeError:
        # Attempt 2: desktop UA as fallback
        logger.warning("移动端 UA 下载失败，尝试桌面端 UA...")
        cmd_fallback = [
            ytdlp,
            "--add-header",
            "Referer: https://www.douyin.com",
            "--add-header",
            f"User-Agent: {_COMMON_UA}",
            "--no-check-certificates",
            "-f",
            "best",
            "-o",
            output_template,
            "--retries",
            "3",
            url,
        ]
        _run_ytdlp(cmd_fallback)

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
