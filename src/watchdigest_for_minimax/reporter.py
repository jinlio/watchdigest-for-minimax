"""Markdown report generation."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path


def save_report(
    output_dir: Path,
    video_id: str,
    summary: str,
    duration_str: str,
    token_estimate: int,
    source: str = "B站 / 抖音",
) -> Path:
    """Save analysis report as Markdown file.

    Args:
        output_dir: Directory to save report.
        video_id: Video identifier.
        summary: Model-generated summary.
        duration_str: Video duration string.
        token_estimate: Estimated token usage.
        source: Video source platform.

    Returns:
        Path to saved report.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    report_path = output_dir / f"{video_id}.md"

    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    token_wan = token_estimate / 10_000

    # Estimate cost (≤512K tier): input ¥2.10/M tokens, output ¥8.40/M tokens
    input_cost = (token_estimate / 1_000_000) * 2.10
    output_cost = (4096 / 1_000_000) * 8.40  # ~4096 output tokens
    total_cost = input_cost + output_cost

    report = f"""# {video_id}

> **来源**: {source}
> **时长**: {duration_str}
> **生成时间**: {now}
> **Token 用量**: {token_wan:.1f} 万 / 成本 ¥{total_cost:.2f}

{summary}
"""

    report_path.write_text(report, encoding="utf-8")
    return report_path
