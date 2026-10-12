from types import SimpleNamespace

from backend.main import build_claim_verdicts_for_segments
from pipeline.domain_trust import get_domain_trust_tier


def test_build_claim_verdicts_splits_compound_claims():
    segments = [
        SimpleNamespace(text="The sky is blue and the grass is green.", start=0.0, end=3.0),
    ]

    results = build_claim_verdicts_for_segments(
        video_url="https://example.com/video",
        segments=segments,
        detected_language="en",
    )

    assert len(results) >= 2


def test_domain_trust_tier_is_explicit_for_major_outlets():
    assert get_domain_trust_tier("https://www.reuters.com/world") == 1
    assert get_domain_trust_tier("https://example.com/news") == 3
