"""
search.py — Evidence Search & Fact-Check Reasoning Pipeline
============================================================
Priority order for evidence:
  1. Translate claim to English (if Hinglish/Hindi/other language)
  2. LLM-generated targeted search queries (2 precise queries per claim)
  3. NewsAPI  (real news sources with real article URLs — single NEWS_API_KEY)
  4. DuckDuckGo (web fallback)
  5. Groq news relevance scoring on NewsAPI results
  6. Wikipedia (filtered by Jaccard & BM25 relevance — no automatic priority)
  7. Groq LLM reasons ONLY over the gathered, relevance-filtered evidence.
"""

import json
import re
import time
import warnings
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional, Tuple, Set

warnings.filterwarnings("ignore", category=RuntimeWarning, message=".*duckduckgo_search.*")
warnings.filterwarnings("ignore", category=RuntimeWarning, message=".*renamed to.*")
warnings.filterwarnings("ignore", category=RuntimeWarning, module="duckduckgo_search")

DDGS = None
try:
    from ddgs import DDGS
except ImportError:
    try:
        from duckduckgo_search import DDGS
    except ImportError:
        DDGS = None

from pipeline.domain_trust import get_domain_trust_tier
from shared.llm import get_llm_client, get_llm_model, call_llm_with_fallback, get_redis_client
from shared.news_client import search_newsapi
from pipeline.rag import run_rag_pipeline
from shared.resilience import execute_with_resilience
from pipeline.evidence_classifier import (
    EvidenceStance,
    ClassifiedEvidenceItem,
    classify_evidence_items,
    compute_consensus_and_metrics,
    compute_calibrated_confidence,
    is_medical_health_claim,
    detect_medical_guideline_conflict,
)
import hashlib


def _detect_medical_conflict(claim_text: str, evidence_items: List[Any]) -> bool:
    """Detect if evidence items contain warnings or conflicting medical guidelines."""
    if not is_medical_health_claim(claim_text):
        return False
    for item in evidence_items:
        text = f"{getattr(item, 'source_title', '')} {getattr(item, 'snippet', '')} {getattr(item, 'explanation', '')}".lower()
        if detect_medical_guideline_conflict(claim_text, text):
            return True
    return False

_in_memory_verdict_cache = {}


def clear_verdict_cache():
    global _in_memory_verdict_cache
    _in_memory_verdict_cache.clear()

def get_cached_verdict(claim_text: str) -> Optional[Dict[str, Any]]:
    normalized = claim_text.strip().lower()
    h = hashlib.md5(f"v7:{normalized}".encode("utf-8")).hexdigest()
    
    # 1. Redis Cache
    redis_client = get_redis_client()
    if redis_client:
        try:
            cached = redis_client.get(f"verdict_cache:{h}")
            if cached:
                print(f"[Cache] Redis hit for claim: '{claim_text[:50]}'")
                return json.loads(cached)
        except Exception as e:
            print(f"[Cache] Redis get error: {e}")
            
    # 2. In-Memory Cache Fallback
    if h in _in_memory_verdict_cache:
        result, expires_at = _in_memory_verdict_cache[h]
        if time.time() < expires_at:
            print(f"[Cache] In-memory hit for claim: '{claim_text[:50]}'")
            return result
        else:
            del _in_memory_verdict_cache[h]
            
    return None

def set_cached_verdict(claim_text: str, result: Dict[str, Any]):
    normalized = claim_text.strip().lower()
    h = hashlib.md5(f"v7:{normalized}".encode("utf-8")).hexdigest()
    ttl = 24 * 3600  # 24 hours
    
    # 1. Redis Cache
    redis_client = get_redis_client()
    if redis_client:
        try:
            redis_client.setex(f"verdict_cache:{h}", ttl, json.dumps(result))
            print(f"[Cache] Saved to Redis for claim: '{claim_text[:50]}'")
        except Exception as e:
            print(f"[Cache] Redis set error: {e}")
            
    # 2. In-Memory Cache
    _in_memory_verdict_cache[h] = (result, time.time() + ttl)
    print(f"[Cache] Saved to In-memory for claim: '{claim_text[:50]}'")


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _make_unavailable_placeholder(source_name: str, title: str, domain: str) -> Dict[str, Any]:
    return {
        "source_url": f"https://{domain}/unavailable",
        "source_title": title,
        "domain": domain,
        "domain_trust": "low",
        "domain_trust_tier": 3,
        "snippet": f"The {source_name} source was unavailable or rate-limited during verification. Confidence score was lowered.",
        "relevance_score": 0.0,
        "publication_date": "",
        "supports_claim": None,
        "service_unavailable": True
    }

def _normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "")).strip()


def _extract_json_payload(text: str) -> Optional[Dict[str, Any]]:
    if not text:
        return None
    text = text.strip()
    match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", text)
    if match:
        text = match.group(1)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        match2 = re.search(r"\{.*\}", text, flags=re.DOTALL)
        if not match2:
            return None
        try:
            return json.loads(match2.group(0))
        except json.JSONDecodeError:
            return None


def _make_evidence_item(url: str, title: str, snippet: str, published: str = "") -> Dict[str, Any]:
    domain = url.split("//")[-1].split("/")[0].lower()
    trust_tier = get_domain_trust_tier(url)
    trust_label = "high" if trust_tier == 1 else "medium" if trust_tier == 2 else "low"
    return {
        "source_url": url,
        "source_title": title or domain,
        "domain": domain,
        "domain_trust": trust_label,
        "domain_trust_tier": trust_tier,
        "snippet": (snippet or "No snippet available.")[:400],
        "relevance_score": 0.0,   # Set by BM25 in rag.py
        "publication_date": published or "",
        "supports_claim": None,
    }


# ─── Step 1: Detect & Translate to English ────────────────────────────────────

