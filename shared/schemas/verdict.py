from datetime import datetime, timezone
from enum import Enum
from typing import List, Optional, Dict, Any
from uuid import UUID, uuid4
from pydantic import BaseModel, Field


class VerdictLabel(str, Enum):
    """
    Possible outcomes of a fact-checking verification.
    Displays exactly three final verdicts: TRUE, FALSE, and MISLEADING.
    """
    TRUE = "true"
    FALSE = "false"
    MISLEADING = "misleading"

    @classmethod
    def _missing_(cls, value: object):
        val_str = str(value or "").lower().strip()
        mapping = {
            "supported": cls.TRUE,
            "verified": cls.TRUE,
            "contradicted": cls.FALSE,
            "refuted": cls.FALSE,
            "debunked": cls.FALSE,
            "partially_supported": cls.MISLEADING,
            "ambiguous": cls.MISLEADING,
            "unverifiable": cls.MISLEADING,
            "unverified": cls.MISLEADING,
            "partial": cls.MISLEADING,
        }
        if val_str in mapping:
            return mapping[val_str]
        return cls.MISLEADING


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
    stance: Optional[str] = Field(None, description="Stance: supports, partially_supports, contradicts, neutral, unrelated, or insufficient")
    is_independent: Optional[bool] = Field(True, description="Whether source is independent of syndicated wire reprints")
    explanation: Optional[str] = Field(None, description="Concise rationale for why passage supports/contradicts/is irrelevant")
    relevant_passage: Optional[str] = Field(None, description="Exact passage context from original document")
    quote: Optional[str] = Field(None, description="Exact verbatim quotation extracted from original source")
    quote_location: Optional[str] = Field(None, description="Location of quote in document (e.g. section or paragraph)")
    quote_verified: Optional[bool] = Field(None, description="Whether quote was verified against the full source page")
    publisher: Optional[str] = Field(None, description="Name of the publisher / publishing organization")
    retrieval_timestamp: Optional[str] = Field(None, description="ISO timestamp when source page was retrieved")
    credibility_limitation: Optional[str] = Field(None, description="Known limitations or source bias notes")


class AtomicClaimAssessment(BaseModel):
    """Assessment of an individual atomic sub-claim within a compound claim."""
    id: str = Field(default_factory=lambda: str(uuid4())[:8], description="Atomic claim identifier")
    atomic_claim: str = Field(..., description="Normalized atomic sub-claim proposition")
    verdict: VerdictLabel = Field(..., description="Verdict for this specific atomic claim: true, false, misleading")
    reasoning: str = Field(..., description="Plain-language explanation for this atomic claim")
    confidence: float = Field(default=0.8, description="Confidence in this atomic assessment")
    supporting_quote_ids: List[str] = Field(default_factory=list, description="URLs or IDs of supporting sources")
    contradicting_quote_ids: List[str] = Field(default_factory=list, description="URLs or IDs of contradicting sources")


class Verdict(BaseModel):
    """
    The final verification result for a given claim.
    """
    id: UUID = Field(default_factory=uuid4, description="Unique identifier for the verdict")
    claim_id: UUID = Field(..., description="Foreign key linking to the evaluated Claim")
    
    label: VerdictLabel = Field(..., description="The final truthfulness label: true, false, misleading")
    confidence: float = Field(..., description="Confidence score of the verdict (0.0 to 1.0), based on signal agreement")
    evidence: List[Evidence] = Field(default_factory=list, description="List of sources and evidence supporting the verdict")
    reasoning: str = Field(..., description="A short textual explanation for why this verdict was reached")
    summary: Optional[str] = Field(None, description="One-sentence verdict summary")
    
    atomic_assessments: Optional[List[AtomicClaimAssessment]] = Field(default_factory=list, description="Assessment of atomic sub-claims")
    canonical_hash: Optional[str] = Field(None, description="Deterministic canonical record hash")
    unresolved_uncertainties: Optional[List[str]] = Field(default_factory=list, description="Specific uncertainties or missing context")

    search_runs: Optional[List[Dict[str, Any]]] = Field(default_factory=list, description="Detailed trace of all search queries and outcomes")
    llm_checks: Optional[List[Dict[str, Any]]] = Field(default_factory=list, description="Auditable trace of multi-agent validation checks")
    fact_check_summary: Optional[Dict[str, Any]] = Field(None, description="Summary metrics: searches_run, consensus_score, etc.")
    queries_executed: Optional[List[str]] = Field(default_factory=list, description="All search queries executed across retrieval rounds")
    retrieval_rounds: Optional[int] = Field(1, description="Number of iterative search rounds executed")
    stopping_reason: Optional[str] = Field(None, description="Reason retrieval loop stopped: sufficient_evidence, max_rounds, etc.")

    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), description="Timestamp when the verdict was generated")
