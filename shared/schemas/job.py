from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import UUID, uuid4
from pydantic import BaseModel, Field


class JobStatus(str, Enum):
    """The current status of a video processing job in the pipeline."""
    PENDING = "pending"
    EXTRACTING = "extracting"
    TRANSCRIBING = "transcribing"
    EXTRACTING_CLAIMS = "extracting_claims"
    FORENSICS_ANALYSIS = "forensics_analysis"
    OSINT_COLLECTION = "osint_collection"
    DATA_MINING = "data_mining"
    VERIFYING = "verifying"
    DONE = "done"
    FAILED = "failed"
    NO_CLAIMS_FOUND = "no_claims_found"
    EXTRACTION_FAILED = "extraction_failed"


class Job(BaseModel):
    """
    Tracks the progress of a video through the entire forensics + fact-checking pipeline.
    """
    id: UUID = Field(default_factory=uuid4, description="Unique identifier for the job")
    video_url: str = Field(..., description="The original URL of the video being processed")

    status: JobStatus = Field(default=JobStatus.PENDING, description="The current stage of the pipeline")
    progress_percent: float = Field(default=0.0, description="Overall pipeline completion percentage (0.0 to 100.0)")
    error_message: Optional[str] = Field(None, description="Detailed error message if the job failed. Nullable.")

    claim_ids: List[UUID] = Field(default_factory=list, description="List of Claim UUIDs extracted during this job")

    # Overall verdict fields populated after fact-checking
    overall_verdict: Optional[str] = Field(None, description="Aggregated verdict across all extracted claims")
    verdict_breakdown: Optional[Dict[str, Any]] = Field(None, description="Breakdown of verdict counts")

    # Final forensics category: Genuine | Deepfake | Edited | Misleading | Fake | Unverified
    final_verdict_category: Optional[str] = Field(None, description="Final forensics verdict category")

    # Multi-modal scores
    video_score: Optional[float] = Field(None, description="Video integrity score 0-100")
    audio_score: Optional[float] = Field(None, description="Audio integrity score 0-100")
    metadata_score: Optional[float] = Field(None, description="Metadata integrity score 0-100")
    osint_score: Optional[float] = Field(None, description="OSINT confidence score 0-100")
    dm_score: Optional[float] = Field(None, description="Data mining confidence score 0-100")
    overall_confidence: Optional[float] = Field(None, description="Fused confidence score 0-100")

    # Reports from new modules
    forensics_report: Optional[Dict[str, Any]] = Field(None, description="Forensics analysis report")
    osint_report: Optional[Dict[str, Any]] = Field(None, description="OSINT collection report")
    dm_report: Optional[Dict[str, Any]] = Field(None, description="Data mining analysis report")

    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
