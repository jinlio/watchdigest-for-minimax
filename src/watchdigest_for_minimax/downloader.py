"""Video downloader: Bilibili + Douyin with anti-crawl measures.

Douyin strategy (参考 snailzsh/douyin-video-downloader):
1. 解析视频 ID
2. 构造 iesdouyin.com 分享页
3. 移动端 UA 抓取 HTML
4. 提取 play URL（无水印）

Bilibili strategy:
1. Bilibili API 直接获取 DASH 流
2. 下载视频 + 音频流
3. ffmpeg 合并
"""

from __future__ import annotations

import json
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
    """Extract Douyin URL from share text."""
    match = re.search(r"https?://v\.douyin\.com/[\w\-/]+", text)
    if match:
        return match.group(0).rstrip("/")
    match = re.search(r"https?://www\.douyin\.com/video/(\d+)", text)
    if match:
        return match.group(0)
    match = re.search(r"https?://www\.iesdouyin\.com/share/video/(\d+)", text)
    if match:
        return match.group(0)
    return None


def _resolve_douyin_short_url(url: str) -> str | None:
    """Resolve short URL (v.douyin.com) to get video ID."""
    import urllib.request

    # Extract video ID patterns
    patterns = [
        r"/video/(\d+)",
        r"/share/video/(\d+)",
        r"aweme_id[=:](\d+)",
        r"item_ids[=:]?(\d+)",
    ]

    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)

    # Need to follow redirect for short URLs
    if "v.douyin.com" in url:
        try:
            req = urllib.request.Request(url, method="HEAD")
            req.add_header("User-Agent", _MOBILE_UA)
            # Don't follow redirects, just get Location header
            import http.client
            from urllib.parse import urlparse

            parsed = urlparse(url)
            if not parsed.hostname:
                return None
            conn = http.client.HTTPSConnection(parsed.hostname, timeout=10)
            conn.request("HEAD", parsed.path, headers={"User-Agent": _MOBILE_UA})
            resp = conn.getresponse()
            location = resp.getheader("Location", "")
            conn.close()

            if location:
                for pattern in patterns:
                    match = re.search(pattern, location)
                    if match:
                        return match.group(1)
        except Exception as e:
            logger.debug("解析短链接失败: %s", e)

    return None


def _fetch_douyin_video_url(video_id: str) -> dict[str, str | list[str]] | None:
    """Fetch Douyin video data by parsing share page HTML.

    参考 snailzsh/douyin-video-downloader 的实现。
    """
    import urllib.request

    share_url = f"https://www.iesdouyin.com/share/video/{video_id}/"

    headers = {
        "User-Agent": _MOBILE_UA,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    }

    try:
        req = urllib.request.Request(share_url, headers=headers)
        with urllib.request.urlopen(req, timeout=15) as resp:
            html = resp.read().decode("utf-8", errors="replace")
    except Exception as e:
        logger.warning("获取抖音分享页失败: %s", e)
        return None

    # Method 1: Search for aweme.snssdk.com URL
    search_str = "aweme.snssdk.com"
    idx = html.find(search_str)
    if idx > 0:
        start = html.rfind("http", 0, idx)
        if start < 0:
            start = max(0, idx - 50)
        end = html.find('"', idx)
        if end < 0:
            end = idx + 200

        video_url = html[start:end]
        video_url = video_url.replace("\\u002F", "/").replace("\\u003D", "=")
        video_url = video_url.replace("\\u0026", "&").replace("\\u003F", "?")

        # playwm = watermark, play = no watermark
        if "playwm" in video_url:
            video_url = video_url.replace("playwm", "play")

        title = "未知标题"
        desc_match = re.search(r'"desc":"([^"]+)"', html)
        if desc_match:
            title = desc_match.group(1)

        return {"title": title, "video_urls": [video_url]}

    # Method 2: __INITIAL_STATE__
    match = re.search(r"window\.__INITIAL_STATE__\s*=\s*({.*?});", html, re.DOTALL)
    if match:
        try:
            data = json.loads(match.group(1))
            aweme = data.get("aweme", data.get("detail", {}))
            if isinstance(aweme, dict) and "video" in aweme:
                play_addr = aweme["video"].get("play_addr", {})
                url_list = play_addr.get("url_list", [])
                if url_list:
                    return {
                        "title": aweme.get("desc", "未知标题"),
                        "video_urls": url_list,
                    }
        except (json.JSONDecodeError, KeyError):
            pass

    # Method 3: _ROUTER_DATA
    match = re.search(r"window\._ROUTER_DATA\s*=\s*(\{.+?\});\s*</script>", html, re.DOTALL)
    if match:
        try:
            data_str = match.group(1).replace("\\u002F", "/")
            data = json.loads(data_str)

            def find_video(obj: object) -> dict[str, object] | None:
                if isinstance(obj, dict):
                    if "play_addr" in obj and "desc" in obj:
                        return obj
                    for v in obj.values():
                        result = find_video(v)
                        if result:
                            return result
                elif isinstance(obj, list):
                    for item in obj:
                        result = find_video(item)
                        if result:
                            return result
                return None

            video_data = find_video(data)
            if video_data:
                video_obj = video_data.get("video")
                if isinstance(video_obj, dict):
                    play_addr = video_obj.get("play_addr")
                    if isinstance(play_addr, dict):
                        url_list = play_addr.get("url_list", [])
                        if isinstance(url_list, list) and url_list:
                            return {
                                "title": str(video_data.get("desc", "未知标题")),
                                "video_urls": [str(u) for u in url_list],
                            }
        except (json.JSONDecodeError, KeyError):
            pass

    return None


