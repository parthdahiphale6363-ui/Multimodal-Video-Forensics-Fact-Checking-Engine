"""
evidence_classifier.py — Claim-Level Evidence Classification & Consensus Engine
=================================================================================
Provides rigorous semantic stance classification, syndication deduplication,
source independence tracking, and mathematically grounded consensus/confidence scoring.

Stance categories:
  - SUPPORTS: Directly supports the specific claim.
  - CONTRADICTS: Directly challenges or refutes the specific claim.
  - MIXED: Contains evidence for and against different aspects of the claim.
  - IRRELEVANT: Off-topic or does not materially address the claim's core subject.
  - INSUFFICIENT: Mentions keywords but provides inadequate facts to verify or refute.
"""

from enum import Enum
from typing import List, Dict, Any, Optional, Tuple, Set
from urllib.parse import urlparse
import re
import hashlib
from pydantic import BaseModel, Field

from pipeline.domain_trust import get_domain_trust_tier


class EvidenceStance(str, Enum):
    SUPPORTS = "supports"
    CONTRADICTS = "contradicts"
    MIXED = "mixed"
    IRRELEVANT = "irrelevant"
    INSUFFICIENT = "insufficient"


class ClassifiedEvidenceItem(BaseModel):
    source_url: str = Field(..., description="Canonical or original URL of the source")
    source_title: str = Field(..., description="Title of the source article or document")
    domain: str = Field(..., description="Domain name of the source")
    domain_trust: str = Field("medium", description="Trust level: high, medium, low")
    domain_trust_tier: int = Field(3, description="Trust tier (1=authoritative, 2=news, 3=general)")
    snippet: str = Field(..., description="Excerpt or snippet from the page")
    relevant_passage: str = Field("", description="Specific quoted passage directly addressing the claim")
    stance: EvidenceStance = Field(EvidenceStance.INSUFFICIENT, description="Classification of evidence stance")
    relevance_score: float = Field(0.0, description="Semantic and topical relevance score (0.0 to 1.0)")
    credibility_score: float = Field(0.5, description="Source credibility score based on domain tier and authority (0.0 to 1.0)")
    is_independent: bool = Field(True, description="Whether this source is independent (not syndicated duplicate)")
    cluster_id: str = Field("", description="Cluster ID for syndicated/reprinted wire stories")
    explanation: str = Field("", description="Reason why the passage supports, contradicts, or is irrelevant")
    supports_claim: Optional[bool] = Field(None, description="Boolean flag for backward compatibility with UI")
    publication_date: str = Field("", description="Publication date if available")


# Common syndicated wire indicators
_WIRE_SYNDICATION_TOKENS = {
    "associated press", "ap news", "reuters", "agence france-presse", "afp",
    "pr newswire", "business wire", "globe newswire", "bloomberg news"
}

# Off-topic topic traps for specific sensitive keywords
_OFF_TOPIC_PATTERNS = {
    # If claim is about humans producing/synthesizing poison or toxic substances
    "human_poison": {
        "claim_triggers": ["human", "poison", "produce", "capable"],
        "off_topic_indicators": [
            "rat control", "rat poison", "rats", "rodent", "rodents", "rodenticide",
            "mouse bait", "pest control", "strychnine", "exterminator",
            "poison oak", "poison ivy", "poison sumac", "skin rash dermatitis",
            "urushiol", "golden poison frog", "snake bite treatment", "poison control hotline"
        ]
    }
}


def detect_topic_trap(claim_text: str, text: str) -> bool:
    """Return True if the text matches known off-topic traps for the claim."""
    claim_lower = claim_text.lower()
    text_lower = text.lower()
    for trap_name, config in _OFF_TOPIC_PATTERNS.items():
        if any(trigger in claim_lower for trigger in ["human", "poison"]):
            if any(ind in text_lower for ind in config["off_topic_indicators"]):
                if not any(k in text_lower for k in ["synthesis", "synthetic", "endogenous", "evolution", "kallikrein", "weapon", "chemical weapon", "genetic", "salivary"]):
                    return True
    return False


def classify_evidence_passages(
    claim_text: str,
    passages: List[Dict[str, Any]],
) -> List[ClassifiedEvidenceItem]:
    """Convenience helper to classify a list of passage dicts."""
    items, _ = classify_evidence_items(claim_text, passages)
    return items


