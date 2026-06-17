"""Token estimation and video chunking."""

from __future__ import annotations

# M3 video frame ~256 token/frame
FRAME_TOKEN_ESTIMATE = 256

# Single call safe threshold
SINGLE_CALL_SAFE_TOKENS = 500_000

# Chunk duration in seconds (10 minutes)
CHUNK_DURATION_SECONDS = 600


def estimate_tokens(frame_count: int, fps: float = 1.0) -> int:
    """Estimate token count from frame count."""
    return int(frame_count * FRAME_TOKEN_ESTIMATE)


def needs_chunking(token_estimate: int) -> bool:
    """Check if video needs to be chunked."""
    return token_estimate >= SINGLE_CALL_SAFE_TOKENS


def chunk_frames(
    frames_b64: list[str],
    fps: float = 1.0,
) -> list[list[str]]:
    """Split frames into chunks based on CHUNK_DURATION_SECONDS.

    Each chunk corresponds to CHUNK_DURATION_SECONDS of video.
    """
    frames_per_chunk = int(CHUNK_DURATION_SECONDS * fps)
    if frames_per_chunk <= 0:
        frames_per_chunk = 1

    chunks: list[list[str]] = []
    for i in range(0, len(frames_b64), frames_per_chunk):
        chunks.append(frames_b64[i : i + frames_per_chunk])

    return chunks