def _is_english(text: str) -> bool:
    alpha = [c for c in text if c.isalpha()]
    if not alpha:
        return True
    ascii_alpha = [c for c in alpha if ord(c) < 128]
    ratio = len(ascii_alpha) / len(alpha)
    hinglish_markers = ["ko", "nahi", "hai", "ka", "ke", "ki", "mein", "aata",
                        "hota", "jaisa", "insaan", "bhalu", "pasina", "khana"]
    words = text.lower().split()
    hinglish_hits = sum(1 for w in words if w in hinglish_markers)
    return ratio >= 0.75 and hinglish_hits < 2


_translation_cache: Dict[str, str] = {}

def translate_claim_to_english(claim_text: str) -> str:
    if _is_english(claim_text):
        return claim_text

    norm = claim_text.strip().lower()
    if norm in _translation_cache:
        return _translation_cache[norm]

    client = get_llm_client()
    if not client:
        return claim_text

    try:
        response = call_llm_with_fallback(
            client=client,
            model=get_llm_model(),
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a translator. Translate the given text to clear, concise English. "
                        "Preserve all factual claims, numbers, and names exactly. "
                        "Return ONLY the English translation — no explanation, no quotation marks."
                    ),
                },
                {"role": "user", "content": f"Translate to English: {claim_text}"},
            ],
            temperature=0.0,
            max_tokens=600,
            timeout=30,
        )
        if response.choices:
            translated = (getattr(response.choices[0].message, "content", "") or "").strip()
            if translated:
                safe_tr = translated.replace("→", "->").encode("ascii", "replace").decode("ascii")
                print(f"[search] Translated: '{claim_text[:60]}' -> '{safe_tr[:60]}'")
                _translation_cache[norm] = translated
                return translated
    except Exception as e:
        print(f"[search] Translation error: {e}")

    return claim_text


# ─── Step 2: LLM-Powered Query Builder ────────────────────────────────────────

def _keyword_fallback_queries(claim_text: str) -> List[str]:
    """Fast keyword-only fallback when LLM is unavailable."""
    stop = {
        "the", "a", "an", "is", "are", "was", "were", "be", "been", "being",
        "have", "has", "had", "do", "does", "did", "will", "would", "could",
        "should", "may", "might", "shall", "can", "need", "that", "this",
        "these", "those", "and", "but", "or", "not", "to", "of", "in", "on",
        "at", "by", "for", "with", "from", "as", "into", "about", "than",
        "then", "also", "some", "any", "all", "more", "very", "just", "now",
        "equal", "amount", "per", "next",
    }
    tokens = re.findall(r"[A-Za-z0-9]+", claim_text)
    keywords = [t for t in tokens if t.lower() not in stop and len(t) > 2]
    if not keywords:
        keywords = [t for t in tokens if len(t) > 2]
    if not keywords:
        keywords = tokens
    
    kw = " ".join(keywords[:6])
    core_kw = " ".join(keywords[:4])
    if not kw.strip():
        kw = "video content"
        core_kw = "video content"

    clean_claim = re.sub(r'["\']', '', claim_text).strip()
    queries = []
    if len(clean_claim.split()) <= 10:
        queries.append(clean_claim)
    queries.extend([
        f"{core_kw} scientific evidence",
        f"{core_kw} debunked false myth",
        f"did {core_kw} official records",
        kw,
    ])
    return list(dict.fromkeys(queries))


def build_search_queries(claim_text: str) -> List[str]:
    """
    Build diverse search queries for a claim.
    Generates exact claim, scientific concepts, and counterevidence queries.
    """
    import os
    if os.getenv("DISABLE_LLM_QUERIES", "0") == "1":
        queries = _keyword_fallback_queries(claim_text)
        print(f"[search] Keyword queries (LLM queries disabled): {queries[:2]}")
        return queries

    client = get_llm_client()
    if not client:
        return _keyword_fallback_queries(claim_text)

    try:
        response = call_llm_with_fallback(
            client=client,
            model=get_llm_model(),
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are an expert fact-checking research scientist and OSINT investigator.\n"
                        "Given a claim from a video transcript, identify the real-world factual context, "
                        "scientific study, viral discovery, or historical event being referenced.\n"
                        "Note: Claims in videos often use colloquial phrasing (e.g. 'produce poison' when referring to 'venom genetics' or salivary toxins, or 'brain eats itself' when referring to 'neuronal autophagy').\n"
                        "Generate 3-4 diverse, targeted search queries designed to retrieve authoritative, peer-reviewed, or investigative evidence:\n"
                        "1. Natural question/claim with common synonyms (e.g. 'can humans produce venom or poison')\n"
                        "2. Specific scientific study or viral story (e.g. 'human salivary glands venom genetics study PNAS')\n"
                        "3. Underlying biological, chemical, historical, or physical mechanisms\n"
                        "4. Direct verification or counterevidence inquiry\n"
                        "Do NOT include words like 'fact check' or 'true false'. Focus on factual reality and scientific discoveries.\n"
                        "Return ONLY a JSON array of strings: [\"query1\", \"query2\", \"query3\", \"query4\"]"
                    ),
                },
                {
                    "role": "user",
                    "content": f"Generate targeted fact-checking search queries for this claim: {claim_text}",
                },
            ],
            temperature=0.0,
            max_tokens=500,
            timeout=25,
        )
        raw = ""
        if response.choices:
            raw = (getattr(response.choices[0].message, "content", "") or "").strip()

        # Parse the JSON array
        raw = raw.strip()
        match = re.search(r"\[.*\]", raw, re.DOTALL)
        if match:
            raw_array = match.group(0)
            queries = None
            try:
                queries = json.loads(raw_array)
            except Exception:
                try:
                    queries = json.loads(raw_array.replace("'", '"'))
                except Exception:
                    import ast
                    try:
                        queries = ast.literal_eval(raw_array)
                    except Exception:
                        pass

            if isinstance(queries, list) and len(queries) >= 1:
                cleaned_queries = []
                for q in queries:
                    s = str(q).strip()
                    s = s.replace("\u2011", "-").replace("\u2013", "-").replace("\u2014", "-")
                    s = s.replace("\u2018", "'").replace("\u2019", "'").replace("\u201c", '"').replace("\u201d", '"')
                    if s:
                        cleaned_queries.append(s)
                # Prioritize targeted conceptual queries over long colloquial transcript sentences
                clean_claim = re.sub(r'["\']', '', claim_text).strip()
                kw_queries = _keyword_fallback_queries(claim_text)
                if len(clean_claim.split()) <= 6:
                    combined = list(dict.fromkeys([clean_claim] + cleaned_queries + kw_queries))
                else:
                    combined = list(dict.fromkeys(cleaned_queries + [clean_claim] + kw_queries))
                try:
                    print(f"[search] Combined search queries: {combined[:5]}")
                except Exception:
                    pass
                return combined[:5]

    except Exception as e:
        print(f"[search] LLM query generation failed ({e}), using keyword fallback")

    return _keyword_fallback_queries(claim_text)


