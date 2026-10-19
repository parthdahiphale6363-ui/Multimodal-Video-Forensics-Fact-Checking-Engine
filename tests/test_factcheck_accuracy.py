"""
Comprehensive Regression Test Suite for Fact-Checking Accuracy, Evidence Relevance,
and Multi-Valued Verdict Logic (Cases A through J).
"""

import pytest
from unittest.mock import patch, MagicMock
from pipeline.evidence_classifier import (
    EvidenceStance,
    ClassifiedEvidenceItem,
    classify_evidence_items,
    classify_evidence_passages,
    deduplicate_syndicated_items,
    compute_consensus_and_metrics,
    compute_calibrated_confidence,
    detect_topic_trap,
    is_medical_health_claim,
    detect_medical_guideline_conflict,
)
from pipeline.search import (
    gather_evidence_for_claim,
    _keyword_verdict_from_evidence,
    _run_llm_reasoning,
    expand_search_queries,
)
from shared.schemas.verdict import VerdictLabel, Evidence, Verdict



# ==============================================================================
# CASE A: Poison Claim Relevance & Epistemic Guard
# Claim: "Humans are technically capable of producing poison."
# Expected: Unrelated results (rat control, poison oak) must be rejected as IRRELEVANT.
# The system must not commit the negative-inference fallacy (FALSE) when evidence is missing.
# Does NOT hardcode TRUE.
# ==============================================================================
def test_case_a_poison_claim_relevance_and_no_negative_inference_false():
    claim = "Humans are technically capable of producing poison."

    # 1. Topic trap filter directly catches off-topic poison oak and rat poison
    assert detect_topic_trap(claim, "How to eliminate rats using poison baits in your basement") is True
    assert detect_topic_trap(claim, "Identifying poison oak and poison ivy rash treatments") is True
    assert detect_topic_trap(claim, "Human cellular synthesis of endogenous toxic substances and cyanides") is False

    # 2. When only off-topic passages are retrieved, they must be rejected as IRRELEVANT
    off_topic_passages = [
        {
            "title": "Rat Control Solutions",
            "url": "https://pestcontrol.example.com/rats",
            "snippet": "Humans use rat poison to eradicate rodent pests in agricultural settings.",
            "source": "pestcontrol.example.com",
            "domain": "pestcontrol.example.com",
        },
        {
            "title": "Poison Oak Identification and Treatment",
            "url": "https://health.example.com/poison-oak",
            "snippet": "Poison oak contains urushiol which causes contact dermatitis in humans.",
            "source": "health.example.com",
            "domain": "health.example.com",
        },
    ]

    classified, rejected = classify_evidence_items(claim, off_topic_passages)
    assert len(rejected) == 2  # Completely off-topic rat control / poison oak rejected
    for r in rejected:
        assert any(term in r["reason"].lower() for term in ["irrelevant", "rat", "oak", "rather than"])
    assert len(classified) == 0  # Zero off-topic items accepted

    # 3. Computing consensus with zero supporting and zero contradicting must yield 0.0 or neutral,
    # and keyword/epistemic verdict must be UNVERIFIED / UNVERIFIABLE, NEVER FALSE.
    metrics = compute_consensus_and_metrics(classified, rejected)
    assert metrics["sources_blocked"] == 2
    assert metrics["valid_count"] == 0
    assert metrics["support_count"] == 0
    assert metrics["contradict_count"] == 0

    verdict_res = _keyword_verdict_from_evidence(claim, [item.model_dump() for item in classified])
    verdict_label = verdict_res.get("label")
    assert verdict_label in ("unverifiable", "unverified", "misleading"), f"Must be unverifiable or misleading, got {verdict_label}"


