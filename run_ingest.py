"""
End-to-end ingestion test: extract audio -> prep -> Groq Whisper translation.

Usage:
  python run_ingest.py --url "https://www.youtube.com/watch?v=..."
  python run_ingest.py --audio path/to/local.mp3
  python run_ingest.py --audio clip.mp3 --language es
"""
import argparse
import logging
import os
import sys

from dotenv import load_dotenv

load_dotenv()
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from pipeline.ingest import ingest_video
from shared.schemas.job import Job, JobStatus
from transcription.groq_translator import SilentAudioError, GroqTranslationError

logging.basicConfig(level=logging.INFO, format="%(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


def main():
    parser = argparse.ArgumentParser(description="Run the video ingestion pipeline.")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--url", help="Video URL (YouTube, etc.)")
    group.add_argument("--audio", help="Local audio/video file path")
    parser.add_argument("--language", help="Optional source language hint (ISO 639-1, e.g. es, hi)")
    args = parser.parse_args()

    source = args.url or args.audio
    job = Job(video_url=source)

    logger.info(f"Starting job {job.id}")
    result = ingest_video(job, language_hint=args.language)

    print("\n" + "=" * 60)
    print(f"Job ID:    {job.id}")
    print(f"Status:    {job.status.value}")
    print(f"Progress:  {job.progress_percent:.1f}%")

    if job.status == JobStatus.FAILED:
        print(f"Error:     {job.error_message}")
        sys.exit(1)

    if not result:
        sys.exit(1)

    print(f"Language:  {result.detected_source_language.upper()}")
    print(f"Segments:  {len(result.segments)}")
    print(f"Chunks:    {result.chunk_count}")
    print(f"Duration:  {result.audio_duration_seconds:.1f}s")
    print("=" * 60)
    print("\n[ENGLISH TRANSLATION]\n")
    print(result.english_text)

    if result.original_language_text:
        print("\n" + "=" * 60)
        print("\n[ORIGINAL LANGUAGE TRANSCRIPT]\n")
        print(result.original_language_text)

    if result.segments:
        print("\n" + "=" * 60)
        print("\n[TIMESTAMPED SEGMENTS — first 10]\n")
        for seg in result.segments[:10]:
            print(f"  [{seg.start:6.1f}s → {seg.end:6.1f}s]  {seg.text}")
        if len(result.segments) > 10:
            print(f"  ... +{len(result.segments) - 10} more segments")


if __name__ == "__main__":
    try:
        main()
    except (SilentAudioError, GroqTranslationError) as e:
        logger.error(str(e))
        sys.exit(1)
