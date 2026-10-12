from datetime import datetime, timezone
from enum import Enum
from typing import List, Optional, Dict, Any
from uuid import UUID, uuid4
from pydantic import BaseModel, Field


class VerdictLabel(str, Enum):
    """Possible outcomes of a fact-checking verification."""
    TRUE = "true"
    FALSE = "false"
    MISLEADING = "misleading"
    UNVERIFIABLE = "unverifiable"
    UNVERIFIED = "unverifiable"  # Standard alias for UNVERIFIABLE


class Evidence(BaseModel):
    """Supporting evidence found during the verification process."""
    source_url: str = Field(..., description="The URL of the source providing the evidence")
    source_title: str = Field(..., description="The title of the source page or article")
    snippet: str = Field(..., description="Relevant text snippet from the source")
    relevance_score: float = Field(..., description="A score indicating how relevant this evidence is to the claim (e.g., 0.0 to 1.0)")
    domain: Optional[str] = Field(None, description="Domain name")
    domain_trust: Optional[str] = Field(None, description="Domain trust label: high, medium, low")
    domain_trust_tier: Optional[int] = Field(None, description="Domain trust tier (1, 2, 3)")
    supports_claim: Optional[bool] = Field(None, description="Whether this evidence supports the claim")
    publication_date: Optional[str] = Field(None, description="Publication date string")
    stance: Optional[str] = Field(None, description="Stance category: supports, contradicts, mixed, irrelevant, insufficient")
    is_independent: Optional[bool] = Field(True, description="Whether source is independent of syndicated wire reprints")
    explanation: Optional[str] = Field(None, description="Concise rationale for why passage supports/contradicts/is irrelevant")


class Verdict(BaseModel):
    """
    The final verification result for a given claim.
    """
    id: UUID = Field(default_factory=uuid4, description="Unique identifier for the verdict")
    claim_id: UUID = Field(..., description="Foreign key linking to the evaluated Claim")
    
    label: VerdictLabel = Field(..., description="The final truthfulness label")
    confidence: float = Field(..., description="Confidence score of the verdict (0.0 to 1.0), based on signal agreement")
    evidence: List[Evidence] = Field(default_factory=list, description="List of sources and evidence supporting the verdict")
    reasoning: str = Field(..., description="A short textual explanation for why this verdict was reached")
    summary: Optional[str] = Field(None, description="One-sentence verdict summary")
    
    search_runs: Optional[List[Dict[str, Any]]] = Field(default_factory=list, description="Detailed trace of all search queries and outcomes")
    llm_checks: Optional[List[Dict[str, Any]]] = Field(default_factory=list, description="Auditable trace of multi-agent validation checks")
    fact_check_summary: Optional[Dict[str, Any]] = Field(None, description="Summary metrics: searches_run, consensus_score, etc.")
    queries_executed: Optional[List[str]] = Field(default_factory=list, description="All search queries executed across retrieval rounds")
    retrieval_rounds: Optional[int] = Field(1, description="Number of iterative search rounds executed")
    stopping_reason: Optional[str] = Field(None, description="Reason retrieval loop stopped: sufficient_evidence, max_rounds, etc.")

    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), description="Timestamp when the verdict was generated")