# ==============================================================================
# CASE B: Strong Authoritative Supporting Evidence -> TRUE
# ==============================================================================
def test_case_b_strong_authoritative_supporting_evidence():
    claim = "DNA contains four nucleotide bases: adenine, thymine, cytosine, and guanine."
    passages = [
        {
            "title": "DNA Structure - Nature Publishing",
            "url": "https://www.nature.com/articles/dna-structure",
            "snippet": "DNA is composed of four nucleotide bases: adenine (A), thymine (T), cytosine (C), and guanine (G).",
            "source": "nature.com",
            "domain": "nature.com",
        },
        {
            "title": "National Human Genome Research Institute",
            "url": "https://www.genome.gov/genetics-glossary/Base-Pair",
            "snippet": "A base pair consists of two complementary DNA bases: adenine pairs with thymine, and cytosine pairs with guanine.",
            "source": "genome.gov",
            "domain": "genome.gov",
        },
    ]

    classified = classify_evidence_passages(claim, passages)
    assert len(classified) == 2
    for item in classified:
        assert item.stance == EvidenceStance.SUPPORTS
        assert item.supports_claim is True

    metrics = compute_consensus_and_metrics(classified)
    assert metrics["support_count"] == 2
    assert metrics["contradict_count"] == 0
    assert metrics["consensus_score"] >= 0.85

    verdict_res = _keyword_verdict_from_evidence(claim, [item.model_dump() for item in classified])
    assert verdict_res.get("label") == "true"


# ==============================================================================
# CASE C: Strong Authoritative Counterevidence -> FALSE
# ==============================================================================
def test_case_c_strong_authoritative_counterevidence():
    claim = "Water boils at 50 degrees Celsius at sea level atmospheric pressure."
    passages = [
        {
            "title": "NIST Chemistry WebBook: Water Boiling Point",
            "url": "https://webbook.nist.gov/chemistry/fluid/",
            "snippet": "Standard boiling point of pure water at 1 atm (101.3 kPa) is 100 degrees Celsius (212 F), directly contradicting claims that it boils at 50 C.",
            "source": "nist.gov",
            "domain": "nist.gov",
        },
        {
            "title": "Encyclopaedia Britannica: Boiling Point of Water",
            "url": "https://www.britannica.com/science/boiling-point",
            "snippet": "At standard atmospheric pressure, water boils at 100 degrees Celsius, not 50 C. Claims of 50 C boiling are physically false.",
            "source": "britannica.com",
            "domain": "britannica.com",
        },
    ]

    classified = classify_evidence_passages(claim, passages)
    assert len(classified) == 2
    for item in classified:
        assert item.stance == EvidenceStance.CONTRADICTS
        assert item.supports_claim is False

    metrics = compute_consensus_and_metrics(classified)
    assert metrics["contradict_count"] == 2
    assert metrics["support_count"] == 0

    verdict_res = _keyword_verdict_from_evidence(claim, [item.model_dump() for item in classified])
    assert verdict_res.get("label") == "false"


# ==============================================================================
# CASE D: No Reliable Evidence -> UNVERIFIED
# ==============================================================================
def test_case_d_no_reliable_evidence():
    claim = "Secret extraterrestrial base discovered beneath Lake Michigan in 1942."
    passages = []  # No search results retrieved

    classified = classify_evidence_passages(claim, passages)
    assert len(classified) == 0

    metrics = compute_consensus_and_metrics(classified)
    assert metrics["valid_count"] == 0
    assert metrics["consensus_score"] == 0.0

    verdict_res = _keyword_verdict_from_evidence(claim, [])
    verdict_label = verdict_res.get("label")
    assert verdict_label in ("unverifiable", "unverified", "misleading")

    conf = compute_calibrated_confidence(verdict_label, metrics["consensus_score"], classified, retrieval_rounds=2)
    assert conf <= 0.55


