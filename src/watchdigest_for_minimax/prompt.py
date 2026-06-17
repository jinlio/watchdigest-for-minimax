"""Prompt templates for video_url mode (chunk + merge)."""

from __future__ import annotations

SYSTEM_PROMPT = "你是视频总结助手，擅长分析视频内容并生成结构化摘要。"


def _format_seconds(seconds: float) -> str:
    """Format seconds to MM:SS or HH:MM:SS."""
    total = int(seconds)
    hours = total // 3600
    minutes = (total % 3600) // 60
    secs = total % 60
    if hours > 0:
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"
    return f"{minutes:02d}:{secs:02d}"


def build_chunk_prompt(
    chunk_index: int,
    total_chunks: int,
    chunk_start_s: float,
    chunk_end_s: float,
) -> str:
    """Map 阶段 prompt：分析这一段视频（video_url 模式）。"""
    start_mmss = _format_seconds(chunk_start_s)
    end_mmss = _format_seconds(chunk_end_s)

    return f"""你是专业的视频内容分析助手。

请详细分析下面这段视频（这是整个视频的第 {chunk_index}/{total_chunks} 段，时间范围 {start_mmss} - {end_mmss}）。

**输出要求**：
1. 按时间顺序描述这段视频的内容
2. 用时间戳标注关键事件（格式：`mm:ss - <事件>`）
3. 识别主要人物（如能看出身份请标注，如"中年男性，戴眼镜，演讲者"）
4. 提取画面中的中英文文字（OCR 字幕、标题、logo）
5. 描述场景变化（场景转换、镜头切换）
6. 如果是技术视频，记录关键技术名词、产品名、操作步骤

**输出格式**（Markdown）：
```
## 时间线
- 00:00 - <事件1>
- 00:15 - <事件2>
...

## 关键人物
- <人物1描述>
- <人物2描述>

## 文字内容
- "<OCR 文字1>"
- "<OCR 文字2>"

## 技术细节（如适用）
- <技术点1>
- <技术点2>

## 简要总结
<1-2 句话总结这段视频讲了什么>
```

请保持客观、具体，避免主观推测。
"""


def build_merge_prompt(
    chunk_summaries: list[str],
    video_title: str,
    uploader: str,
    duration_s: float,
) -> str:
    """Reduce 阶段 prompt：合并 N 段总结为 1 篇连贯总总结。"""
    duration_str = _format_seconds(duration_s)

    chunks_text = "\n\n".join(f"### 第 {i + 1} 段总结\n{summary}" for i, summary in enumerate(chunk_summaries))

    return f"""你是专业的视频内容总结助手。

下面是视频《{video_title}》（UP 主：{uploader}，时长 {duration_str}）的 {len(chunk_summaries)} 段分段总结：

{chunks_text}

**任务**：将以上分段总结合并为 1 篇连贯的完整视频总结。

**输出要求**：
1. 用一段连贯的文字描述整个视频讲了什么（200-500 字）
2. 保持时间顺序的逻辑流畅性
3. 不要重复分段中的冗余信息
4. 突出视频的核心主题和关键观点
5. 使用 Markdown 格式，包含以下结构：
   - **# 视频总结**（标题）
   - **## 核心主题**（1-2 句）
   - **## 主要内容**（连贯段落，200-400 字）
   - **## 关键事件时间线**（5-10 个关键时间点 + 事件）
   - **## 技术要点**（如适用）
   - **## 一句话总结**（30 字以内）

请保持客观、准确、有信息密度。
"""
