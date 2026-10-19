"""
forensics.py — Multimodal Forensics Analysis Module
=====================================================
Performs forensic analysis using LLM reasoning + heuristics:
  - Deepfake probability estimation
  - Voice clone detection heuristics
  - Scene / temporal consistency analysis
  - Metadata integrity analysis
  - Geolocation extraction & verification hints
  - Manipulation red flag detection
"""

import os
import re
import json
import shutil
import datetime
import subprocess
from typing import Any, Dict, List, Optional

from shared.llm import get_llm_client, get_llm_model, call_llm_with_fallback


# ─── FFprobe & FFmpeg Helpers ────────────────────────────────────────────────

def _find_ffprobe() -> Optional[str]:
    """Locate the ffprobe executable."""
    env_path = os.environ.get("FFMPEG_PATH")
    if env_path:
        candidate_dir = env_path if os.path.isdir(env_path) else os.path.dirname(env_path)
        candidate = os.path.join(candidate_dir, "ffprobe.exe" if os.name == "nt" else "ffprobe")
        if os.path.exists(candidate):
            return candidate

    ffprobe_on_path = shutil.which("ffprobe")
    if ffprobe_on_path:
        return ffprobe_on_path

    # Try Winget location or standard windows dirs
    local_app_data = os.environ.get("LOCALAPPDATA", "")
    winget_base = os.path.join(local_app_data, "Microsoft", "WinGet", "Packages")
    if os.path.isdir(winget_base):
        for pkg_dir in os.listdir(winget_base):
            if "ffmpeg" in pkg_dir.lower():
                for root, dirs, files in os.walk(os.path.join(winget_base, pkg_dir)):
                    for f in files:
                        if f.lower() == ("ffprobe.exe" if os.name == "nt" else "ffprobe"):
                            return os.path.join(root, f)
    return None


def _find_ffmpeg() -> Optional[str]:
    """Locate the ffmpeg executable."""
    env_path = os.environ.get("FFMPEG_PATH")
    if env_path:
        candidate_dir = env_path if os.path.isdir(env_path) else os.path.dirname(env_path)
        candidate = os.path.join(candidate_dir, "ffmpeg.exe" if os.name == "nt" else "ffmpeg")
        if os.path.exists(candidate):
            return candidate

    ffmpeg_on_path = shutil.which("ffmpeg")
    if ffmpeg_on_path:
        return ffmpeg_on_path
    return None


