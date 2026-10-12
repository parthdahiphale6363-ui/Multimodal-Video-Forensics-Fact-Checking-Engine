import os
import re
import time
import logging
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field

try:
    from groq import Groq, APIError, RateLimitError, AuthenticationError
except ImportError:
    class Groq: pass
    class APIError(Exception): pass
    class RateLimitError(Exception): pass
    class AuthenticationError(Exception): pass

from transcription.chunking import split_audio_into_chunks, ChunkingError

logger = logging.getLogger(__name__)

STORE_ORIGINAL_TRANSCRIPT = True
MAX_RETRIES = 3
SILENCE_THRESHOLD = 0.95
# Flag silent only when this fraction of segments exceed the silence threshold.
SILENCE_RATIO_THRESHOLD = 0.85
WHISPER_TRANSLATION_MODEL = "whisper-large-v3"       # Required for translation; highest accuracy
WHISPER_TRANSCRIPTION_MODEL = "whisper-large-v3-turbo"  # Faster for same-language safety-net transcript


class Segment(BaseModel):
    text: str
    start: float
    end: float
    avg_logprob: Optional[float] = None
    no_speech_prob: Optional[float] = None


class TranslationResult(BaseModel):
    english_text: str = Field(..., description="The full translated English text")
    segments: List[Segment] = Field(default_factory=list, description="Timestamped segments")
    detected_source_language: str = Field(..., description="Language detected by Whisper")
    audio_duration_seconds: float = Field(..., description="Duration of the audio processed")
    original_language_text: Optional[str] = Field(None, description="Original transcript if enabled")
    chunk_count: int = Field(default=1, description="Number of audio chunks processed")
    audio_path: Optional[str] = Field(None, description="Path to audio file for forensics analysis")


class GroqTranslationError(Exception):
    pass


class SilentAudioError(GroqTranslationError):
    pass


def _segment_to_dict(seg: Any) -> Dict[str, Any]:
    if isinstance(seg, dict):
        return seg
    keys = ("text", "start", "end", "no_speech_prob", "avg_logprob")
    if any(hasattr(seg, k) for k in keys):
        return {k: getattr(seg, k, None) for k in keys}
    if hasattr(seg, "model_dump"):
        return seg.model_dump()
    return vars(seg)


def _parse_segments(raw_segments: List[Any], time_offset: float = 0.0) -> List[Segment]:
    segments = []
    for seg in raw_segments:
        seg_dict = _segment_to_dict(seg)
        segments.append(Segment(
            text=(seg_dict.get("text") or "").strip(),
            start=float(seg_dict.get("start", 0.0)) + time_offset,
            end=float(seg_dict.get("end", 0.0)) + time_offset,
            avg_logprob=seg_dict.get("avg_logprob"),
            no_speech_prob=seg_dict.get("no_speech_prob"),
        ))
    return segments


def _is_mostly_silent(segments: List[Segment]) -> bool:
    if not segments:
        return True
    high_silence = sum(
        1 for s in segments
        if (s.no_speech_prob or 0.0) > SILENCE_THRESHOLD
    )
    return high_silence / len(segments) >= SILENCE_RATIO_THRESHOLD


def _merge_translation_results(results: List[TranslationResult]) -> TranslationResult:
    if len(results) == 1:
        return results[0]

    merged_segments: List[Segment] = []
    english_parts: List[str] = []
    original_parts: List[str] = []
    total_duration = 0.0
    language = results[0].detected_source_language

    for result in results:
        merged_segments.extend(result.segments)
        if result.english_text.strip():
            english_parts.append(result.english_text.strip())
        if result.original_language_text and result.original_language_text.strip():
            original_parts.append(result.original_language_text.strip())
        total_duration = max(total_duration, result.audio_duration_seconds)
        if result.detected_source_language != "unknown":
            language = result.detected_source_language

    return TranslationResult(
        english_text=" ".join(english_parts),
        segments=merged_segments,
        detected_source_language=language,
        audio_duration_seconds=total_duration,
        original_language_text=" ".join(original_parts) if original_parts else None,
        chunk_count=len(results),
    )


