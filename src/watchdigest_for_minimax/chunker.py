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
) -> list[tuple[list[str], float, float]]:
    """Split frames into chunks with time ranges.

    Returns list of (frames_b64_slice, start_seconds, end_seconds).
    """
    frames_per_chunk = int(CHUNK_DURATION_SECONDS * fps)
    if frames_per_chunk <= 0:
        frames_per_chunk = 1

    chunks: list[tuple[list[str], float, float]] = []
    for i in range(0, len(frames_b64), frames_per_chunk):
        chunk_frames_slice = frames_b64[i : i + frames_per_chunk]
        start_s = i / fps
        end_s = min((i + frames_per_chunk) / fps, len(frames_b64) / fps)
        chunks.append((chunk_frames_slice, start_s, end_s))

    return chunks
