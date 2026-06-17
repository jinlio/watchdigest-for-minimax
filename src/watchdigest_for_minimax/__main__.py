"""CLI entry point for watchdigest."""

from __future__ import annotations

import argparse
import logging
import shutil
import sys
import tempfile
from pathlib import Path

from watchdigest_for_minimax.chunker import chunk_frames, estimate_tokens, needs_chunking
from watchdigest_for_minimax.config import get_output_dir
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
    fps: float = args.fps
    max_duration: int = args.max_duration
    output_dir = Path(args.output) if args.output else get_output_dir()
    no_cleanup: bool = args.no_cleanup

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

        # Check max duration
        duration_seconds = float(info.get("duration", 0))
        if duration_seconds > max_duration:
            logger.error("视频时长 %d 秒超过限制 %d 秒", int(duration_seconds), max_duration)
            sys.exit(1)

        # Step 3: Extract frames
        logger.info("抽帧中 (fps=%.2f)...", fps)
        frames_b64 = extract_frames_base64(video_path, temp_dir, fps=fps)
        logger.info("抽取 %d 帧", len(frames_b64))

        # Step 4: Token estimation and chunking
        token_estimate = estimate_tokens(len(frames_b64))
        logger.info("预估 Token: %s", f"{token_estimate:,}")

        # Step 5: Call MiniMax-M3
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

        # Step 6: Generate report
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
    finally:
        if no_cleanup:
            logger.info("保留临时目录: %s", temp_dir)
        else:
            shutil.rmtree(temp_dir, ignore_errors=True)


if __name__ == "__main__":
    main()
