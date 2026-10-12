# Video Fact-Checker: Backend Documentation

This document describes the design, architecture, API contract, and performance optimizations implemented in the Video Fact-Checker backend.

---

## 🚀 1. Tech Stack & Technologies Used

- **Framework**: [FastAPI](https://fastapi.tiangolo.com/) (Asynchronous python web framework)
- **Validation & Schemas**: [Pydantic v2](https://docs.pydantic.dev/)
- **Media Processing**:
  - [yt-dlp](https://github.com/yt-dlp/yt-dlp) for video/audio extraction.
  - [FFmpeg](https://ffmpeg.org/) for audio conversion, loudness normalization, and audio chunking.
- **LLM & Transcription Services**:
  - [Groq API Python SDK](https://github.com/groq/groq-python) using:
    - `whisper-large-v3` (for translation)
    - `whisper-large-v3-turbo` (for transcription)
    - `llama-3.3-70b-versatile` (primary model for claim extraction & fact-check reasoning)
    - `llama-3.1-8b-instant` (fallback model automatically used if primary fails)
- **External Search APIs**:
  - [NewsAPI](https://newsapi.org/) (for news verification)
  - [NewsData.io](https://newsdata.io/) (secondary news indexing)
  - [MediaWiki API](https://www.mediawiki.org/wiki/API:Main_page) (for live Wikipedia intro extracts)
  - [Google Fact Check Tools API](https://developers.google.com/fact-check/tools/api)
  - [DuckDuckGo Search (via duckduckgo_search)](https://github.com/deedy5/duckduckgo_search) (as a general web fallback)
- **Caching & Queuing**:
  - **Redis** for distributed caching (verdicts) and job queue processing.
  - **In-Memory fallback** seamlessly handles both if Redis is unconfigured or down.

---

## 🛠️ 2. API Documentation (Endpoints)

All routes are prefix-mounted under `/jobs` in [routers/jobs.py](file:///c:/Users/Asus/Desktop/Parth%202D/backend/routers/jobs.py).

### Create Job
- **POST** `/jobs`
- **Headers**:
  - `X-API-Key`: `your-api-key` (required if `API_KEYS` is configured in environment)
- **Request Body**:
  ```json
  {
    "video_url": "https://www.youtube.com/watch?v=example"
  }
  ```
- **Response**: Returns a JSON representation of the `Job` database object including its unique `id` and current status.
- **Domain Restriction**: Only allows supported video platforms (YouTube, Vimeo). Others return `400 Bad Request`.

### Health Check / API Diagnostics
- **GET** `/jobs/health`
- **Response**: JSON report of all configured API key statuses.
- **Example Response**:
  ```json
  {
    "status": "degraded",
    "apis": {
      "groq": {"status": "ok", "keys_configured": 2, "keys_active": 2, "model": "openai/gpt-oss-120b"},
      "newsapi_org": {"status": "ok", "key_configured": true},
      "newsdata_io": {"status": "missing", "key_configured": false},
      "google_factcheck": {"status": "ok", "key_configured": true},
      "duckduckgo": {"status": "ok", "no_key_required": true},
      "wikipedia": {"status": "ok", "no_key_required": true},
      "redis": {"status": "unavailable", "using_fallback": true}
    },
    "warnings": ["NEWSDATA_API_KEY not configured — NewsData.io search disabled"]
  }
  ```

### Real-time Event Stream (SSE)
- **GET** `/jobs/{job_id}/stream`
- **Response**: Server-Sent Events (`text/event-stream`).
- **Events emitted**:
  - `event: claim` (data: JSON of verified claim verdict as it finishes)
  - `event: done` (data: done)
  - `event: error` (data: error message if job fails)

### Get Job Details
- **GET** `/jobs/{job_id}`
- **Response**: The complete `Job` schema (status, progress percentage, overall verdicts, multi-modal confidence scores).

### Get Claims & Verdicts
- **GET** `/jobs/{job_id}/claims`
- **Response**: An array of extracted claims along with their normalizations, supports list, and evidence citations.

### Get Transcript
- **GET** `/jobs/{job_id}/transcript`
- **Response**: An array of subtitle segments (`text`, `start`, `end`).

---

## 🛡️ 3. Resilience, Security & Performance

### Resilience
- **Exponential Backoff & Retries**: All external search APIs (NewsAPI, NewsData.io, Wikipedia, Google Fact Check, DuckDuckGo) are wrapped with 3 retries and exponential backoff.
- **Circuit Breakers**: Per-source circuit breakers prevent overload/lag if a service is down. Failed sources trigger a temporary bypass cooldown.
- **Graceful Degradation**: If a source fails, verification still proceeds with other sources. The confidence score is lowered proportionally and the unavailable source is recorded in the evidence list.
- **Multi-Key Groq Rotation**: Supports comma-separated `GROQ_API_KEY` values. On rate limit (429), automatically rotates to the next available key. On auth failure (401/403), marks key as permanently invalid and rotates.

### Security
- **API Key & Rate Limiting**: Limit job submissions to 5 per hour per API Key. API keys are specified via comma-separated list in `API_KEYS` environment variable.
- **SSRF Prevention**: Strict domain verification only allow YouTube/Vimeo URLs.

### Caching
- **Verdict Cache**: Factual verdicts are cached in Redis (with in-memory fallback) for 24 hours. Identical claims are returned instantly without invoking LLMs/Search APIs.
- **Semantic Deduplication**: Claims extracted from the same video are semantically matched and deduplicated via LLM prior to verification to save API requests.

---

## ⚙️ 4. Local Execution & Configuration

### Docker Setup (Easiest)
Spin up the backend and a local Redis container in one command:
```bash
docker-compose up --build
```

### Manual Environment Setup
Create a `.env` file at the root containing:
```ini
# Groq LLM (REQUIRED) — comma-separate multiple keys for rotation
GROQ_API_KEY=gsk_key1,gsk_key2

# News APIs (at least one recommended)
NEWS_API_KEY=your-newsapi-org-key
NEWSDATA_API_KEY=pub_your-newsdata-io-key

# Google Fact Check Tools (recommended)
GOOGLE_FACTCHECK_API_KEY=your-google-api-key

# FFmpeg path (required for audio processing)
FFMPEG_PATH=C:\path\to\ffmpeg\bin

# Redis (optional — uses in-memory fallback if not set)
REDIS_URL=redis://localhost:6379

# API Keys for job submission auth (optional)
API_KEYS=key1,key2,key3
```

### API Key Sources
| API | Where to get | Cost |
|-----|-------------|------|
| Groq | https://console.groq.com | Free tier available |
| NewsAPI.org | https://newsapi.org/register | Free (100 req/day) |
| NewsData.io | https://newsdata.io/register | Free (200 credits/day) |
| Google Fact Check | https://console.cloud.google.com | Free |
| DuckDuckGo | No key required | Free |
| Wikipedia | No key required | Free |

### Run Python Server
```bash
cd backend
python -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

### Check API Key Status
```bash
curl http://localhost:8000/jobs/health
```

### Run Pipeline Tests
```bash
$env:PYTHONPATH="c:\Users\Asus\Desktop\Parth 2D;c:\Users\Asus\Desktop\Parth 2D\backend"
python -m pytest tests/
```
