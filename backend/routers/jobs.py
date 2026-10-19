from fastapi import APIRouter, HTTPException, Header
from pydantic import BaseModel
try:
    from backend.services.job_service import (
        jobs_db, claims_verdicts_db, transcripts_db,
        forensics_db, osint_db, dm_db, process_video,
        job_dispatcher, enqueue_job
    )
except ModuleNotFoundError:  # pragma: no cover - support running from backend/
    from services.job_service import (
        jobs_db, claims_verdicts_db, transcripts_db,
        forensics_db, osint_db, dm_db, process_video,
        job_dispatcher, enqueue_job
    )
from shared.schemas.job import Job, JobStatus
from fastapi.responses import StreamingResponse
import asyncio
import json
import urllib.parse
import time
import os
from collections import defaultdict
from shared.llm import get_redis_client

router = APIRouter()

rate_limit_db = defaultdict(list)


# ─── Health Check / Diagnostics ───────────────────────────────────────────────

@router.get("/health")
async def health_check():
    """
    Diagnostic endpoint: validates all configured API keys and returns their status.
    Returns status of Groq, NewsAPI.org, NewsData.io, Google Fact Check, DuckDuckGo,
    Wikipedia, and Redis.
    """
    import sys
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from shared.api_keys import get_api_key_manager
    manager = get_api_key_manager()
    report = manager.validate_all_keys()
    return report

def validate_video_url(url: str) -> bool:
    # Allow local paths for testing
    if not url.startswith("http://") and not url.startswith("https://"):
        return True
    try:
        parsed = urllib.parse.urlparse(url)
        domain = parsed.netloc.lower().split(":")[0]
        allowed = {"youtube.com", "youtu.be", "vimeo.com", "example.com"}
        return any(domain == dom or domain.endswith("." + dom) for dom in allowed)
    except Exception:
        return False

def check_rate_limit(api_key: str) -> bool:
    now = time.time()
    one_hour_ago = now - 3600

    redis_client = get_redis_client()
    if redis_client:
        try:
            key = f"rate_limit:{api_key}"
            redis_client.zremrangebyscore(key, 0, one_hour_ago)
            count = redis_client.zcard(key)
            if count >= 5:
                return False
            redis_client.zadd(key, {str(now): now})
            redis_client.expire(key, 3600)
            return True
        except Exception as e:
            print(f"[RateLimit] Redis error: {e}. Falling back to in-memory.")

    timestamps = rate_limit_db[api_key]
    timestamps = [t for t in timestamps if t > one_hour_ago]
    rate_limit_db[api_key] = timestamps
    if len(timestamps) >= 5:
        return False
    rate_limit_db[api_key].append(now)
    return True

class JobCreate(BaseModel):
    video_url: str

@router.post("")
async def create_job(req: JobCreate, x_api_key: str = Header(None)):
    # 1. Domain allowlist validation
    if not validate_video_url(req.video_url):
        raise HTTPException(
            status_code=400,
            detail="Unsupported video platform. Only YouTube and Vimeo URLs are allowed."
        )

    # 2. API Key and Rate Limit validation
    allowed_keys_str = os.getenv("API_KEYS", "")
    if allowed_keys_str:
        allowed_keys = [k.strip() for k in allowed_keys_str.split(",") if k.strip()]
        if not x_api_key or x_api_key not in allowed_keys:
            raise HTTPException(status_code=401, detail="Invalid or missing API key")
        
        if not check_rate_limit(x_api_key):
            raise HTTPException(status_code=429, detail="Rate limit exceeded. Max 5 jobs per hour.")

    job = Job(video_url=req.video_url)
    jobs_db[str(job.id)] = job
    enqueue_job(str(job.id))
    return job

@router.get("/demo-cases")
async def get_demo_cases():
    """Returns curated multimodal demonstration cases for instant zero-latency evaluation."""
    from backend.services.demo_cases import DEMO_CASES
    return DEMO_CASES