def analyze_audio_stream(audio_path: Optional[str] = None) -> Dict[str, Any]:
    """
    Perform technical audio stream analysis using ffprobe / ffmpeg:
      - Sample rate (TTS / cloned voice models often output at 22050 Hz or 24000 Hz)
      - Bitrate & channel count
      - Duration consistency
      - Silence burst analysis (detects splice editing / stitched voice generation)
    """
    default_result = {
        "audio_stream_available": False,
        "sample_rate": None,
        "channels": None,
        "codec_name": None,
        "bit_rate_kbps": None,
        "duration_seconds": None,
        "silence_burst_count": 0,
        "technical_anomaly_score": 0.0,
        "technical_flags": [],
        "technical_summary": "No audio file provided or available for technical stream analysis.",
    }

    if not audio_path or not os.path.isfile(audio_path):
        return default_result

    ffprobe = _find_ffprobe()
    if not ffprobe:
        return {
            **default_result,
            "technical_summary": "ffprobe binary not found on system; stream analysis skipped.",
        }

    technical_flags = []
    anomaly_score = 0.0
    sample_rate = None
    channels = None
    codec_name = None
    bit_rate_kbps = None
    duration = None

    try:
        cmd = [
            ffprobe,
            "-v", "quiet",
            "-print_format", "json",
            "-show_format",
            "-show_streams",
            audio_path,
        ]
        res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=15)
        if res.returncode == 0 and res.stdout:
            data = json.loads(res.stdout)
            streams = data.get("streams", [])
            audio_streams = [s for s in streams if s.get("codec_type") == "audio"]
            format_info = data.get("format", {})

            if audio_streams:
                s0 = audio_streams[0]
                codec_name = s0.get("codec_name")
                channels = int(s0.get("channels", 1))
                try:
                    sample_rate = int(s0.get("sample_rate", 0))
                except (ValueError, TypeError):
                    sample_rate = None

                raw_bitrate = s0.get("bit_rate") or format_info.get("bit_rate")
                if raw_bitrate:
                    try:
                        bit_rate_kbps = round(float(raw_bitrate) / 1000.0, 1)
                    except (ValueError, TypeError):
                        bit_rate_kbps = None

                raw_dur = s0.get("duration") or format_info.get("duration")
                if raw_dur:
                    try:
                        duration = round(float(raw_dur), 2)
                    except (ValueError, TypeError):
                        duration = None

                # ── Heuristic technical anomaly checks ──
                # 1. Unusual sample rate (common in AI speech models like Bark/Tortoise/ElevenLabs older exports)
                if sample_rate in (22050, 24000):
                    technical_flags.append(f"Unusual sample rate ({sample_rate} Hz) characteristic of neural TTS / voice models")
                    anomaly_score += 0.30

                # 2. Extremely low bitrate in modern speech
                if bit_rate_kbps and bit_rate_kbps < 32:
                    technical_flags.append(f"Very low audio bitrate ({bit_rate_kbps} kbps) — possible artifact suppression")
                    anomaly_score += 0.15

    except Exception as e:
        print(f"[forensics] ffprobe error: {e}")

    # ── Silence burst analysis via ffmpeg (detects splice editing) ──
    silence_burst_count = 0
    ffmpeg = _find_ffmpeg()
    if ffmpeg and audio_path and os.path.isfile(audio_path):
        try:
            silence_cmd = [
                ffmpeg,
                "-i", audio_path,
                "-af", "silencedetect=noise=-30dB:d=0.25",
                "-f", "null",
                "-",
            ]
            s_res = subprocess.run(silence_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=20)
            stderr_out = s_res.stderr or ""
            silence_starts = re.findall(r"silence_start:\s*([\d.]+)", stderr_out)
            silence_burst_count = len(silence_starts)

            # High frequency of micro-silences (<0.5s bursts spaced closely) suggests audio splicing / cut-and-paste
            if silence_burst_count >= 6:
                technical_flags.append(f"Multiple abrupt silence gaps detected ({silence_burst_count} cuts) — possible splice/sentence grafting")
                anomaly_score += 0.25
        except Exception as e:
            print(f"[forensics] silencedetect error: {e}")

    anomaly_score = min(round(anomaly_score, 3), 1.0)
    summary = (
        f"Technical audio analysis: Codec {codec_name or 'unknown'}, {sample_rate or 'unknown'} Hz, "
        f"{channels or 'unknown'} ch, {bit_rate_kbps or 'unknown'} kbps. "
        + (f"⚠️ Flags: {'; '.join(technical_flags)}" if technical_flags else "No technical audio anomalies detected.")
    )

    return {
        "audio_stream_available": True,
        "sample_rate": sample_rate,
        "channels": channels,
        "codec_name": codec_name,
        "bit_rate_kbps": bit_rate_kbps,
        "duration_seconds": duration,
        "silence_burst_count": silence_burst_count,
        "technical_anomaly_score": anomaly_score,
        "technical_flags": technical_flags,
        "technical_summary": summary,
    }


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _call_groq(prompt_system: str, prompt_user: str, max_tokens: int = 800) -> Optional[str]:
    client = get_llm_client()
    if not client:
        return None
    
    try:
        response = call_llm_with_fallback(
            client=client,
            model=get_llm_model(),
            messages=[
                {"role": "system", "content": prompt_system},
                {"role": "user", "content": prompt_user},
            ],
            temperature=0.0,
            max_tokens=max_tokens,
        )
        if response.choices:
            return getattr(response.choices[0].message, "content", "") or ""
    except Exception as e:
        print(f"[forensics] Groq API error: {e}")
    return None


def _extract_json(text: str) -> Optional[Dict]:
    if not text:
        return None
    # 1. Clean markdown code fences if present
    cleaned = text.strip()
    fence_match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", cleaned, re.IGNORECASE)
    if fence_match:
        cleaned = fence_match.group(1).strip()

    # 2. Try direct json parse
    try:
        data = json.loads(cleaned)
        if isinstance(data, dict):
            return data
    except Exception:
        pass

    # 3. Find balanced braces for the first valid JSON object
    start = cleaned.find("{")
    while start != -1:
        depth = 0
        in_string = False
        escape = False
        for i in range(start, len(cleaned)):
            c = cleaned[i]
            if escape:
                escape = False
                continue
            if c == '\\':
                escape = True
                continue
            if c == '"':
                in_string = not in_string
                continue
            if not in_string:
                if c == '{':
                    depth += 1
                elif c == '}':
                    depth -= 1
                    if depth == 0:
                        candidate = cleaned[start:i+1]
                        try:
                            parsed = json.loads(candidate)
                            if isinstance(parsed, dict):
                                return parsed
                        except Exception:
                            pass
                        break
        start = cleaned.find("{", start + 1)

    return None



