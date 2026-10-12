import pytest
from unittest.mock import patch, MagicMock
from types import SimpleNamespace
import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from transcription.groq_translator import (
    GroqTranslator,
    SilentAudioError,
    GroqTranslationError,
    _is_mostly_silent,
    Segment,
)
from transcription.audio_prep import prep_audio_for_groq, AudioPrepError
from transcription.chunking import split_audio_into_chunks, needs_chunking
from pipeline.ingest import ingest_video
from shared.schemas.job import Job, JobStatus
from backend.main import build_claim_verdicts_for_segments
from groq import RateLimitError


@pytest.fixture
def mock_groq_client():
    with patch("transcription.groq_translator.Groq") as MockGroq:
        mock_instance = MagicMock()
        MockGroq.return_value = mock_instance
        yield mock_instance


@pytest.fixture
def single_chunk():
    with patch("transcription.groq_translator.split_audio_into_chunks") as mock_split:
        mock_split.side_effect = lambda path: [(path, 0.0)]
        yield mock_split


def _mock_translation_response(text="Hello world in English.", language="es", duration=5.0, segments=None):
    mock_response = MagicMock()
    mock_response.text = text
    mock_response.language = language
    mock_response.duration = duration
    if segments is None:
        mock_segment = MagicMock()
        mock_segment.text = "Hola mundo"
        mock_segment.start = 0.0
        mock_segment.end = 5.0
        mock_segment.no_speech_prob = 0.1
        mock_segment.avg_logprob = -0.2
        mock_response.segments = [mock_segment]
    else:
        mock_response.segments = segments
    return mock_response


def test_successful_translation(mock_groq_client, single_chunk, tmp_path):
    audio_file = tmp_path / "test.mp3"
    audio_file.write_bytes(b"dummy content")

    mock_groq_client.audio.translations.create.return_value = _mock_translation_response()
    mock_groq_client.audio.transcriptions.create.return_value = MagicMock(text="Hola mundo")

    translator = GroqTranslator(api_key="test_key", store_original=True)
    result = translator.translate_audio(str(audio_file))

    assert result.english_text == "Hello world in English."
    assert result.detected_source_language == "es"
    assert len(result.segments) == 1
    assert result.audio_duration_seconds == 5.0
    assert result.chunk_count == 1
    mock_groq_client.audio.translations.create.assert_called_once()


@patch("time.sleep", return_value=None)
def test_rate_limit_retry_backoff(mock_sleep, mock_groq_client, single_chunk, tmp_path):
    audio_file = tmp_path / "test.mp3"
    audio_file.write_bytes(b"dummy content")

    mock_success = _mock_translation_response(text="Success after retry.")
    error_mock = RateLimitError("Rate limit exceeded", response=MagicMock(), body=None)

    mock_groq_client.audio.translations.create.side_effect = [error_mock, error_mock, mock_success]

    translator = GroqTranslator(api_key="test_key", store_original=False)
    result = translator.translate_audio(str(audio_file))

    assert result.english_text == "Success after retry."
    assert mock_groq_client.audio.translations.create.call_count == 3
    assert mock_sleep.call_count == 2
    mock_sleep.assert_any_call(1)
    mock_sleep.assert_any_call(2)


def test_silent_audio_flagged(mock_groq_client, single_chunk, tmp_path):
    audio_file = tmp_path / "test.mp3"
    audio_file.write_bytes(b"dummy content")

    mock_response = MagicMock()
    mock_response.text = " "
    mock_response.segments = []
    mock_groq_client.audio.translations.create.return_value = mock_response

    translator = GroqTranslator(api_key="test_key", store_original=False)

    with pytest.raises(SilentAudioError):
        translator.translate_audio(str(audio_file))


def test_high_silence_probability_flagged(mock_groq_client, single_chunk, tmp_path):
    audio_file = tmp_path / "test.mp3"
    audio_file.write_bytes(b"dummy content")

    mock_segment = MagicMock()
    mock_segment.text = "Um..."
    mock_segment.start = 0.0
    mock_segment.end = 10.0
    mock_segment.no_speech_prob = 0.99
    mock_segment.avg_logprob = -2.0

    mock_groq_client.audio.translations.create.return_value = _mock_translation_response(
        text="Um...", segments=[mock_segment]
    )

    translator = GroqTranslator(api_key="test_key", store_original=False)

    with pytest.raises(SilentAudioError):
        translator.translate_audio(str(audio_file))


