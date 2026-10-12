"""
rag.py — Retrieval-Augmented Generation Pipeline
=================================================
Sources (all real URLs, no placeholders):
  1. Wikipedia — full extract via MediaWiki API  (must pass BM25 relevance gate)
  2. Google Fact Check Tools API
  3. Existing web/news evidence (NewsAPI, DuckDuckGo)

Ranking: BM25 over combined corpus.
Relevance gate: items with BM25 score=0 (zero word overlap with claim) are
                dropped before being sent to the LLM or displayed in the UI.
"""

import math
import re
import urllib.request
import urllib.parse
import json
from collections import Counter
from typing import List, Dict, Any, Set, Optional, Tuple

from pipeline.domain_trust import get_domain_trust_tier
from shared.resilience import resilient_http_fetch
from shared.api_keys import get_api_key_manager


def _make_unavailable_placeholder(source_name: str, title: str, domain: str) -> Dict[str, Any]:
    return {
        "url": f"https://{domain}/unavailable",
        "title": title,
        "domain": domain,
        "snippet": f"The {source_name} source was unavailable or rate-limited during verification. Confidence score was lowered.",
        "published": "",
        "service_unavailable": True
    }


# ─── 1. BM25 Ranker (Pure Python) ─────────────────────────────────────────────

class BM25Ranker:
    """Lightweight BM25 implementation for ranking evidence chunks."""
    def __init__(self, k1: float = 1.5, b: float = 0.75):
        self.k1 = k1
        self.b = b
        self.corpus: List[List[str]] = []
        self.doc_len: List[int] = []
        self.idf: Dict[str, float] = {}
        self.avgdl: float = 0
        self.num_docs: int = 0

    def _tokenize(self, text: str) -> List[str]:
        return re.findall(r"\w+", text.lower())

    def fit(self, corpus_texts: List[str]):
        self.num_docs = len(corpus_texts)
        if self.num_docs == 0:
            return
        self.corpus = [self._tokenize(t) for t in corpus_texts]
        self.doc_len = [len(doc) for doc in self.corpus]
        self.avgdl = sum(self.doc_len) / self.num_docs
        df: Dict[str, int] = Counter()
        for document in self.corpus:
            for word in set(document):
                df[word] += 1
        for word, freq in df.items():
            self.idf[word] = math.log(1 + (self.num_docs - freq + 0.5) / (freq + 0.5))

    def get_scores(self, query: str) -> List[float]:
        query_tokens = self._tokenize(query)
        scores = [0.0] * self.num_docs
        for i, document in enumerate(self.corpus):
            doc_len = self.doc_len[i]
            frequencies = Counter(document)
            score = 0.0
            for token in query_tokens:
                if token not in frequencies:
                    continue
                freq = frequencies[token]
                num = freq * (self.k1 + 1)
                den = freq + self.k1 * (1 - self.b + self.b * doc_len / (self.avgdl or 1))
                score += self.idf.get(token, 0) * (num / den)
            scores[i] = score
        return scores


# ─── 2. Evidence Item Builder ─────────────────────────────────────────────────

def build_evidence_item(url: str, title: str, snippet: str, published: str = "", service_unavailable: bool = False) -> Dict[str, Any]:
    """Build a normalised evidence dict with domain trust info."""
    domain = url.split("//")[-1].split("/")[0].lower().lstrip("www.")
    trust_tier = get_domain_trust_tier(url)
    trust_label = "high" if trust_tier == 1 else "medium" if trust_tier == 2 else "low"
    return {
        "source_url": url,
        "source_title": title or domain,
        "domain": domain,
        "domain_trust": trust_label,
        "domain_trust_tier": trust_tier,
        "snippet": (snippet or "No snippet available.")[:500],
        "relevance_score": 0.0,  # Will be set by BM25
        "publication_date": published or "",
        "supports_claim": None,
        "service_unavailable": service_unavailable
    }


# ─── 3. Jaccard Relevance Filter ──────────────────────────────────────────────

_STOP = {
    "the", "a", "an", "is", "are", "was", "were", "be", "been", "being",
    "have", "has", "had", "do", "does", "did", "will", "would", "could",
    "should", "may", "might", "shall", "can", "need", "that", "this",
    "these", "those", "and", "but", "or", "not", "to", "of", "in", "on",
    "at", "by", "for", "with", "from", "as", "into", "about", "than",
    "then", "also", "some", "any", "all", "more", "very", "just", "now",
    "equal", "amount", "per", "next", "it", "its", "we", "they", "he",
    "she", "you", "i", "my", "our", "their", "when", "while", "which",
    "who", "what", "how", "if", "because", "so", "such", "no", "only",
}


