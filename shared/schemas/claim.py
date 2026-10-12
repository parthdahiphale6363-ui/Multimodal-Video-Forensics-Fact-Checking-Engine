from datetime import datetime
from enum import Enum
from typing import Optional
from uuid import UUID, uuid4
from pydantic import BaseModel, Field


class SourcePlatform(str, Enum):
    """Supported platforms for video extraction."""
    YOUTUBE = "youtube"
    INSTAGRAM = "instagram"
    FACEBOOK = "facebook"


class Claim(BaseModel):
    """
    Represents an atomic, independently checkable factual claim extracted from a video transcript.
    """
    id: UUID = Field(default_factory=uuid4, description="Unique identifier for the claim")
    source_video_id: str = Field(..., description="The ID of the source video (e.g., YouTube video ID)")
    source_platform: SourcePlatform = Field(..., description="The platform where the video was published")
    
    raw_text: str = Field(..., description="The original raw text from the transcript")
    normalized_text: str = Field(..., description="The rewritten, atomic, and independently checkable claim")
    language: str = Field(..., description="ISO 639-1 language code of the claim (e.g., 'en', 'es')")
    timestamp_in_video: float = Field(..., description="The starting timestamp of the claim in the video, in seconds")
    
    embedding_id: Optional[str] = Field(None, description="Reference to the vector store embedding. Nullable until computed.")
    created_at: datetime = Field(default_factory=datetime.utcnow, description="Timestamp when the claim was extracted")

