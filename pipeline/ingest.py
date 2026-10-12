import logging
import os
from datetime import datetime, timezone
from typing import Optional

try:
    from shared.schemas.job import Job, JobStatus
except ImportError:
    import sys
    sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from shared.schemas.job import Job, JobStatus

from transcription.audio_prep import prep_audio_for_groq, AudioPrepError
from transcription.extractor import extract_audio, ExtractionError, ExtractionResult
from transcription.groq_translator import (
    GroqTranslator,
    TranslationResult,
    GroqTranslationError,
    SilentAudioError,
)

logger = logging.getLogger(__name__)

# Progress weights per pipeline stage (sum = 100)
PROGRESS = {
    JobStatus.EXTRACTING: 15.0,
    JobStatus.TRANSCRIBING: 55.0,
    JobStatus.DONE: 100.0,
}


def _update_job(job: Job, status: JobStatus, progress: float, error: str = None) -> None:
    job.status = status
    job.progress_percent = progress
    job.updated_at = datetime.now(timezone.utc)
    if error:
        job.error_message = error


def ingest_video(
    job: Job,
    video_url: str = None,
    language_hint: Optional[str] = None,
) -> Optional[TranslationResult]:
    """
    Orchestrates ingestion: extract audio -> prep -> Groq translation.
    Accepts a video URL (via yt-dlp) or a local media file path.
    """
    url_to_process = video_url or job.video_url
    extraction: Optional[ExtractionResult] = None

    try:
        _update_job(job, JobStatus.EXTRACTING, 5.0)
        logger.info(f"Job {job.id} - Extracting audio from {url_to_process}")

        if callable(extract_audio):
            extraction = extract_audio(url_to_process)
        else:
            extraction = None
        if extraction is None:
            raise ExtractionError("No extraction result returned")
        _update_job(job, JobStatus.EXTRACTING, PROGRESS[JobStatus.EXTRACTING])

        logger.info(f"Job {job.id} - Preparing audio")
        prepped_audio_path = prep_audio_for_groq(extraction.audio_path)

        _update_job(job, JobStatus.TRANSCRIBING, 25.0)
        logger.info(f"Job {job.id} - Translating audio using Groq Whisper")

        translator = GroqTranslator()
        translation_result = translator.translate_audio(prepped_audio_path, language_hint=language_hint)

        # Do NOT mark the job as DONE here — process_video in main.py will
        # set DONE only after claims have been built and stored.
        _update_job(job, JobStatus.TRANSCRIBING, PROGRESS[JobStatus.TRANSCRIBING])
        logger.info(
            f"Job {job.id} - Ingestion complete "
            f"({translation_result.detected_source_language}, "
            f"{len(translation_result.segments)} segments, "
            f"{translation_result.chunk_count} chunk(s))"
        )
        translation_result.audio_path = prepped_audio_path
        return translation_result

    except SilentAudioError as e:
        _update_job(job, JobStatus.FAILED, job.progress_percent, f"No speech detected: {e}")
        logger.warning(job.error_message)
        return None

    except AudioPrepError as e:
        _update_job(job, JobStatus.FAILED, job.progress_percent, f"Audio preparation failed: {e}")
        logger.error(job.error_message)
        return None

    except ExtractionError as e:
        _update_job(job, JobStatus.FAILED, job.progress_percent, f"Extraction failed: {e}")
        logger.error(job.error_message)
        return None

    except GroqTranslationError as e:
        _update_job(job, JobStatus.FAILED, job.progress_percent, f"Transcription failed: {e}")
        logger.error(job.error_message)
        return None

    except Exception as e:
        _update_job(job, JobStatus.FAILED, job.progress_percent, f"Unexpected ingestion error: {e}")
        logger.exception(job.error_message)
        return None
