"""
news_client.py — Unified News Evidence Collection
===================================================
Uses separate keys for each news API (no more auto-detection):
  - NEWS_API_KEY      → NewsAPI.org (https://newsapi.org/v2/everything)
  - NEWSDATA_API_KEY  → NewsData.io (https://newsdata.io/api/1/news)

Fallback chain: NewsAPI.org → NewsData.io → DuckDuckGo (handled in search.py)
"""

import json
import os
import re
import urllib.parse
from typing import Any, Dict, List, Optional, Set

from shared.llm import get_llm_client, get_llm_model, call_llm_with_fallback
from shared.resilience import resilient_http_fetch
from shared.api_keys import get_api_key_manager

# Domains that are never valid news evidence
JUNK_NEWS_DOMAINS = {
    "typing.com", "typingclub.com", "typingtest.com", "keybr.com",
    "10fastfingers.com", "nitrotype.com", "typerush.com",
    "facebook.com", "instagram.com", "pinterest.com", "tiktok.com",
    "amazon.com", "ebay.com", "wikipedia.org", "youtube.com", "youtu.be",
    "reddit.com", "quora.com", "stackoverflow.com",
}

_STOP = {
    "the", "a", "an", "is", "are", "was", "were", "be", "been", "being",
    "have", "has", "had", "do", "does", "did", "will", "would", "could",
    "should", "may", "might", "can", "that", "this", "these", "those",
    "and", "but", "or", "not", "to", "of", "in", "on", "at", "by", "for",
    "with", "from", "as", "into", "about", "then", "also", "some", "any",
    "all", "more", "very", "just", "now", "it", "its", "we", "they", "you",
    "i", "my", "your", "if", "when", "where", "what", "how", "who", "which",
    "there", "here", "so", "no", "yes", "one", "two", "first", "keep", "apply",
}

_NEWS_QUERY_FILLERS = {
    "technically", "essentially", "actually", "probably", "literally", "capable",
    "producing", "contains", "substances", "instead", "found", "study", "studies",
    "according", "shows", "show", "reported", "said", "says", "claims", "claim",
    "various", "certain", "type", "types", "true", "false", "fact", "check",
    "video", "watch", "bad", "good", "start", "starts", "starting", "need",
}


def get_news_api_key() -> str:
    """Get NewsAPI.org key from APIKeyManager."""
    return get_api_key_manager().get_newsapi_key() or ""


def get_newsdata_api_key() -> str:
    """Get NewsData.io key from APIKeyManager."""
    return get_api_key_manager().get_newsdata_key() or ""


def condense_search_query(text: str, max_words: int = 4) -> str:
    """
    Extract the most salient, natural keywords for news search.
    Strips quotes, removes stop words and filler adverbs, and preserves
    the natural word order of meaningful nouns/verbs.
    """
    clean_text = re.sub(r'["\'\(\)\[\]\{\}\:\;\?\!\,\.]', ' ', text).lower()
    words = [w for w in clean_text.split() if len(w) > 2]
    
    # First pass: drop stop words and conversational filler words
    meaningful = [w for w in words if w not in _STOP and w not in _NEWS_QUERY_FILLERS]
    
    # If too few words remain, allow words not in _STOP
    if len(meaningful) < 2:
        meaningful = [w for w in words if w not in _STOP]
    
    # If still empty, return original words
    if not meaningful:
        meaningful = words[:max_words]
        
    # Deduplicate while preserving order
    seen = set()
    deduped = []
    for w in meaningful:
        if w not in seen:
            seen.add(w)
            deduped.append(w)
            
    return " ".join(deduped[:max_words]).strip()


def _content_tokens(text: str) -> Set[str]:
    return {w for w in re.findall(r"[a-z]+", text.lower()) if w not in _STOP and len(w) > 2}


def jaccard_relevance(topic: str, text: str) -> float:
    t1 = _content_tokens(topic)
    t2 = _content_tokens(text)
    if not t1 or not t2:
        return 0.0
    return len(t1 & t2) / len(t1 | t2)


def is_junk_news_domain(url: str) -> bool:
    domain = url.split("//")[-1].split("/")[0].lower().lstrip("www.")
    return any(jd in domain for jd in JUNK_NEWS_DOMAINS)


def filter_relevant_news(
    articles: List[Dict[str, Any]],
    topic: str,
    min_jaccard: float = 0.02,
) -> List[Dict[str, Any]]:
    """Remove junk domains and off-topic articles."""
    kept = []
    for art in articles:
        url = art.get("url", "")
        if not url or is_junk_news_domain(url):
            continue
        combined = f"{art.get('title', '')} {art.get('snippet', '')}"
        score = jaccard_relevance(topic, combined)
        if score >= min_jaccard:
            art["relevance_score"] = round(score, 2)
            kept.append(art)
    return kept


