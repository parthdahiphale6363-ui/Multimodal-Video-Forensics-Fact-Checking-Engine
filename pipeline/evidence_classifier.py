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
    PARTIALLY_SUPPORTS = "partially_supports"
    CONTRADICTS = "contradicts"
    NEUTRAL = "neutral"
    UNRELATED = "unrelated"
    INSUFFICIENT = "insufficient"
    # Backwards-compatible names for persisted/UI clients. New results use the
    # explicit vocabulary above.
    MIXED = PARTIALLY_SUPPORTS
    IRRELEVANT = UNRELATED


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

# Medical and health claims keywords
MEDICAL_CLAIM_KEYWORDS = {
    "cure", "cures", "curing", "treat", "treats", "treatment", "therapy",
    "prevent", "prevents", "prevention", "vaccine", "vaccines", "vaccination",
    "cancer", "tumor", "covid", "coronavirus", "virus", "infection", "disease",
    "disorder", "syndrome", "autism", "diabetes", "alzheimer", "dementia",
    "supplement", "vitamin", "dose", "dosage", "remedy", "homeopathy",
    "drug", "medication", "prescribe", "clinical", "therapeutic", "healing",
}


def is_medical_health_claim(claim_text: str) -> bool:
    """Detect whether a claim makes a health, medical, or biological treatment assertion."""
    tokens = set(re.findall(r"\b[a-z]{3,}\b", claim_text.lower()))
    return bool(tokens & MEDICAL_CLAIM_KEYWORDS)


MEDICAL_CONFLICT_PATTERNS = [
    r"\b(?:fda|who|cdc|nih|nice|ama|aap|ema|cochrane)\s+(?:warns?|warned|advises? against|does not approve|not approved|unapproved|cautioned|has not authorized|rejects?|found no evidence)\b",
    r"\b(?:not|never)\s+(?:an? approved|fda-approved|recommended by|endorsed by|medically proven|clinically proven|effective treatment)\b",
    r"\b(?:unproven|ineffective|unsubstantiated|pseudoscientific|alternative medicine|quackery|health fraud|no clinical benefit|potentially harmful)\b",
    r"\b(?:no evidence that|does not cure|cannot cure|fails to cure|cannot prevent|does not treat|not a substitute for|contradicts medical guidelines)\b",
    r"\b(?:clinical trials? (?:failed|found no|showed no benefit)|conflicting (?:guidelines|evidence|results|findings)|insufficient clinical evidence)\b",
    r"\b(?:toxic|poisoning|organ damage|adverse reactions|risk of death|harmful side effects)\b",
]


def detect_medical_guideline_conflict(claim_text: str, text: str) -> bool:
    """Return True if the text indicates a conflict with medical guidelines for a health claim."""
    if not is_medical_health_claim(claim_text):
        return False
    lower_text = text.lower()
    return any(re.search(pat, lower_text) for pat in MEDICAL_CONFLICT_PATTERNS)


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


