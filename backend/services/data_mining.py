"""
data_mining.py — Data Mining Module
====================================
Implements the full DM pipeline for the Multimodal Video Forensics Engine:
  1. Data Cleaning          — deduplicate & normalize evidence
  2. Classification         — multi-signal Real/Fake/Misleading/Deepfake scoring
  3. Clustering             — group similar claims/evidence by topic (cosine TF-IDF)
  4. Outlier Detection      — flag anomalous confidence + suspicious metadata
  5. Association Rules      — find co-occurring verdict patterns
  6. Pattern Mining         — temporal + thematic patterns in claims
  7. Similarity Analysis    — fuzzy match against known misinformation heuristics
"""

import re
import math
from collections import Counter, defaultdict
from typing import Any, Dict, List, Optional, Tuple


# ─── 1. Data Cleaning ─────────────────────────────────────────────────────────

def clean_evidence_items(evidence_list: List[Dict]) -> List[Dict]:
    """Remove duplicates, normalize scores, filter empty entries."""
    seen_urls = set()
    cleaned = []
    for ev in evidence_list:
        url = ev.get("source_url") or ev.get("url") or ""
        snippet = (ev.get("snippet") or ev.get("excerpt") or "").strip()
        if not snippet or url in seen_urls:
            continue
        seen_urls.add(url)
        # Normalize relevance score to [0, 1]
        rel = float(ev.get("relevance_score", 0.7))
        ev["relevance_score"] = min(max(rel, 0.0), 1.0)
        cleaned.append(ev)
    return cleaned


def normalize_claim_scores(claim_items: List[Dict]) -> List[Dict]:
    """Normalize confidence scores across all claims to prevent score inflation."""
    if not claim_items:
        return claim_items
    confidences = [item["verdict"]["confidence"] for item in claim_items if "verdict" in item]
    if not confidences:
        return claim_items
    avg = sum(confidences) / len(confidences)
    std = math.sqrt(sum((c - avg) ** 2 for c in confidences) / len(confidences)) or 0.1
    for item in claim_items:
        if "verdict" in item:
            raw = item["verdict"]["confidence"]
            # Soft normalization — keep in [0.3, 0.99]
            normalized = 0.5 + (raw - avg) / (2 * std) * 0.3
            item["verdict"]["confidence"] = round(min(max(normalized, 0.3), 0.99), 3)
    return claim_items


# ─── 2. Classification ────────────────────────────────────────────────────────

MISINFORMATION_KEYWORDS = [
    "secret", "they don't want you to know", "cover up", "banned", "censored",
    "mainstream media won't tell", "wake up", "sheeple", "plandemic", "hoax",
    "fake news", "deep state", "conspiracy", "suppressed", "hidden truth",
    "100% cure", "miracle", "doctors hate", "big pharma", "government hiding",
]

CREDIBILITY_SIGNALS = [
    "study shows", "research found", "scientists say", "according to",
    "official report", "peer reviewed", "published in", "data shows",
    "statistics indicate", "experts agree", "evidence suggests",
]


