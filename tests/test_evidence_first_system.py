"""
Unit & Integration Tests for TruthLens AI Evidence-First Fact-Checking Engine:
- 3-Verdict taxonomy (TRUE, FALSE, MISLEADING)
- Epistemic handling of insufficient evidence (fail-safe to MISLEADING with explicit unverified explanation)
- SSRF-safe URL fetching and verbatim quote verification
- Canonical verification records & deterministic SHA-256 reproducibility
- Atomic claim decomposition and aggregation
"""

import pytest
from shared.schemas.verdict import VerdictLabel, Evidence, Verdict, AtomicClaimAssessment
from pipeline.page_fetcher import (
    is_safe_url,
    verify_and_locate_quote,
    _SimpleHTMLTextExtractor,
)
from pipeline.canonical_record import (
    compute_canonical_hash,
    CanonicalVerificationRecord,
    explain_verdict_drift,
)
from backend.services.job_service import decompose_compound_claim, compute_overall_verdict


# ─── 1. VERDICT TAXONOMY ─────────────────────────────────────────────────────

def test_verdict_taxonomy_strictly_three_labels():
    """Verify that only true, false, and misleading exist in VerdictLabel."""
    valid_values = {v.value for v in VerdictLabel}
    assert valid_values == {"true", "false", "misleading"}


def test_verdict_taxonomy_normalizes_legacy_labels():
    """Verify _missing_ maps legacy labels to the canonical 3-verdict taxonomy."""
    assert VerdictLabel("supported") == VerdictLabel.TRUE
    assert VerdictLabel("true") == VerdictLabel.TRUE
    assert VerdictLabel("refuted") == VerdictLabel.FALSE
    assert VerdictLabel("debunked") == VerdictLabel.FALSE
    assert VerdictLabel("false") == VerdictLabel.FALSE
    assert VerdictLabel("unverified") == VerdictLabel.MISLEADING
    assert VerdictLabel("unverifiable") == VerdictLabel.MISLEADING
    assert VerdictLabel("ambiguous") == VerdictLabel.MISLEADING
    assert VerdictLabel("misleading") == VerdictLabel.MISLEADING


# ─── 2. SSRF SAFEGUARD & TEXT EXTRACTION ─────────────────────────────────────

def test_ssrf_safety_blocks_private_and_local_networks():
    """Test that is_safe_url aggressively blocks SSRF vectors."""
    # Loopback
    assert is_safe_url("http://127.0.0.1/admin") is False
    assert is_safe_url("http://localhost:8000/") is False
    assert is_safe_url("http://[::1]/status") is False
    # Cloud metadata
    assert is_safe_url("http://169.254.169.254/latest/meta-data/") is False
    assert is_safe_url("http://metadata.google.internal/computeMetadata/v1/") is False
    # Private CIDRs
    assert is_safe_url("http://10.0.0.1/internal") is False
    assert is_safe_url("http://172.16.5.10/api") is False
    assert is_safe_url("http://192.168.1.1/router") is False
    # Invalid schemes
    assert is_safe_url("file:///etc/passwd") is False
    assert is_safe_url("ftp://ftp.example.com/file") is False
    # Safe public URLs
    assert is_safe_url("https://www.who.int/emergencies") is True
    assert is_safe_url("https://webbook.nist.gov/chemistry/fluid/") is True


def test_html_text_extractor_strips_scripts_and_styles():
    html_doc = """
    <html>
      <head><title>Scientific Report</title><style>.hidden { display: none; }</style></head>
      <body>
        <script>console.log("secret token");</script>
        <h1>Climate Findings</h1>
        <p>Global atmospheric CO2 concentrations exceeded 420 ppm in 2024.</p>
      </body>
    </html>
    """
    extractor = _SimpleHTMLTextExtractor()
    extractor.feed(html_doc)
    text = extractor.get_text()
    assert "console.log" not in text
    assert ".hidden" not in text
    assert "Global atmospheric CO2 concentrations exceeded 420 ppm in 2024." in text


def test_verify_and_locate_quote():
    page_text = (
        "The Intergovernmental Panel on Climate Change (IPCC) sixth assessment report affirms that "
        "human activities have unequivocally caused global warming. Observed warming since 1850 is "
        "predominantly driven by greenhouse gas emissions."
    )
    # Verbatim substring match
    verbatim = "human activities have unequivocally caused global warming"
    is_valid, quote, loc = verify_and_locate_quote(page_text, verbatim)
    assert is_valid is True
    assert verbatim in quote
    assert "Paragraph 1" in loc

    # Fabricated / hallucinated quote not present in source text
    fake_quote = "IPCC proves that volcanoes emit 100 times more CO2 than automobiles."
    is_valid, quote, loc = verify_and_locate_quote(page_text, fake_quote)
    assert is_valid is False
    assert "paraphrased" in loc.lower()


# ─── 3. CANONICAL RECORD & REPRODUCIBILITY ───────────────────────────────────

def test_canonical_hash_is_deterministic():
    claim_a = "Water boils at 100 degrees Celsius at sea level."
    claim_b = "  WATER boils at 100 degrees celsius at sea level.  "
    hash_a = compute_canonical_hash(claim_a, context="Physics standard")
    hash_b = compute_canonical_hash(claim_b, context="Physics standard")
    assert hash_a == hash_b
    assert len(hash_a) == 64


def test_verdict_drift_explanation():
    rec = {
        "canonical_hash": "abc12345",
        "original_wording": "Test claim",
        "normalized_claim": "test claim",
        "final_verdict": "misleading",
        "confidence": 0.40,
        "consensus_score": 0.0,
        "reasoning": "Unverified due to zero retrieved sources.",
        "summary": "Unverified summary",
        "evidence": [],
    }
    explanation = explain_verdict_drift(
        rec,
        new_verdict="true",
        new_evidence=[{"source_url": "https://example.com/1"}],
    )
    assert "updated from MISLEADING to TRUE" in explanation
    assert "1 new sources were retrieved" in explanation


# ─── 4. ATOMIC CLAIM DECOMPOSITION & AGGREGATION ─────────────────────────────

def test_compound_claim_decomposition():
    compound = "The Earth is flat and the Apollo 11 Moon landing was completely staged in a Hollywood studio."
    atoms = decompose_compound_claim(compound)
    assert len(atoms) >= 2
    assert any("flat" in a.lower() for a in atoms)
    assert any("moon landing" in a.lower() for a in atoms)


def test_atomic_claim_verdict_rollup():
    """If one atomic sub-claim is False and another is True, overall verdict must be Misleading."""
    verdicts = [
        {"verdict": {"label": "true", "confidence": 0.90}},
        {"verdict": {"label": "false", "confidence": 0.88}},
    ]
    res = compute_overall_verdict(verdicts)
    assert res["overall_verdict"].startswith("Misleading")
    assert res["verdict_breakdown"]["true"] == 1
    assert res["verdict_breakdown"]["false"] == 1
    assert res["verdict_breakdown"]["misleading"] == 0
