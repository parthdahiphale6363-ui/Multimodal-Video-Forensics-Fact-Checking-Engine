"""
pipeline/canonical_record.py — Deterministic Canonical Verification Record & Reproducibility Cache
=================================================================================================
Maintains versioned canonical records for claims, ensuring reproducible verdicts across identical
inputs and evidence snapshots, and generating auditable drift explanations when evidence changes.
"""

import hashlib
import json
import time
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any
from pydantic import BaseModel, Field

# In-memory store for canonical records: {canonical_hash: CanonicalVerificationRecord}
_CANONICAL_RECORDS_STORE: Dict[str, Dict[str, Any]] = {}
ENGINE_VERSION = "TruthLens-v2.5.0-epistemic"


class CanonicalEvidenceItem(BaseModel):
    source_url: str
    source_title: str
    publisher: str
    domain: str
    domain_trust: str
    publication_date: str
    retrieval_timestamp: str
    quote: str
    quote_location: Optional[str] = None
    quote_verified: bool = False
    relevance_score: float = 0.5
    stance: str = "neutral"
    is_independent: bool = True
    credibility_limitation: Optional[str] = None


class CanonicalAtomicAssessment(BaseModel):
    atomic_claim: str
    verdict: str  # true, false, misleading
    reasoning: str
    supporting_sources: List[str] = Field(default_factory=list)
    contradicting_sources: List[str] = Field(default_factory=list)


class CanonicalVerificationRecord(BaseModel):
    canonical_hash: str
    original_wording: str
    normalized_claim: str
    context: Optional[str] = None
    final_verdict: str  # true, false, misleading
    confidence: float
    consensus_score: float
    reasoning: str
    summary: str
    atomic_assessments: List[CanonicalAtomicAssessment] = Field(default_factory=list)
    evidence: List[CanonicalEvidenceItem] = Field(default_factory=list)
    search_queries: List[str] = Field(default_factory=list)
    retrieval_rounds: int = 1
    engine_version: str = ENGINE_VERSION
    verification_timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    reproducibility_token: str = ""

    def compute_token(self) -> str:
        payload = f"{self.canonical_hash}|{self.final_verdict}|{round(self.confidence, 3)}|{len(self.evidence)}"
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


def compute_canonical_hash(normalized_claim: str, context: Optional[str] = None) -> str:
    """Generate a deterministic SHA-256 identifier for a claim and its factual context."""
    norm_c = re_norm = " ".join(normalized_claim.lower().strip().split())
    norm_ctx = " ".join((context or "").lower().strip().split())
    raw = f"{norm_c}||{norm_ctx}||{ENGINE_VERSION}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def get_canonical_record(canonical_hash: str) -> Optional[Dict[str, Any]]:
    """Retrieve a stored canonical verification record by its hash."""
    return _CANONICAL_RECORDS_STORE.get(canonical_hash)


def save_canonical_record(record_dict: Dict[str, Any]) -> str:
    """Save canonical record into deterministic repository store."""
    c_hash = record_dict.get("canonical_hash")
    if not c_hash:
        c_hash = compute_canonical_hash(record_dict.get("normalized_claim", ""), record_dict.get("context"))
        record_dict["canonical_hash"] = c_hash
    _CANONICAL_RECORDS_STORE[c_hash] = record_dict
    return c_hash


def explain_verdict_drift(
    old_record: Dict[str, Any],
    new_verdict: str,
    new_evidence: List[Dict[str, Any]],
) -> Optional[str]:
    """
    When a claim is re-evaluated and changes, explicitly generate an explanation of what changed.
    """
    old_v = str(old_record.get("final_verdict", "")).lower()
    new_v = str(new_verdict).lower()
    if old_v == new_v:
        return None

    old_urls = {e.get("source_url") for e in old_record.get("evidence", [])}
    new_urls = {e.get("source_url") for e in new_evidence}
    added_urls = new_urls - old_urls

    if added_urls:
        sample_source = list(added_urls)[0]
        return (
            f"Verdict updated from {old_v.upper()} to {new_v.upper()} because {len(added_urls)} new sources "
            f"were retrieved (including {sample_source}), which provided revised evidence."
        )
    return (
        f"Verdict updated from {old_v.upper()} to {new_v.upper()} due to updated consensus calculations "
        f"across corroborating and contradicting evidence."
    )