@router.get("/{job_id}/export")
async def export_job_dossier(job_id: str, format: str = "json"):
    """
    Exports a comprehensive forensic dossier in structured JSON or Markdown report format.
    """
    from backend.services.demo_cases import DEMO_CASES
    from backend.services.export_service import generate_markdown_dossier
    from fastapi.responses import PlainTextResponse

    demo = None
    for key, case in DEMO_CASES.items():
        if case.get("id") == job_id or key == job_id:
            demo = case
            break

    if demo:
        job_data = {
            "id": demo["id"],
            "video_url": demo["video_url"],
            "overall_verdict": demo["overall_verdict"],
            "final_verdict_category": demo["final_verdict_category"],
            "overall_confidence": demo["overall_confidence"],
            "verdict_breakdown": demo["verdict_breakdown"],
            "claims": demo["claims"],
            "forensics": demo.get("forensics"),
            "osint": demo.get("osint"),
            "dm_report": demo.get("dm_report"),
        }
    elif job_id in jobs_db:
        job_obj = jobs_db[job_id]
        claims = claims_verdicts_db.get(job_id, [])
        forensics = forensics_db.get(job_id)
        osint = osint_db.get(job_id)
        dm_report = dm_db.get(job_id)
        job_data = {
            "id": str(job_obj.id),
            "video_url": job_obj.video_url,
            "overall_verdict": job_obj.overall_verdict or "Pending Verification",
            "final_verdict_category": job_obj.final_verdict_category or "Unverified",
            "overall_confidence": job_obj.overall_confidence or 0.0,
            "verdict_breakdown": job_obj.verdict_breakdown or {},
            "claims": claims,
            "forensics": forensics,
            "osint": osint,
            "dm_report": dm_report,
        }
    else:
        raise HTTPException(status_code=404, detail="Job not found")

    if format.lower() in ("markdown", "md"):
        md_text = generate_markdown_dossier(
            job_id=job_data["id"],
            video_url=job_data["video_url"],
            overall_verdict=job_data["overall_verdict"],
            category=job_data["final_verdict_category"],
            confidence=job_data["overall_confidence"],
            breakdown=job_data["verdict_breakdown"],
            claims=job_data["claims"],
            forensics=job_data["forensics"],
            osint=job_data["osint"],
            dm_report=job_data["dm_report"]
        )
        return PlainTextResponse(content=md_text, media_type="text/markdown")

    import hashlib
    import datetime
    content_to_hash = f"{job_data['id']}:{job_data['video_url']}:{job_data['overall_verdict']}:{job_data['overall_confidence']}:{len(job_data['claims'])}"
    audit_hash = hashlib.sha256(content_to_hash.encode("utf-8")).hexdigest()[:16].upper()
    job_data["dossier_metadata"] = {
        "export_version": "1.0.0",
        "generated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "audit_hash": f"SHA256-{audit_hash}",
        "schema": "truthlens.dossier.v1"
    }

    return job_data


@router.get("/{job_id}")
async def get_job(job_id: str):
    from backend.services.demo_cases import DEMO_CASES
    for key, case in DEMO_CASES.items():
        if case.get("id") == job_id or key == job_id:
            return case
    if job_id not in jobs_db:
        raise HTTPException(status_code=404, detail="Job not found")
    return jobs_db[job_id]

@router.get("/{job_id}/claims")
async def get_claims(job_id: str):
    from backend.services.demo_cases import DEMO_CASES
    for key, case in DEMO_CASES.items():
        if case.get("id") == job_id or key == job_id:
            return case.get("claims", [])
    if job_id in claims_verdicts_db:
        return claims_verdicts_db[job_id]
    if job_id in jobs_db:
        return []
    raise HTTPException(status_code=404, detail="Job not found")

