"""
run_labeled_benchmark.py — Comprehensive Empirical Evaluation Runner
====================================================================
Evaluates the TruthLens AI pipeline on the 100-case labeled benchmark dataset:
  1. Stance Classification Accuracy & Confusion Matrix (supports, contradicts, partial, irrelevant, insufficient)
  2. Evidence Relevance & Topic-Trap Rejection (False Positive Rate on irrelevant passages)
  3. Source Traceability & Deduplication Fingerprinting
  4. Claim Verdict Aggregation (True, False, Misleading, Unverified)
  5. Safe Handling of Missing Evidence / API Failures (fail-closed to UNVERIFIED)
  6. Confidence Calibration: Expected Calibration Error (ECE) and Brier Score
"""

import json
import os
import sys
from typing import Dict, List, Any, Tuple
from collections import defaultdict, Counter

# Ensure root directory is in sys.path
ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from pipeline.evidence_classifier import (
    EvidenceStance,
    classify_passage_stance,
    classify_evidence_items,
    compute_consensus_and_metrics,
    compute_calibrated_confidence,
    compute_content_fingerprint,
    check_domain_independence,
    detect_topic_trap,
)
import argparse
from pipeline.search import _canonical_verdict_label, _keyword_verdict_from_evidence, _run_llm_reasoning


def normalize_stance_name(stance_val: Any) -> str:
    """Normalize enum or string stance names to canonical evaluation labels."""
    if isinstance(stance_val, EvidenceStance):
        stance_str = stance_val.value
    else:
        stance_str = str(stance_val or "").lower()
    
    mapping = {
        "supports": "supports",
        "contradicts": "contradicts",
        "partially_supports": "partial",
        "mixed": "partial",
        "neutral": "insufficient",
        "unrelated": "irrelevant",
        "irrelevant": "irrelevant",
        "insufficient": "insufficient",
    }
    return mapping.get(stance_str, "insufficient")


def calculate_ece(confidences: List[float], correct_flags: List[bool], n_bins: int = 5) -> float:
    """Calculate Expected Calibration Error (ECE)."""
    if not confidences:
        return 0.0
    
    bin_size = 1.0 / n_bins
    total_samples = len(confidences)
    ece = 0.0
    
    for i in range(n_bins):
        bin_lower = i * bin_size
        bin_upper = (i + 1) * bin_size
        # Indices in this bin
        bin_indices = [
            idx for idx, c in enumerate(confidences)
            if (bin_lower <= c < bin_upper) or (i == n_bins - 1 and bin_lower <= c <= bin_upper)
        ]
        
        if not bin_indices:
            continue
        
        bin_acc = sum(1 for idx in bin_indices if correct_flags[idx]) / len(bin_indices)
        bin_conf = sum(confidences[idx] for idx in bin_indices) / len(bin_indices)
        weight = len(bin_indices) / total_samples
        ece += weight * abs(bin_acc - bin_conf)
        
    return round(ece, 4)


def calculate_brier_score(confidences: List[float], correct_flags: List[bool]) -> float:
    """Calculate Brier Score for confidence estimates."""
    if not confidences:
        return 0.0
    squared_errors = [((c - (1.0 if corr else 0.0)) ** 2) for c, corr in zip(confidences, correct_flags)]
    return round(sum(squared_errors) / len(squared_errors), 4)