def classify_content(
    transcript: str,
    claim_items: List[Dict],
    forensics_report: Dict,
    osint_report: Dict,
) -> Dict[str, Any]:
    """
    Multi-signal classification → one of:
      Genuine | Likely Genuine | Misleading | Manipulated | Deepfake | Fake | Unverified
    Returns a dict with category, confidence, and signal breakdown.
    """
    signals = {}

    # Signal 1: Claim verdict distribution
    verdicts = [item["verdict"]["label"].lower() for item in claim_items]
    v_counter = Counter(verdicts)
    total_claims = len(verdicts) or 1
    false_ratio = (v_counter.get("false", 0) + v_counter.get("contradicted", 0) + v_counter.get("misleading", 0)) / total_claims
    true_ratio = (v_counter.get("true", 0) + v_counter.get("supported", 0)) / total_claims
    signals["false_claim_ratio"] = false_ratio
    signals["true_claim_ratio"] = true_ratio

    # Signal 2: Transcript keyword analysis
    transcript_lower = transcript.lower()
    misinfo_hits = sum(1 for kw in MISINFORMATION_KEYWORDS if kw in transcript_lower)
    credibility_hits = sum(1 for kw in CREDIBILITY_SIGNALS if kw in transcript_lower)
    signals["misinfo_keyword_score"] = min(misinfo_hits / 5.0, 1.0)
    signals["credibility_keyword_score"] = min(credibility_hits / 5.0, 1.0)

    # Signal 3: Forensics red flags
    red_flags = forensics_report.get("red_flag_count", 0)
    signals["forensics_red_flags"] = min(red_flags / 5.0, 1.0)

    # Signal 4: Deepfake probability from forensics
    deepfake_prob = forensics_report.get("deepfake_probability", 0.0)
    # Only a validated detector may assert synthetic media. Heuristic scores are
    # diagnostic metadata and must not become a truthfulness veto.
    is_synthetic = forensics_report.get("detector_status") == "validated" and forensics_report.get("is_synthetic", False)
    signals["deepfake_probability"] = deepfake_prob
    signals["is_synthetic"] = 1.0 if is_synthetic else 0.0

    # Signal 5: OSINT contradiction score & recycled footage
    osint_contradictions = osint_report.get("contradiction_count", 0)
    recycled_content = osint_report.get("potential_recycled_content", False) or osint_report.get("recycled_footage_detected", False)
    signals["osint_contradiction_score"] = min(osint_contradictions / 3.0, 1.0)
    signals["recycled_content"] = 1.0 if recycled_content else 0.0

    # Weighted classification score (higher = more suspicious)
    suspicion_score = (
        false_ratio * 0.35
        + signals["misinfo_keyword_score"] * 0.15
        + signals["forensics_red_flags"] * 0.20
        + signals["deepfake_probability"] * 0.20
        + signals["osint_contradiction_score"] * 0.10
        + (0.25 if recycled_content else 0.0)
    )
    credibility_bonus = (true_ratio * 0.2 + signals["credibility_keyword_score"] * 0.1)
    final_score = min(max(0.0, suspicion_score - credibility_bonus), 1.0)

    # Multi-Modal Veto & Map score to forensic category
    dm_veto = {"veto": False, "verdict": None, "reason": None}

    if is_synthetic:
        category = "Deepfake Video"
        confidence = max(0.85, 0.60 + deepfake_prob * 0.3)
        dm_veto = {
            "veto": True,
            "verdict": "Deepfake Video",
            "reason": "Data mining validated forensic synthetic speech / deepfake indicators",
        }
    elif recycled_content:
        category = "Manipulated Out of Context"
        confidence = max(0.80, 0.50 + false_ratio * 0.4)
        dm_veto = {
            "veto": True,
            "verdict": "Manipulated Out of Context",
            "reason": "Data mining identified recycled footage out-of-context pattern",
        }
    elif false_ratio >= 0.50 or final_score >= 0.60:
        category = "Deceptive Media / Debunked Content"
        confidence = 0.60 + final_score * 0.35
        dm_veto = {
            "veto": True,
            "verdict": "Fake",
            "reason": f"Data mining suspicion score ({final_score:.2f}) indicates severe misinformation density",
        }
    elif v_counter.get("false", 0) >= 2 or (v_counter.get("false", 0) >= 1 and v_counter.get("misleading", 0) >= 1):
        category = "Misinformation Pattern Detected"
        confidence = max(0.75, 0.58 + (v_counter.get("false", 0) / total_claims) * 0.35)
        dm_veto = {
            "veto": True,
            "verdict": "Fake",
            "reason": f"Systematic misinformation pattern: {v_counter.get('false', 0)} independently debunked false claims identified",
        }
    elif v_counter.get("false", 0) == 1:
        category = "Debunked False Claims"
        confidence = max(0.68, 0.55 + (1 / total_claims) * 0.30)
        dm_veto = {
            "veto": True,
            "verdict": "Misleading",
            "reason": "Verified false claim detected within media content",
        }
    elif v_counter.get("misleading", 0) >= 1 or final_score >= 0.35:
        category = "Misleading Narrative"
        confidence = max(0.65, 0.50 + final_score * 0.25)
        dm_veto = {
            "veto": True,
            "verdict": "Misleading",
            "reason": "Elevated pattern matching against deceptive / misleading narrative structures",
        }
    elif true_ratio >= 0.60 and final_score <= 0.20:
        category = "Verified Authentic Content"
        confidence = min(0.95, 0.72 + true_ratio * 0.25)
    elif true_ratio > 0 and (v_counter.get("false", 0) > 0 or v_counter.get("misleading", 0) > 0):
        category = "Mixed Veracity / Partially Misleading"
        confidence = 0.68
    elif true_ratio > 0.30 and final_score <= 0.35:
        category = "Likely Genuine Video"
        confidence = max(0.60, 0.65 - final_score)
    else:
        # Contextual label when claims lack sufficient independent verification data
        category = "Unsubstantiated Media Claims"
        confidence = 0.45

    return {
        "category": category,
        "confidence": round(min(confidence, 0.98), 3),
        "suspicion_score": round(final_score, 3),
        "dm_veto": dm_veto,
        "signals": signals,
    }


