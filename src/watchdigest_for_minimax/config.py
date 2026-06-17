"""Configuration: environment variable reading."""

from __future__ import annotations

import os
from pathlib import Path


def get_api_key() -> str:
    """Get API key from environment, with fallback."""
    key = os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_AUTH_TOKEN")
    if not key:
        raise RuntimeError("未设置 ANTHROPIC_API_KEY 环境变量。请 export ANTHROPIC_API_KEY=<your_key>")
    return key


def get_base_url() -> str:
    """Get API base URL."""
    return os.getenv("ANTHROPIC_BASE_URL", "https://api.minimaxi.com/anthropic")


def get_output_dir() -> Path:
    """Get output directory for reports."""
    return Path.home() / "Documents" / "watchdigest"


def get_pricing() -> dict[str, float]:
    """Get pricing from environment, with defaults."""
    return {
        "input_per_million": float(os.getenv("WATCHDIGEST_INPUT_PRICE", "2.10")),
        "output_per_million": float(os.getenv("WATCHDIGEST_OUTPUT_PRICE", "8.40")),
    }


def get_video_mode() -> str:
    """Get video processing mode."""
    return os.getenv("WATCHDIGEST_VIDEO_MODE", "auto")


def get_chunk_seconds() -> int:
    """Get chunk duration in seconds for video_url mode."""
    return int(os.getenv("WATCHDIGEST_CHUNK_SECONDS", "45"))


def get_chunk_target_size_mb() -> int:
    """Get target chunk size in MB."""
    return int(os.getenv("WATCHDIGEST_CHUNK_TARGET_SIZE_MB", "5"))


def get_http_port() -> int:
    """Get HTTP server port for video_url mode."""
    return int(os.getenv("WATCHDIGEST_HTTP_PORT", "41234"))


def get_public_host() -> str:
    """Get public host IP for video_url mode."""
    return os.getenv("WATCHDIGEST_PUBLIC_HOST", "8.136.148.185")
