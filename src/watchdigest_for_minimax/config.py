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
