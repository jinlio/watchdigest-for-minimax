"""CLI entry point for watchdigest."""

from __future__ import annotations

import sys
from pathlib import Path

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


def main(argv: list[str] | None = None) -> None:
    if argv is None:
        argv = sys.argv[1:]

    if not argv:
        print("用法: watchdigest <url_or_path>")
        print("支持: B站URL | 抖音分享文本/URL | 本地 mp4/mov 文件")
        sys.exit(1)

    input_arg = argv[0]
    temp_dir = Path.home() / "watchdigest_temp"
    temp_dir.mkdir(exist_ok=True)

    # Step 1: Download or validate local file
    print("📥 获取视频...")
    if is_local_file(input_arg):
        video_path = Path(input_arg)
        if not video_path.exists():
            print(f"❌ 文件不存在: {video_path}")
            sys.exit(1)
        video_id = video_path.stem
    elif "douyin" in input_arg or "抖音" in input_arg:
        douyin_url = parse_douyin_share(input_arg)
        if not douyin_url:
            print("❌ 无法从分享文本中提取抖音 URL")
            sys.exit(1)
        video_path = download_douyin(douyin_url, temp_dir)
        video_id = video_path.stem
    elif "bilibili" in input_arg or "b23.tv" in input_arg:
        video_path = download_bilibili(input_arg, temp_dir)
        video_id = video_path.stem
    else:
        print(f"❌ 无法识别输入: {input_arg}")
        print("支持: B站URL | 抖音分享文本/URL | 本地 mp4/mov 文件")
        sys.exit(1)

    print(f"✅ 视频就绪: {video_path}")

    # Step 2: Get video info
    print("📊 分析视频信息...")
    info = get_video_info(video_path)
    duration_str = str(info["duration_str"])
    print(f"   时长: {duration_str} | 分辨率: {info['width']}x{info['height']}")

    # Step 3: Extract frames
    print("🎞️ 抽帧中...")
    frames_b64 = extract_frames_base64(video_path, temp_dir)
    print(f"   抽取 {len(frames_b64)} 帧")

    # Step 4: Token estimation and chunking
    from watchdigest_for_minimax.chunker import estimate_tokens, needs_chunking

    token_estimate = estimate_tokens(len(frames_b64))
    print(f"📐 预估 Token: {token_estimate:,}")

    # Step 5: Call MiniMax-M3
    print("🤖 调用 MiniMax-M3 分析中...")
    client = MinimaxClient()

    if needs_chunking(token_estimate):
        from watchdigest_for_minimax.chunker import chunk_frames

        chunks = chunk_frames(frames_b64, fps=1.0)
        results: list[str] = []
        for i, chunk in enumerate(chunks):
            print(f"   处理分片 {i + 1}/{len(chunks)}...")
            prompt = build_user_prompt(
                duration_str,
                is_chunk=True,
                chunk_index=i + 1,
                total_chunks=len(chunks),
            )
            result = client.analyze_video(chunk, prompt)
            results.append(result)
        summary = "\n\n".join(results)
    else:
        prompt = build_user_prompt(duration_str)
        summary = client.analyze_video(frames_b64, prompt)

    # Step 6: Generate report
    print("📝 生成报告...")
    output_dir = get_output_dir()
    report_path = save_report(
        output_dir=output_dir,
        video_id=video_id,
        summary=summary,
        duration_str=duration_str,
        token_estimate=token_estimate,
    )

    print(f"\n✅ 报告已保存: {report_path}")
    print(f"📊 Token 用量: {token_estimate:,}")


if __name__ == "__main__":
    main()
