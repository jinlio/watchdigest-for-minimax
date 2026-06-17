"""CLI entry point for watchdigest."""

from __future__ import annotations

import argparse
import logging
import shutil
import sys
import tempfile
from pathlib import Path

from watchdigest_for_minimax.chunker import chunk_frames, estimate_tokens, needs_chunking
from watchdigest_for_minimax.config import (
    get_chunk_seconds,
    get_http_port,
    get_output_dir,
    get_public_host,
    get_video_mode,
)
from watchdigest_for_minimax.downloader import (
    download_bilibili,
    download_douyin,
    is_local_file,
    parse_douyin_share,
)
from watchdigest_for_minimax.minimax_client import MinimaxClient
from watchdigest_for_minimax.prompt import build_user_prompt
from watchdigest_for_minimax.reporter import save_report
from watchdigest_for_minimax.transcoder import extract_frames_base64, get_video_info
from watchdigest_for_minimax.video_splitter import get_video_duration

logger = logging.getLogger(__name__)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="watchdigest",
        description="B站/抖音视频一键变摘要（MiniMax-M3）",
    )
    parser.add_argument("input", help="B站URL / 抖音分享文本或URL / 本地 mp4/mov 文件")
    parser.add_argument("--fps", type=float, default=1.0, help="抽帧率，默认 1.0（推荐 0.5 节省 token）")
    parser.add_argument("--max-duration", type=int, default=7200, help="视频最长时长（秒），超过则拒绝，默认 7200")
    parser.add_argument("--output", type=str, default=None, help="输出目录，默认 ~/Documents/watchdigest")
    parser.add_argument("--no-cleanup", action="store_true", help="保留 temp 目录（debug 用）")
    parser.add_argument(
        "--mode",
        choices=["auto", "base64", "video_url"],
        default=None,
        help="视频处理模式：auto (智能选择) / base64 (抽帧) / video_url (直接传视频)",
    )
    parser.add_argument("-v", "--verbose", action="store_true", help="详细日志（DEBUG 级）")
    parser.add_argument("-q", "--quiet", action="store_true", help="只输出错误")
    return parser


def _setup_logging(verbose: bool, quiet: bool) -> None:
    if quiet:
        level = logging.ERROR
    elif verbose:
        level = logging.DEBUG
    else:
        level = logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%H:%M:%S",
    )


def detect_mode(video_path: Path) -> str:
    """auto 模式下根据视频大小选择模式。"""
    try:
        duration_s = get_video_duration(video_path)
    except Exception:
        return "base64"

    size_mb = video_path.stat().st_size / 1024 / 1024
    estimated_compressed_mb = size_mb * 0.3

    if estimated_compressed_mb <= 5 and duration_s < 300:
        return "video_url"
    elif duration_s < 600:
        return "video_url"
    else:
        return "base64"


def run_video_url_mode(
    video_path: Path,
    video_id: str,
    duration_str: str,
    duration_s: float,
    output_dir: Path,
    no_cleanup: bool,
) -> None:
    """video_url 模式主流程。"""
    from watchdigest_for_minimax.analyzer import analyze_chunk, get_public_url, merge_summaries
    from watchdigest_for_minimax.http_server import start_server, stop_server
    from watchdigest_for_minimax.video_splitter import split_long_video

    chunk_seconds = get_chunk_seconds()
    http_port = get_http_port()
    public_host = get_public_host()

    work_dir = Path(tempfile.mkdtemp(prefix="watchdigest_video_"))

    try:
        # 1. 压缩 + 切分
        logger.info("压缩并切分视频...")
        chunks = split_long_video(video_path, work_dir / "splits", chunk_seconds=chunk_seconds)
        logger.info("切分为 %d 段", len(chunks))

        # 2. 起 HTTP server
        serve_dir = chunks[0].parent
        server = start_server(serve_dir, port=http_port)
        logger.info("HTTP server 已启动在端口 %d", http_port)

        try:
            # 3. Map: 每段 analyze
            chunk_summaries: list[str] = []
            for i, chunk in enumerate(chunks):
                url = get_public_url(chunk.name, host=public_host, port=http_port)
                start_s = i * chunk_seconds
                end_s = min(start_s + chunk_seconds, duration_s)

                summary = analyze_chunk(
                    chunk,
                    i + 1,
                    len(chunks),
                    start_s,
                    end_s,
                    url,
                )
                chunk_summaries.append(summary)

            # 4. Reduce: 合并总结
            if len(chunk_summaries) == 1:
                final_summary = chunk_summaries[0]
            else:
                final_summary = merge_summaries(
                    chunk_summaries,
                    video_title=video_id,
                    uploader="",
                    duration_s=duration_s,
                )

            # 5. 输出 report
            logger.info("生成报告...")
            report_path = save_report(
                output_dir=output_dir,
                video_id=video_id,
                summary=final_summary,
                duration_str=duration_str,
                token_estimate=0,
            )
            logger.info("报告已保存: %s", report_path)
        finally:
            stop_server(server)
    finally:
        if no_cleanup:
            logger.info("保留临时目录: %s", work_dir)
        else:
            shutil.rmtree(work_dir, ignore_errors=True)