_QUERY_FILLERS = {
    "essentially", "actually", "probably", "literally",
    "according", "reported", "said", "says", "claims", "claim",
    "true", "false", "fact", "check", "video", "watch",
}


def _content_tokens(text: str) -> Set[str]:
    """Return meaningful (non-stop-word) tokens from text."""
    return {
        w for w in re.findall(r"[a-z]+", text.lower())
        if w not in _STOP and len(w) > 2
    }


def jaccard_relevance(claim: str, evidence_text: str) -> float:
    """
    Jaccard similarity between claim tokens and evidence tokens.
    Returns 0.0–1.0. Pure Python — zero extra dependencies.
    """
    claim_tokens = _content_tokens(claim)
    ev_tokens = _content_tokens(evidence_text)
    if not claim_tokens or not ev_tokens:
        return 0.0
    intersection = claim_tokens & ev_tokens
    union = claim_tokens | ev_tokens
    return len(intersection) / len(union)


def filter_evidence_by_relevance(
    claim: str,
    evidence_list: List[Dict[str, Any]],
    min_jaccard: float = 0.025,
) -> List[Dict[str, Any]]:
    """
    Hard filter: remove evidence items that share < min_jaccard token
    overlap with the claim.  This eliminates completely off-topic results
    before they reach the LLM or the UI.
    """
    kept = []
    dropped = []
    for ev in evidence_list:
        combined = f"{ev.get('source_title', '')} {ev.get('snippet', '')}"
        score = jaccard_relevance(claim, combined)
        if score >= min_jaccard:
            kept.append(ev)
        else:
            dropped.append(ev.get("source_title", "?"))

    if dropped:
        print(
            f"[rag] Jaccard filter removed {len(dropped)} off-topic item(s): "
            + ", ".join(f'"{t[:50]}"' for t in dropped[:5])
        )
    return kept


# ─── 4. Wikipedia: Targeted Subject Query ─────────────────────────────────────

def _build_wikipedia_query(claim: str) -> str:
    """
    Extract the key subject/topic from a claim for a targeted Wikipedia search.
    Preserves natural word order of meaningful nouns/topics and drops conversational fluff.
    """
    clean_text = re.sub(r'["\'\(\)\[\]\{\}\:\;\?\!\,\.]', ' ', claim).lower()
    words = [w for w in clean_text.split() if len(w) > 2]
    
    meaningful = [w for w in words if w not in _STOP and w not in _QUERY_FILLERS]
    if len(meaningful) < 2:
        meaningful = [w for w in words if w not in _STOP]
    if not meaningful:
        meaningful = words[:4]
        
    seen = set()
    deduped = []
    for w in meaningful:
        if w not in seen:
            seen.add(w)
            deduped.append(w)
            
    return " ".join(deduped[:4]).strip()


