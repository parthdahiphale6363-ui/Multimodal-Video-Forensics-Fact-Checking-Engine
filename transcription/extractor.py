import logging
import os
import shutil
import tempfile
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger(__name__)


class ExtractionError(Exception):
    """Raised when audio cannot be extracted from a video URL or path."""
    pass


def _find_ffmpeg_dir() -> Optional[str]:
    """Locate the directory containing ffmpeg/ffprobe binaries."""
    # 1. Explicit env var — can be a directory OR the ffmpeg.exe path itself
    env_path = os.environ.get("FFMPEG_PATH")
    if env_path:
        if os.path.isfile(env_path):
            return os.path.dirname(env_path)
        if os.path.isdir(env_path):
            return env_path

    # 2. Already on PATH
    ffmpeg_on_path = shutil.which("ffmpeg")
    if ffmpeg_on_path:
        return os.path.dirname(ffmpeg_on_path)

    # 3. Common winget install location
    local_app_data = os.environ.get("LOCALAPPDATA", "")
    winget_base = os.path.join(local_app_data, "Microsoft", "WinGet", "Packages")
    if os.path.isdir(winget_base):
        for pkg_dir in os.listdir(winget_base):
            if "FFmpeg" in pkg_dir or "ffmpeg" in pkg_dir:
                for root, dirs, files in os.walk(os.path.join(winget_base, pkg_dir)):
                    lower_files = [f.lower() for f in files]
                    if "ffmpeg.exe" in lower_files and "ffprobe.exe" in lower_files:
                        return root

    # 4. Chocolatey / Scoop / common manual install locations
    candidate_dirs = [
        os.path.join(os.environ.get("PROGRAMFILES", ""), "ffmpeg", "bin"),
        os.path.join(os.environ.get("PROGRAMFILES(X86)", ""), "ffmpeg", "bin"),
        os.path.join(os.environ.get("USERPROFILE", ""), "scoop", "shims"),
        r"C:\ffmpeg\bin",
        r"C:\tools\ffmpeg\bin",
    ]
    for d in candidate_dirs:
        if d and os.path.isdir(d):
            lower_files = [f.lower() for f in os.listdir(d)]
            if "ffmpeg.exe" in lower_files:
                return d

    return None


@dataclass
class ExtractionResult:
    audio_path: str
    title: Optional[str] = None
    duration_seconds: Optional[float] = None
    is_temporary: bool = False


def _is_local_media(path_or_url: str) -> bool:
    """Treat existing local paths or test mock paths as direct audio/video inputs."""
    if os.path.isfile(path_or_url):
        return True
    path_lower = path_or_url.lower()
    if not (path_lower.startswith("http://") or path_lower.startswith("https://") or path_lower.startswith("www.")):
        return True
    return False


