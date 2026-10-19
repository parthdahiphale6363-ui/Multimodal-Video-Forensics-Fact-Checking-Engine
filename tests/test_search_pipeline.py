from pipeline.search import build_search_queries, gather_evidence_for_claim


def test_build_search_queries_creates_multiple_distinct_queries():
    queries = build_search_queries("The sky is blue and the grass is green.")

    assert len(queries) >= 2
    assert len(set(queries)) == len(queries)


def test_gather_evidence_for_claim_returns_fallback_evidence_without_api_keys(monkeypatch):
    monkeypatch.delenv("TAVILY_API_KEY", raising=False)
    monkeypatch.delenv("SERPAPI_KEY", raising=False)
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    monkeypatch.delenv("NEWS_API_KEY", raising=False)
    monkeypatch.delenv("NEWSDATA_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_FACTCHECK_API_KEY", raising=False)
    monkeypatch.delenv("MISTRAL_API_KEY", raising=False)

    from pipeline.search import _in_memory_verdict_cache
    _in_memory_verdict_cache.clear()

    # Reset the APIKeyManager singleton so it re-reads cleared env vars
    import shared.api_keys as _akm
    _akm._manager = None
    _akm.APIKeyManager._instance = None

    result = gather_evidence_for_claim("The sky is blue.", "The sky is blue during daytime.")

    # A transcript is context, not an independently citable source. Without a
    # verifier, the system must fail closed and expose no fabricated citation.
    assert result["label"] in ("misleading", "unverified")
    assert result["evidence"] == []
    assert result["confidence"] <= 0.5
    assert "no llm" in result["reasoning"].lower() or "transcript" in result["reasoning"].lower()