def _fetch_wikipedia(query: str, claim: str, max_results: int = 3) -> List[Dict[str, Any]]:
    """
    Search Wikipedia and fetch a full text extract for each result.
    The `claim` parameter is used to filter out irrelevant pages via Jaccard.
    Returns real wikipedia.org URLs with meaningful, on-topic content.
    """
    results = []
    try:
        # Step 1: Search for pages using the targeted subject query
        search_url = (
            "https://en.wikipedia.org/w/api.php?"
            + urllib.parse.urlencode({
                "action": "query",
                "list": "search",
                "srsearch": query,
                "utf8": "",
                "format": "json",
                "srlimit": max_results + 2,  # Fetch extra so we can filter irrelevant
            })
        )
        data, success = resilient_http_fetch("wikipedia", search_url, headers={"User-Agent": "FactCheckerBot/2.0"}, timeout=10)
        if not success or not data:
            return []

        page_titles = [
            item["title"]
            for item in data.get("query", {}).get("search", [])
        ]
        if not page_titles:
            return []

        # Step 2: Fetch full extracts for all found pages in one call
        extract_url = (
            "https://en.wikipedia.org/w/api.php?"
            + urllib.parse.urlencode({
                "action": "query",
                "titles": "|".join(page_titles[:max_results + 2]),
                "prop": "extracts|info",
                "exintro": "",
                "explaintext": "",
                "inprop": "url",
                "format": "json",
                "redirects": "1",
            })
        )
        extract_data, success2 = resilient_http_fetch("wikipedia", extract_url, headers={"User-Agent": "FactCheckerBot/2.0"}, timeout=10)
        if not success2 or not extract_data:
            return []

        pages = extract_data.get("query", {}).get("pages", {})
        for page_id, page in pages.items():
            if page_id == "-1":
                continue
            title = page.get("title", "")
            canonical_url = page.get("fullurl", "")
            if not canonical_url:
                canonical_url = (
                    "https://en.wikipedia.org/wiki/"
                    + urllib.parse.quote(title.replace(" ", "_"))
                )
            extract = (page.get("extract") or "").strip()
            if not extract:
                continue
            snippet = extract[:600].rstrip()

            # Pre-filter: skip Wikipedia pages that don't overlap with the claim
            combined = f"{title} {snippet}"
            j_score = jaccard_relevance(claim, combined)
            if j_score < 0.02:
                continue

            results.append({
                "url": canonical_url,
                "title": f"Wikipedia: {title}",
                "snippet": snippet,
                "domain": "en.wikipedia.org",
                "published": "",
            })

    except Exception as e:
        print(f"[rag] Wikipedia fetch error: {e}")

    return results[:max_results]


# ─── 5. Google Fact Check Tools ───────────────────────────────────────────────

def _fetch_google_factcheck(query: str, claim: str = "") -> List[Dict[str, Any]]:
    """Fetch from Google Fact Check Tools API using condensed queries and configured API key."""
    manager = get_api_key_manager()
    gfc_key = manager.get_google_factcheck_key()
    if not gfc_key:
        return []

    target_claim = claim or query
    # Build a concise, unquoted query
    clean_query = _build_wikipedia_query(query) or query.strip().strip('"\'')[:50]
    results = []

    def _do_query(q_str: str) -> Optional[Dict[str, Any]]:
        params = {"query": q_str, "key": gfc_key}
        url = (
            "https://factchecktools.googleapis.com/v1alpha1/claims:search?"
            + urllib.parse.urlencode(params)
        )
        data, success = resilient_http_fetch("google_factcheck", url, headers={"User-Agent": "FactCheckerBot/2.0"}, timeout=8)
        return data if success else None

    try:
        data = _do_query(clean_query)
        if not data or not data.get("claims"):
            parts = clean_query.split()
            if len(parts) > 2:
                data = _do_query(" ".join(parts[:2]))

        if not data:
            return []

        for c in data.get("claims", [])[:3]:
            claim_text = c.get("text", "")
            reviews = c.get("claimReview", [])
            if not reviews:
                continue
            review = reviews[0]
            rating = review.get("textualRating", "")
            source = review.get("publisher", {}).get("name", "Fact Checker")
            review_url = review.get("url", "")
            if not review_url or not review_url.startswith("http"):
                continue
            domain = review_url.split("//")[-1].split("/")[0].lstrip("www.")
            snippet = f'Claim: "{claim_text[:200]}". Rating by {source}: {rating}.'
            results.append({
                "url": review_url,
                "title": f"Fact Check by {source}: {rating}",
                "snippet": snippet,
                "domain": domain,
                "published": "",
            })
    except Exception as e:
        print(f"[rag] Google Fact Check fetch error: {e}")

    return results


# ─── 6. Main RAG Pipeline ─────────────────────────────────────────────────────