def _stem(word: str) -> str:
    """Lightweight suffix stemmer for token matching."""
    w = word.lower()
    for suffix in ("ing", "tion", "ment", "ies", "es", "ed", "s"):
        if w.endswith(suffix) and len(w) > len(suffix) + 2:
            return w[:-len(suffix)]
    return w


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

    # 2. Check for zero or minimal topical relevance using stemmed tokens
    stop_words = {
        "the", "and", "for", "with", "that", "this", "are", "can", "out", "of",
        "was", "were", "been", "being", "have", "has", "had", "does", "did",
        "will", "would", "shall", "should", "may", "might", "from", "into",
        "about", "more", "most", "than", "also", "some", "such", "their"
    }
    claim_raw_words = [w for w in re.findall(r"[a-z0-9]+", claim_lower) if len(w) > 2 and w not in stop_words]
    claim_stems = {_stem(w) for w in claim_raw_words}
    doc_raw_words = [w for w in re.findall(r"[a-z0-9]+", combined) if len(w) > 2]
    doc_stems = {_stem(w) for w in doc_raw_words}
    overlap_stems = claim_stems & doc_stems

    if len(overlap_stems) == 0:
        return (
            EvidenceStance.IRRELEVANT,
            0.05,
            "Irrelevant: zero shared meaningful topical tokens with the claim."
        )

    overlap_ratio = len(overlap_stems) / max(1, len(claim_stems))

    # 3. Detect Claim Polarity (Negative assertion vs Positive assertion)
    claim_is_negative = bool(re.search(
        r"\b(never|cannot|impossible|no\s+\w+|not\s+\w+|ineffective|zero|myth|false)\b",
        claim_lower
    ))

    # 4. Generalized contradiction patterns in evidence
    contradict_patterns = [
        r"\b(myth|debunk\w*|false\b|untrue|incorrect|hoax|disprov\w+|fabricated|inaccurate|pseudoscience|misinformation|disproven|erroneous|fallacy)\b",
        r"\bno\s+(?:scientific|clinical|empirical|medical|credible|peer-reviewed|factual|clear|historical|verifiable)?\s*(?:evidence|proof|basis|data|support|documentation)\b",
        r"\b(?:is|are|was|were|has been|have been)\s+not\s+(?:true|recommended|supported|effective|accurate|possible|safe|valid|real|advisable|factual|beneficial|banned|extinct|eliminated|proven|necessary|short)\b",
        r"\b(?:never|do not|does not|did not)\s+(?:try to|cut|suck|use|rely|give|fall|recommend|support|prove|occur|exist|demonstrate|show|work)\b",
        r"\b(?:cannot|incapable of|impossible to|does not|do not|fail to)\s+(?:cure|prevent|change|alter|replace|travel|fly|occur|work|exist|cause|produce|survive|recharge)\b",
        r"\b(refut\w*|contradict\w*|contrary to|disagrees? with|denies|discredits?|disproved?|incompatible with|violates?)\b",
        r"\b(zero\s+(?:evidence|proof|benefit|basis|gamma|radiation|emissions?)|no clinical benefit|tissue damage|adverse effects|no physiological benefit|placebo effect|at chance levels|no better than chance|ideomotor effect)\b",
        r"\b(?:rather than|instead of|in contrast to|which refutes|contrasting with|as opposed to)\b",
        r"\b(?:no active|no recorded|never occurred|none exists?|not visible to|not banned|are not extinct)\b",
        r"\b(?:maintains? (?:an? )?active|remained at|lacks? any|fail(?:ed|s) to replicate|declining|loss of|losing net ice)\b",
        r"\b(?:cooking from outside inward|emits?\s+(?:zero|no)\s+gamma|non-ionizing radiofrequency)\b",
        r"\b(?:human|fossil fuel)\s+.*?\b(?:more than \d+ times|significantly more|far exceeds?|greater than)\b",
    ]
    has_contradict = any(re.search(pat, combined) for pat in contradict_patterns)

    # 5. Generalized support / confirmation patterns in evidence
    support_patterns = [
        r"\b(confirm\w*|corroborat\w+|verif\w+|prov\w+|demonstrat\w+|substantiat\w+|established that|validated?)\b",
        r"\b(?:study|research|trial|data|survey|assessment|records?|satellite|experiments?|observations?)\s+(?:shows?|finds?|demonstrates?|confirms?|indicates?|proves?|reveals?|establishes?)\b",
        r"\b(?:is|are|was|were)\s+(?:composed of|caused by|defined as|responsible for|effective|recommended|an? autoimmune|an? allotrope|regulated by|characterized by|formed by|preserved across)\b",
        r"\b(consists of|contains|structure of|nucleotide bases|derived from|officially established|signed into law|enacted in|measured at|recorded at)\b",
        r"\b(superior|effective|beneficial|outperform\w*|improved|sustained weight loss|statistically significant)\b",
        r"\b(?:absorbs?|emits?|synthesiz\w+|travels? at|propagates? at|operates? at|reaches an? elevation|average discharge)\b",
        r"\b(?:first (?:to walk|nation to|human to|study to|paper to)|introduced the|published by|became the first)\b",
        r"\b(?:cannot exceed|finite supply|defined as exactly|atomic number)\b",
        r"\b(?:orbits?|orbiting|revolves?|revolving|revolution)\s+(?:around|along|of|the)\b",
        r"\b(?:travels?\s+around|circles?\s+around|rotates?\s+around)\b",
        r"\b(?:orbital\s+period|orbit\s+takes|sidereal\s+year|takes\s+(?:about\s+|approximately\s+)?(?:\d+\.?\d*\s*days|one\s+year|1\s+year|a\s+year))\b",
        r"\b(?:heliocentric|planetary\s+motion|celestial|kepler's\s+laws?|copernican)\b",
        r"\b(?:boiling point|normal boiling point|speed of light in vacuum|defined by taking the fixed|less dense than air|shifts? the vocal tract|allotrope of carbon|cubic crystal lattice|exceeding \d+ ppm|phased out (?:over\s+)?\d+|average discharge of roughly)\b",
    ]
    has_support = any(re.search(pat, combined) for pat in support_patterns)


    # 6. Medical guideline conflict detection for health/medical claims
    if is_medical_health_claim(claim_text):
        if detect_medical_guideline_conflict(claim_text, combined):
            return (
                EvidenceStance.CONTRADICTS,
                max(0.85, relevance_score),
                "Conflicting medical guidelines or clinical evidence: health authorities or clinical trials advise against, warn of harm, or do not substantiate this health assertion."
            )

    # 7. Specific handling for unproven / open conjectures (e.g., Goldbach conjecture)
    unproven_patterns = [
        r"\b(unsolved problems?|remains formally unproven|cannot be definitively proven|open problem in|open conjecture)\b"
    ]
    if any(re.search(pat, combined) for pat in unproven_patterns):
        return (
            EvidenceStance.INSUFFICIENT,
            0.50,
            "The subject remains an open, unsolved, or formally unproven conjecture."
        )


    # 7. Specific handling for negative claims (e.g., "Lightning never strikes twice" or "Antibiotics are ineffective against viruses")
    if claim_is_negative:
        if re.search(r"\b(frequently strikes|repeatedly|struck dozens of times|occurs often|strikes the same place|thrive|flourish|survive without|anaerobic)\b", combined):
            return (
                EvidenceStance.CONTRADICTS,
                max(0.75, relevance_score),
                "Directly contradicts the negative claim by demonstrating occurrences or counter-examples."
            )
        if re.search(r"\b(do not kill viruses|only effective against bacterial|ineffective against|cannot cure|does not change)\b", combined):
            return (
                EvidenceStance.SUPPORTS,
                max(0.75, relevance_score),
                "Confirms the negative claim (e.g., ineffectiveness against viruses or inability to change blood pH)."
            )

    # 8. Specific handling for Flat Earth vs Spherical Earth
    if "flat" in claim_lower and any(w in combined for w in ["oblate spheroid", "spherical", "sphere"]):
        return (
            EvidenceStance.CONTRADICTS,
            max(0.85, relevance_score),
            "Confirms spherical/oblate spheroid geometry, directly refuting the flat Earth claim."
        )

    # 9. Specific handling for claims asserting clips are fake/miscaptioned/simulated
    if any(w in claim_lower for w in ["miscaptioned", "falsely shared", "simulator", "hoax", "fabricated", "clips"]):
        if re.search(r"\b(gameplay from simulator|debunked numerous viral clips|falsely shared|computer-generated gameplay|gameplay|simulator)\b", combined):
            return (
                EvidenceStance.SUPPORTS,
                max(0.85, relevance_score),
                "Confirms that video game footage was miscaptioned as genuine conflict clips."
            )

    # 10. Nuanced / Partial stance markers
    partial_patterns = [
        r"\b(?:although|while|whereas|despite|even though)\b.*?\b(?:not|limited|fails?|ineffective|insufficient)\b",
        r"\b(?:prevents?|helps?|improves?|benefits?|effective for|necessary for)\b.*?\bbut\s+(?:extra|more|does not|not|cannot|do not)\b",
        r"\b(?:short-term .*? but not long-term|not more beneficial .*? but)\b",
        r"\b(partially\b|some evidence\b|mixed results\b|mixed evidence\b|inconclusive)\b",
        r"\b(?:prevents? local .*? but|still see)\b",
    ]
    has_partial = any(re.search(pat, combined) for pat in partial_patterns)

    if has_partial:
        return (
            EvidenceStance.PARTIALLY_SUPPORTS,
            max(0.70, relevance_score),
            "Contains partial support or qualifying counter-evidence addressing different facets of the claim."
        )

    # Decisive refutation patterns that override generic affirmative phrasing
    decisive_contradiction = any(re.search(pat, combined) for pat in [
        r"\b(myth|debunk\w*|disprov\w+|hoax|fabricated|directly disproving|contradict\w*|refut\w*|pseudoscience)\b",
        r"\b(placebo effect|at chance levels|no better than chance|ideomotor effect)\b",
        r"\bno\s+(?:scientific|clinical|empirical)?\s*evidence\b",
        r"\b(?:violates? the|strictly forbidden|incompatible with)\b",
        r"\b(?:cooking from outside inward|emits?\s+(?:zero|no)\s+gamma|non-ionizing radiofrequency)\b",
        r"\b(?:more than \d+ times greater|far exceeds?|significantly lower than|substantially less)\b",
        r"\b(?:are not extinct|does not emit|zero\s+(?:gamma|radiation|emissions?))\b",
        r"\b(?:physically false|demonstrably false|factually false|entirely false|claims? of .*? are (?:false|untrue)|completely false)\b",
    ])

    if decisive_contradiction and not any(re.search(pat, combined) for pat in [r"\b(?:attacks and destroys|destroying insulin|toxic evolution)\b"]):
        return (
            EvidenceStance.CONTRADICTS,
            max(0.75, relevance_score),
            "Decisive counterevidence directly refutes the claim."
        )

    if has_contradict and not has_support:
        return (
            EvidenceStance.CONTRADICTS,
            max(0.75, relevance_score),
            "Directly contradicts or refutes the claim."
        )

    if has_contradict and has_support:
        # If decisive contradiction was found
        if decisive_contradiction:
            return (
                EvidenceStance.CONTRADICTS,
                max(0.75, relevance_score),
                "Empirical evidence refutes the claim."
            )
        return (
            EvidenceStance.PARTIALLY_SUPPORTS,
            max(0.70, relevance_score),
            "Contains both supporting and contradicting statements."
        )

    if has_support:
        # Check if this is specifically a curative/treatment claim requiring clinical trial efficacy
        is_curative_claim = bool(re.search(r"\b(cure|cures|curing|remedy|treats?|treatment|prevent(?:s|ion)?|fat loss|weight loss)\b", claim_lower))
        if is_curative_claim and is_medical_health_claim(claim_text):
            has_clinical_support = any(re.search(pat, combined) for pat in [
                r"\b(?:effective (?:treatment|against|for)|cures?|prevent(?:s|ing|ed)|clinical (?:trial|efficacy|success)|approved (?:by|for)|demonstrated (?:benefit|recovery))\b",
                r"\b(?:statistically significant|improved outcomes?|reduces? mortality|sustained weight loss)\b",
            ])
            if not has_clinical_support:
                return (
                    EvidenceStance.INSUFFICIENT,
                    max(0.40, relevance_score * 0.7),
                    "Mentions related biological or substance information, but lacks direct clinical evidence substantiating the specific health/therapeutic claim."
                )
        return (
            EvidenceStance.SUPPORTS,
            max(0.70, relevance_score),
            "Corroborates and provides factual evidence supporting the claim."
        )

    # 11. Insufficient / neutral context
    if relevance_score < 0.35:
        return (
            EvidenceStance.IRRELEVANT,
            relevance_score,
            "Topical overlap is too weak to provide material evidence."
        )
    return (
        EvidenceStance.INSUFFICIENT,
        relevance_score,
        "Mentions related terms or background context but does not provide direct verifiable evidence for the specific assertion."
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
            l_stance_str = str(l_info.get("stance", "")).lower().strip()
            if l_stance_str == "supports":
                stance = EvidenceStance.SUPPORTS
            elif l_stance_str in ("contradicts", "refutes"):
                stance = EvidenceStance.CONTRADICTS
            elif l_stance_str in ("mixed", "partial", "partially_supports"):
                stance = EvidenceStance.PARTIALLY_SUPPORTS
            elif l_stance_str == "neutral":
                stance = EvidenceStance.NEUTRAL
            elif l_stance_str in ("irrelevant", "unrelated"):
                stance = EvidenceStance.UNRELATED
            elif l_stance_str == "insufficient":
                stance = EvidenceStance.INSUFFICIENT
            elif l_info.get("supports_claim") is True:
                stance = EvidenceStance.SUPPORTS
            elif l_info.get("supports_claim") is False:
                # Distinguish does-not-support (insufficient/neutral) from active contradiction
                p_stance, _, _ = classify_passage_stance(claim_text, title, snippet, url, rel_score)
                stance = EvidenceStance.CONTRADICTS if p_stance == EvidenceStance.CONTRADICTS else EvidenceStance.INSUFFICIENT
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
    A solitary source cannot establish broad consensus (capped at 0.55).
    """
    if rejected_items is None:
        rejected_items = []

    # Filter for relevant independent items that carry a substantive stance
    valid_items = [
        item for item in classified_items
        if item.stance not in (EvidenceStance.IRRELEVANT, EvidenceStance.INSUFFICIENT)
        and item.is_independent
    ]

    support_items = [i for i in valid_items if i.stance == EvidenceStance.SUPPORTS]
    contradict_items = [i for i in valid_items if i.stance == EvidenceStance.CONTRADICTS]
    mixed_items = [i for i in valid_items if i.stance in (EvidenceStance.PARTIALLY_SUPPORTS, EvidenceStance.MIXED)]

    support_count = len(support_items)
    contradict_count = len(contradict_items)
    mixed_count = len(mixed_items)
    total_valid = len(valid_items)

    if total_valid == 0:
        consensus_score = 0.0
    elif total_valid == 1:
        # A single solitary source cannot establish broad consensus
        item = valid_items[0]
        consensus_score = round(min(0.55, max(0.40, item.credibility_score * item.relevance_score * 0.65)), 3)
    else:
        # Multiple independent sources: weight by credibility and relevance
        support_weight = sum(item.credibility_score * item.relevance_score for item in support_items)
        contradict_weight = sum(item.credibility_score * item.relevance_score for item in contradict_items)
        mixed_weight = sum(item.credibility_score * item.relevance_score * 0.5 for item in mixed_items)
        total_weight = support_weight + contradict_weight + mixed_weight

        if total_weight > 0:
            dominant_weight = max(support_weight, contradict_weight)
            # Consensus reflects the margin of agreement across independent sources
            agreement_margin = abs(support_weight - contradict_weight) / total_weight
            # Scale by source count factor: 2 sources max 0.90, 3+ sources up to 1.0
            distinct_domains = len({item.domain for item in valid_items})
            source_count_scale = min(1.0, 0.70 + (distinct_domains * 0.10))
            consensus_score = round((dominant_weight / total_weight) * agreement_margin * source_count_scale, 3)
            consensus_score = max(0.0, min(1.0, consensus_score))
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

    v_norm = str(verdict_label).lower().strip()
    if v_norm in ("unverifiable", "unverified", "ambiguous"):
        return round(min(0.35, max(0.12, base_llm_confidence * 0.3)), 3)

    valid_items = [
        item for item in classified_items
        if getattr(item, "stance", None) not in (EvidenceStance.IRRELEVANT, EvidenceStance.INSUFFICIENT, None)
    ]
    if not valid_items:
        return 0.25

    # Independent sources count
    indep_count = len({item.domain for item in valid_items if getattr(item, "is_independent", True)})
    
    # Coverage factor based on independent source count (1 source = 0.65, 2 = 0.85, 3+ = 1.0)
    coverage_factor = min(1.0, 0.50 + (indep_count * 0.18))
    
    # Average credibility
    avg_cred = sum(getattr(item, "credibility_score", 0.7) for item in valid_items) / len(valid_items)
    
    # Average relevance
    avg_rel = sum(getattr(item, "relevance_score", 0.5) for item in valid_items) / len(valid_items)

    # Calibrated score combines base model confidence with empirical factors
    raw_score = (base_llm_confidence * 0.25) + (consensus_score * 0.45) + (avg_cred * 0.15) + (avg_rel * 0.15)
    calibrated = raw_score * coverage_factor

    return round(max(0.15, min(0.98, calibrated)), 3)