# ─── 3. Clustering ────────────────────────────────────────────────────────────

def _simple_tfidf_vector(text: str, corpus: List[str]) -> Dict[str, float]:
    """Compute a simple TF-IDF vector for text given a corpus."""
    tokens = re.findall(r'\b[a-z]{3,}\b', text.lower())
    tf = Counter(tokens)
    total_tokens = sum(tf.values()) or 1
    tf_norm = {t: c / total_tokens for t, c in tf.items()}

    n = len(corpus)
    df = defaultdict(int)
    for doc in corpus:
        doc_tokens = set(re.findall(r'\b[a-z]{3,}\b', doc.lower()))
        for t in doc_tokens:
            df[t] += 1

    vector = {}
    for term, tf_val in tf_norm.items():
        idf = math.log((n + 1) / (df[term] + 1)) + 1.0
        vector[term] = tf_val * idf
    return vector


def _cosine_similarity(v1: Dict[str, float], v2: Dict[str, float]) -> float:
    """Cosine similarity between two TF-IDF vectors."""
    keys = set(v1.keys()) & set(v2.keys())
    if not keys:
        return 0.0
    dot = sum(v1[k] * v2[k] for k in keys)
    mag1 = math.sqrt(sum(x ** 2 for x in v1.values()))
    mag2 = math.sqrt(sum(x ** 2 for x in v2.values()))
    if mag1 == 0 or mag2 == 0:
        return 0.0
    return dot / (mag1 * mag2)


def cluster_claims(claim_items: List[Dict], threshold: float = 0.35) -> Dict[str, Any]:
    """
    Group claims into topic clusters using TF-IDF cosine similarity.
    Returns cluster assignments and representative claims.
    """
    if not claim_items:
        return {"clusters": [], "cluster_count": 0}

    texts = [item["claim"].get("normalized_text", "") for item in claim_items]
    vectors = [_simple_tfidf_vector(t, texts) for t in texts]

    # Simple greedy clustering
    clusters: List[List[int]] = []
    assigned = [False] * len(texts)

    for i in range(len(texts)):
        if assigned[i]:
            continue
        cluster = [i]
        assigned[i] = True
        for j in range(i + 1, len(texts)):
            if not assigned[j]:
                sim = _cosine_similarity(vectors[i], vectors[j])
                if sim >= threshold:
                    cluster.append(j)
                    assigned[j] = True
        clusters.append(cluster)

    cluster_summaries = []
    for idx, cluster in enumerate(clusters):
        representative = texts[cluster[0]] if cluster else ""
        verdicts = [claim_items[i]["verdict"]["label"] for i in cluster]
        dominant_verdict = Counter(verdicts).most_common(1)[0][0] if verdicts else "unverifiable"
        cluster_summaries.append({
            "cluster_id": idx + 1,
            "size": len(cluster),
            "representative_claim": representative[:120],
            "dominant_verdict": dominant_verdict,
            "claim_indices": cluster,
        })

    return {
        "clusters": cluster_summaries,
        "cluster_count": len(clusters),
        "largest_cluster_size": max((c["size"] for c in cluster_summaries), default=0),
    }


# ─── 4. Outlier Detection ─────────────────────────────────────────────────────