def extract_audio(url_or_path: str, output_dir: str = None) -> ExtractionResult:
    """
    Extract audio from a video URL via yt-dlp, or pass through a local media file.
    """
    if _is_local_media(url_or_path):
        logger.info(f"Using local media file: {url_or_path}")
        return ExtractionResult(audio_path=url_or_path, is_temporary=False)

    if output_dir is None:
        output_dir = tempfile.mkdtemp(prefix="video_factcheck_")

    os.makedirs(output_dir, exist_ok=True)
    output_template = os.path.join(output_dir, "%(id)s.%(ext)s")

    try:
        import yt_dlp
    except ImportError as e:
        raise ExtractionError("yt-dlp is not installed. Run: pip install yt-dlp") from e

    ydl_opts = {
        "format": "bestaudio/best",
        "outtmpl": output_template,
        "quiet": True,
        "no_warnings": True,
        "socket_timeout": 60,
        "retries": 10,
        "fragment_retries": 10,
        "postprocessors": [{
            "key": "FFmpegExtractAudio",
            "preferredcodec": "mp3",
            "preferredquality": "128",
        }],
        "noplaylist": True,
        # ── Anti-403 / Bot-detection bypass ──────────────────────────────────
        # Use the web_creator client which bypasses PO Token requirements
        "extractor_args": {
            "youtube": {
                "player_client": ["web_creator", "web", "android"],
                "skip": ["hls", "dash"],
            }
        },
        # Spoof a real browser user-agent
        "http_headers": {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/131.0.0.0 Safari/537.36"
            ),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
            "Accept-Encoding": "gzip, deflate",
            "Sec-Fetch-Mode": "navigate",
        },
        # Sleep between requests to avoid rate limiting
        "sleep_interval": 1,
        "max_sleep_interval": 5,
        # Allow age-restricted content workaround
        "age_limit": None,
    }

    # Point yt-dlp to ffmpeg/ffprobe if they're not on the process PATH
    ffmpeg_dir = _find_ffmpeg_dir()
    if ffmpeg_dir:
        # yt-dlp uses ffmpeg_location for both ffmpeg and ffprobe
        ydl_opts["ffmpeg_location"] = ffmpeg_dir
        logger.info(f"Using ffmpeg from: {ffmpeg_dir}")

        # Also inject the directory into the subprocess PATH so that the
        # FFmpegPostProcessor can spawn ffprobe correctly on all yt-dlp versions
        current_path = os.environ.get("PATH", "")
        if ffmpeg_dir not in current_path:
            os.environ["PATH"] = ffmpeg_dir + os.pathsep + current_path
            logger.info(f"Prepended {ffmpeg_dir} to PATH for this process")
    else:
        logger.warning(
            "ffmpeg not found — yt-dlp postprocessing will likely fail. "
            "Install ffmpeg or set the FFMPEG_PATH environment variable."
        )

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url_or_path, download=True)
            audio_path = ydl.prepare_filename(info)
            # After FFmpegExtractAudio postprocessor, extension becomes mp3
            base, _ = os.path.splitext(audio_path)
            mp3_path = base + ".mp3"
            if os.path.exists(mp3_path):
                audio_path = mp3_path
            elif not os.path.exists(audio_path):
                raise ExtractionError("yt-dlp finished but no audio file was found.")

            duration = info.get("duration")
            title = info.get("title")
            logger.info(f"Extracted audio to {audio_path}")
            return ExtractionResult(
                audio_path=audio_path,
                title=title,
                duration_seconds=float(duration) if duration else None,
                is_temporary=True,
            )
    except ExtractionError:
        raise
    except Exception as e:
        import re as _re
        # Strip ANSI escape codes from yt-dlp error messages (prevents garbled UI output)
        raw = _re.sub(r'\x1b\[[0-9;]*m', '', str(e))
        err_msg = raw.lower()
        if "private" in err_msg or "unauthorized" in err_msg:
            msg = "This video is private. Please ensure the video is public."
        elif "sign in to confirm your age" in err_msg or "confirm your age" in err_msg or "age-gated" in err_msg:
            msg = "This video is age-restricted. Age-restricted videos cannot be downloaded."
        elif "geo-restricted" in err_msg or "not available in your country" in err_msg:
            msg = "This video is geo-blocked/geo-restricted and cannot be downloaded from this location."
        elif "deleted" in err_msg or "not exist" in err_msg or "removed" in err_msg or "404" in err_msg:
            msg = "This video does not exist or has been deleted/removed."
        elif "403" in err_msg or "forbidden" in err_msg or "unable to download video data" in err_msg:
            msg = (
                "YouTube blocked the download (HTTP 403 Forbidden). "
                "This usually happens with heavily restricted videos. "
                "Try a different video or a YouTube Shorts link."
            )
        elif "sign in" in err_msg or "login" in err_msg:
            msg = "This video requires sign-in to watch and cannot be accessed."
        else:
            msg = f"Failed to extract audio from URL: {raw}"
        raise ExtractionError(msg) from e