def build_search_topic(claims: List[str], transcript_snippet: str) -> str:
    """Build a focused search topic from claims (preferred) or transcript keywords."""
    if claims:
        topic = condense_search_query(claims[0], max_words=5)
        if topic:
            return topic
        combined = " ".join(claims[:2])
        return condense_search_query(combined, max_words=5)

    return condense_search_query(transcript_snippet, max_words=5) or "fact check news"


def search_newsapi(query: str, page_size: int = 10, topic: str = "") -> List[Dict[str, Any]]:
    """
    Fetch news articles using separate keys for each API.
    Fallback chain: NewsAPI.org → NewsData.io
    Uses smart keyword condensation and multi-tier query fallbacks.
    """
    clean_query = condense_search_query(query, max_words=4)
    if not clean_query:
        clean_query = query.strip().strip('"\'')[:50]
        
    filter_topic = topic or clean_query
    results: List[Dict[str, Any]] = []

    # Step 1: Try NewsAPI.org (primary)
    newsapi_key = get_news_api_key()
    if newsapi_key:
        results = _fetch_from_newsapi_org(clean_query, newsapi_key, page_size)
        if not results and len(clean_query.split()) > 2:
            # Broaden to core 2-keyword query if initial query returned 0
            broader_query = " ".join(clean_query.split()[:2])
            results = _fetch_from_newsapi_org(broader_query, newsapi_key, page_size)
            
        if results:
            filtered = filter_relevant_news(results, filter_topic)
            if filtered:
                return filtered
        print("[news] NewsAPI.org returned no results — trying NewsData.io fallback...")

    # Step 2: Try NewsData.io (secondary)
    newsdata_key = get_newsdata_api_key()
    if newsdata_key:
        results = _fetch_from_newsdata_io(clean_query, newsdata_key, page_size)
        if not results and len(clean_query.split()) > 2:
            # Broaden to core 2-keyword query if initial query returned 0
            broader_query = " ".join(clean_query.split()[:2])
            results = _fetch_from_newsdata_io(broader_query, newsdata_key, page_size)
            
        if results:
            filtered = filter_relevant_news(results, filter_topic)
            if filtered:
                return filtered
        print("[news] NewsData.io also returned no results.")
    elif not newsapi_key:
        print("[news] No news API keys configured — skipping news search.")

    return filter_relevant_news(results, filter_topic)


def _parse_news_articles(items: List[Dict], url_key: str, title_key: str, snippet_keys: tuple, date_key: str) -> List[Dict[str, Any]]:
    results: List[Dict[str, Any]] = []
    seen: set = set()
    for article in items:
        art_url = (article.get(url_key) or "").strip()
        if not art_url or art_url in seen or "[Removed]" in art_url or is_junk_news_domain(art_url):
            continue
        seen.add(art_url)
        snippet = ""
        for sk in snippet_keys:
            if article.get(sk):
                snippet = str(article[sk])[:400]
                break
        domain = art_url.split("//")[-1].split("/")[0].lower().lstrip("www.")
        results.append({
            "url": art_url,
            "title": article.get(title_key) or domain,
            "snippet": snippet,
            "domain": domain,
            "published_date": (article.get(date_key) or "")[:10],
        })
    return results


def _fetch_from_newsapi_org(query: str, api_key: str, page_size: int) -> List[Dict[str, Any]]:
    clean_q = query.strip().strip('"\'')[:100]
    params = urllib.parse.urlencode({
        "q": clean_q,
        "language": "en",
        "sortBy": "relevancy",
        "pageSize": min(page_size, 20),
        "apiKey": api_key,
    })
    url = f"https://newsapi.org/v2/everything?{params}"

    data, success = resilient_http_fetch(
        "newsapi", url, headers={"User-Agent": "FactChecker/2.0"}, timeout=12
    )
    if not success or not data:
        return []

    if data.get("status") != "ok":
        error_msg = data.get("message", "unknown")
        print(f"[news] NewsAPI.org error: {error_msg}")
        if "apiKey" in error_msg.lower() or "invalid" in error_msg.lower():
            print("[news] ❌ NEWS_API_KEY appears to be invalid for NewsAPI.org")
        return []

    results = _parse_news_articles(
        data.get("articles", []),
        url_key="url", title_key="title",
        snippet_keys=("description", "content"),
        date_key="publishedAt",
    )
    for r in results:
        r["source"] = "newsapi"
    print(f"[news] NewsAPI.org returned {len(results)} articles for: {clean_q[:60]}")
    return results