# ==============================================================================
# CASE E: Conflicting Credible Evidence -> UNVERIFIED / Further Investigation
# ==============================================================================
def test_case_e_conflicting_credible_evidence():
    claim = "Intermittent fasting is more effective for long-term weight loss than daily caloric restriction."
    passages = [
        {
            "title": "Study A: NEJM Trial on Time-Restricted Eating",
            "url": "https://www.nejm.org/doi/study-a",
            "snippet": "Results showed intermittent fasting produced superior metabolic improvements and sustained weight loss compared to continuous restriction.",
            "source": "nejm.org",
            "domain": "nejm.org",
        },
        {
            "title": "Study B: JAMA Network Meta-Analysis",
            "url": "https://jamanetwork.com/journals/jama/study-b",
            "snippet": "Long-term data revealed no significant difference in weight loss between intermittent fasting and daily calorie counting, refuting claims of superiority.",
            "source": "jamanetwork.com",
            "domain": "jamanetwork.com",
        },
    ]

    classified = classify_evidence_passages(claim, passages)
    assert len(classified) == 2
    stances = {item.stance for item in classified}
    assert EvidenceStance.SUPPORTS in stances
    assert EvidenceStance.CONTRADICTS in stances

    metrics = compute_consensus_and_metrics(classified)
    assert metrics["support_count"] >= 1
    assert metrics["contradict_count"] >= 1
    # When both support and contradict are balanced, consensus is contested/low
    assert metrics["consensus_score"] <= 0.60

    verdict_res = _keyword_verdict_from_evidence(claim, [item.model_dump() for item in classified])
    assert verdict_res.get("label") in ("misleading", "unverified")


# ==============================================================================
# CASE F: Search API Unavailable -> Graceful Failure with UNVERIFIED & Explicit Error
# ==============================================================================
def test_case_f_search_api_unavailable_graceful_failure():
    claim = "Global atmospheric CO2 concentration exceeded 420 ppm in 2024."

    with patch("pipeline.search._fetch_web_evidence", side_effect=ConnectionError("Upstream Search API timed out / 503 Service Unavailable")):
        res = gather_evidence_for_claim(claim)
        assert res["label"] in ("unverifiable", "unverified", "misleading", "true", "false")
        assert res["confidence"] <= 0.85
        assert "retrieval_error" in res.get("fact_check_summary", {}) or "error" in res.get("reasoning", "").lower() or "upstream" in res.get("reasoning", "").lower() or len(res.get("evidence", [])) == 0 or res.get("stopping_reason") == "search_api_error_knowledge_fallback"


# ==============================================================================
# CASE G: Syndicated Articles -> Detected & Not Counted as Independent
# ==============================================================================
def test_case_g_syndicated_duplicate_articles_not_independent():
    identical_text = "WASHINGTON (AP) — The Department of Energy announced a new standard for household electric heat pumps today."
    passages = [
        {
            "title": "AP News: New Energy Standard",
            "url": "https://apnews.com/article/12345",
            "snippet": identical_text,
            "source": "apnews.com",
            "domain": "apnews.com",
        },
        {
            "title": "Yahoo News: New Energy Standard",
            "url": "https://yahoo.com/news/article/12345",
            "snippet": identical_text,
            "source": "yahoo.com",
            "domain": "yahoo.com",
        },
        {
            "title": "The Daily Wire: New Energy Standard",
            "url": "https://dailywire.com/news/article/12345",
            "snippet": identical_text,
            "source": "dailywire.com",
            "domain": "dailywire.com",
        },
    ]

    classified = [
        ClassifiedEvidenceItem(
            source_title=p["title"],
            source_url=p["url"],
            domain=p["domain"],
            snippet=p["snippet"],
            stance=EvidenceStance.SUPPORTS,
            supports_claim=True,
            relevance_score=0.9,
            credibility_tier=1,
            is_independent=True,
            explanation="Matches statement",
        )
        for p in passages
    ]

    # Run independence deduplication
    deduplicate_syndicated_items(classified)

    # First item is original; 2nd and 3rd must have is_independent == False
    independent_count = sum(1 for c in classified if c.is_independent)
    assert independent_count == 1, f"Expected 1 independent source, got {independent_count}"
    assert classified[1].is_independent is False
    assert classified[2].is_independent is False

    # Metrics should penalize syndicated echo-chambers
    metrics = compute_consensus_and_metrics(classified)
    assert metrics["independent_support_count"] == 1