def detect_outliers(claim_items: List[Dict]) -> Dict[str, Any]:
    """
    Detect suspicious/anomalous claims based on:
    - Confidence score outliers (unusually high or low)
    - Evidence count anomalies
    - Verdict isolation (single claim contradicting all others)
    """
    if not claim_items:
        return {"outliers": [], "outlier_count": 0, "anomaly_score": 0.0}

    confidences = [item["verdict"]["confidence"] for item in claim_items]
    evidence_counts = [len(item["verdict"].get("evidence", [])) for item in claim_items]

    if len(confidences) < 2:
        return {"outliers": [], "outlier_count": 0, "anomaly_score": 0.0}

    avg_conf = sum(confidences) / len(confidences)
    std_conf = math.sqrt(sum((c - avg_conf) ** 2 for c in confidences) / len(confidences)) or 0.1
    avg_ev = sum(evidence_counts) / len(evidence_counts)

    outliers = []
    for i, item in enumerate(claim_items):
        reasons = []
        conf = item["verdict"]["confidence"]
        ev_count = len(item["verdict"].get("evidence", []))
        z_score = abs(conf - avg_conf) / std_conf

        if z_score > 2.0:
            reasons.append(f"Confidence outlier (z-score: {z_score:.1f})")
        if ev_count == 0:
            reasons.append("No supporting evidence found")
        if ev_count > avg_ev * 2.5:
            reasons.append("Unusually high evidence volume")
        if conf < 0.35:
            reasons.append("Very low confidence — claim barely verifiable")

        # Check if this claim's verdict isolates against the majority
        all_verdicts = [x["verdict"]["label"].lower() for x in claim_items]
        majority = Counter(all_verdicts).most_common(1)[0][0]
        if item["verdict"]["label"].lower() != majority and len(claim_items) >= 3:
            reasons.append(f"Verdict isolation — differs from majority ({majority})")

        if reasons:
            outliers.append({
                "claim_index": i,
                "claim_text": item["claim"].get("normalized_text", "")[:80],
                "reasons": reasons,
                "anomaly_severity": "high" if len(reasons) >= 2 else "medium",
            })

    anomaly_score = min(len(outliers) / max(len(claim_items), 1), 1.0)
    return {
        "outliers": outliers,
        "outlier_count": len(outliers),
        "anomaly_score": round(anomaly_score, 3),
        "avg_confidence": round(avg_conf, 3),
        "std_confidence": round(std_conf, 3),
    }


# ─── 5. Association Rules ─────────────────────────────────────────────────────

def mine_association_rules(claim_items: List[Dict]) -> Dict[str, Any]:
    """
    Find associations between claim verdicts and evidence patterns.
    Uses simplified confidence-support mining (Apriori-inspired).
    """
    rules = []

    if len(claim_items) < 2:
        return {"rules": rules, "strong_rules": []}

    # Build item sets from verdicts + evidence domain patterns
    all_labels = [item["verdict"]["label"].lower() for item in claim_items]
    all_domains = []
    for item in claim_items:
        for ev in item["verdict"].get("evidence", []):
            domain = ev.get("domain", "").split(".")[-2] if "." in ev.get("domain", "") else ev.get("domain", "")
            if domain:
                all_domains.append(domain)

    verdict_counter = Counter(all_labels)
    domain_counter = Counter(all_domains)

    n = len(claim_items)
    for label, count in verdict_counter.items():
        support = count / n
        if support >= 0.2:
            rules.append({
                "antecedent": f"claim_verdict={label}",
                "consequent": "high_suspicion" if label in ("false", "misleading") else "low_risk",
                "support": round(support, 3),
                "confidence": round(min(0.5 + support * 0.4, 0.95), 3),
                "lift": round(1.0 + support, 3),
            })

    # Domain authority association
    for domain, count in domain_counter.most_common(3):
        if count >= 1:
            rules.append({
                "antecedent": f"source_domain={domain}",
                "consequent": "domain_credibility_signal",
                "support": round(count / max(len(all_domains), 1), 3),
                "confidence": 0.75,
                "lift": 1.2,
            })

    strong_rules = [r for r in rules if r["confidence"] >= 0.7 and r["support"] >= 0.25]
    return {
        "rules": rules,
        "strong_rules": strong_rules,
        "total_rules": len(rules),
    }


# ─── 6. Pattern Mining ────────────────────────────────────────────────────────

