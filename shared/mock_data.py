import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from datetime import datetime, timezone
from uuid import UUID
from schemas.claim import Claim, SourcePlatform
from schemas.verdict import Verdict, VerdictLabel, Evidence

# --- MOCK CLAIMS ---

MOCK_CLAIM_1 = Claim(
    id=UUID("c1111111-1111-1111-1111-111111111111"),
    source_video_id="yt_vid_001",
    source_platform=SourcePlatform.YOUTUBE,
    raw_text="The sky is completely red today because of the new government lasers.",
    normalized_text="The sky turned red on June 28, 2026, due to government lasers.",
    language="en",
    timestamp_in_video=15.5,
    embedding_id="emb_001",
    created_at=datetime.now(timezone.utc)
)

MOCK_CLAIM_2 = Claim(
    id=UUID("c2222222-2222-2222-2222-222222222222"),
    source_video_id="fb_vid_002",
    source_platform=SourcePlatform.FACEBOOK,
    raw_text="El agua con limón cura todas las enfermedades.",
    normalized_text="El agua con limón cura todas las enfermedades conocidas.",
    language="es",
    timestamp_in_video=42.0,
    embedding_id="emb_002",
    created_at=datetime.now(timezone.utc)
)

MOCK_CLAIM_3 = Claim(
    id=UUID("c3333333-3333-3333-3333-333333333333"),
    source_video_id="ig_vid_003",
    source_platform=SourcePlatform.INSTAGRAM,
    raw_text="Drinking 8 glasses of water a day keeps you hydrated.",
    normalized_text="Drinking 8 glasses of water a day is sufficient for hydration for most people.",
    language="en",
    timestamp_in_video=5.0,
    embedding_id="emb_003",
    created_at=datetime.now(timezone.utc)
)

MOCK_CLAIM_4 = Claim(
    id=UUID("c4444444-4444-4444-4444-444444444444"),
    source_video_id="yt_vid_004",
    source_platform=SourcePlatform.YOUTUBE,
    raw_text="A new study shows coffee might make you live forever.",
    normalized_text="A recent study concludes that drinking coffee grants immortality.",
    language="en",
    timestamp_in_video=120.0,
    embedding_id="emb_004",
    created_at=datetime.now(timezone.utc)
)

MOCK_CLAIM_5 = Claim(
    id=UUID("c5555555-5555-5555-5555-555555555555"),
    source_video_id="ig_vid_005",
    source_platform=SourcePlatform.INSTAGRAM,
    raw_text="L'ancienne civilisation a caché des vaisseaux sous les pyramides.",
    normalized_text="Ancient civilizations hid spaceships underneath the Egyptian pyramids.",
    language="fr",
    timestamp_in_video=88.2,
    embedding_id="emb_005",
    created_at=datetime.now(timezone.utc)
)


# --- MOCK VERDICTS ---

MOCK_VERDICT_1 = Verdict(
    id=UUID("a1111111-1111-1111-1111-111111111111"),
    claim_id=MOCK_CLAIM_1.id,
    label=VerdictLabel.FALSE,
    confidence=0.98,
    evidence=[
        Evidence(
            source_url="https://science.example.com/sky-color",
            source_title="Why the Sky is Blue, not Red",
            snippet="Rayleigh scattering causes the sky to appear blue. There is no evidence of government lasers altering atmospheric colors.",
            relevance_score=0.95
        )
    ],
    reasoning="Atmospheric science clearly explains sky color, and claims of government space lasers affecting it are baseless conspiracies.",
    created_at=datetime.now(timezone.utc)
)

MOCK_VERDICT_2 = Verdict(
    id=UUID("a2222222-2222-2222-2222-222222222222"),
    claim_id=MOCK_CLAIM_2.id,
    label=VerdictLabel.MISLEADING,
    confidence=0.90,
    evidence=[
        Evidence(
            source_url="https://health.example.es/limon-mitos",
            source_title="Mitos y verdades del agua con limón",
            snippet="Aunque el agua con limón tiene vitamina C y es saludable, no es una cura milagrosa para ninguna enfermedad grave.",
            relevance_score=0.92
        )
    ],
    reasoning="While lemon water is healthy, it is an exaggeration and misleading to claim it cures all diseases.",
    created_at=datetime.now(timezone.utc)
)

MOCK_VERDICT_3 = Verdict(
    id=UUID("a3333333-3333-3333-3333-333333333333"),
    claim_id=MOCK_CLAIM_3.id,
    label=VerdictLabel.TRUE,
    confidence=0.99,
    evidence=[
        Evidence(
            source_url="https://health.example.com/hydration",
            source_title="Hydration Guidelines",
            snippet="Health experts commonly recommend eight 8-ounce glasses of water a day, commonly known as the 8x8 rule.",
            relevance_score=0.99
        )
    ],
    reasoning="This aligns with general, widely-accepted medical advice regarding daily hydration needs.",
    created_at=datetime.now(timezone.utc)
)

MOCK_VERDICT_4 = Verdict(
    id=UUID("a4444444-4444-4444-4444-444444444444"),
    claim_id=MOCK_CLAIM_4.id,
    label=VerdictLabel.FALSE,
    confidence=0.99,
    evidence=[
        Evidence(
            source_url="https://news.example.com/coffee-study",
            source_title="Coffee Study Misinterpreted",
            snippet="The recent study only found a 5% decrease in all-cause mortality for coffee drinkers, not immortality.",
            relevance_score=0.98
        )
    ],
    reasoning="The original study was vastly misrepresented; it showed marginal health benefits, not immortality.",
    created_at=datetime.now(timezone.utc)
)

MOCK_VERDICT_5 = Verdict(
    id=UUID("a5555555-5555-5555-5555-555555555555"),
    claim_id=MOCK_CLAIM_5.id,
    label=VerdictLabel.UNVERIFIABLE,
    confidence=0.85,
    evidence=[],
    reasoning="There is no historical or scientific evidence to either prove or absolutely disprove the existence of hidden objects deeply buried beneath the pyramids without exhaustive, invasive excavation, though it is highly improbable.",
    created_at=datetime.now(timezone.utc)
)

MOCK_CLAIMS = [MOCK_CLAIM_1, MOCK_CLAIM_2, MOCK_CLAIM_3, MOCK_CLAIM_4, MOCK_CLAIM_5]
MOCK_VERDICTS = [MOCK_VERDICT_1, MOCK_VERDICT_2, MOCK_VERDICT_3, MOCK_VERDICT_4, MOCK_VERDICT_5]

if __name__ == "__main__":
    import json
    print("=== MOCK CLAIMS ===")
    for claim in MOCK_CLAIMS:
        print(f"- {claim.normalized_text} ({claim.language})")
    
    print("\n=== MOCK VERDICTS ===")
    for verdict in MOCK_VERDICTS:
        print(f"- {verdict.label.name}: {verdict.reasoning}")
