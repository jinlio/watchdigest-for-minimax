"""CLI entry point for watchdigest — video_url mode only."""

from __future__ import annotations

import argparse
import logging
import shutil
import sys
import tempfile
from pathlib import Path

from watchdigest_for_minimax.config import (
    get_chunk_seconds,
    get_http_port,
    get_output_dir,
    get_public_host,
)
from watchdigest_for_minimax.downloader import (
    download_bilibili,
    download_douyin,
    is_local_file,
    parse_douyin_share,
)
from watchdigest_for_minimax.reporter import save_report
from watchdigest_for_minimax.transcoder import get_video_info

logger = logging.getLogger(__name__)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="watchdigest",
        description="B站/抖音视频一键变摘要（MiniMax-M3 video_url 模式）",
    )
    parser.add_argument("input", help="B站URL / 抖音分享文本或URL / 本地 mp4/mov 文件")
    parser.add_argument("--max-duration", type=int, default=7200, help="视频最长时长（秒），超过则拒绝，默认 7200")
    parser.add_argument("--output", type=str, default=None, help="输出目录，默认 ~/Documents/watchdigest")
    parser.add_argument("--no-cleanup", action="store_true", help="保留 temp 目录（debug 用）")
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


def main(argv: list[str] | None = None) -> None:
    parser = _build_parser()
    args = parser.parse_args(argv)

    _setup_logging(args.verbose, args.quiet)

    input_arg: str = args.input
    max_duration: int = args.max_duration
    output_dir = Path(args.output) if args.output else get_output_dir()
    no_cleanup: bool = args.no_cleanup

    chunk_seconds = get_chunk_seconds()
    http_port = get_http_port()
    public_host = get_public_host()

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

        # Step 3: video_url mode
        from watchdigest_for_minimax.analyzer import analyze_chunk, get_public_url, merge_summaries
        from watchdigest_for_minimax.http_server import start_server, stop_server
        from watchdigest_for_minimax.video_splitter import split_long_video

        work_dir = Path(tempfile.mkdtemp(prefix="watchdigest_video_"))

        try:
            logger.info("压缩并切分视频...")
            chunks = split_long_video(video_path, work_dir / "splits", chunk_seconds=chunk_seconds)
            logger.info("切分为 %d 段", len(chunks))

            serve_dir = chunks[0].parent
            server = start_server(serve_dir, port=http_port)
            logger.info("HTTP server 已启动在端口 %d", http_port)

            try:
                chunk_summaries: list[str] = []
                for i, chunk in enumerate(chunks):
                    url = get_public_url(chunk.name, host=public_host, port=http_port)
                    start_s = i * chunk_seconds
                    end_s = min(start_s + chunk_seconds, duration_seconds)

                    summary = analyze_chunk(
                        chunk,
                        i + 1,
                        len(chunks),
                        start_s,
                        end_s,
                        url,
                    )
                    chunk_summaries.append(summary)

                if len(chunk_summaries) == 1:
                    final_summary = chunk_summaries[0]
                else:
                    final_summary = merge_summaries(
                        chunk_summaries,
                        video_title=video_id,
                        uploader="",
                        duration_s=duration_seconds,
                    )

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
    finally:
        if no_cleanup:
            logger.info("保留临时目录: %s", temp_dir)
        else:
            shutil.rmtree(temp_dir, ignore_errors=True)


if __name__ == "__main__":
    main()