def mine_patterns(transcript: str, claim_items: List[Dict]) -> Dict[str, Any]:
    """
    Detect thematic and linguistic patterns:
    - High-frequency misinformation phrases
    - Emotional language intensity
    - Temporal inconsistency markers
    - Hedging language (reduces claim credibility)
    """
    patterns_found = []

    text_lower = transcript.lower()

    # Emotional intensifiers (often signal sensationalism)
    emotional_words = ["shocking", "devastating", "incredible", "unbelievable", "outrageous",
                       "explosive", "bombshell", "breaking", "urgent", "alert", "danger"]
    emotion_hits = [w for w in emotional_words if w in text_lower]
    if emotion_hits:
        patterns_found.append({
            "pattern": "Emotional Intensifiers",
            "type": "linguistic",
            "indicators": emotion_hits[:5],
            "severity": "medium" if len(emotion_hits) < 4 else "high",
            "description": "High emotional language detected — may indicate sensationalism or manufactured urgency.",
        })

    # Hedging language (reduces credibility of strong claims)
    hedging_words = ["allegedly", "reportedly", "sources say", "rumored", "unconfirmed",
                     "some believe", "it is said", "people are saying", "i heard"]
    hedge_hits = [w for w in hedging_words if w in text_lower]
    if hedge_hits:
        patterns_found.append({
            "pattern": "Hedging Language",
            "type": "linguistic",
            "indicators": hedge_hits[:5],
            "severity": "low",
            "description": "Speculative language found — claims may lack direct sourcing.",
        })

    # Absolute claims (often red flags)
    absolute_words = ["always", "never", "everyone knows", "nobody talks about",
                      "the only", "100%", "proven fact", "guaranteed"]
    abs_hits = [w for w in absolute_words if w in text_lower]
    if abs_hits:
        patterns_found.append({
            "pattern": "Absolute Claims",
            "type": "factual",
            "indicators": abs_hits[:5],
            "severity": "medium",
            "description": "Absolute / universal claims detected — these are rarely accurate and often indicate overstatement.",
        })

    # Cross-claim consistency check
    false_claims = [i["claim"].get("normalized_text", "")[:60] for i in claim_items if i["verdict"]["label"].lower() == "false"]
    if len(false_claims) >= 2:
        patterns_found.append({
            "pattern": "Multiple False Claims",
            "type": "credibility",
            "indicators": false_claims[:3],
            "severity": "high",
            "description": f"{len(false_claims)} independently verified false claims detected — systematic misinformation pattern.",
        })

    return {
        "patterns": patterns_found,
        "pattern_count": len(patterns_found),
        "high_severity_patterns": sum(1 for p in patterns_found if p["severity"] == "high"),
        "linguistic_risk_score": round(min(len(patterns_found) / 4.0, 1.0), 3),
    }


# ─── 7. Similarity Analysis ───────────────────────────────────────────────────

KNOWN_MISINFO_TEMPLATES = [
    "this cure was suppressed by doctors",
    "the government is hiding this",
    "you won't see this in mainstream media",
    "they are poisoning us with",
    "this video will be deleted soon",
    "share before it's removed",
    "wake up people",
    "the truth about",
    "what they don't want you to know",
    "secret exposed",
]


def similarity_analysis(transcript: str, claim_items: List[Dict]) -> Dict[str, Any]:
    """
    Fuzzy-match transcript against known misinformation template patterns.
    Uses simple word-overlap similarity (Jaccard index).
    """
    transcript_tokens = set(re.findall(r'\b[a-z]{4,}\b', transcript.lower()))
    matches = []

    for template in KNOWN_MISINFO_TEMPLATES:
        template_tokens = set(re.findall(r'\b[a-z]{4,}\b', template.lower()))
        intersection = transcript_tokens & template_tokens
        union = transcript_tokens | template_tokens
        jaccard = len(intersection) / len(union) if union else 0
        if jaccard >= 0.08 or any(t in transcript.lower() for t in template.split() if len(t) > 4):
            exact_match = template.lower() in transcript.lower()
            matches.append({
                "template": template,
                "similarity_score": round(max(jaccard, 0.2 if exact_match else 0.0), 3),
                "exact_match": exact_match,
                "match_type": "exact" if exact_match else "fuzzy",
            })

    # Also check individual claim similarity
    claim_matches = []
    for item in claim_items:
        text = item["claim"].get("normalized_text", "").lower()
        for template in KNOWN_MISINFO_TEMPLATES:
            if any(word in text for word in template.split() if len(word) > 4):
                claim_matches.append({
                    "claim": text[:80],
                    "matching_template": template,
                })

    max_sim = max((m["similarity_score"] for m in matches), default=0.0)
    return {
        "template_matches": matches,
        "claim_pattern_matches": claim_matches[:5],
        "total_matches": len(matches),
        "max_similarity": round(max_sim, 3),
        "misinfo_pattern_score": round(min(len(matches) / 3.0, 1.0), 3),
    }