@router.get("/{job_id}/transcript")
async def get_transcript(job_id: str):
    from backend.services.demo_cases import DEMO_CASES
    for key, case in DEMO_CASES.items():
        if case.get("id") == job_id or key == job_id:
            return case.get("transcript", [])
    if job_id in transcripts_db:
        return transcripts_db[job_id]
    if job_id in jobs_db:
        return []
    raise HTTPException(status_code=404, detail="Job not found")

@router.get("/{job_id}/forensics")
async def get_forensics(job_id: str):
    """Return the full forensics analysis report for a job."""
    from backend.services.demo_cases import DEMO_CASES
    for key, case in DEMO_CASES.items():
        if case.get("id") == job_id or key == job_id:
            return case.get("forensics", {})
    if job_id in forensics_db:
        return forensics_db[job_id]
    if job_id in jobs_db:
        return {}
    raise HTTPException(status_code=404, detail="Job not found")

@router.get("/{job_id}/osint")
async def get_osint(job_id: str):
    """Return the OSINT collection report for a job."""
    from backend.services.demo_cases import DEMO_CASES
    for key, case in DEMO_CASES.items():
        if case.get("id") == job_id or key == job_id:
            return case.get("osint", {})
    if job_id in osint_db:
        return osint_db[job_id]
    if job_id in jobs_db:
        return {}
    raise HTTPException(status_code=404, detail="Job not found")

@router.get("/{job_id}/dm_report")
async def get_dm_report(job_id: str):
    """Return the Data Mining analysis report for a job."""
    from backend.services.demo_cases import DEMO_CASES
    for key, case in DEMO_CASES.items():
        if case.get("id") == job_id or key == job_id:
            return case.get("dm_report", {})
    if job_id in dm_db:
        return dm_db[job_id]
    if job_id in jobs_db:
        return {}
    raise HTTPException(status_code=404, detail="Job not found")


@router.get("/{job_id}/stream")
async def stream_job_events(job_id: str):
    if job_id not in jobs_db:
        raise HTTPException(status_code=404, detail="Job not found")

    async def event_generator():
        queue = asyncio.Queue()
        job_dispatcher.register(job_id, queue)
        
        # If job is already done, emit all completed claims and done
        if job_id in claims_verdicts_db:
            for claim in claims_verdicts_db[job_id]:
                yield f"event: claim\ndata: {json.dumps(claim)}\n\n"
            yield f"event: done\ndata: done\n\n"
            job_dispatcher.unregister(job_id, queue)
            return

        # If job failed already, emit error
        job_obj = jobs_db[job_id]
        if job_obj.status == JobStatus.FAILED:
            err_msg = job_obj.error_message or "Job failed"
            yield f"event: error\ndata: {err_msg}\n\n"
            job_dispatcher.unregister(job_id, queue)
            return

        # Setup subscription to Redis pub/sub if available
        redis_task = None
        if job_dispatcher.redis_client:
            async def listen_redis():
                pubsub = job_dispatcher.redis_client.pubsub()
                await pubsub.subscribe(f"job_stream:{job_id}")
                try:
                    async for message in pubsub.listen():
                        if message["type"] == "message":
                            payload = json.loads(message["data"])
                            await queue.put((payload["event"], payload["data"]))
                except asyncio.CancelledError:
                    pass
                finally:
                    await pubsub.unsubscribe(f"job_stream:{job_id}")
            redis_task = asyncio.create_task(listen_redis())

        try:
            while True:
                event_type, data = await queue.get()
                if event_type == "claim":
                    yield f"event: claim\ndata: {json.dumps(data)}\n\n"
                elif event_type == "done":
                    yield f"event: done\ndata: done\n\n"
                    break
                elif event_type == "error":
                    yield f"event: error\ndata: {data.get('error', 'Job failed')}\n\n"
                    break
        except asyncio.CancelledError:
            pass
        finally:
            if redis_task:
                redis_task.cancel()
            job_dispatcher.unregister(job_id, queue)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        }
    )
