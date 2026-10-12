import pytest
import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.services.job_service import compute_overall_verdict, fuse_scores
from backend.services.forensics import analyze_deepfake_heuristics, run_forensics_pipeline, analyze_audio_stream
from backend.services.osint import build_reverse_search_queries, run_osint_pipeline
from backend.services.data_mining import classify_content, run_data_mining_pipeline


def test_forensics_deepfake_veto():
    """Verify that forensics synthetic speech/deepfake veto overrides true claims."""
    claim_items = [
        {"claim": {"normalized_text": "The earth revolves around the sun."}, "verdict": {"label": "true", "confidence": 0.95}},
        {"claim": {"normalized_text": "Water boils at 100 degrees Celsius."}, "verdict": {"label": "true", "confidence": 0.95}},
    ]
    forensics_report = {
        "deepfake_probability": 0.72,
        "voice_clone_probability": 0.65,
        "is_synthetic": True,
        "forensics_veto": {"veto": True, "verdict": "Deepfake", "reason": "Synthetic cloned voice detected"},
    }
    result = compute_overall_verdict(claim_items, forensics_report=forensics_report)
    assert result["final_verdict_category"] == "Deepfake"
    assert "Deepfake" in result["overall_verdict"]
    assert result["verdict_breakdown"]["veto_applied"]["type"] == "forensics_synthetic_veto"


def test_osint_recycled_footage_veto():
    """Verify that OSINT recycled footage veto marks video Manipulated even if facts are real."""
    claim_items = [
        {"claim": {"normalized_text": "A massive flood inundated the bridge."}, "verdict": {"label": "true", "confidence": 0.90}},
    ]
    osint_report = {
        "recycled_footage_detected": True,
        "potential_recycled_content": True,
        "old_video_reuse_signals": ["Match [from 2018] in: Old footage from 2018 reused"],
        "osint_veto": {"veto": True, "verdict": "Manipulated", "reason": "Historical footage from 2018 reused"},
    }
    result = compute_overall_verdict(claim_items, osint_report=osint_report)
    assert result["final_verdict_category"] == "Manipulated"
    assert "Recycled Footage Out of Context" in result["overall_verdict"]
    assert result["verdict_breakdown"]["veto_applied"]["type"] == "osint_recycled_footage_veto"


def test_osint_google_factcheck_debunk_veto():
    """Verify that Google Fact Check certified debunks force Fake category."""
    claim_items = [
        {"claim": {"normalized_text": "A secret cure has been discovered."}, "verdict": {"label": "unverifiable", "confidence": 0.50}},
    ]
    osint_report = {
        "google_factcheck": {
            "debunked_count": 2,
            "manipulated_count": 0,
            "total_reviews": 2,
        },
        "osint_veto": {"veto": True, "verdict": "Fake", "reason": "Debunked by certified fact-checkers"},
    }
    result = compute_overall_verdict(claim_items, osint_report=osint_report)
    assert result["final_verdict_category"] == "Fake"
    assert result["verdict_breakdown"]["veto_applied"]["type"] == "osint_google_factcheck_veto"


def test_data_mining_governor_veto():
    """Verify that high data mining suspicion score vetoes Genuine ratings."""
    claim_items = [
        {"claim": {"normalized_text": "Doctors are hiding this cure."}, "verdict": {"label": "true", "confidence": 0.80}},
    ]
    dm_report = {
        "classification": {"category": "Fake", "confidence": 0.85, "suspicion_score": 0.75},
        "dm_veto": {"veto": True, "verdict": "Fake", "reason": "Systematic misinformation signals exceed threshold"},
    }
    result = compute_overall_verdict(claim_items, dm_report=dm_report)
    assert result["final_verdict_category"] == "Fake"
    assert result["verdict_breakdown"]["veto_applied"]["type"] == "dm_active_governor_veto"


def test_fuse_scores_penalizes_contradictions():
    """Verify that score fusion dampens confidence when contradictions or red flags are high."""
    clean_scores = fuse_scores(
        forensics_report={"video_integrity_score": 85.0, "audio_integrity_score": 85.0, "metadata_integrity_score": 90.0, "red_flag_count": 0},
        osint_report={"osint_score": 80.0, "contradiction_count": 0},
        dm_report={"dm_score": 80.0},
        claim_items=[{"verdict": {"label": "true"}}],
    )
    
    contradicted_scores = fuse_scores(
        forensics_report={"video_integrity_score": 85.0, "audio_integrity_score": 85.0, "metadata_integrity_score": 90.0, "red_flag_count": 3},
        osint_report={"osint_score": 80.0, "contradiction_count": 4},
        dm_report={"dm_score": 80.0},
        claim_items=[{"verdict": {"label": "true"}}],
    )

    assert clean_scores["overall_confidence"] > contradicted_scores["overall_confidence"]


def test_data_mining_active_claim_calibration():
    """Verify that data mining pipeline re-weights claims matching misinformation templates."""
    claim_items = [
        {"claim": {"normalized_text": "Doctors are hiding this miracle cure from you."}, "verdict": {"label": "true", "confidence": 0.90, "evidence": []}},
    ]
    dm_report = run_data_mining_pipeline(
        transcript="Doctors are hiding this miracle cure from you in secret. Share before deleted.",
        claim_items=claim_items,
        forensics_report={},
        osint_report={},
    )
    assert dm_report["calibrated_claims_count"] >= 1
    # Confidence should be penalized
    assert claim_items[0]["verdict"]["confidence"] < 0.90
    assert claim_items[0]["verdict"].get("dm_calibrated") is True


def test_forensics_audio_stream_analysis_empty_path():
    """Ensure analyze_audio_stream handles empty/missing audio cleanly without crash."""
    res = analyze_audio_stream(None)
    assert res["audio_stream_available"] is False
    assert res["technical_anomaly_score"] == 0.0


def test_demo_cases_structure_and_export():
    """Ensure all pre-built demo cases and markdown dossier exports are complete and valid."""
    from backend.services.demo_cases import DEMO_CASES
    from backend.services.export_service import generate_markdown_dossier
    assert len(DEMO_CASES) == 3
    for case_id, case in DEMO_CASES.items():
        assert case["id"].startswith("demo-")
        assert len(case["claims"]) >= 1
        assert "overall_verdict" in case
        assert "forensics" in case
        assert "osint" in case
        assert "dm_report" in case
        md = generate_markdown_dossier(
            job_id=case["id"],
            video_url=case["video_url"],
            overall_verdict=case["overall_verdict"],
            category=case["final_verdict_category"],
            confidence=case["overall_confidence"],
            breakdown=case["verdict_breakdown"],
            claims=case["claims"],
            forensics=case["forensics"],
            osint=case["osint"],
            dm_report=case["dm_report"],
        )
        assert "TruthLens AI" in md
        assert "SHA256-" in md
        assert case["overall_verdict"] in md