def test_mostly_silent_requires_high_ratio():
    mixed = [
        Segment(text="a", start=0, end=1, no_speech_prob=0.99),
        Segment(text="b", start=1, end=2, no_speech_prob=0.1),
    ]
    assert not _is_mostly_silent(mixed)

    all_silent = [
        Segment(text="a", start=0, end=1, no_speech_prob=0.99),
        Segment(text="b", start=1, end=2, no_speech_prob=0.98),
    ]
    assert _is_mostly_silent(all_silent)


@patch("subprocess.run")
@patch("os.path.getsize")
def test_unsupported_format_triggers_ffmpeg(mock_getsize, mock_subprocess, tmp_path):
    audio_file = tmp_path / "test.xyz"
    audio_file.write_text("dummy")

    mock_getsize.return_value = 1024
    mock_subprocess.return_value = MagicMock(returncode=0)

    output = prep_audio_for_groq(str(audio_file), output_dir=str(tmp_path))

    assert output.endswith("test_prepared.mp3")
    mock_subprocess.assert_called()
    cmd = mock_subprocess.call_args[0][0]
    assert "ffmpeg" in cmd
    assert "-ar" in cmd
    assert "16000" in cmd
    assert "loudnorm" in cmd[cmd.index("-af") + 1]


@patch("pipeline.ingest.GroqTranslator")
@patch("pipeline.ingest.prep_audio_for_groq")
@patch("pipeline.ingest.extract_audio")
def test_ingest_pipeline_success(mock_extract, mock_prep, mock_translator_cls):
    from pipeline.ingest import ingest_video
    job = Job(video_url="/tmp/demo.mp3")
    mock_extract.return_value = MagicMock(audio_path="/tmp/demo.mp3", is_temporary=False)
    mock_prep.return_value = "/tmp/demo_prepared.mp3"
    mock_translator_cls.return_value.translate_audio.return_value = MagicMock(
        detected_source_language="en",
        segments=[MagicMock()],
        chunk_count=1,
    )

    result = ingest_video(job)

    assert result is not None
    assert job.status == JobStatus.TRANSCRIBING
    assert job.progress_percent == 55.0
    mock_extract.assert_called_once_with("/tmp/demo.mp3")
    mock_prep.assert_called_once()
    mock_translator_cls.return_value.translate_audio.assert_called_once()


@patch("pipeline.ingest.GroqTranslator")
@patch("pipeline.ingest.prep_audio_for_groq")
@patch("pipeline.ingest.extract_audio")
def test_ingest_pipeline_silent_audio(mock_extract, mock_prep, mock_translator_cls):
    from pipeline.ingest import ingest_video
    job = Job(video_url="/tmp/silent.mp3")
    mock_extract.return_value = MagicMock(audio_path="/tmp/silent.mp3", is_temporary=False)
    mock_prep.return_value = "/tmp/silent_prepared.mp3"
    mock_translator_cls.return_value.translate_audio.side_effect = SilentAudioError("No speech")

    result = ingest_video(job)

    assert result is None
    assert job.status == JobStatus.FAILED
    assert "No speech detected" in job.error_message


@patch("subprocess.run")
def test_split_audio_skips_short_files(mock_subprocess, tmp_path):
    audio_file = tmp_path / "short.mp3"
    audio_file.write_bytes(b"x" * 100)

    with patch("transcription.chunking.get_audio_duration_seconds", return_value=30.0):
        chunks = split_audio_into_chunks(str(audio_file))

    assert chunks == [(str(audio_file), 0.0)]
    mock_subprocess.assert_not_called()


def test_needs_chunking_by_size(tmp_path):
    audio_file = tmp_path / "big.mp3"
    audio_file.write_bytes(b"x" * (25 * 1024 * 1024))

    with patch("transcription.chunking.get_audio_duration_seconds", return_value=60.0):
        assert needs_chunking(str(audio_file))


def test_build_claim_verdicts_for_segments_extracts_all_claims():
    segments = [
        SimpleNamespace(text="The sky is blue during daylight.", start=0.0, end=3.0),
        SimpleNamespace(text="Water freezes at zero degrees Celsius.", start=4.0, end=7.0),
    ]

    results = build_claim_verdicts_for_segments(
        video_url="https://example.com/video",
        segments=segments,
        detected_language="en",
    )

    assert len(results) == 2
    assert results[0]["claim"]["normalized_text"].startswith("The sky")
    assert results[1]["claim"]["normalized_text"].startswith("Water")
    assert {item["verdict"]["label"] for item in results}.issubset({"true", "false"})
