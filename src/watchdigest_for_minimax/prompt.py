"""System prompt and user prompt templates."""

from __future__ import annotations

SYSTEM_PROMPT = """你是视频总结助手，擅长分析视频内容并生成结构化摘要。

你的任务是：
1. 观看视频帧序列，理解视频的整体内容
2. 生成结构化的 Markdown 摘要报告

输出格式要求：
- 一句话总览（≤50字）
- 分段时间轴（按内容逻辑分段，标注起止时间）
- 关键要点（5-10条）
- 视觉要点（画面里看到但转录文字看不到的信息，如图表、演示、人物表情等）

请用中文输出。"""


def build_user_prompt(
    duration_str: str,
    is_chunk: bool = False,
    chunk_index: int = 0,
    total_chunks: int = 0,
) -> str:
    """Build user prompt for video analysis.

    Args:
        duration_str: Video duration string (e.g., "23:45").
        is_chunk: Whether this is a chunk of a longer video.
        chunk_index: Current chunk index (1-based).
        total_chunks: Total number of chunks.

    Returns:
        Formatted prompt string.
    """
    if is_chunk:
        return (
            f"这是视频的第 {chunk_index}/{total_chunks} 个片段（每片段约10分钟）。\n"
            f"请分析这个片段的内容，输出：\n"
            f"1. 本片段的时间轴摘要\n"
            f"2. 本片段的关键要点\n"
            f"3. 本片段的视觉要点\n\n"
            f"请用中文输出，格式为 Markdown。"
        )

    return (
        f"视频总时长: {duration_str}\n\n"
        f"请分析整个视频的内容，生成结构化摘要报告，包含：\n"
        f"1. 一句话总览（≤50字）\n"
        f"2. 分段时间轴（按内容逻辑分段，标注起止时间）\n"
        f"3. 关键要点（5-10条）\n"
        f"4. 视觉要点（画面里看到但转录文字看不到的信息）\n\n"
        f"请用中文输出，格式为 Markdown。"
    )
