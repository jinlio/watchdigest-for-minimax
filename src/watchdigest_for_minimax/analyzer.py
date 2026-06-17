"""Map-reduce 视频总结。

Map: 每段视频 → 详细总结（带时间戳）
Reduce: N 段总结 → 1 篇连贯总总结
"""

from __future__ import annotations

import json
import logging
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any
from urllib.parse import quote

from watchdigest_for_minimax.config import get_api_key, get_base_url
from watchdigest_for_minimax.prompt import build_chunk_prompt, build_merge_prompt

logger = logging.getLogger(__name__)

DEFAULT_PUBLIC_HOST = "8.136.148.185"
DEFAULT_HTTP_PORT = 41234


def get_public_url(
    path: str,
    host: str = DEFAULT_PUBLIC_HOST,
    port: int = DEFAULT_HTTP_PORT,
) -> str:
    """生成本地文件的公网 URL。"""
    return f"http://{host}:{port}/{quote(path)}"


def call_minimax_native(
    messages: list[dict[str, object]],
    model: str = "MiniMax-M3",
    max_tokens: int = 1500,
    timeout: int = 120,
) -> dict[str, object]:
    """调用 minimax 原生 ChatCompletion API（非 Anthropic 兼容）。

    支持 video_url 块。
    """
    api_key = get_api_key()
    base_url = get_base_url().replace("/anthropic", "")

    payload = {
        "model": model,
        "max_tokens": max_tokens,
        "messages": messages,
    }

    req = urllib.request.Request(
        f"{base_url}/v1/text/chatcompletion_v2",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            result: dict[str, object] = json.loads(resp.read().decode("utf-8"))
            return result
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", "replace")
        raise RuntimeError(f"minimax API error {e.code}: {body}") from e


def analyze_chunk(
    chunk_path: Path,
    chunk_index: int,
    total_chunks: int,
    chunk_start_s: float,
    chunk_end_s: float,
    public_url: str,
    max_tokens: int = 1500,
) -> str:
    """Map: 分析一段视频，返回该段总结。"""
    prompt = build_chunk_prompt(
        chunk_index=chunk_index,
        total_chunks=total_chunks,
        chunk_start_s=chunk_start_s,
        chunk_end_s=chunk_end_s,
    )

    logger.info(
        "Analyzing chunk %d/%d (%s) via video_url...",
        chunk_index,
        total_chunks,
        chunk_path.name,
    )

    t0 = time.time()
    response = call_minimax_native(
        messages=[
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {"type": "video_url", "video_url": {"url": public_url}},
                ],
            }
        ],
        max_tokens=max_tokens,
    )
    elapsed = time.time() - t0

    base_resp: dict[str, Any] = response.get("base_resp", {})  # type: ignore[assignment]
    if base_resp.get("status_code") != 0:
        raise RuntimeError(f"minimax error {base_resp.get('status_code')}: {base_resp.get('status_msg')}")

    choices: list[dict[str, Any]] = response.get("choices", [])  # type: ignore[assignment]
    if not choices:
        raise RuntimeError(f"minimax returned no choices: {response}")

    message: dict[str, Any] = choices[0].get("message", {})
    text: str = message.get("content", "").strip()
    logger.info("Chunk %d analyzed in %.1fs (%d chars)", chunk_index, elapsed, len(text))
    return text


def merge_summaries(
    chunk_summaries: list[str],
    video_title: str,
    uploader: str,
    duration_s: float,
    max_tokens: int = 2000,
) -> str:
    """Reduce: 合并 N 段总结为 1 篇连贯总总结。"""
    prompt = build_merge_prompt(
        chunk_summaries=chunk_summaries,
        video_title=video_title,
        uploader=uploader,
        duration_s=duration_s,
    )

    logger.info("Merging %d chunk summaries into final report...", len(chunk_summaries))

    t0 = time.time()
    response = call_minimax_native(
        messages=[{"role": "user", "content": prompt}],
        max_tokens=max_tokens,
    )
    elapsed = time.time() - t0

    base_resp: dict[str, Any] = response.get("base_resp", {})  # type: ignore[assignment]
    if base_resp.get("status_code") != 0:
        raise RuntimeError(f"minimax merge error {base_resp.get('status_code')}: {base_resp.get('status_msg')}")

    choices: list[dict[str, Any]] = response.get("choices", [])  # type: ignore[assignment]
    if not choices:
        raise RuntimeError(f"minimax merge returned no choices: {response}")

    message: dict[str, Any] = choices[0].get("message", {})
    text: str = message.get("content", "").strip()
    logger.info("Final merge completed in %.1fs (%d chars)", elapsed, len(text))
    return text