def run_benchmark(mode: str = "heuristic"):
    dataset_path = os.path.join(ROOT_DIR, "tests", "data", "labeled_benchmark_100.json")
    if not os.path.exists(dataset_path):
        raise FileNotFoundError(f"Benchmark dataset not found at {dataset_path}")
        
    with open(dataset_path, "r", encoding="utf-8") as f:
        data = json.load(f)
        
    cases = data["cases"]
    total_cases = len(cases)
    print(f"\n=======================================================")
    print(f"  TruthLens AI — Labeled Evaluation Benchmark Runner")
    print(f"  Dataset: {data.get('dataset_name')} ({total_cases} cases)")
    print(f"  Execution Mode: {mode.upper()} ({'Live LLM Pipeline' if mode == 'llm' else 'Deterministic Offline Fallback'})")
    print(f"=======================================================\n")
    
    # ── Evaluation 1: Stance Classification & Relevance ──
    total_passages = 0
    stance_correct = 0
    confusion_matrix = defaultdict(lambda: defaultdict(int))
    irrelevant_tested = 0
    irrelevant_false_positives = 0
    
    for case in cases:
        claim_text = case["claim"]
        for p in case.get("passages", []):
            total_passages += 1
            expected = normalize_stance_name(p["expected_stance"])
            
            # Run classifier
            pred_stance, rel_score, expl = classify_passage_stance(
                claim_text=claim_text,
                title=p.get("title", ""),
                snippet=p.get("snippet", ""),
                url=p.get("url", ""),
                relevance_score=0.5,
            )
            pred = normalize_stance_name(pred_stance)
            confusion_matrix[expected][pred] += 1
            
            if expected == pred:
                stance_correct += 1
                
            if expected == "irrelevant":
                irrelevant_tested += 1
                if pred in ("supports", "contradicts"):
                    irrelevant_false_positives += 1
                    print(f"[RELEVANCE LEAK] Case {case['id']} '{claim_text[:40]}...' Passage: '{p['snippet'][:50]}...' Expected: irrelevant, Got: {pred}")
                    
    stance_acc = round(stance_correct / max(1, total_passages), 4)
    irrelevant_fpr = round(irrelevant_false_positives / max(1, irrelevant_tested), 4)
    
    # ── Evaluation 2: Verdict Aggregation, Confidence, and Missing Evidence Safety ──
    verdict_correct = 0
    total_claims_tested = 0
    missing_evidence_tested = 0
    missing_evidence_safe = 0
    
    verdicts_gt: List[str] = []
    verdicts_pred: List[str] = []
    confidences: List[float] = []
    correct_flags: List[bool] = []
    
    category_metrics = defaultdict(lambda: {"total": 0, "correct": 0})
    verdict_confusion = defaultdict(lambda: defaultdict(int))
    failed_cases = []
    
    for case in cases:
        total_claims_tested += 1
        claim_text = case["claim"]
        gt_verdict = _canonical_verdict_label(case["ground_truth_label"])
        cat = case.get("category", "general")
        passages = case.get("passages", [])
        
        # Build raw evidence objects from passages
        raw_evidence = [
            {
                "source_url": p.get("url", f"https://example.com/{idx}"),
                "source_title": p.get("title", "Evidence Source"),
                "snippet": p.get("snippet", ""),
                "domain": p.get("domain", "example.com"),
                "relevance_score": 0.5,
            }
            for idx, p in enumerate(passages)
        ]
        
        # Test missing evidence safety
        if not raw_evidence:
            missing_evidence_tested += 1
            
        # Run verdict aggregation using selected engine (live LLM or deterministic offline heuristic)
        if mode == "llm":
            try:
                v_res = _run_llm_reasoning(claim_text, claim_text, "", raw_evidence)
            except Exception as e:
                v_res = {"label": "unverified", "confidence": 0.20, "reasoning": str(e)}
        else:
            v_res = _keyword_verdict_from_evidence(
                claim=claim_text,
                english_claim_or_evidence=claim_text,
                web_evidence=raw_evidence,
                error_msg="Benchmark evaluation over controlled evidence",
            )
        pred_label = _canonical_verdict_label(v_res.get("label", "unverified"))
        pred_conf = float(v_res.get("confidence", 0.5))
        
        is_match = (pred_label == gt_verdict)
        verdicts_gt.append(gt_verdict)
        verdicts_pred.append(pred_label)
        confidences.append(pred_conf)
        correct_flags.append(is_match)
        
        verdict_confusion[gt_verdict][pred_label] += 1
        category_metrics[cat]["total"] += 1
        if is_match:
            verdict_correct += 1
            category_metrics[cat]["correct"] += 1
        else:
            failed_cases.append({
                "id": case["id"],
                "claim": claim_text,
                "category": cat,
                "ground_truth": gt_verdict,
                "predicted": pred_label,
                "confidence": pred_conf,
                "evidence_count": len(passages),
            })
            
        if not raw_evidence:
            reasoning_text = v_res.get("reasoning", "").lower()
            is_safe = (pred_label in ("misleading", "unverified")) and (
                "unverified" in reasoning_text or "insufficient" in reasoning_text or v_res.get("unverified", False)
            )
            if is_safe:
                missing_evidence_safe += 1
            else:
                print(f"[SAFETY VIOLATION] Case {case['id']} had 0 evidence but verdict was '{pred_label}' without explicit unverified explanation!")
                
    verdict_acc = round(verdict_correct / max(1, total_claims_tested), 4)
    missing_evidence_safety_rate = round(missing_evidence_safe / max(1, missing_evidence_tested), 4) if missing_evidence_tested else 1.0
    ece_score = calculate_ece(confidences, correct_flags, n_bins=5)
    brier_score = calculate_brier_score(confidences, correct_flags)
    
    # ── Evaluation 3: Source Independence & Deduplication ──
    fp1 = compute_content_fingerprint("Reuters Wire: Market Drops", "Wall Street tumbled today amid inflation fears.")
    fp2 = compute_content_fingerprint("Yahoo Finance: Market Drops", "Wall Street tumbled today amid inflation fears.")
    fp_indep, _ = check_domain_independence("https://yahoo.com/1", "Yahoo Finance", "Wall Street tumbled today amid inflation fears.", {fp1: "reuters.com"})
    dedup_works = (fp1 == fp2) and (fp_indep is False)

    # ── Print Detailed Benchmark Results ──
    print(f"\n=======================================================")
    print(f"                   BENCHMARK RESULTS                   ")
    print(f"=======================================================")
    print(f"1. Stance Classification & Relevance Gate:")
    print(f"   - Total Labeled Passages Evaluated : {total_passages}")
    print(f"   - Stance Accuracy                  : {stance_acc * 100:.2f}% ({stance_correct}/{total_passages})")
    print(f"   - Irrelevant Topic-Trap FPR        : {irrelevant_fpr * 100:.2f}% ({irrelevant_false_positives}/{irrelevant_tested})")
    
    print(f"\n2. Verdict Aggregation & Epistemic Correctness:")
    print(f"   - Overall Claim Verdict Accuracy   : {verdict_acc * 100:.2f}% ({verdict_correct}/{total_claims_tested})")
    print(f"   - Missing Evidence Fail-Safe Rate  : {missing_evidence_safety_rate * 100:.2f}% ({missing_evidence_safe}/{missing_evidence_tested})")
    
    print(f"\n3. Confidence Calibration:")
    print(f"   - Expected Calibration Error (ECE) : {ece_score}")
    print(f"   - Brier Score                      : {brier_score}")
    
    print(f"\n4. Source Traceability & Deduplication:")
    print(f"   - Wire Fingerprint Matching Works  : {dedup_works}")
    
    print(f"\n5. Performance by Domain Category:")
    for cat, cdata in sorted(category_metrics.items()):
        c_acc = (cdata["correct"] / cdata["total"]) * 100 if cdata["total"] else 0
        print(f"   - {cat:<24}: {c_acc:5.1f}% ({cdata['correct']}/{cdata['total']})")
        
    print(f"\n6. Verdict Confusion Matrix (Row: Ground Truth, Col: Predicted):")
    all_labels = ["true", "false", "misleading", "unverified"]
    header = "             " + "".join(f"{lbl:>12}" for lbl in all_labels)
    print(header)
    for row in all_labels:
        row_str = f"{row:<12} " + "".join(f"{verdict_confusion[row][col]:>12}" for col in all_labels)
        print(row_str)
        
    print(f"\n7. Failures Summary ({len(failed_cases)} cases):")
    for fcase in failed_cases[:10]:
        print(f"   - Case {fcase['id']}: GT={fcase['ground_truth']} vs Pred={fcase['predicted']} | Claim: {fcase['claim'][:70]}")
    if len(failed_cases) > 10:
        print(f"   ... and {len(failed_cases) - 10} more failures.")
        
    # Save benchmark report to JSON
    report = {
        "dataset_name": data.get("dataset_name"),
        "total_cases": total_claims_tested,
        "total_passages": total_passages,
        "stance_accuracy": stance_acc,
        "irrelevant_false_positive_rate": irrelevant_fpr,
        "verdict_accuracy": verdict_acc,
        "missing_evidence_safety_rate": missing_evidence_safety_rate,
        "expected_calibration_error": ece_score,
        "brier_score": brier_score,
        "dedup_works": dedup_works,
        "category_metrics": dict(category_metrics),
        "verdict_confusion": {k: dict(v) for k, v in verdict_confusion.items()},
        "failed_cases_count": len(failed_cases),
        "failed_cases": failed_cases,
    }
    
    out_path = os.path.join(ROOT_DIR, "tests", "data", f"benchmark_evaluation_results_{mode}.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)
    canonical_path = os.path.join(ROOT_DIR, "tests", "data", "benchmark_evaluation_results.json")
    with open(canonical_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)
    print(f"\nSaved detailed benchmark metrics to: {out_path}\n")
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="TruthLens AI Labeled Benchmark Runner")
    parser.add_argument(
        "--mode",
        choices=["heuristic", "llm"],
        default="heuristic",
        help="Evaluation mode: heuristic (offline rule-based) or llm (live LLM reasoning)",
    )
    args = parser.parse_args()
    run_benchmark(mode=args.mode)