def _download_file(url: str, output_path: Path, referer: str = "https://www.douyin.com/") -> None:
    """Download file using curl with proper headers."""
    curl = shutil.which("curl")
    if not curl:
        raise RuntimeError("未找到 curl")

    cmd = [
        curl,
        "-L",
        "-o",
        str(output_path),
        "-H",
        f"User-Agent: {_MOBILE_UA}",
        "-H",
        f"Referer: {referer}",
        "--progress-bar",
        "--connect-timeout",
        "15",
        "--max-time",
        "300",
        url,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if result.returncode != 0:
        raise RuntimeError(f"curl 下载失败: {result.stderr}")


def download_bilibili(url: str, out_dir: Path) -> Path:
    """Download Bilibili video using API directly (避免 412 反爬).

    Strategy:
    1. 通过 API 获取视频信息（cid、标题）
    2. 通过 API 获取 FLV/MP4 流地址（fnval=0 避免 DASH CDN 问题）
    3. 下载视频文件（带重试）
    """
    import urllib.request

    # Extract BV ID
    bv_match = re.search(r"(BV[\w]+)", url)
    if not bv_match:
        raise RuntimeError(f"无法从 URL 提取 BV ID: {url}")
    bv_id = bv_match.group(1)
    logger.info("B站 BV ID: %s", bv_id)

    api_headers = {
        "User-Agent": _COMMON_UA,
        "Referer": "https://www.bilibili.com",
    }

    # Step 1: Get video info
    info_url = f"https://api.bilibili.com/x/web-interface/view?bvid={bv_id}"
    req = urllib.request.Request(info_url, headers=api_headers)
    with urllib.request.urlopen(req, timeout=15) as resp:
        info = json.loads(resp.read().decode("utf-8"))

    if info["code"] != 0:
        raise RuntimeError(f"B站 API 错误: {info.get('message', info)}")

    title = info["data"]["title"]
    cid = info["data"]["cid"]
    logger.info("标题: %s (CID: %s)", title, cid)

    # Step 2: Get play URL (fnval=0 → FLV/MP4 直接链接，避免 DASH CDN 问题)
    play_url = f"https://api.bilibili.com/x/player/playurl?bvid={bv_id}&cid={cid}&qn=32&fnval=0"
    req = urllib.request.Request(play_url, headers=api_headers)
    with urllib.request.urlopen(req, timeout=15) as resp:
        play = json.loads(resp.read().decode("utf-8"))

    if play["code"] != 0:
        raise RuntimeError(f"B站播放地址 API 错误: {play.get('message', play)}")

    durl = play["data"].get("durl", [])
    if not durl:
        raise RuntimeError("B站未返回视频流地址")

    video_url = durl[0]["url"]
    logger.info("视频流: %s...", video_url[:80])

    # Step 3: Download with retry
    safe_title = re.sub(r'[\\/*?:"<>|]', "_", title)[:100]
    output_path = out_dir / f"{safe_title}.mp4"

    for attempt in range(3):
        try:
            logger.info("下载中 (attempt %d/3)...", attempt + 1)
            req = urllib.request.Request(video_url, headers=api_headers)
            with urllib.request.urlopen(req, timeout=120) as resp:
                data = resp.read()
                output_path.write_bytes(data)
                size_mb = len(data) / 1024 / 1024
                logger.info("下载成功: %.1f MB", size_mb)
                return output_path
        except Exception as e:
            logger.warning("下载失败 (attempt %d/3): %s", attempt + 1, e)
            if attempt < 2:
                time.sleep(2 ** attempt)

    raise RuntimeError("B站视频下载失败（重试 3 次）")


def download_douyin(url: str, out_dir: Path) -> Path:
    """Download Douyin video.

    Strategy 1: 直接解析 HTML 提取 play URL（参考 douyin-video-downloader）
    Strategy 2: yt-dlp fallback
    """
    # Parse video ID
    video_id = _resolve_douyin_short_url(url)

    if video_id:
        logger.info("抖音视频 ID: %s", video_id)
        video_info = _fetch_douyin_video_url(video_id)

        if video_info and video_info.get("video_urls"):
            video_urls = video_info["video_urls"]
            title = str(video_info.get("title", video_id))
            logger.info("标题: %s", title)

            # Clean filename
            safe_title = re.sub(r'[\\/*?:"<>|]', "_", title)[:100]
            output_path = out_dir / f"{safe_title}.mp4"

            # Try each URL
            for i, video_url in enumerate(video_urls):
                try:
                    logger.info("尝试下载 URL %d/%d...", i + 1, len(video_urls))
                    _download_file(video_url, output_path)
                    if output_path.exists() and output_path.stat().st_size > 0:
                        size_mb = output_path.stat().st_size / 1024 / 1024
                        logger.info("下载成功: %.1f MB", size_mb)
                        return output_path
                except Exception as e:
                    logger.warning("URL %d 下载失败: %s", i + 1, e)
                    continue

    # Fallback: yt-dlp
    logger.info("直接解析失败，尝试 yt-dlp...")
    return _download_douyin_ytdlp(url, out_dir)


def _download_douyin_ytdlp(url: str, out_dir: Path) -> Path:
    """Fallback: download Douyin via yt-dlp."""
    ytdlp = _get_ytdlp()
    output_template = str(out_dir / "%(id)s.%(ext)s")

    cmd = [
        ytdlp,
        "--add-header",
        "Referer: https://www.douyin.com",
        "--add-header",
        f"User-Agent: {_MOBILE_UA}",
        "--no-check-certificates",
        "-f",
        "best",
        "-o",
        output_template,
        "--retries",
        "3",
        url,
    ]

    try:
        _run_ytdlp(cmd)
    except RuntimeError:
        logger.warning("移动端 UA 失败，尝试桌面端 UA...")
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