# ─── 1. Deepfake & Manipulation Detection ────────────────────────────────────

DEEPFAKE_RED_FLAGS = [
    "the audio doesn't match",
    "lip sync is off",
    "background noise inconsistency",
    "unnatural speech pattern",
    "voice sounds robotic",
    "audio cuts abruptly",
    "unusual facial movements",
]

MANIPULATION_PHRASES = [
    "this was edited",
    "clip was taken out of context",
    "original video was altered",
    "the recording was manipulated",
    "voices were changed",
]


def analyze_deepfake_heuristics(
    transcript: str,
    video_url: str,
    technical_audio: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    technical_flags = list((technical_audio or {}).get("technical_flags", []))
    red_flags_found = list(technical_flags)
    transcript_lower = transcript.lower()

    for flag in DEEPFAKE_RED_FLAGS:
        if flag in transcript_lower:
            red_flags_found.append(flag)

    for phrase in MANIPULATION_PHRASES:
        if phrase in transcript_lower:
            red_flags_found.append(f"Self-reference to manipulation: '{phrase}'")

    sentences = [s.strip() for s in re.split(r'[.!?]', transcript) if s.strip()]
    avg_sentence_length = sum(len(s.split()) for s in sentences) / max(len(sentences), 1)
    repetition_score = 0.0
    if sentences:
        unique_ratio = len(set(sentences)) / len(sentences)
        repetition_score = 1.0 - unique_ratio

    if repetition_score > 0.3:
        red_flags_found.append(f"High phrase repetition detected (score: {repetition_score:.2f})")

    if avg_sentence_length < 4:
        red_flags_found.append("Unusually short speech segments — possible splice editing")

    # Technical audio signals (sample rate anomalies, silence bursts)
    tech_anomaly_score = 0.0
    if technical_audio:
        tech_flags = technical_audio.get("technical_flags", [])
        if tech_flags:
            red_flags_found.extend(tech_flags)
        tech_anomaly_score = float(technical_audio.get("technical_anomaly_score", 0.0))

    # LLM-based deepfake analysis
    llm_deepfake_prob = 0.0
    llm_analysis = ""
    system_prompt = (
        "You are a video forensics expert specializing in deepfake detection. "
        "Analyze the video transcript for signs of deepfake manipulation, AI-generated speech, "
        "voice cloning, context manipulation, or out-of-context editing. "
        "Return ONLY valid JSON with keys: deepfake_probability (0.0–1.0), "
        "voice_clone_probability (0.0–1.0), manipulation_indicators (list of strings), "
        "analysis_summary (string), scene_consistency_score (0.0–1.0)."
    )
    user_prompt = (
        f"Video URL: {video_url}\n\n"
        f"Transcript (first 3000 chars):\n{transcript[:3000]}\n\n"
        "Analyze for: deepfake indicators, voice cloning, context manipulation, "
        "out-of-context clips, AI-generated speech patterns, or audio inconsistencies."
    )

    raw = _call_groq(system_prompt, user_prompt, max_tokens=600)
    parsed = _extract_json(raw) if raw else None

    if parsed:
        llm_deepfake_prob = float(parsed.get("deepfake_probability", 0.0))
        voice_clone_prob = float(parsed.get("voice_clone_probability", 0.0))
        llm_indicators = parsed.get("manipulation_indicators", [])
        llm_analysis = parsed.get("analysis_summary", "")
        scene_consistency = float(parsed.get("scene_consistency_score", 0.8))
        if llm_indicators:
            red_flags_found.extend(llm_indicators[:3])
    elif raw and len(raw.strip()) > 25 and not raw.strip().lower().startswith("error"):
        # Salvage LLM analysis text even if response was not in strict JSON
        clean_text = re.sub(r"```(?:json)?\s*[\s\S]*?\s*```", "", raw).strip() or raw.strip()
        clean_text = re.sub(r'[\{\}"\[\]]', '', clean_text).strip()
        llm_analysis = clean_text[:400].strip() if len(clean_text) > 20 else "Audio and speech patterns analyzed."
        llm_deepfake_prob = min(len(red_flags_found) / 5.0 * 0.4, 0.6)
        voice_clone_prob = min(repetition_score * 0.5, 0.5)
        scene_consistency = max(0.5, 1.0 - len(red_flags_found) / 8.0)
    else:
        # Fallback: estimate from heuristics with descriptive summary
        llm_deepfake_prob = min(len(red_flags_found) / 5.0 * 0.4, 0.6)
        voice_clone_prob = min(repetition_score * 0.5, 0.5)
        scene_consistency = max(0.5, 1.0 - len(red_flags_found) / 8.0)
        if red_flags_found:
            llm_analysis = f"Heuristic analysis completed: {len(red_flags_found)} speech/audio anomaly indicator(s) identified."
        else:
            llm_analysis = "Speech pattern analysis indicates natural cadence and consistency with no deepfake or voice cloning markers."


    # Incorporate technical audio stream anomaly
    voice_clone_prob = min(round(voice_clone_prob + tech_anomaly_score * 0.45, 3), 0.98)
    base_deepfake_prob = min(round(llm_deepfake_prob + len(red_flags_found) * 0.05 + tech_anomaly_score * 0.35, 3), 0.98)

    # Multi-modal synthetic media classification
    is_synthetic = bool(base_deepfake_prob >= 0.55 or voice_clone_prob >= 0.60)
    forensics_veto = {
        "veto": is_synthetic,
        "verdict": "Deepfake" if is_synthetic else None,
        "reason": "Synthetic audio/deepfake indicators exceed threshold" if is_synthetic else None,
    }

    return {
        "deepfake_probability": round(base_deepfake_prob, 3),
        "voice_clone_probability": round(voice_clone_prob, 3),
        "is_synthetic": is_synthetic,
        "forensics_veto": forensics_veto,
        "scene_consistency_score": round(scene_consistency, 3),
        "red_flags": list(set(red_flags_found))[:8],
        "red_flag_count": len(set(red_flags_found)),
        "repetition_score": round(repetition_score, 3),
        "avg_sentence_length": round(avg_sentence_length, 1),
        "analysis_summary": llm_analysis or "No significant deepfake indicators found in transcript.",
    }


# ─── 2. Metadata Analysis ─────────────────────────────────────────────────────

SUSPICIOUS_URL_PATTERNS = [
    r'bit\.ly', r'tinyurl', r't\.co', r'shorturl', r'is\.gd', r'buff\.ly',  # URL shorteners
    r'[?&](?:redirect|dest|url)=https?://',  # Open redirect patterns
    r'[?&]v=[^&]+[?&]v=',  # Duplicate conflicting video IDs
]

LEGITIMATE_URL_PARAMS = {
    # YouTube parameters
    'v', 't', 'time_continue', 'start', 'list', 'index', 'ab_channel',
    'si', 'feature', 'app', 'pp', 'src', 'theme', 'hl', 'gl',
    'embeds_referring_euri', 'embeds_referring_origin', 'source_ve_path',
    'clip', 'clipt', 'cbrd', 'ucbcb', 'rv', 'sub_confirmation',
    # Standard campaign / tracking parameters
    'utm_source', 'utm_medium', 'utm_campaign', 'utm_term', 'utm_content',
    # Social platform parameters
    'fbclid', 'igshid', 's', 'sfnsn', 'ref', 'source', 'context',
}


def analyze_metadata(video_url: str) -> Dict[str, Any]:
    """
    Analyze video URL and metadata for integrity signals.
    """
    integrity_issues = []
    integrity_score = 100.0

    # Check URL shorteners / unusual parameters
    for pattern in SUSPICIOUS_URL_PATTERNS:
        if re.search(pattern, video_url, re.IGNORECASE):
            integrity_issues.append(f"URL shortener/redirect detected: {pattern}")
            integrity_score -= 15

    # Platform detection
    platform = "unknown"
    if "youtube.com" in video_url or "youtu.be" in video_url:
        platform = "YouTube"
    elif "instagram.com" in video_url:
        platform = "Instagram"
    elif "tiktok.com" in video_url:
        platform = "TikTok"
        integrity_issues.append("TikTok content — higher risk of context manipulation")
        integrity_score -= 10
    elif "facebook.com" in video_url or "fb.watch" in video_url:
        platform = "Facebook"

    # Extract YouTube video ID for additional checks
    yt_match = re.search(r'(?:v=|youtu\.be/)([A-Za-z0-9_-]{11})', video_url)
    video_id = yt_match.group(1) if yt_match else None

    # Check for suspicious query parameters (ignoring standard platform & share parameters)
    params = re.findall(r'[?&]([^=]+)=([^&]+)', video_url)
    suspicious_params = [f"{k}={v}" for k, v in params if k.lower() not in LEGITIMATE_URL_PARAMS]
    if suspicious_params:
        integrity_issues.append(f"Unusual URL parameters: {', '.join(suspicious_params[:3])}")
        integrity_score -= 5

    integrity_score = max(integrity_score, 0.0)


    return {
        "platform": platform,
        "video_id": video_id,
        "integrity_score": round(integrity_score, 1),
        "integrity_issues": integrity_issues,
        "url_length": len(video_url),
        "has_tracking_params": bool(suspicious_params),
        "metadata_summary": f"Video from {platform}. Metadata integrity: {integrity_score:.0f}/100.",
    }


# ─── 3. Geolocation Extraction ───────────────────────────────────────────────

# Simple NER for locations using pattern matching
COUNTRY_NAMES = [
    "india", "china", "usa", "united states", "russia", "ukraine", "pakistan",
    "iran", "israel", "france", "germany", "uk", "brazil", "australia",
    "canada", "japan", "south korea", "north korea", "afghanistan", "iraq",
    "syria", "turkey", "egypt", "nigeria", "mexico", "italy", "spain",
]

CITY_PATTERNS = [
    r'\b(new york|los angeles|london|paris|beijing|moscow|mumbai|delhi|'
    r'tokyo|berlin|sydney|toronto|dubai|singapore|istanbul|cairo|lagos|'
    r'karachi|dhaka|tehran|baghdad|kabul|kyiv|warsaw|rome|madrid|'
    r'barcelona|amsterdam|brussels|vienna|stockholm|oslo|copenhagen)\b'
]


def extract_geolocation_claims(transcript: str) -> Dict[str, Any]:
    """
    Extract geographic references from transcript using pattern matching.
    """
    transcript_lower = transcript.lower()
    locations_found = []

    # Country detection
    for country in COUNTRY_NAMES:
        if country in transcript_lower:
            locations_found.append({"type": "country", "name": country.title()})

    # City detection
    for pattern in CITY_PATTERNS:
        matches = re.findall(pattern, transcript_lower)
        for m in matches:
            locations_found.append({"type": "city", "name": m.title()})

    # Deduplicate
    seen = set()
    unique_locations = []
    for loc in locations_found:
        key = f"{loc['type']}:{loc['name']}"
        if key not in seen:
            seen.add(key)
            unique_locations.append(loc)

    # Check for conflicting geographic claims
    countries_mentioned = [l["name"] for l in unique_locations if l["type"] == "country"]
    geo_conflict = len(countries_mentioned) >= 4  # Many countries = potential misattribution

    return {
        "locations_found": unique_locations[:10],
        "location_count": len(unique_locations),
        "countries": [l["name"] for l in unique_locations if l["type"] == "country"],
        "cities": [l["name"] for l in unique_locations if l["type"] == "city"],
        "potential_misattribution": geo_conflict,
        "geo_summary": (
            f"Found {len(unique_locations)} geographic references: "
            f"{', '.join(l['name'] for l in unique_locations[:5])}."
            if unique_locations else "No specific geographic references detected."
        ),
    }


# ─── 4. Temporal Consistency ─────────────────────────────────────────────────

DATE_PATTERNS = [
    r'\b(january|february|march|april|may|june|july|august|september|october|november|december)\s+\d{1,2},?\s+\d{4}\b',
    r'\b\d{1,2}/\d{1,2}/\d{2,4}\b',
    r'\b\d{4}-\d{2}-\d{2}\b',
    r'\b(last year|this year|yesterday|last week|last month|in \d{4})\b',
    r'\b(20\d{2})\b',
]


def analyze_temporal_consistency(transcript: str) -> Dict[str, Any]:
    """
    Extract and analyze temporal references in the transcript for consistency.
    """
    transcript_lower = transcript.lower()
    date_refs = []

    for pattern in DATE_PATTERNS:
        matches = re.findall(pattern, transcript_lower)
        for m in matches:
            if isinstance(m, tuple):
                date_refs.extend([x for x in m if x])
            else:
                date_refs.append(m)

    # Extract years specifically
    years = re.findall(r'\b(19\d{2}|20\d{2})\b', transcript)
    year_ints = [int(y) for y in years]
    current_year = datetime.datetime.now().year

    temporal_issues = []
    if year_ints:
        future_years = [y for y in year_ints if y > current_year]
        if future_years:
            temporal_issues.append(f"Future dates referenced: {future_years}")

        year_span = max(year_ints) - min(year_ints)
        if year_span > 20:
            temporal_issues.append(f"Large date range span ({year_span} years) — possible old footage misrepresentation")

    contradictory_tense = False
    past_indicators = sum(1 for w in ["was", "were", "had", "did", "happened"] if w in transcript_lower.split())
    present_indicators = sum(1 for w in ["is", "are", "has", "does", "happens"] if w in transcript_lower.split())
    if past_indicators > 0 and present_indicators > 0:
        tense_ratio = abs(past_indicators - present_indicators) / max(past_indicators + present_indicators, 1)
        if tense_ratio < 0.2 and (past_indicators + present_indicators) > 20:
            contradictory_tense = True

    return {
        "date_references": list(set(date_refs))[:8],
        "years_mentioned": sorted(set(year_ints)),
        "temporal_issues": temporal_issues,
        "contradictory_tense": contradictory_tense,
        "temporal_consistency_score": round(max(0.4, 1.0 - len(temporal_issues) * 0.2), 3),
        "temporal_summary": (
            f"Temporal analysis: {len(date_refs)} date references found. "
            + (f"Issues: {'; '.join(temporal_issues)}" if temporal_issues else "No temporal inconsistencies detected.")
        ),
    }


# ─── Master Forensics Orchestrator ────────────────────────────────────────────

def run_forensics_pipeline(
    transcript: str,
    video_url: str,
    audio_path: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Run the complete forensics analysis pipeline.
    Combines LLM transcript analysis, technical audio stream metrics, metadata, and consistency checks.
    """
    print("[forensics] Performing technical audio stream analysis...")
    technical_audio = analyze_audio_stream(audio_path)

    print("[forensics] Running deepfake heuristics...")
    deepfake = analyze_deepfake_heuristics(transcript, video_url, technical_audio=technical_audio)

    print("[forensics] Analyzing metadata...")
    metadata = analyze_metadata(video_url)

    print("[forensics] Extracting geolocation...")
    geolocation = extract_geolocation_claims(transcript)

    print("[forensics] Analyzing temporal consistency...")
    temporal = analyze_temporal_consistency(transcript)

    # Compute aggregate forensics scores incorporating technical audio anomaly
    tech_penalty = technical_audio.get("technical_anomaly_score", 0.0) * 0.20
    manipulation_risk = (
        deepfake["deepfake_probability"] * 0.35
        + (1 - metadata["integrity_score"] / 100) * 0.15
        + (1 - temporal["temporal_consistency_score"]) * 0.15
        + (deepfake["voice_clone_probability"] * 0.25)
        + tech_penalty
    )

    video_integrity_score = round(max(0.0, min(100.0, (1 - manipulation_risk) * 100)), 1)
    effective_audio_risk = max(deepfake["voice_clone_probability"], technical_audio.get("technical_anomaly_score", 0.0))
    audio_integrity_score = round(max(0.0, min(100.0, (1 - effective_audio_risk) * 100)), 1)

    red_flag_count = (
        deepfake["red_flag_count"]
        + len(metadata["integrity_issues"])
        + len(temporal["temporal_issues"])
    )

    return {
        "video_integrity_score": video_integrity_score,
        "audio_integrity_score": audio_integrity_score,
        "metadata_integrity_score": metadata["integrity_score"],
        "deepfake_probability": deepfake["deepfake_probability"],
        "voice_clone_probability": deepfake["voice_clone_probability"],
        "scene_consistency_score": deepfake["scene_consistency_score"],
        "is_synthetic": deepfake.get("is_synthetic", False),
        "forensics_veto": deepfake.get("forensics_veto", {"veto": False}),
        "technical_audio": technical_audio,
        "red_flag_count": red_flag_count,
        "red_flags": deepfake["red_flags"] + metadata["integrity_issues"] + temporal["temporal_issues"],
        "deepfake_analysis": deepfake,
        "metadata_analysis": metadata,
        "geolocation": geolocation,
        "temporal_analysis": temporal,
        "platform": metadata["platform"],
        "summary": (
            f"Forensics analysis: Deepfake probability {int(deepfake['deepfake_probability'] * 100)}%, "
            f"Voice clone probability {int(deepfake['voice_clone_probability'] * 100)}%, "
            f"Video integrity {video_integrity_score:.0f}/100, "
            f"{red_flag_count} red flags detected, "
            f"Platform: {metadata['platform']}."
            + (" ⚠️ [VETO] Synthetic media detected." if deepfake.get("is_synthetic") else "")
        ),
    }