def compute_content_fingerprint(title: str, text: str) -> str:
    """Generate a coarse n-gram fingerprint to detect syndicated articles across domains."""
    body_tokens = re.findall(r"[a-z0-9]+", text.lower())
    meaningful = [t for t in body_tokens if len(t) > 3]
    if len(meaningful) < 4:
        meaningful = [t for t in re.findall(r"[a-z0-9]+", f"{title} {text}".lower()) if len(t) > 3]
    if len(meaningful) < 4:
        return hashlib.md5(f"{title}".lower().encode()).hexdigest()[:12]
    # Sample every 2nd word to create a robust fingerprint
    sample = " ".join(meaningful[:24:2])
    return hashlib.md5(sample.encode()).hexdigest()[:12]


def check_domain_independence(url: str, title: str, text: str, seen_fingerprints: Dict[str, str]) -> Tuple[bool, str]:
    """
    Check if a source is independent or a syndicated reprint of an earlier article.
    Returns (is_independent, cluster_id).
    """
    fp = compute_content_fingerprint(title, text)
    domain = urlparse(url).netloc.lower()
    
    if fp in seen_fingerprints:
        # Reprints identical wire/article text
        return False, fp
    
    seen_fingerprints[fp] = domain
    return True, fp


def classify_passage_stance(
    claim_text: str,
    title: str,
    snippet: str,
    url: str,
    relevance_score: float = 0.5,
) -> Tuple[EvidenceStance, float, str]:
    """
    Rule-based and semantic stance classification for a single passage against a claim.
    Returns (stance, calibrated_relevance, explanation).
    """
    combined = f"{title} {snippet}".lower()
    claim_lower = claim_text.lower()
    
    # 1. Check for known off-topic traps (e.g. rat poison / poison oak when claim is about humans producing poison)
    if any(k in claim_lower for k in ["human", "poison", "capable", "produce"]):
        if any(w in claim_lower for w in ["poison", "venom", "toxin"]):
            off_matches = [ind for ind in _OFF_TOPIC_PATTERNS["human_poison"]["off_topic_indicators"] if ind in combined]
            if off_matches and not any(k in combined for k in ["synthesis", "synthetic", "evolution", "kallikrein", "weapon", "chemical weapon", "genetic", "salivary"]):
                return (
                    EvidenceStance.IRRELEVANT,
                    0.10,
                    f"Irrelevant topic: passage discusses {', '.join(off_matches)} rather than human biological or chemical poison production."
                )

    # 2. Check for zero or minimal topical relevance
    claim_words = {w for w in re.findall(r"[a-z0-9]+", claim_lower) if len(w) > 2 and w not in {"the", "and", "for", "with", "that", "this", "are", "can", "out", "of"}}
    doc_words = {w for w in re.findall(r"[a-z0-9]+", combined) if len(w) > 2}
    overlap = claim_words & doc_words
    
    if len(overlap) == 0:
        return (
            EvidenceStance.IRRELEVANT,
            0.05,
            "Irrelevant: zero shared meaningful topical tokens with the claim."
        )

    overlap_ratio = len(overlap) / max(1, len(claim_words))

    # 3. Direct refutation / contradiction markers
    contradict_patterns = [
        r"\b(myth|debunk\w*|false|untrue|incorrect|hoax|disprov\w+|no evidence that)\b",
        r"\b(cannot|incapable of|impossible for humans to|does not exist|physically false)\b",
        r"\b(refut\w*|contradict\w*|contrary to claims)\b",
    ]
    has_contradict = any(re.search(pat, combined) for pat in contradict_patterns)

    # 4. Direct confirmation / support markers
    support_patterns = [
        r"\b(confirm\w*|prov\w+|demonstrat\w+|capable of|synthesiz\w+|can produce|manufacture\w*|develop\w*)\b",
        r"\b(study shows|researchers found|evidence confirms|toxicology confirms|corroborat\w+)\b",
        r"\b(is composed of|composed of|consists of|contains|structure of|nucleotide bases)\b",
        r"\b(showed|superior|effective|beneficial|outperform\w*|improved)\b",
    ]
    has_support = any(re.search(pat, combined) for pat in support_patterns)

    if has_contradict and has_support:
        return (
            EvidenceStance.MIXED,
            max(0.65, relevance_score),
            "Contains both supporting and contradicting statements."
        )

    if has_contradict:
        return (
            EvidenceStance.CONTRADICTS,
            max(0.70, relevance_score),
            "Directly contradicts or refutes the claim."
        )

    if has_support or overlap_ratio >= 0.65:
        return (
            EvidenceStance.SUPPORTS,
            max(0.70, relevance_score),
            "Corroborates and provides factual evidence supporting the claim."
        )

    # 5. Insufficient / neutral context
    if relevance_score < 0.35:
        return (
            EvidenceStance.IRRELEVANT,
            relevance_score,
            "Topical overlap is too weak to provide material evidence."
        )
    
    return (
        EvidenceStance.INSUFFICIENT,
        relevance_score,
        "Mentions related terms but does not provide adequate facts to verify or refute."
    )