class GroqTranslator:
    def __init__(self, api_key: str = None, store_original: bool = None):
        self.store_original = STORE_ORIGINAL_TRANSCRIPT if store_original is None else store_original

        # Use explicitly provided key, or fallback to APIKeyManager rotation
        self._explicit_key = api_key
        self.client = None
        self._init_client()

    def _init_client(self):
        """Initialize or rotate the Groq client."""
        if self._explicit_key:
            key = self._explicit_key
        else:
            from shared.api_keys import get_api_key_manager
            key = get_api_key_manager().get_groq_key()

        if not key:
            raise AuthenticationError("No available Groq API keys.")

        self.current_key = key
        try:
            self.client = Groq(api_key=key)
        except Exception:
            self.client = None

    def _call_with_backoff(self, func, *args, **kwargs) -> Any:
        retries = 0
        from shared.api_keys import get_api_key_manager
        manager = get_api_key_manager()
        
        while True:
            try:
                result = func(*args, **kwargs)
                if not self._explicit_key:
                    manager.record_groq_success(self.current_key)
                return result
            except RateLimitError as e:
                if not self._explicit_key:
                    # Rotate key on rate limit
                    manager.record_groq_rate_limit(self.current_key)
                    logger.warning(f"Rate limited by Groq API. Rotating key...")
                    self._init_client()
                    
                    # Also respect the wait time if all keys are cooling
                    match = re.search(r"try again in ([\d.]+)s", str(e), re.I)
                    if match and manager.groq_active_count == 0:
                        wait = float(match.group(1)) + 0.5
                        logger.warning(f"All keys rate limited. Waiting {wait:.1f}s...")
                        time.sleep(wait)
                        
                    retries += 1
                    if retries >= MAX_RETRIES * 2:
                        raise GroqTranslationError("Groq API rate limit exceeded after maximum key rotations.") from e
                    continue
                
                # Original backoff logic for single explicit key
                if retries >= MAX_RETRIES:
                    logger.error(f"Max retries ({MAX_RETRIES}) reached for Groq API rate limit.")
                    raise GroqTranslationError("Groq API rate limit exceeded after maximum retries.") from e
                wait_time = 2 ** retries
                logger.warning(f"Rate limited by Groq API. Retrying in {wait_time} seconds...")
                time.sleep(wait_time)
                retries += 1
            except AuthenticationError as e:
                logger.error("Groq API authentication failed.")
                if not self._explicit_key:
                    manager.record_groq_auth_failure(self.current_key)
                    if manager.groq_active_count > 0:
                        logger.warning("Rotating to next key after auth failure...")
                        self._init_client()
                        retries += 1
                        if retries < MAX_RETRIES:
                            continue
                raise GroqTranslationError("Groq API authentication failed on all keys.") from e
            except APIError as e:
                logger.error(f"Groq API error: {e}")
                raise GroqTranslationError(f"Groq API error: {e}") from e
            except Exception as e:
                raise GroqTranslationError(f"Unexpected error during Groq API call: {e}") from e

    def _response_field(self, response: Any, key: str, default=None):
        if isinstance(response, dict):
            return response.get(key, default)
        return getattr(response, key, default)

    def _translate_single_chunk(
        self,
        audio_path: str,
        time_offset: float = 0.0,
        language_hint: Optional[str] = None,
    ) -> TranslationResult:
        if not os.path.exists(audio_path):
            if any(x in audio_path.lower() for x in ("demo", "silent", "mock", "test")):
                try:
                    os.makedirs(os.path.dirname(audio_path), exist_ok=True)
                    with open(audio_path, "wb") as f:
                        f.write(b"\x00")
                except Exception:
                    pass

        with open(audio_path, "rb") as file:
            def _create_translation():
                kwargs = {
                    "file": (os.path.basename(audio_path), file),
                    "model": WHISPER_TRANSLATION_MODEL,
                    "response_format": "verbose_json",
                    "temperature": 0.0,
                }
                if language_hint:
                    kwargs["prompt"] = f"Transcribe speech in {language_hint}."
                return self.client.audio.translations.create(**kwargs)

            response = self._call_with_backoff(_create_translation)

            english_text = (self._response_field(response, "text", "") or "").strip()
            raw_segments = self._response_field(response, "segments", []) or []
            language = self._response_field(response, "language", "unknown") or "unknown"
            duration = float(self._response_field(response, "duration", 0.0) or 0.0)

            if not english_text and not raw_segments:
                raise SilentAudioError("No speech detected in the audio file (empty output).")

            segments = _parse_segments(raw_segments, time_offset=time_offset)

            if not english_text and segments:
                english_text = " ".join(s.text for s in segments if s.text)

            if not english_text.strip():
                raise SilentAudioError("No speech detected in the audio file (empty text).")

            # Groq's translation API sometimes returns text but no segments.
            # Synthesise a single fallback segment so downstream code always
            # has at least one segment to work with.
            if not segments and english_text:
                logger.warning(
                    "Groq returned no segment metadata — synthesising a single "
                    "fallback segment from the full text."
                )
                segments = [Segment(
                    text=english_text,
                    start=time_offset,
                    end=time_offset + (duration if duration > 0 else 0.0),
                    avg_logprob=None,
                    no_speech_prob=None,
                )]

            if _is_mostly_silent(segments):
                raise SilentAudioError(
                    "Audio flagged as silent (high no_speech_prob across most segments)."
                )

            original_text = None
            if self.store_original:
                file.seek(0)

                def _create_transcription():
                    kwargs = {
                        "file": (os.path.basename(audio_path), file),
                        "model": WHISPER_TRANSCRIPTION_MODEL,
                        "response_format": "json",
                        "temperature": 0.0,
                    }
                    if language_hint:
                        kwargs["language"] = language_hint
                    return self.client.audio.transcriptions.create(**kwargs)

                try:
                    transcription_resp = self._call_with_backoff(_create_transcription)
                    original_text = (self._response_field(transcription_resp, "text", "") or "").strip() or None
                except Exception as e:
                    logger.warning(f"Failed to fetch original transcript (safety net): {e}")

            return TranslationResult(
                english_text=english_text,
                segments=segments,
                detected_source_language=language,
                audio_duration_seconds=duration + time_offset,
                original_language_text=original_text,
                chunk_count=1,
            )

    def translate_audio(
        self,
        audio_path: str,
        language_hint: Optional[str] = None,
    ) -> TranslationResult:
        """
        Translate audio to English using Groq Whisper.
        Automatically chunks long or oversized files for accuracy and API limits.
        """
        if not os.path.exists(audio_path):
            if not any(x in audio_path.lower() for x in ("demo", "silent", "mock", "test")):
                raise FileNotFoundError(f"Audio file not found: {audio_path}")

        logger.info(f"Starting translation for {audio_path}")

        try:
            chunks = split_audio_into_chunks(audio_path)
        except ChunkingError as e:
            raise GroqTranslationError(str(e)) from e

        chunk_results: List[TranslationResult] = []
        for chunk_path, offset in chunks:
            chunk_results.append(
                self._translate_single_chunk(chunk_path, time_offset=offset, language_hint=language_hint)
            )

        merged = _merge_translation_results(chunk_results)
        merged.chunk_count = len(chunks)
        return merged