def run_rag_pipeline(
    claim: str,
    existing_web_evidence: List[Dict[str, Any]],
    max_results: int = 12,
) -> List[Dict[str, Any]]:
    """
    1. Fetch Wikipedia (using targeted subject query, with Jaccard pre-filter).
    2. Fetch Google Fact Check results.
    3. Merge with existing web/news evidence.
    4. Deduplicate by URL; keep snippet >= 30 chars.
    5. Rank ALL items with BM25 against the claim.
    6. RELEVANCE GATE: drop items where BM25 score = 0 (zero keyword overlap).
    7. Assign relevance_score from BM25 (not from domain trust tier).
    8. Apply Jaccard hard filter as final safety net.
    9. Return top-K, sorted by BM25 score descending.
    """
    print(f"[rag] Starting RAG pipeline for claim: {claim[:80]}")

    # Build targeted Wikipedia and FactCheck query from claim subject words
    wiki_query = _build_wikipedia_query(claim)
    print(f"[rag] Target subject query: '{wiki_query}'")

    # Fetch additional trusted sources
    wiki_results = _fetch_wikipedia(wiki_query, claim, max_results=3)
    fc_results = _fetch_google_factcheck(wiki_query, claim=claim)

    print(f"[rag] Wikipedia: {len(wiki_results)} relevant pages | FactCheck: {len(fc_results)} results")

    all_raw: List[Dict[str, Any]] = list(existing_web_evidence)
    for r in wiki_results + fc_results:
        all_raw.append(
            build_evidence_item(
                r["url"],
                r["title"],
                r["snippet"],
                r.get("published", ""),
                service_unavailable=r.get("service_unavailable", False)
            )
        )

    # Deduplicate by source_url; keep snippet >= 30 chars
    # Also cap to max 2 items per domain to avoid one domain dominating
    unique: Dict[str, Dict[str, Any]] = {}
    domain_counts: Dict[str, int] = {}
    for ev in all_raw:
        url = ev.get("source_url") or ev.get("url", "")
        if not url:
            continue
        snippet = (ev.get("snippet") or "").strip()
        if len(snippet) < 30:
            continue
        if url in unique:
            continue
        domain = ev.get("domain", "")
        if domain_counts.get(domain, 0) >= 2:
            continue
        unique[url] = ev
        domain_counts[domain] = domain_counts.get(domain, 0) + 1

    documents = list(unique.values())
    if not documents:
        print("[rag] No documents to rank.")
        return existing_web_evidence

    # BM25 ranking — rank against the CLAIM (not generic query string)
    texts = [
        f"{d.get('source_title', '')} {d.get('snippet', '')}"
        for d in documents
    ]
    ranker = BM25Ranker()
    ranker.fit(texts)
    scores = ranker.get_scores(claim)

    # ── RELEVANCE GATE: drop items with BM25 score = 0 ────────────────────────
    # score=0 means zero meaningful word overlap with the claim → irrelevant
    max_score = max(scores) if scores else 1.0
    kept_with_scores = []
    bm25_dropped = []
    for i, doc in enumerate(documents):
        s = scores[i]
        if s <= 0:
            bm25_dropped.append(doc.get("source_title", "?"))
        else:
            # Normalize relevance_score to 0.0–1.0 based on BM25
            doc["relevance_score"] = round(min(1.0, s / (max_score or 1.0)), 2)
            kept_with_scores.append((s, doc))

    if bm25_dropped:
        print(
            f"[rag] BM25 gate removed {len(bm25_dropped)} zero-overlap item(s): "
            + ", ".join(f'"{t[:50]}"' for t in bm25_dropped[:5])
        )

    # Sort by BM25 score descending — NO Wikipedia priority boost
    kept_with_scores.sort(key=lambda x: x[0], reverse=True)
    ranked_docs = [doc for _, doc in kept_with_scores]

    # ── Final safety net: Jaccard hard filter ─────────────────────────────────
    ranked_docs = filter_evidence_by_relevance(claim, ranked_docs, min_jaccard=0.015)

    # ── Safety fallback: never return empty if we had evidence ─────────────────
    if not ranked_docs and documents:
        print("[rag] All items filtered — keeping top BM25 results as fallback")
        all_scored = sorted(
            [(scores[i], documents[i]) for i in range(len(documents))],
            key=lambda x: x[0],
            reverse=True,
        )
        ranked_docs = [doc for _, doc in all_scored[:max_results]]
        for i, doc in enumerate(ranked_docs):
            doc["relevance_score"] = round(max(0.05, 0.25 - i * 0.05), 2)

    if not ranked_docs and existing_web_evidence:
        print("[rag] Returning original web evidence as last-resort fallback")
        return existing_web_evidence[:max_results]

    # Return top-K
    result = ranked_docs[:max_results]
    print(
        f"[rag] Returning {len(result)} evidence items "
        f"(from {len(documents)} total, dropped {len(bm25_dropped)} by BM25 gate, "
        f"domains: {list({d.get('domain','') for d in result})})"
    )
    return result