# ─── Master DM Orchestrator ───────────────────────────────────────────────────

def run_data_mining_pipeline(
    transcript: str,
    claim_items: List[Dict],
    forensics_report: Dict,
    osint_report: Dict,
) -> Dict[str, Any]:
    """
    Run the full Data Mining pipeline and return a comprehensive DM report.
    Actively re-weights and calibrates claim confidences based on outlier detection,
    misinformation template matches, and pattern mining signals.
    """
    # 1. Data cleaning
    for item in claim_items:
        if "verdict" in item and "evidence" in item["verdict"]:
            item["verdict"]["evidence"] = clean_evidence_items(item["verdict"]["evidence"])
    claim_items = normalize_claim_scores(claim_items)

    # 2. Classification
    classification = classify_content(transcript, claim_items, forensics_report, osint_report)

    # 3. Clustering
    clustering = cluster_claims(claim_items)

    # 4. Outlier detection
    outliers = detect_outliers(claim_items)

    # 5. Association rules
    associations = mine_association_rules(claim_items)

    # 6. Pattern mining
    patterns = mine_patterns(transcript, claim_items)

    # 7. Similarity analysis
    similarity = similarity_analysis(transcript, claim_items)

    # ── Active Claim Calibration & Re-weighting ──
    calibrated_claims_count = 0
    outlier_indices = {o["claim_index"]: o for o in outliers.get("outliers", [])}
    template_claim_texts = {m.get("claim", "").lower() for m in similarity.get("claim_pattern_matches", [])}

    for idx, item in enumerate(claim_items):
        if "verdict" not in item:
            continue
        conf = item["verdict"].get("confidence", 0.70)
        c_text = item.get("claim", {}).get("normalized_text", "").lower()
        penalty = 0.0

        # Misinformation template penalty
        if any(t in c_text for t in template_claim_texts) or similarity.get("misinfo_pattern_score", 0.0) >= 0.5:
            penalty += 0.20

        # Outlier isolation penalty
        if idx in outlier_indices:
            out_info = outlier_indices[idx]
            is_high = out_info.get("anomaly_severity") == "high"
            penalty += 0.25 if is_high else 0.15
            item["verdict"]["outlier_flag"] = True
            item["verdict"]["outlier_reasons"] = out_info.get("reasons", [])

        # Emotional intensifier discount on unverified / true claims
        if patterns.get("high_severity_patterns", 0) > 0 and item["verdict"]["label"].lower() in ("true", "likely true"):
            penalty += 0.10

        if penalty > 0:
            new_conf = max(0.20, min(0.99, round(conf * (1.0 - penalty), 3)))
            item["verdict"]["confidence"] = new_conf
            item["verdict"]["dm_calibrated"] = True
            calibrated_claims_count += 1

    # Compute DM confidence score (0–100)
    suspicion = classification["suspicion_score"]
    misinfo_pat = similarity["misinfo_pattern_score"]
    anomaly = outliers["anomaly_score"]
    high_severity_patterns = patterns["high_severity_patterns"]

    dm_risk = (suspicion * 0.4 + misinfo_pat * 0.25 + anomaly * 0.2 + min(high_severity_patterns / 3.0, 1.0) * 0.15)
    dm_score = round(max(15.0, min(95.0, (1 - dm_risk) * 100)), 1)

    return {
        "dm_score": dm_score,
        "classification": classification,
        "clustering": clustering,
        "outlier_detection": outliers,
        "association_rules": associations,
        "pattern_mining": patterns,
        "similarity_analysis": similarity,
        "dm_veto": classification.get("dm_veto", {"veto": False}),
        "calibrated_claims_count": calibrated_claims_count,
        "summary": (
            f"Data Mining analysis complete: {clustering['cluster_count']} claim clusters identified, "
            f"{outliers['outlier_count']} anomalies detected, "
            f"{patterns['pattern_count']} linguistic patterns found, "
            f"{calibrated_claims_count} claims calibrated. "
            f"Classification: {classification['category']} "
            f"(confidence {int(classification['confidence'] * 100)}%)."
            + (f" ⚠️ [VETO] {classification['dm_veto']['reason']}" if classification.get("dm_veto", {}).get("veto") else "")
        ),
    }