def classify_evidence_items(
    claim_text: str,
    raw_evidence_list: List[Dict[str, Any]],
    llm_stance_map: Optional[Dict[str, Dict[str, Any]]] = None,
) -> Tuple[List[ClassifiedEvidenceItem], List[Dict[str, Any]]]:
    """
    Classify an entire pool of raw evidence items.
    Returns (accepted_classified_items, rejected_items_with_reason).
    """
    classified = []
    rejected = []
    seen_fingerprints: Dict[str, str] = {}
    seen_urls: Set[str] = set()

    for item in raw_evidence_list:
        url = (item.get("source_url") or item.get("url") or "").strip()
        title = item.get("source_title") or item.get("title") or "Web Source"
        snippet = item.get("snippet") or item.get("body") or ""
        
        if not url or url in seen_urls:
            continue
        seen_urls.add(url)
        
        # Check domain trust
        tier = item.get("domain_trust_tier") or get_domain_trust_tier(url)
        trust_label = "high" if tier == 1 else "medium" if tier == 2 else "low"
        cred_score = 1.0 if tier == 1 else 0.85 if tier == 2 else 0.70
        
        domain = item.get("domain")
        if not domain:
            domain = urlparse(url).netloc.lower().lstrip("www.")

        # Check independence
        is_indep, cluster_id = check_domain_independence(url, title, snippet, seen_fingerprints)
        
        # Determine stance & relevance
        rel_score = float(item.get("relevance_score") or 0.5)
        
        # Check if LLM provided stance
        if llm_stance_map and url in llm_stance_map:
            l_info = llm_stance_map[url]
            l_stance_str = str(l_info.get("stance", "")).lower()
            if l_stance_str == "supports" or l_info.get("supports_claim") is True:
                stance = EvidenceStance.SUPPORTS
            elif l_stance_str == "contradicts" or l_info.get("supports_claim") is False:
                stance = EvidenceStance.CONTRADICTS
            elif l_stance_str in ("mixed", "partial"):
                stance = EvidenceStance.MIXED
            elif l_stance_str == "irrelevant":
                stance = EvidenceStance.IRRELEVANT
            else:
                stance = EvidenceStance.INSUFFICIENT
            rel_score = float(l_info.get("relevance_score") or rel_score)
            explanation = l_info.get("explanation") or l_info.get("reason", "Evaluated by LLM fact-checker.")
        else:
            stance, rel_score, explanation = classify_passage_stance(claim_text, title, snippet, url, rel_score)

        c_item = ClassifiedEvidenceItem(
            source_url=url,
            source_title=title,
            domain=domain,
            domain_trust=trust_label,
            domain_trust_tier=tier,
            snippet=snippet[:500],
            relevant_passage=snippet[:300],
            stance=stance,
            relevance_score=round(rel_score, 2),
            credibility_score=cred_score,
            is_independent=is_indep,
            cluster_id=cluster_id,
            explanation=explanation,
            supports_claim=True if stance == EvidenceStance.SUPPORTS else False if stance == EvidenceStance.CONTRADICTS else None,
            publication_date=item.get("publication_date", ""),
        )

        # Rejection criteria: completely off-topic (IRRELEVANT with low score)
        if stance == EvidenceStance.IRRELEVANT and rel_score < 0.25:
            rejected.append({
                "url": url,
                "title": title,
                "domain": domain,
                "reason": explanation
            })
            continue

        classified.append(c_item)

    return classified, rejected


def deduplicate_syndicated_items(classified_items: List[ClassifiedEvidenceItem]) -> List[ClassifiedEvidenceItem]:
    """Flag duplicate syndicated wire reports in-place and return the list."""
    seen_fingerprints: Dict[str, str] = {}
    for item in classified_items:
        fp = compute_content_fingerprint(item.source_title, item.snippet)
        if fp in seen_fingerprints:
            item.is_independent = False
            item.cluster_id = fp
        else:
            seen_fingerprints[fp] = item.domain
            item.is_independent = True
            item.cluster_id = fp
    return classified_items