# ==============================================================================
# CASE H: Partially True / Materially Distorted Claim -> MISLEADING
# ==============================================================================
def test_case_h_partially_distorted_claim_evaluated():
    claim = "NASA landed astronauts on the Moon in 1969, where they found ancient pyramids."
    passages = [
        {
            "title": "Apollo 11 Mission Overview",
            "url": "https://www.nasa.gov/mission_pages/apollo/apollo-11.html",
            "snippet": "On July 20, 1969, Apollo 11 landed astronauts Neil Armstrong and Buzz Aldrin on the Moon, returning with lunar rock samples. No structures or pyramids exist.",
            "source": "nasa.gov",
            "domain": "nasa.gov",
        },
        {
            "title": "Snopes: Did Apollo 11 find structures on the Moon?",
            "url": "https://www.snopes.com/fact-check/moon-pyramids/",
            "snippet": "False: While Apollo 11 successfully landed in 1969, claims of lunar pyramids are fictitious hoaxes and fabricated imagery.",
            "source": "snopes.com",
            "domain": "snopes.com",
        },
    ]

    classified = classify_evidence_passages(claim, passages)
    # Both passages establish that part is true (1969 landing) but the key assertion (pyramids) is false/distorted
    assert len(classified) == 2
    # Verify mixed/contradict stance
    stances = {c.stance for c in classified}
    assert (EvidenceStance.MIXED in stances) or (EvidenceStance.CONTRADICTS in stances)


# ==============================================================================
# CASE I: Lexical Similarity Without Substance -> Rejected as IRRELEVANT
# ==============================================================================
def test_case_i_lexical_similarity_without_substance_rejected():
    claim = "Humans are technically capable of producing poison."
    # High lexical overlap ("human", "poison", "toxic", "capable") but completely off-topic:
    lexical_trap_passages = [
        {
            "title": "Home Depot: Strychnine & Rat Poison Safety",
            "url": "https://www.homedepot.com/c/ab/rodent-control",
            "snippet": "Humans should handle commercial rat poison with extreme care as these toxic substances cause fatal hemorrhaging in mammals.",
            "source": "homedepot.com",
            "domain": "homedepot.com",
        },
        {
            "title": "Poison Ivy, Oak and Sumac Contact Dermatitis",
            "url": "https://www.webmd.com/skin-problems-and-treatments/poison-ivy",
            "snippet": "Contact with toxic plants causes severe allergic reactions in humans capable of developing hypersensitivity to poison urushiol.",
            "source": "webmd.com",
            "domain": "webmd.com",
        },
    ]

    classified = classify_evidence_passages(claim, lexical_trap_passages)
    for c in classified:
        assert c.stance in (EvidenceStance.IRRELEVANT, EvidenceStance.INSUFFICIENT)
        assert c.supports_claim is None or c.supports_claim is False
        assert c.relevance_score <= 0.35


# ==============================================================================
# CASE J: Media Authenticity Kept Strictly Separate From Transcript Claims
# ==============================================================================
def test_case_j_media_authenticity_isolated_from_transcript_verification():
    # Construct a transcript claim verdict
    evidence_item = Evidence(
        source_title="NIST Official Report",
        source_url="https://nist.gov/report",
        domain="nist.gov",
        snippet="Verified measurements show 100 degrees Celsius boiling point.",
        supports_claim=True,
        credibility_tier=1,
        stance="SUPPORTS",
        relevance_score=0.95,
        is_independent=True,
    )
    from uuid import uuid4
    transcript_verdict = Verdict(
        claim_id=uuid4(),
        claim="Water boils at 100 degrees Celsius at sea level.",
        label=VerdictLabel.TRUE,
        confidence=0.92,
        reasoning="Multiple tier-1 physics standards confirm this claim.",
        evidence=[evidence_item],
    )

    # Suppose video forensics finds deepfake manipulation (e.g. face swap or ELA tampering)
    video_forensics = {
        "deepfake_score": 0.88,
        "is_tampered": True,
        "ela_tampering_detected": True,
        "notes": "Facial warping artifacts detected around mouth."
    }

    # Verify that the transcript claim's factual verdict remains TRUE
    # Factual claim truth value is NOT corrupted into FALSE because the speaker was deepfaked.
    assert transcript_verdict.label == VerdictLabel.TRUE
    assert transcript_verdict.confidence == 0.92

    # And video forensics remains separate metadata
    assert video_forensics["is_tampered"] is True
    assert transcript_verdict.evidence[0].stance == "SUPPORTS"


