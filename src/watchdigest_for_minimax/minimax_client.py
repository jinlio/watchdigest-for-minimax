"""MiniMax-M3 API client using Anthropic SDK."""

from __future__ import annotations

import anthropic

from watchdigest_for_minimax.config import get_api_key, get_base_url


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
            system="你是视频总结助手，擅长分析视频内容并生成结构化摘要。",
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