def _fetch_from_newsdata_io(query: str, api_key: str, page_size: int) -> List[Dict[str, Any]]:
    clean_q = query.strip().strip('"\'')[:100]
    params = urllib.parse.urlencode({
        "apikey": api_key,
        "q": clean_q,
        "language": "en",
        "size": min(page_size, 10),
    })
    url = f"https://newsdata.io/api/1/news?{params}"

    data, success = resilient_http_fetch(
        "newsdata", url, headers={"User-Agent": "FactChecker/2.0"}, timeout=12
    )
    if not success or not data:
        print("[news] NewsData.io unavailable.")
        return []

    if data.get("status") != "success":
        error_msg = data.get("message", str(data))
        print(f"[news] NewsData.io error: {error_msg}")
        if "apikey" in str(error_msg).lower() or "unauthorized" in str(error_msg).lower():
            print("[news] ❌ NEWSDATA_API_KEY appears to be invalid")
        return []

    results = _parse_news_articles(
        data.get("results", []),
        url_key="link", title_key="title",
        snippet_keys=("description", "content"),
        date_key="pubDate",
    )
    for r in results:
        r["source"] = "newsdata"
    print(f"[news] NewsData.io returned {len(results)} articles for: {query[:60]}")
    return results


def _extract_json_array(text: str) -> Optional[List]:
    if not text:
        return None
    match = re.search(r"\[.*\]", text.strip(), re.DOTALL)
    if not match:
        return None
    try:
        return json.loads(match.group(0))
    except json.JSONDecodeError:
        try:
            import ast
            return ast.literal_eval(match.group(0))
        except Exception:
            return None


def groq_analyze_news_for_claim(claim: str, articles: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Use Groq to score news relevance. Skipped if no client or too few articles."""
    if not articles:
        return {
            "scored_articles": [],
            "support_count": 0,
            "contradiction_count": 0,
            "groq_summary": "No news articles found for this claim.",
        }

    client = get_llm_client()
    if not client:
        return {"scored_articles": articles, "support_count": 0, "contradiction_count": 0, "groq_summary": ""}

    article_block = "\n".join(
        f"[{i+1}] {a.get('title', '')[:100]} | {a.get('snippet', '')[:150]}"
        for i, a in enumerate(articles[:8])
    )

    try:
        response = call_llm_with_fallback(
            client=client,
            model=get_llm_model(),
            messages=[
                {"role": "system", "content": (
                    "Score each news article's relevance to the claim (0-1) and stance "
                    "(support/contradict/neutral). Return ONLY JSON array: "
                    '[{"index":1,"relevance":0.8,"stance":"support","reason":"brief"}]'
                )},
                {"role": "user", "content": f"Claim: {claim}\n\nArticles:\n{article_block}"},
            ],
            temperature=0.0,
            max_tokens=400,
            timeout=30,
        )
        raw = getattr(response.choices[0].message, "content", "") if response.choices else ""
        parsed = _extract_json_array(raw) or []
        support_count = contradiction_count = 0
        scored = list(articles)
        index_map = {i + 1: i for i in range(len(articles[:8]))}

        for item in parsed:
            if not isinstance(item, dict):
                continue
            idx = item.get("index")
            if idx not in index_map or index_map[idx] >= len(scored):
                continue
            arr_idx = index_map[idx]
            stance = str(item.get("stance", "neutral")).lower()
            scored[arr_idx]["groq_relevance"] = round(float(item.get("relevance", 0.5)), 2)
            scored[arr_idx]["groq_stance"] = stance
            scored[arr_idx]["groq_reason"] = item.get("reason", "")
            if stance == "support":
                support_count += 1
            elif stance == "contradict":
                contradiction_count += 1

        parts = []
        if support_count:
            parts.append(f"{support_count} support")
        if contradiction_count:
            parts.append(f"{contradiction_count} contradict")
        groq_summary = "Groq news analysis: " + (", ".join(parts) + "." if parts else "neutral coverage.")

        return {
            "scored_articles": scored,
            "support_count": support_count,
            "contradiction_count": contradiction_count,
            "groq_summary": groq_summary,
        }
    except Exception as e:
        print(f"[news] Groq news analysis error: {e}")
        return {"scored_articles": articles, "support_count": 0, "contradiction_count": 0, "groq_summary": ""}