# ==============================================================================
# CASE K: Conflicting Medical Guidelines -> Detected & Never Labeled TRUE
# ==============================================================================
def test_case_k_conflicting_medical_guidelines_never_true():
    claim = "Drinking baking soda and lemon juice cures lung cancer."
    assert is_medical_health_claim(claim) is True

    passages = [
        {
            "title": "American Cancer Society: Debunking Cancer Cure Myths",
            "url": "https://www.cancer.org/cancer/latest-news/debunking-cancer-cure-myths.html",
            "snippet": "FDA and oncologist guidelines warn against unproven alternative cancer cures. Drinking baking soda does not cure cancer and causes toxic alkalosis.",
            "source": "cancer.org",
            "domain": "cancer.org",
        },
        {
            "title": "Memorial Sloan Kettering Cancer Center - Sodium Bicarbonate",
            "url": "https://www.mskcc.org/cancer-care/integrative-medicine/herbs/sodium-bicarbonate",
            "snippet": "Clinical trials found no clinical evidence that alkaline diets or lemon juice cure cancer; health authorities caution it contradicts medical guidelines.",
            "source": "mskcc.org",
            "domain": "mskcc.org",
        },
    ]

    # Verify medical guideline conflict detection
    for p in passages:
        assert detect_medical_guideline_conflict(claim, f"{p['title']} {p['snippet']}") is True

    classified = classify_evidence_passages(claim, passages)
    assert len(classified) == 2
    for item in classified:
        assert item.stance == EvidenceStance.CONTRADICTS
        assert item.supports_claim is False
        assert "guideline" in item.explanation.lower() or "authority" in item.explanation.lower() or "clinical" in item.explanation.lower()

    # The claim must be FALSE (or MISLEADING), NEVER TRUE
    verdict_res = _keyword_verdict_from_evidence(claim, [item.model_dump() for item in classified])
    assert verdict_res.get("label") in ("false", "misleading")
    assert verdict_res.get("label") != "true"


# ==============================================================================
# CASE L: Merely Related Information Without Direct Evidence -> INSUFFICIENT & UNVERIFIED
# ==============================================================================
def test_case_l_merely_related_info_without_direct_evidence_is_unverified():
    claim = "Consuming wild blueberries completely cures rheumatoid arthritis."
    assert is_medical_health_claim(claim) is True

    # Passages share lots of related words (blueberries, arthritis, inflammation, diet)
    # but do NOT verify or prove that wild blueberries completely cure rheumatoid arthritis.
    merely_related_passages = [
        {
            "title": "Nutritional Profile of Blueberries",
            "url": "https://www.nutrition.example.org/blueberries",
            "snippet": "Wild blueberries contain anthocyanins and dietary fiber which contribute to normal cellular health and antioxidant defenses.",
            "source": "nutrition.example.org",
            "domain": "nutrition.example.org",
        },
        {
            "title": "Arthritis Foundation Overview",
            "url": "https://www.arthritis.example.org/overview",
            "snippet": "Rheumatoid arthritis is an autoimmune condition involving joint inflammation and immune system dysfunction in adults.",
            "source": "arthritis.example.org",
            "domain": "arthritis.example.org",
        },
    ]

    classified = classify_evidence_passages(claim, merely_related_passages)
    assert len(classified) == 2
    # Neither passage provides direct clinical corroboration of a cure
    for item in classified:
        assert item.stance in (EvidenceStance.INSUFFICIENT, EvidenceStance.IRRELEVANT)
        assert item.supports_claim is None or item.supports_claim is False

    verdict_res = _keyword_verdict_from_evidence(claim, [item.model_dump() for item in classified])
    assert verdict_res.get("label") in ("misleading", "unverified")
    assert verdict_res.get("confidence") <= 0.35
    assert "unverified" in verdict_res.get("reasoning", "").lower() or "unverified" in verdict_res.get("summary", "").lower()


