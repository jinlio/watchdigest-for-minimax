"""MiniMax-M3 API client using Anthropic SDK."""

from __future__ import annotations

import logging

import anthropic
from tenacity import before_sleep_log, retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from watchdigest_for_minimax.config import get_api_key, get_base_url
from watchdigest_for_minimax.prompt import SYSTEM_PROMPT

logger = logging.getLogger(__name__)

_RETRYABLE_EXCEPTIONS = (
    anthropic.APIConnectionError,
    anthropic.RateLimitError,
    anthropic.InternalServerError,
)


class MinimaxClient:
    """Client for MiniMax-M3 multimodal model via Anthropic-compatible API."""

    def __init__(self) -> None:
        self.base_url = get_base_url()
        api_key = get_api_key()
        self.client = anthropic.Anthropic(
            api_key=api_key,
            base_url=self.base_url,
        )
        self.model = "MiniMax-M3"

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type(_RETRYABLE_EXCEPTIONS),
        before_sleep=before_sleep_log(logger, logging.WARNING),  # type: ignore[arg-type]
        reraise=True,
    )
    def analyze_video(self, frames_b64: list[str], prompt: str) -> str:
        """Analyze video frames and return summary.

        Args:
            frames_b64: List of base64-encoded JPEG frames.
            prompt: User prompt for analysis.

        Returns:
            Model response text.
        """
        # Build content blocks for the message
        content_blocks: list[anthropic.types.ContentBlockParam] = []

        # Add video frames as image content
        for frame_b64 in frames_b64:
            content_blocks.append(
                anthropic.types.ImageBlockParam(
                    type="image",
                    source=anthropic.types.Base64ImageSourceParam(
                        type="base64",
                        media_type="image/jpeg",
                        data=frame_b64,
                    ),
                )
            )

        # Add text prompt
        content_blocks.append(anthropic.types.TextBlockParam(type="text", text=prompt))

        # ⚠️ MUST use system role, NOT developer role (M3 returns error 2013 otherwise)
        response = self.client.messages.create(
            model=self.model,
            max_tokens=4096,
            system=SYSTEM_PROMPT,
            messages=[
                {
                    "role": "user",
                    "content": content_blocks,
                }
            ],
        )

        # Extract text from response
        for block in response.content:
            if block.type == "text":
                return block.text

        return ""
