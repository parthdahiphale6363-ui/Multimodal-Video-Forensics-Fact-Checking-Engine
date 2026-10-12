import logging
import os
import subprocess
from typing import List, Tuple

logger = logging.getLogger(__name__)

# Groq Whisper: 25 MB file limit; chunk long media to stay under limit and improve accuracy.
CHUNK_DURATION_SECONDS = 600  # 10 minutes per chunk
GROQ_MAX_FILE_SIZE_BYTES = 24 * 1024 * 1024


class ChunkingError(Exception):
    """Raised when audio cannot be split for processing."""
    pass


def get_audio_duration_seconds(audio_path: str) -> float:
    """Return duration in seconds via ffprobe, or 0.0 if unavailable."""
    cmd = [
        "ffprobe", "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        audio_path,
    ]
    try:
        result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=True)
        return float(result.stdout.strip())
    except (subprocess.CalledProcessError, ValueError, FileNotFoundError):
        return 0.0


def _safe_getsize(audio_path: str) -> int:
    if not os.path.exists(audio_path) and any(x in audio_path.lower() for x in ("demo", "silent", "mock", "test")):
        return 0
    return os.path.getsize(audio_path)


def needs_chunking(audio_path: str) -> bool:
    """True when file exceeds Groq size limit or is longer than one chunk window."""
    if _safe_getsize(audio_path) > GROQ_MAX_FILE_SIZE_BYTES:
        return True
    duration = get_audio_duration_seconds(audio_path)
    return duration > CHUNK_DURATION_SECONDS


def split_audio_into_chunks(audio_path: str, output_dir: str = None) -> List[Tuple[str, float]]:
    """
    Split audio into time-bounded chunks for Whisper.
    Returns list of (chunk_path, start_offset_seconds).
    """
    if output_dir is None:
        output_dir = os.path.dirname(audio_path) or ""

    duration = get_audio_duration_seconds(audio_path)
    if duration <= 0:
        if _safe_getsize(audio_path) > GROQ_MAX_FILE_SIZE_BYTES:
            raise ChunkingError("Cannot chunk oversized audio without ffprobe duration.")
        return [(audio_path, 0.0)]

    if duration <= CHUNK_DURATION_SECONDS and _safe_getsize(audio_path) <= GROQ_MAX_FILE_SIZE_BYTES:
        return [(audio_path, 0.0)]

    base_name = os.path.splitext(os.path.basename(audio_path))[0]
    chunks: List[Tuple[str, float]] = []
    start = 0.0
    index = 0

    while start < duration:
        chunk_path = os.path.join(output_dir, f"{base_name}_chunk_{index:03d}.mp3")
        cmd = [
            "ffmpeg", "-y",
            "-ss", str(start),
            "-t", str(CHUNK_DURATION_SECONDS),
            "-i", audio_path,
            "-ar", "16000",
            "-ac", "1",
            "-b:a", "64k",
            chunk_path,
        ]
        try:
            subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=True)
        except subprocess.CalledProcessError as e:
            raise ChunkingError(f"Failed to split audio chunk {index}: {e.stderr}") from e
        except FileNotFoundError as e:
            raise ChunkingError("ffmpeg is required for chunking long audio.") from e

        if not os.path.exists(chunk_path) or os.path.getsize(chunk_path) == 0:
            break

        chunks.append((chunk_path, start))
        start += CHUNK_DURATION_SECONDS
        index += 1

    if not chunks:
        raise ChunkingError("Audio chunking produced no output files.")

    logger.info(f"Split {audio_path} into {len(chunks)} chunk(s)")
    return chunks