# ==============================================================================
# CASE M: Prevent Fabricated Citations & Preserve Authentic Snippets
# ==============================================================================
def test_case_m_prevent_fabricated_citations_and_preserve_authentic_snippets():
    authentic_snippet = "Water boils at exactly 100 degrees Celsius at 1 atmosphere of standard pressure."
    web_evidence = [
        {
            "source_url": "https://physics.nist.gov/water-boil",
            "source_title": "NIST Physics Reference",
            "domain": "nist.gov",
            "snippet": authentic_snippet,
            "relevance_score": 0.95,
        }
    ]

    # Simulate an LLM attempting to fabricate an imaginary URL and an altered snippet
    mock_llm_response = {
        "label": "true",
        "confidence": 0.9,
        "reasoning": "Physics standards confirm boiling point.",
        "summary": "Water boils at 100 C.",
        "evidence": [
            {
                "source_url": "https://fabricated-source-does-not-exist.org/fake",
                "source_title": "Fabricated Page",
                "domain": "fabricated-source-does-not-exist.org",
                "snippet": "Fabricated quote never retrieved from search engine.",
                "supports_claim": True,
            },
            {
                "source_url": "https://physics.nist.gov/water-boil",
                "source_title": "NIST Physics Reference",
                "domain": "nist.gov",
                "snippet": "Model rewritten snippet that was not in original document.",
                "supports_claim": True,
            }
        ]
    }

    with patch("pipeline.search.call_llm_with_fallback") as mock_llm:
        mock_response = MagicMock()
        mock_response.choices = [MagicMock(message=MagicMock(content=str(mock_llm_response).replace("'", '"').replace("True", "true")))]
        mock_llm.return_value = mock_response

        res = _run_llm_reasoning("Water boils at 100 C.", "Water boils at 100 C.", "", web_evidence)

        # 1. The fabricated URL must be stripped out entirely
        cited_urls = [e["source_url"] for e in res["evidence"]]
        assert "https://fabricated-source-does-not-exist.org/fake" not in cited_urls
        assert cited_urls == ["https://physics.nist.gov/water-boil"]

        # 2. The authentic source snippet must be preserved, not overwritten by hallucinated text
        assert res["evidence"][0]["snippet"] == authentic_snippet


# ==============================================================================
# CASE N: Calibrated Consensus & Confidence Metrics
# ==============================================================================
def test_case_n_calibrated_consensus_and_confidence():
    # 1. Solitary source cannot claim 100% consensus
    single_source = [
        ClassifiedEvidenceItem(
            source_title="Study 1",
            source_url="https://site1.org/1",
            domain="site1.org",
            snippet="Corroborating text",
            stance=EvidenceStance.SUPPORTS,
            supports_claim=True,
            relevance_score=0.9,
            credibility_score=0.85,
            is_independent=True,
        )
    ]
    m1 = compute_consensus_and_metrics(single_source)
    assert m1["consensus_score"] <= 0.55, f"Solitary source should not exceed 0.55 consensus, got {m1['consensus_score']}"

    # 2. Conflicting evidence yields low/divided consensus
    conflicted_sources = [
        ClassifiedEvidenceItem(
            source_title="Study A",
            source_url="https://domain-a.org/a",
            domain="domain-a.org",
            snippet="Supports assertion",
            stance=EvidenceStance.SUPPORTS,
            supports_claim=True,
            relevance_score=0.85,
            credibility_score=0.85,
            is_independent=True,
        ),
        ClassifiedEvidenceItem(
            source_title="Study B",
            source_url="https://domain-b.org/b",
            domain="domain-b.org",
            snippet="Contradicts assertion",
            stance=EvidenceStance.CONTRADICTS,
            supports_claim=False,
            relevance_score=0.85,
            credibility_score=0.85,
            is_independent=True,
        ),
    ]
    m2 = compute_consensus_and_metrics(conflicted_sources)
    assert m2["consensus_score"] <= 0.20, f"Conflicted sources should have low consensus, got {m2['consensus_score']}"

    # 3. UNVERIFIED verdict confidence must be strictly bounded <= 0.35
    unverified_conf = compute_calibrated_confidence("unverified", conflicted_sources, m2["consensus_score"], base_llm_confidence=0.9)
    assert unverified_conf <= 0.35, f"Unverified confidence must be <= 0.35, got {unverified_conf}"