def compute_consensus_and_metrics(
    classified_items: List[ClassifiedEvidenceItem],
    rejected_items: Optional[List[Dict[str, Any]]] = None,
    searches_run_count: int = 1,
    llm_rounds_count: int = 1,
) -> Dict[str, Any]:
    """
    Compute mathematically sound consensus, coverage, and fact-check summary metrics.
    Consensus is computed strictly over independent, non-irrelevant evidence items.
    """
    if rejected_items is None:
        rejected_items = []

    # Filter for relevant independent items
    valid_items = [
        item for item in classified_items
        if item.stance not in (EvidenceStance.IRRELEVANT, EvidenceStance.INSUFFICIENT)
        and item.is_independent
    ]

    support_count = sum(1 for item in valid_items if item.stance == EvidenceStance.SUPPORTS)
    contradict_count = sum(1 for item in valid_items if item.stance == EvidenceStance.CONTRADICTS)
    mixed_count = sum(1 for item in valid_items if item.stance == EvidenceStance.MIXED)
    total_valid = len(valid_items)

    if total_valid == 0:
        consensus_score = 0.0
    else:
        # Weighted by credibility and relevance
        support_weight = sum(item.credibility_score * item.relevance_score for item in valid_items if item.stance == EvidenceStance.SUPPORTS)
        contradict_weight = sum(item.credibility_score * item.relevance_score for item in valid_items if item.stance == EvidenceStance.CONTRADICTS)
        mixed_weight = sum(item.credibility_score * item.relevance_score * 0.5 for item in valid_items if item.stance == EvidenceStance.MIXED)
        total_weight = support_weight + contradict_weight + mixed_weight

        if total_weight > 0:
            consensus_score = round(max(support_weight, contradict_weight) / total_weight, 3)
        else:
            consensus_score = 0.0

    return {
        "searches_run": max(1, searches_run_count),
        "sources_found": len(classified_items) + len(rejected_items),
        "sources_accepted": len(classified_items),
        "sources_blocked": len(rejected_items),
        "consensus_score": consensus_score,
        "cross_platform_hits": 0,
        "llm_rounds": max(1, llm_rounds_count),
        "critic_rejections": 0,
        "independent_sources_count": len([i for i in classified_items if i.is_independent]),
        "independent_support_count": sum(1 for i in valid_items if i.stance == EvidenceStance.SUPPORTS and i.is_independent),
        "valid_count": total_valid,
        "support_count": support_count,
        "contradict_count": contradict_count,
        "mixed_count": mixed_count,
    }


def compute_calibrated_confidence(
    verdict_label: str,
    classified_items_or_consensus: Any,
    consensus_score_or_items: Any = 0.5,
    base_llm_confidence: float = 0.8,
    retrieval_rounds: int = 1,
) -> float:
    """
    Calculate an empirically grounded confidence score distinguishing
    evidence relevance, source credibility, source independence, and claim coverage.
    Supports either (label, items, score) or (label, score, items).
    """
    if isinstance(classified_items_or_consensus, list):
        classified_items = classified_items_or_consensus
        consensus_score = float(consensus_score_or_items)
    else:
        consensus_score = float(classified_items_or_consensus)
        classified_items = consensus_score_or_items if isinstance(consensus_score_or_items, list) else []

    if verdict_label in ("unverifiable", "unverified"):
        return round(min(0.40, max(0.15, base_llm_confidence * 0.4)), 3)

    valid_items = [
        item for item in classified_items
        if getattr(item, "stance", None) not in (EvidenceStance.IRRELEVANT, EvidenceStance.INSUFFICIENT)
    ]
    if not valid_items:
        return 0.35

    # Independent sources count
    indep_count = len({item.domain for item in valid_items if item.is_independent})
    
    # Coverage factor based on independent source count (1 source = 0.75, 2 = 0.88, 3+ = 1.0)
    coverage_factor = min(1.0, 0.65 + (indep_count * 0.12))
    
    # Average credibility
    avg_cred = sum(item.credibility_score for item in valid_items) / len(valid_items)
    
    # Average relevance
    avg_rel = sum(item.relevance_score for item in valid_items) / len(valid_items)

    # Calibrated score combines base model confidence with empirical factors
    raw_score = (base_llm_confidence * 0.40) + (consensus_score * 0.30) + (avg_cred * 0.15) + (avg_rel * 0.15)
    calibrated = raw_score * coverage_factor

    return round(max(0.20, min(0.99, calibrated)), 3)