def expand_search_queries(claim_text: str, existing_queries: List[str]) -> List[str]:
    """
    Generate second-round expanded queries when initial search results are sparse or off-topic.
    Approaches the claim from technical, biological, chemical, or counterevidence perspectives.
    """
    client = get_llm_client()
    if client:
        try:
            prompt = (
                f"The initial web search queries for '{claim_text}' yielded sparse or off-topic results.\n"
                f"Previous queries were: {existing_queries[:4]}.\n"
                "Think about what real scientific paper, viral discovery, historical event, or popular science story this claim refers to.\n"
                "Account for common layperson terminology vs scientific terminology (e.g. venom vs poison, enzymes, genetics, journals like PNAS/Nature/Science).\n"
                "Generate 2-3 NEW, highly specific search queries targeting the underlying evidence or direct counterevidence:\n"
                "Return ONLY a JSON array of strings: [\"new_query1\", \"new_query2\", \"new_query3\"]"
            )
            response = call_llm_with_fallback(
                client=client,
                model=get_llm_model(),
                messages=[
                    {"role": "system", "content": "You are a research specialist. Return ONLY a JSON array of search strings."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.1,
                max_tokens=400,
                timeout=20,
            )
            raw = (response.choices[0].message.content or "").strip() if response.choices else ""
            match = re.search(r"\[.*\]", raw, re.DOTALL)
            if match:
                queries = json.loads(match.group(0))
                if isinstance(queries, list) and queries:
                    new_q = [str(q).strip() for q in queries if str(q).strip() and str(q).strip() not in existing_queries]
                    if new_q:
                        print(f"[search] Expanded queries (Round 2): {new_q[:3]}")
                        return new_q[:3]
        except Exception as e:
            print(f"[search] Query expansion LLM call failed ({e})")

    tokens = [w for w in re.findall(r"[a-z0-9]+", claim_text.lower()) if len(w) > 2]
    core = " ".join(tokens[:5])
    return [
        f"{core} scientific evidence",
        f"{core} toxicology biology research",
        f"{claim_text[:60]} analysis",
    ]


# ─── Step 3: DuckDuckGo Search with Retry ────────────────────────────────────

def _ddgs_search(query: str, max_results: int = 8, retries: int = 3) -> List[Dict]:
    if not DDGS:
        return []
    
    clean_q = re.sub(r'["\'\(\)\[\]\{\}\:\;\?\!\,\.]', ' ', query).strip()
    words = [w for w in clean_q.split() if len(w) > 2]
    condensed_q = " ".join(words[:12]) if words else clean_q[:80]

    def _do_search():
        with DDGS(timeout=4) as ddgs:
            return list(ddgs.text(condensed_q, max_results=max_results))

    res, success = execute_with_resilience("ddg", _do_search)
    if success and res:
        return res
    return []


def _ddgs_news_search(query: str, max_results: int = 6) -> List[Dict[str, Any]]:
    """DuckDuckGo news search — falls back to text search if news.js is rate-limited."""
    if not DDGS:
        return []

    clean_q = re.sub(r'["\'\(\)\[\]\{\}\:\;\?\!\,\.]', ' ', query).strip()
    words = [w for w in clean_q.split() if len(w) > 2]
    condensed_q = " ".join(words[:10]) if words else clean_q[:80]

    def _do_news():
        with DDGS(timeout=4) as ddgs:
            try:
                return list(ddgs.news(condensed_q, max_results=max_results))
            except Exception as e:
                err_s = str(e).lower()
                if "403" in err_s or "ratelimit" in err_s or "connect" in err_s or "eof" in err_s:
                    return list(ddgs.text(f"{condensed_q} news", max_results=max_results))
                raise

    res, success = execute_with_resilience("ddg_news", _do_news)
    if not success or not res:
        return []

    articles = []
    for r in res:
        url = (r.get("url") or r.get("href") or "").strip()
        if not url:
            continue
        articles.append({
            "url": url,
            "title": r.get("title", ""),
            "snippet": (r.get("body") or r.get("excerpt") or "")[:400],
            "domain": url.split("//")[-1].split("/")[0].lower().lstrip("www."),
            "published_date": (r.get("date") or "")[:10],
            "source": "ddg_news",
        })
    return articles


BLOCKED_DOMAINS = {
    "example.com", "localhost", "youtube.com", "youtu.be", "cuemath.com",
}


def _fetch_web_evidence(queries: List[str], claim_text: str = "") -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """
    Collect evidence from NewsAPI (primary) + DuckDuckGo (fallback) concurrently.
    Filters blocked domains. Caps to max 2 results per domain.
    Returns (evidence_list, search_runs_trace).
    """
    from concurrent.futures import ThreadPoolExecutor

    seen_urls: set = set()
    domain_counts: Dict[str, int] = {}
    evidence: List[Dict[str, Any]] = []
    news_raw: List[Dict[str, Any]] = []
    search_runs: List[Dict[str, Any]] = []

    def _add(item: Dict[str, Any]) -> bool:
        url = item.get("source_url", "")
        domain = item.get("domain", "")
        if not url or url in seen_urls:
            return False
        if any(bd in domain for bd in BLOCKED_DOMAINS):
            return False
        if domain_counts.get(domain, 0) >= 2:
            return False
        seen_urls.add(url)
        domain_counts[domain] = domain_counts.get(domain, 0) + 1
        evidence.append(item)
        return True

    # Step A: NewsAPI — primary news source concurrently
    news_queries = queries[:3]
    news_api_failed = False
    if news_queries:
        with ThreadPoolExecutor(max_workers=min(len(news_queries), 3)) as executor:
            futures = [
                executor.submit(search_newsapi, q, 8, claim_text or q)
                for q in news_queries
            ]
            for query, fut in zip(news_queries, futures):
                if len(evidence) >= 12:
                    break
                try:
                    articles = fut.result(timeout=10)
                except Exception as e:
                    print(f"[search] News search failed for '{query[:30]}': {e}")
                    articles = []

                source_name = "NewsData.io" if articles and articles[0].get("source") == "newsdata" else "NewsAPI"
                search_runs.append({
                    "query": query,
                    "source_type": source_name,
                    "results_found": len(articles) if articles else 0,
                    "top_domain": articles[0]["url"].split("//")[-1].split("/")[0] if articles else ("newsdata.io" if source_name == "NewsData.io" else "newsapi.org"),
                    "trust_level": "high" if articles else "medium",
                    "stance": "neutral",
                })
                if not articles:
                    from shared.resilience import get_breaker
                    if get_breaker("newsapi").state == "OPEN" or get_breaker("newsapi").failure_count > 0:
                        news_api_failed = True
                    continue
                for art in articles:
                    news_raw.append(art)
                    _add(_make_evidence_item(
                        url=art["url"],
                        title=art["title"],
                        snippet=art["snippet"],
                        published=art.get("published_date", ""),
                    ))

    # Step A2: DuckDuckGo news if API news returned nothing
    if not news_raw:
        ddg_news_queries = queries[:2]
        if ddg_news_queries:
            with ThreadPoolExecutor(max_workers=min(len(ddg_news_queries), 2)) as executor:
                futures = [
                    executor.submit(_ddgs_news_search, f"{q} news", 6)
                    for q in ddg_news_queries
                ]
                for query, fut in zip(ddg_news_queries, futures):
                    if len(evidence) >= 10:
                        break
                    try:
                        ddg_news = fut.result(timeout=8)
                    except Exception as e:
                        ddg_news = []
                    search_runs.append({
                        "query": f"{query} news",
                        "source_type": "DuckDuckGo News",
                        "results_found": len(ddg_news),
                        "top_domain": ddg_news[0]["domain"] if ddg_news else "duckduckgo.com",
                        "trust_level": "medium",
                        "stance": "neutral",
                    })
                    for art in ddg_news:
                        news_raw.append(art)
                        _add(_make_evidence_item(
                            url=art["url"],
                            title=art["title"],
                            snippet=art["snippet"],
                            published=art.get("published_date", ""),
                        ))
        if news_api_failed and not news_raw:
            print("[search] News API key invalid or unavailable — using DuckDuckGo news + web search.")

    # Step C: Always run DuckDuckGo web search concurrently across queries
    web_queries = queries[:5]
    if web_queries:
        with ThreadPoolExecutor(max_workers=min(len(web_queries), 5)) as executor:
            futures = [
                executor.submit(_ddgs_search, q, 8)
                for q in web_queries
            ]
            for query, fut in zip(web_queries, futures):
                if len(evidence) >= 16:
                    break
                try:
                    results = fut.result(timeout=10)
                except Exception as e:
                    print(f"[search] DDGS search failed for '{query[:30]}': {e}")
                    results = []
                search_runs.append({
                    "query": query,
                    "source_type": "DuckDuckGo Web",
                    "results_found": len(results),
                    "top_domain": results[0].get("href", "").split("//")[-1].split("/")[0] if results else "duckduckgo.com",
                    "trust_level": "medium",
                    "stance": "neutral",
                })
                if not results:
                    from shared.resilience import get_breaker
                    if get_breaker("ddg").state == "OPEN" and not evidence:
                        _add(_make_unavailable_placeholder("duckduckgo", "DuckDuckGo Web Search Unavailable", "duckduckgo.com"))
                else:
                    for res in results:
                        url = res.get("href", "").strip()
                        if not url:
                            continue
                        _add(_make_evidence_item(
                            url=url,
                            title=res.get("title", ""),
                            snippet=res.get("body", ""),
                        ))

    print(f"[search] Total raw evidence collected: {len(evidence)} items (news: {len(news_raw)})")
    return evidence[:15], search_runs


# ─── Step 6: Groq Fact-Check Reasoning ───────────────────────────────────────

_LLM_SYSTEM_PROMPT = """\
You are a rigorous, impartial, world-class fact-checker.

Given a factual claim and a list of retrieved sources, determine whether the evidence supports, partly supports, contradicts, or cannot resolve the claim.

CRITICAL INSTRUCTIONS:
1. Carefully analyze each evidence item. Check whether it directly addresses the claim or discusses an unrelated topic.
2. DISREGARD IRRELEVANT SOURCES: Do NOT treat an article about an unrelated topic (e.g. rat control or plant rashes when evaluating whether humans can produce poison) as evidence that the claim is false!
3. Verdict guidelines:
   - TRUE requires directly relevant, credible supporting evidence.
   - FALSE requires directly relevant, credible counterevidence.
   - MISLEADING requires evidence for a bounded part of the claim plus material missing context, overstatement, or conflict.
   - UNVERIFIED is required when the supplied evidence is insufficient. Never infer a verdict from missing evidence or model knowledge.
4. Cite only URLs supplied in the evidence list. Do not invent a citation, a passage, an article title, or a fact not present in those sources.

Return ONLY valid JSON (no markdown, no preamble):
{
  "label": "true" | "false" | "misleading" | "unverified",
  "confidence": 0.0–1.0,
  "reasoning": "2-4 sentence explanation detailing the evidence and justification.",
  "summary": "One-sentence concise verdict.",
  "evidence": [
    {
      "source_url": "<exact URL from the evidence list>",
      "source_title": "<exact title from the evidence list>",
      "domain": "<domain>",
      "snippet": "<relevant excerpt>",
      "relevance_score": 0.0–1.0,
      "stance": "supports" | "partially_supports" | "contradicts" | "neutral" | "unrelated" | "insufficient",
      "supports_claim": true | false
    }
  ]
}
"""


_LLM_KNOWLEDGE_PROMPT = """\
You are a rigorous, impartial fact-checker with broad general knowledge across science, mechanics, psychology, history, geography, and current events.

External web search returned sparse or no direct results for this claim. Use your comprehensive training knowledge of well-established facts, scientific studies, psychological research, and empirical reality to fact-check it.

Your job is to:
1. Read the claim carefully.
2. Determine whether the claim describes a real, physically/scientifically sound fact, a falsehood, or a misleading statement.
3. Assign a definitive verdict: TRUE, FALSE, or MISLEADING. Do NOT use UNVERIFIABLE.
4. Provide 1-3 evidence items based on well-known authoritative sources, scientific studies, or reference materials.
5. Write detailed reasoning explaining WHY the claim is true, false, or misleading.

Verdict guidelines:
- TRUE: Claim is factually and scientifically correct based on well-established reality and empirical research.
- FALSE: Claim is clearly false, impossible, a proven hoax, or contradicted by established science/facts.
- MISLEADING: Partially true but missing context, exaggerated, or an overgeneralization of a specific study (e.g., claiming everyone will do something when research shows only a minority or specific hypothetical scenario).

Return ONLY valid JSON (no markdown, no preamble):
{
  "label": "true" | "false" | "misleading",
  "confidence": 0.0–1.0,
  "reasoning": "3-5 sentence detailed explanation with specific facts, numbers, and references.",
  "summary": "One-sentence verdict.",
  "evidence": [
    {
      "source_url": "<real URL to authoritative or industry source>",
      "source_title": "<descriptive title>",
      "domain": "<domain>",
      "snippet": "<factual information explaining or corroborating the claim>",
      "relevance_score": 0.8,
      "supports_claim": true | false
    }
  ]
}
"""


def _llm_knowledge_factcheck(
    claim_text: str,
    english_claim: str,
    transcript_text: str,
) -> Dict[str, Any]:
    """Fail closed when retrieval is unavailable; model memory is not citable evidence."""
    return {
        "label": "unverified",
        "confidence": 0.2,
        "reasoning": "No claim-relevant, URL-backed evidence was retrieved. TruthLens does not use model memory as a citation.",
        "summary": "Unverified: external evidence was unavailable.",
        "evidence": [],
    }

    # Kept below temporarily for a low-risk rollback diff. The return above is
    # intentional: this code must never manufacture citations from an LLM.
    client = get_llm_client()
    if not client:
        return {
            "label": "misleading",
            "confidence": 0.4,
            "reasoning": "No LLM client available and no web evidence could be collected.",
            "summary": "Inconclusive without external search results or LLM available.",
            "evidence": [],
        }

    transcript_preview = _normalize_text(transcript_text)[:1000]
    user_content = (
        f"Claim to fact-check: {english_claim}\n"
        f"(Original, may be Hinglish): {claim_text}\n\n"
        f"Video transcript context:\n{transcript_preview}\n\n"
        "IMPORTANT: No external web search results were available. "
        "Use your own knowledge of well-established facts to evaluate this claim. "
        "Provide detailed reasoning and evidence from authoritative sources."
    )

    try:
        response = call_llm_with_fallback(
            client=client,
            model=get_llm_model(),
            messages=[
                {"role": "system", "content": _LLM_KNOWLEDGE_PROMPT},
                {"role": "user", "content": user_content},
            ],
            temperature=0.0,
            max_tokens=2500,
            timeout=45,
        )

        raw = ""
        if response.choices:
            raw = getattr(response.choices[0].message, "content", "") or ""

        parsed = _extract_json_payload(raw)
        if parsed:
            # Build proper evidence items from LLM-generated evidence
            evidence_items = []
            for ev in parsed.get("evidence", []):
                url = ev.get("source_url", "")
                domain = url.split("//")[-1].split("/")[0].lower() if "//" in url else "ai-knowledge"
                evidence_items.append({
                    "source_url": url,
                    "source_title": ev.get("source_title", "AI Knowledge Base"),
                    "domain": domain,
                    "domain_trust": "medium",
                    "domain_trust_tier": 2,
                    "snippet": ev.get("snippet", ""),
                    "relevance_score": ev.get("relevance_score", 0.7),
                    "publication_date": "",
                    "supports_claim": ev.get("supports_claim", False),
                })
            parsed["evidence"] = evidence_items
            parsed["label"] = _canonical_verdict_label(parsed.get("label", "unverified"))
            # Lower confidence slightly since this is knowledge-based, not search-verified
            if "confidence" in parsed:
                parsed["confidence"] = round(min(parsed["confidence"], 0.85), 3)
            print(f"[search] Knowledge-based fact-check: {parsed.get('label')} ({parsed.get('confidence')})")
            return parsed

        print(f"[search] Knowledge-based LLM parse failed. Raw: {raw[:300]}")
    except Exception as e:
        print(f"[search] Knowledge-based fact-check error: {e}")

    return {
        "label": "unverified",
        "confidence": 0.20,
        "reasoning": "External search APIs and knowledge models were unavailable or insufficient to substantiate this claim.",
        "summary": "Unverified — insufficient evidence to substantiate or refute the claim.",
        "evidence": [],
    }


def _run_llm_reasoning(
    claim_text: str,
    english_claim: str,
    transcript_text: str,
    web_evidence: List[Dict[str, Any]],
) -> Dict[str, Any]:
    client = get_llm_client()
    if not client:
        raise RuntimeError("LLM client not available — check GROQ_API_KEY in .env")

    transcript_preview = _normalize_text(transcript_text)[:1500]

    if web_evidence:
        evidence_block = "\n\n".join(
            f"[{i+1}] Title: {e['source_title']}\n"
            f"     URL: {e['source_url']}\n"
            f"     Domain: {e.get('domain','')}\n"
            f"     Snippet: {e['snippet'][:300]}\n"
            f"     Published: {e.get('publication_date', 'unknown')}"
            for i, e in enumerate(web_evidence)
        )
        evidence_note = (
            f"Evidence ({len(web_evidence)} sources — use ONLY these URLs):\n\n"
            + evidence_block
        )
    else:
        # No evidence — use knowledge-based fact-check instead
        return _llm_knowledge_factcheck(claim_text, english_claim, transcript_text)

    user_content = (
        f"Claim to fact-check: {english_claim}\n"
        f"(Original, may be Hinglish): {claim_text}\n\n"
        f"Video transcript context:\n{transcript_preview}\n\n"
        f"{evidence_note}\n\n"
        "Return your verdict as JSON. Only cite URLs from the evidence list above."
    )

    response = call_llm_with_fallback(
        client=client,
        model=get_llm_model(),
        messages=[
            {"role": "system", "content": _LLM_SYSTEM_PROMPT},
            {"role": "user", "content": user_content},
        ],
        temperature=0.0,
        max_tokens=2500,
        timeout=45,
    )

    raw = ""
    if response.choices:
        raw = getattr(response.choices[0].message, "content", "") or ""

    parsed = _extract_json_payload(raw)
    if not parsed:
        print(f"[search] LLM parse failed. Raw (first 300): {raw[:300]}")
        return {
            "label": "unverified",
            "confidence": 0.2,
            "reasoning": "LLM returned an unparseable response. Evidence collected but could not determine verdict.",
            "summary": "Could not determine verdict automatically.",
            "evidence": [],
        }

    # ── Validate & clean evidence citations ──────────────────────────────────
    real_url_map: Dict[str, Dict] = {
        e["source_url"]: e for e in web_evidence
        if not e.get("service_unavailable") and not (e.get("source_url") or "").endswith("/unavailable")
    }
    clean_ev: List[Dict] = []

    for ev in parsed.get("evidence", []):
        ev_url = ev.get("source_url", "")
        if ev_url in real_url_map:
            base = real_url_map[ev_url].copy()
            base["supports_claim"] = ev.get("supports_claim", None)
            # Retain original authentic snippet to prevent model-fabricated quotes
            original_snippet = base.get("snippet", "")
            base["snippet"] = original_snippet
            base["relevant_passage"] = ev.get("snippet") or base.get("relevant_passage") or original_snippet
            if ev.get("relevance_score"):
                base["relevance_score"] = float(ev["relevance_score"])
            clean_ev.append(base)

    # If LLM cited nothing valid or only fabricated URLs, return unverified
    if not clean_ev:
        parsed["label"] = "unverified"
        parsed["confidence"] = min(float(parsed.get("confidence", 0.2)), 0.25)
        parsed["reasoning"] = "The model did not map its conclusion to a retrieved, verified source URL; no evidence-backed verdict was issued."
        parsed["evidence"] = []
        return parsed

    parsed["evidence"] = clean_ev
    return parsed


def _canonical_verdict_label(label: Any) -> str:
    """Normalize legacy/provider labels to the strict 3-verdict taxonomy: true, false, misleading."""
    value = str(label or "").strip().lower()
    return {
        "supported": "true",
        "verified": "true",
        "contradicted": "false",
        "partially_supported": "misleading",
        "ambiguous": "misleading",
        "unverifiable": "misleading",
        "unverified": "misleading",
        "partial": "misleading",
        "true": "true",
        "false": "false",
        "misleading": "misleading",
    }.get(value, "misleading")


def _keyword_verdict_from_evidence(
    claim: str,
    english_claim_or_evidence: Any = "",
    web_evidence: Optional[List[Dict[str, Any]]] = None,
    error_msg: str = "",
) -> Dict[str, Any]:
    """Fallback verdict when Groq is rate-limited but we have web evidence."""
    if isinstance(english_claim_or_evidence, list):
        web_evidence = english_claim_or_evidence
        english_claim = claim
    else:
        english_claim = str(english_claim_or_evidence or claim)
    if web_evidence is None:
        web_evidence = []

    classified, rejected = classify_evidence_items(english_claim, web_evidence)
    metrics = compute_consensus_and_metrics(classified, rejected)
    support = metrics["support_count"]
    contradict = metrics["contradict_count"]
    mixed = metrics.get("mixed_count", 0)
    if not metrics["valid_count"]:
        label = "misleading"
        summary = "Unverified: retrieved sources did not contain claim-relevant evidence. Missing evidence does not prove the claim false."
    elif (support > 0 and contradict > 0) or mixed > 0:
        label = "misleading"
        summary = "Misleading: independent evidence contains mixed, nuanced, or conflicting findings."
    elif support > contradict and support >= 1:
        if is_medical_health_claim(english_claim) and _detect_medical_conflict(english_claim, classified):
            label = "misleading"
            summary = "Medical guidelines or regulatory agencies do not corroborate this health claim."
        else:
            label = "true"
            summary = "Supported by the retrieved claim-relevant evidence."
    elif contradict > support:
        label = "false"
        summary = "Contradicted by the retrieved claim-relevant evidence."
    else:
        label = "misleading"
        summary = "Unverified: no decisive evidence stance was established. Missing evidence does not prove the claim false."
    base_conf = 0.85 if metrics["consensus_score"] >= 0.90 else 0.70 if metrics["consensus_score"] >= 0.70 else 0.55
    confidence = compute_calibrated_confidence(label, classified, metrics["consensus_score"], base_conf)
    if not metrics["valid_count"]:
        reasoning = f"Unverified: Insufficient evidence found to verify this claim. Missing evidence does not prove the claim false. ({error_msg[:100]})"
    else:
        reasoning = (
            f"Verifier fallback after: {error_msg[:120]}. Evidence classifier found "
            f"{support} supporting and {contradict} contradicting independent passages."
        )
    return {
        "label": label,
        "confidence": confidence,
        "reasoning": reasoning,
        "summary": summary,
        "evidence": [item.model_dump() for item in classified],
        "unverified": not bool(metrics["valid_count"]),
    }


# ─── Public API ───────────────────────────────────────────────────────────────

def gather_evidence_for_claim(claim_text: str, transcript_text: str = "") -> Dict[str, Any]:
    """
    Main fact-checking entry point:
    1. Detect language & translate claim to English.
    2. Iterative Multi-Round Retrieval:
       - Round 1: Diverse targeted queries (exact claim, scientific/technical terms, counterevidence).
       - Evaluate relevance coverage: if evidence is sparse or off-topic, trigger Round 2 query expansion.
    3. Claim-level stance classification (SUPPORTS, CONTRADICTS, MIXED, IRRELEVANT, INSUFFICIENT).
    4. Epistemic Decision Engine:
       - Absence of evidence or off-topic results -> UNVERIFIABLE, NEVER FALSE.
       - A FALSE verdict requires affirmative, claim-relevant counterevidence.
    5. Mathematically computed independent consensus & calibrated confidence.
    """
    claim = _normalize_text(claim_text)
    transcript = _normalize_text(transcript_text)

    cached = get_cached_verdict(claim)
    if cached:
        return cached

    # Step 1: Translate to English if needed
    english_claim = translate_claim_to_english(claim)

    # ── Step 2: Multi-Round Iterative Retrieval ──
    executed_queries: List[str] = []
    search_runs_trace: List[Dict[str, Any]] = []

    # Round 1
    round1_queries = build_search_queries(english_claim)
    executed_queries.extend(round1_queries)
    try:
        raw_evidence, runs1 = _fetch_web_evidence(round1_queries, claim_text=english_claim)
        search_runs_trace.extend(runs1)
        web_evidence = run_rag_pipeline(english_claim, raw_evidence)
    except Exception as exc:
        print(f"[search] Search retrieval failed: {exc}")
        fb = _llm_knowledge_factcheck(claim, english_claim, transcript)
        metrics = compute_consensus_and_metrics([], [], len(executed_queries), 1)
        metrics["retrieval_error"] = str(exc)
        fb["fact_check_summary"] = metrics
        fb["search_runs"] = search_runs_trace
        fb["queries_executed"] = executed_queries
        fb["retrieval_rounds"] = 1
        fb["stopping_reason"] = "search_api_error_knowledge_fallback"
        return fb
    retrieval_rounds = 1
    stopping_reason = "single_round_sufficient"

    # Classify Round 1 items
    classified_items, rejected_items = classify_evidence_items(english_claim, web_evidence)
    valid_count = sum(
        1 for item in classified_items
        if item.stance in (EvidenceStance.SUPPORTS, EvidenceStance.CONTRADICTS, EvidenceStance.MIXED)
        and item.relevance_score >= 0.40
    )

    # Round 2: Expand queries if evidence is sparse or off-topic
    if valid_count < 2:
        print(f"[search] Evidence sparse or off-topic ({valid_count} relevant items). Initiating Round 2 search expansion...")
        retrieval_rounds = 2
        round2_queries = expand_search_queries(english_claim, executed_queries)
        if round2_queries:
            executed_queries.extend(round2_queries)
            round2_raw, runs2 = _fetch_web_evidence(round2_queries, claim_text=english_claim)
            search_runs_trace.extend(runs2)
            round2_rag = run_rag_pipeline(english_claim, round2_raw)
            # Merge Round 1 and Round 2
            merged_raw = web_evidence + [e for e in round2_rag if e.get("source_url") not in {x.get("source_url") for x in web_evidence}]
            classified_items, rejected_items = classify_evidence_items(english_claim, merged_raw)
            web_evidence = merged_raw
            stopping_reason = "expanded_round_completed"
    else:
        stopping_reason = "sufficient_initial_evidence"

    # Check for client availability
    if not get_llm_client():
        metrics = compute_consensus_and_metrics(classified_items, rejected_items, len(executed_queries), retrieval_rounds)
        return {
            "label": "misleading",
            "unverified": True,
            "confidence": 0.2,
            "reasoning": "Unverified: No verifier model is configured. A transcript is claim context, not independent evidence. Missing evidence does not prove the claim false.",
            "summary": "Unverified: no evidence-backed verification was completed.",
            "evidence": [],
            "search_runs": search_runs_trace,
            "fact_check_summary": metrics,
            "queries_executed": executed_queries,
            "retrieval_rounds": retrieval_rounds,
            "stopping_reason": "no_llm_client",
        }

    # ── Step 3: Epistemic Decision Engine ──
    # Filter for items accepted for LLM reasoning (drop completely irrelevant/rejected items)
    accepted_for_llm = [
        item for item in classified_items
        if item.stance in (EvidenceStance.SUPPORTS, EvidenceStance.PARTIALLY_SUPPORTS, EvidenceStance.CONTRADICTS)
    ]

    # Rule 1: No relevant evidence in web search -> MISLEADING (Unverified: Never infer a verdict without direct evidence)
    if not accepted_for_llm:
        print(f"[search] No direct, claim-relevant web evidence found after {retrieval_rounds} rounds. Returning MISLEADING (Unverified).")
        metrics = compute_consensus_and_metrics(classified_items, rejected_items, len(executed_queries), retrieval_rounds)
        from pipeline.canonical_record import compute_canonical_hash
        c_hash = compute_canonical_hash(english_claim, transcript)
        res = {
            "label": "misleading",
            "unverified": True,
            "confidence": 0.20,
            "reasoning": "Unverified: No claim-relevant, URL-backed evidence was retrieved. Verdict cannot be established without direct corroboration. Missing evidence does not prove the claim false.",
            "summary": "Unverified: external evidence was insufficient or unavailable to establish a verdict.",
            "evidence": [],
            "fact_check_summary": metrics,
            "search_runs": search_runs_trace,
            "queries_executed": executed_queries,
            "retrieval_rounds": retrieval_rounds,
            "stopping_reason": "no_claim_relevant_evidence",
            "canonical_hash": c_hash,
        }
        set_cached_verdict(claim, res)
        return res

    try:
        # Convert accepted items to dict format for LLM reasoning
        accepted_dicts = [item.model_dump() for item in accepted_for_llm]
        result = _run_llm_reasoning(claim, english_claim, transcript, accepted_dicts)

        # ── Step 4: Epistemic Decision Rules Guard ──
        raw_label = _canonical_verdict_label(result.get("label"))

        # Map LLM citations back to classified items
        llm_stance_map = {}
        for ev in result.get("evidence", []):
            url = ev.get("source_url", "")
            if url:
                llm_stance_map[url] = ev

        # Re-classify and compute consensus
        reclassified_items, _ = classify_evidence_items(english_claim, accepted_dicts, llm_stance_map=llm_stance_map)

        valid_supports = [
            item for item in reclassified_items
            if item.stance == EvidenceStance.SUPPORTS and item.relevance_score >= 0.50
        ]
        valid_contradicts = [
            item for item in reclassified_items
            if item.stance == EvidenceStance.CONTRADICTS and item.relevance_score >= 0.50
        ]
        has_med_conflict = _detect_medical_conflict(english_claim, reclassified_items)

        final_label = raw_label

        # RULE 1: Never label a claim TRUE without sufficient direct evidence
        if final_label == "true":
            if valid_contradicts and not valid_supports:
                final_label = "false"
                result["summary"] = "The claim is refuted by verifiable counterevidence."
            elif valid_contradicts and valid_supports:
                if len(valid_contradicts) >= len(valid_supports) or len(valid_contradicts) >= 2:
                    final_label = "misleading"
                    result["summary"] = "The claim is disputed with conflicting findings across credible sources."
            elif has_med_conflict:
                final_label = "misleading"
                result["summary"] = "Medical guidelines or clinical evidence conflict with or do not substantiate this health claim."
            elif not valid_supports:
                final_label = "misleading"
                result["summary"] = "Unverified: retrieved sources contain related context but lack direct evidence confirming this claim. Missing evidence does not prove the claim false."
                result["reasoning"] = (
                    "Unverified: Insufficient direct evidence to establish this claim as true. Missing evidence does not prove the claim false. "
                    + result.get("reasoning", "")
                ).strip()

        # RULE 2: Medical claims with conflicting guidelines cannot be TRUE
        elif is_medical_health_claim(english_claim) and has_med_conflict:
            if final_label != "false":
                final_label = "misleading"
                result["summary"] = "Conflicting medical guidelines or lack of clinical authorization."

        # RULE 3: Contradicted label consistency check
        elif final_label == "false":
            if not valid_contradicts and valid_supports:
                final_label = "true"
                result["summary"] = "The claim is supported by factual and scientific evidence."
            elif not valid_contradicts and not valid_supports:
                final_label = "misleading"
                result["summary"] = "Unverified: insufficient direct counterevidence to definitively refute this claim. Missing evidence does not prove the claim false."

        final_label = _canonical_verdict_label(final_label)
        result["label"] = final_label

        metrics = compute_consensus_and_metrics(reclassified_items, rejected_items, len(executed_queries), retrieval_rounds)
        consensus_score = metrics["consensus_score"]

        # Compute calibrated confidence
        base_conf = float(result.get("confidence", 0.75))
        calibrated_conf = compute_calibrated_confidence(final_label, reclassified_items, consensus_score, base_conf)
        result["confidence"] = calibrated_conf

        # Enrich evidence items with original source page verification and quotations
        from pipeline.page_fetcher import fetch_page_text, verify_and_locate_quote
        from pipeline.canonical_record import compute_canonical_hash, save_canonical_record

        enriched_evidence = []
        for c_item in reclassified_items:
            item_dict = c_item.model_dump()
            url = item_dict.get("source_url", "")
            snippet = item_dict.get("snippet", "")
            p_text = fetch_page_text(url, timeout=3.0) if url else None
            is_v, quote_text, loc = verify_and_locate_quote(p_text, snippet)
            item_dict["quote"] = quote_text or snippet
            item_dict["quote_verified"] = is_v
            item_dict["quote_location"] = loc
            item_dict["publisher"] = item_dict.get("domain", "")
            item_dict["retrieval_timestamp"] = datetime.now(timezone.utc).isoformat()
            enriched_evidence.append(item_dict)

        result["evidence"] = enriched_evidence

        # Canonical Record and reproducible tokening
        c_hash = compute_canonical_hash(english_claim, transcript)
        result["canonical_hash"] = c_hash
        save_canonical_record({
            "canonical_hash": c_hash,
            "original_wording": claim,
            "normalized_claim": english_claim,
            "context": transcript,
            "final_verdict": final_label,
            "confidence": calibrated_conf,
            "consensus_score": consensus_score,
            "reasoning": result.get("reasoning", ""),
            "summary": result.get("summary", ""),
            "evidence": enriched_evidence,
            "search_queries": executed_queries,
            "retrieval_rounds": retrieval_rounds,
        })

        # Attach auditable fields
        result["fact_check_summary"] = metrics
        result["search_runs"] = search_runs_trace
        result["queries_executed"] = executed_queries
        result["retrieval_rounds"] = retrieval_rounds
        result["stopping_reason"] = stopping_reason

        set_cached_verdict(claim, result)
        return result

    except Exception as e:
        print(f"[search] Groq LLM error: {e}")
        metrics = compute_consensus_and_metrics(classified_items, rejected_items, len(executed_queries), retrieval_rounds)
        if accepted_for_llm:
            fb = _keyword_verdict_from_evidence(claim, english_claim, [i.model_dump() for i in accepted_for_llm], str(e))
            fb["fact_check_summary"] = metrics
            fb["search_runs"] = search_runs_trace
            fb["queries_executed"] = executed_queries
            fb["retrieval_rounds"] = retrieval_rounds
            fb["stopping_reason"] = "llm_error_keyword_fallback"
            return fb
        return {
            "label": "misleading",
            "unverified": True,
            "confidence": 0.20,
            "reasoning": f"Verification pipeline encountered an error: {e}. External evidence was insufficient or inaccessible. Missing evidence does not prove the claim false.",
            "summary": "Unverified: evidence was insufficient or inaccessible to reach a verdict.",
            "evidence": [item.model_dump() for item in classified_items[:4]],
            "fact_check_summary": metrics,
            "search_runs": search_runs_trace,
            "queries_executed": executed_queries,
            "retrieval_rounds": retrieval_rounds,
            "stopping_reason": "error",
        }