def run_base64_mode(
    video_path: Path,
    video_id: str,
    duration_str: str,
    temp_dir: Path,
    output_dir: Path,
    fps: float,
) -> None:
    """base64 模式主流程（现有逻辑）。"""
    logger.info("抽帧中 (fps=%.2f)...", fps)
    frames_b64 = extract_frames_base64(video_path, temp_dir, fps=fps)
    logger.info("抽取 %d 帧", len(frames_b64))

    token_estimate = estimate_tokens(len(frames_b64))
    logger.info("预估 Token: %s", f"{token_estimate:,}")

    logger.info("调用 MiniMax-M3 分析中...")
    client = MinimaxClient()

    if needs_chunking(token_estimate):
        chunks = chunk_frames(frames_b64, fps=fps)
        results: list[str] = []
        for i, (chunk, start_s, end_s) in enumerate(chunks):
            logger.info("处理分片 %d/%d...", i + 1, len(chunks))
            prompt = build_user_prompt(
                duration_str,
                is_chunk=True,
                chunk_index=i + 1,
                total_chunks=len(chunks),
                chunk_start_s=start_s,
                chunk_end_s=end_s,
            )
            result = client.analyze_video(chunk, prompt)
            results.append(result)
        summary = "\n\n".join(results)
    else:
        prompt = build_user_prompt(duration_str)
        summary = client.analyze_video(frames_b64, prompt)

    logger.info("生成报告...")
    report_path = save_report(
        output_dir=output_dir,
        video_id=video_id,
        summary=summary,
        duration_str=duration_str,
        token_estimate=token_estimate,
    )
    logger.info("报告已保存: %s", report_path)
    logger.info("Token 用量: %s", f"{token_estimate:,}")


def main(argv: list[str] | None = None) -> None:
    parser = _build_parser()
    args = parser.parse_args(argv)

    _setup_logging(args.verbose, args.quiet)

    input_arg: str = args.input
    fps: float = args.fps
    max_duration: int = args.max_duration
    output_dir = Path(args.output) if args.output else get_output_dir()
    no_cleanup: bool = args.no_cleanup
    mode: str = args.mode or get_video_mode()

    temp_dir = Path(tempfile.mkdtemp(prefix="watchdigest_"))
    logger.debug("临时目录: %s", temp_dir)

    try:
        # Step 1: Download or validate local file
        logger.info("获取视频...")
        if is_local_file(input_arg):
            video_path = Path(input_arg)
            if not video_path.exists():
                logger.error("文件不存在: %s", video_path)
                sys.exit(1)
            video_id = video_path.stem
        elif "douyin" in input_arg or "抖音" in input_arg:
            douyin_url = parse_douyin_share(input_arg)
            if not douyin_url:
                logger.error("无法从分享文本中提取抖音 URL")
                sys.exit(1)
            video_path = download_douyin(douyin_url, temp_dir)
            video_id = video_path.stem
        elif "bilibili" in input_arg or "b23.tv" in input_arg:
            video_path = download_bilibili(input_arg, temp_dir)
            video_id = video_path.stem
        else:
            logger.error("无法识别输入: %s", input_arg)
            logger.info("支持: B站URL | 抖音分享文本/URL | 本地 mp4/mov 文件")
            sys.exit(1)

        logger.info("视频就绪: %s", video_path)

        # Step 2: Get video info
        logger.info("分析视频信息...")
        info = get_video_info(video_path)
        duration_str = str(info["duration_str"])
        logger.info("时长: %s | 分辨率: %sx%s", duration_str, info["width"], info["height"])

        duration_seconds = float(info.get("duration", 0))
        if duration_seconds > max_duration:
            logger.error("视频时长 %d 秒超过限制 %d 秒", int(duration_seconds), max_duration)
            sys.exit(1)

        # Step 3: Detect mode
        if mode == "auto":
            mode = detect_mode(video_path)
            logger.info("自动选择模式: %s", mode)

        # Step 4: Run
        if mode == "video_url":
            try:
                run_video_url_mode(
                    video_path,
                    video_id,
                    duration_str,
                    duration_seconds,
                    output_dir,
                    no_cleanup,
                )
            except Exception as e:
                logger.warning("video_url 模式失败 (%s)，降级到 base64 模式", e)
                run_base64_mode(video_path, video_id, duration_str, temp_dir, output_dir, fps)
        else:
            run_base64_mode(video_path, video_id, duration_str, temp_dir, output_dir, fps)
    finally:
        if no_cleanup:
            logger.info("保留临时目录: %s", temp_dir)
        else:
            shutil.rmtree(temp_dir, ignore_errors=True)


if __name__ == "__main__":
    main()
