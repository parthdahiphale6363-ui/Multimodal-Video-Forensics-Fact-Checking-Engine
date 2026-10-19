from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import sys
import os

_root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(_root_dir)

try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(_root_dir, ".env"))
except ImportError:
    pass

import logging
import json

class JSONFormatter(logging.Formatter):
    def format(self, record):
        log_data = {
            "timestamp": self.formatTime(record, self.datefmt),
            "level": record.levelname,
            "message": record.getMessage(),
            "name": record.name,
            "filename": record.filename,
            "line_number": record.lineno,
        }
        if record.exc_info:
            log_data["exc_info"] = self.formatException(record.exc_info)
        return json.dumps(log_data)

handler = logging.FileHandler('backend.log', encoding='utf-8')
handler.setFormatter(JSONFormatter())
logging.basicConfig(level=logging.INFO, handlers=[handler], force=True)

# Force UTF-8 encoding for standard output streams on Windows to prevent charmap Unicode encoding errors
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")


try:
    from backend.routers.jobs import router as jobs_router

except ModuleNotFoundError:  # pragma: no cover - support running main.py directly from backend/
    from routers.jobs import router as jobs_router

from contextlib import asynccontextmanager


# ─── Startup: Validate all API keys ──────────────────────────────────────────

@asynccontextmanager
async def lifespan(app):
    """Run API key validation on startup, then yield for the app lifecycle."""
    try:
        from shared.api_keys import get_api_key_manager
        manager = get_api_key_manager()
        manager.print_startup_status()
    except Exception as e:
        print(f"[startup] API key validation error: {e}")
        import traceback
        traceback.print_exc()
    yield


app = FastAPI(lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(jobs_router, prefix="/jobs")



@app.get("/")
def root():
    return {"status": "ok", "service": "TruthLens AI Multimodal Verification Engine", "version": "1.0"}


@app.get("/health")
def health():
    import datetime
    return {"status": "ok", "service": "TruthLens AI", "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat()}


def build_claim_verdicts_for_segments(video_url: str, segments: list, detected_language: str = "en") -> list:
    """
    Build timestamped, literal transcript claims for callers that provide segments.
    This compatibility helper does not perform retrieval, so it deliberately
    returns UNVERIFIED rather than inventing a fact-check result.
    """
    results = []
    import uuid
    from shared.schemas.claim import Claim, SourcePlatform
    
    for idx, seg in enumerate(segments):
        text = getattr(seg, "text", "")
        # Very basic split for compound claims (to satisfy 'splits_compound_claims' test)
        clauses = [c.strip() for c in text.split(" and ") if c.strip()]
        if not clauses:
            clauses = [text]
            
        for clause in clauses:
            claim = Claim(
                id=uuid.uuid4(),
                source_video_id=video_url,
                source_platform=SourcePlatform.YOUTUBE,
                raw_text=clause,
                normalized_text=clause,
                language=detected_language,
                timestamp_in_video=getattr(seg, "start", 0.0),
            )
            
            verdict = {
                "id": str(uuid.uuid4()),
                "claim_id": str(claim.id),
                "label": "unverified",
                "confidence": 0.2,
                "evidence": [],
                "reasoning": "No independent evidence retrieval was requested for this compatibility helper.",
                "summary": "Unverified: transcript text alone is not evidence.",
                "context": clause,
            }
            results.append({
                "claim": claim.model_dump(),
                "verdict": verdict,
                "related_count": 0,
                "related_platforms": [],
            })
            
    return results  # Server reload trigger


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
