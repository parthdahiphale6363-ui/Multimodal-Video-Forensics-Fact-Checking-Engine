"""
osint.py — Open-Source Intelligence (OSINT) Collection Module
=============================================================
Collects and analyzes OSINT evidence:
  1. News Verification       — search for news coverage of claims/topics
  2. Social Media Signals    — search for social media discussion
  3. Reverse Search Hints    — construct image/video reverse search queries
  4. Geolocation Verification — verify geographic claims via web search
  5. Timestamp Verification  — cross-check dates and events
  6. Weather Verification    — validate weather-related claims
  7. Source Authority Check  — assess source credibility
"""

import os
import re
import json
import time
import warnings
import datetime
import urllib.request
import urllib.parse
from typing import Any, Dict, List, Optional
from collections import Counter

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

from shared.llm import get_llm_client, get_llm_model, call_llm_with_fallback
from shared.news_client import search_newsapi, groq_analyze_news_for_claim, build_search_topic, filter_relevant_news, is_junk_news_domain
from shared.resilience import execute_with_resilience


# ─── Helpers ──────────────────────────────────────────────────────────────────

HIGH_CREDIBILITY_DOMAINS = {
    "reuters.com", "apnews.com", "bbc.com", "bbc.co.uk", "nytimes.com",
    "washingtonpost.com", "theguardian.com", "snopes.com", "factcheck.org",
    "politifact.com", "fullfact.org", "afp.com", "bloomberg.com", "ft.com",
    "nature.com", "science.org", "nejm.org", "who.int", "cdc.gov", "nih.gov",
    "gov.uk", "europa.eu", "un.org", "aljazeera.com", "npr.org", "abc.net.au",
    # Indian sources
    "thehindu.com", "ndtv.com", "indianexpress.com", "timesofindia.indiatimes.com",
    "hindustantimes.com", "livemint.com", "businessstandard.com", "thewire.in",
    "scroll.in", "boomlive.in", "factchecker.in", "vishvasnews.com",
    "pib.gov.in", "india.gov.in",
}

LOW_CREDIBILITY_DOMAINS = {
    "beforeitsnews.com", "naturalnews.com", "infowars.com", "breitbart.com",
    "thegatewaypundit.com", "worldtruth.tv", "yournewswire.com",
}


def _get_domain_trust(url: str) -> str:
    domain = url.split("//")[-1].split("/")[0].lower().lstrip("www.")
    if any(hd in domain for hd in HIGH_CREDIBILITY_DOMAINS):
        return "high"
    if any(ld in domain for ld in LOW_CREDIBILITY_DOMAINS):
        return "low"
    return "medium"


def _ddg_search(query: str, max_results: int = 5, news: bool = False) -> List[Dict]:
    """Perform a DuckDuckGo search with retry on rate limit and fallback to text search."""
    if not DDGS:
        return []

    clean_q = re.sub(r'["\'\(\)\[\]\{\}\:\;\?\!\,\.]', ' ', query).strip()
    words = [w for w in clean_q.split() if len(w) > 2]
    condensed_q = " ".join(words[:6]) if words else clean_q[:50]

    def _do_search():
        with DDGS(timeout=4) as ddgs:
            raw = []
            if news:
                try:
                    raw = list(ddgs.news(condensed_q, max_results=max_results))
                except Exception as e:
                    err_s = str(e).lower()
                    if "403" in err_s or "ratelimit" in err_s or "connect" in err_s or "eof" in err_s:
                        # Fallback cleanly to text news search
                        raw = list(ddgs.text(f"{condensed_q} news", max_results=max_results))
                    else:
                        raise
            else:
                raw = list(ddgs.text(condensed_q, max_results=max_results))
            results = []
            for r in raw:
                url = r.get("href") or r.get("url") or ""
                results.append({
                    "url": url,
                    "title": r.get("title", ""),
                    "snippet": r.get("body") or r.get("excerpt") or "",
                    "domain": url.split("//")[-1].split("/")[0].lstrip("www."),
                    "domain_trust": _get_domain_trust(url),
                    "published_date": (r.get("date") or "")[:10],
                })
            return results

    res, success = execute_with_resilience("ddg", _do_search)
    if success and res:
        return res
    return []


def _call_groq_osint(system_prompt: str, user_prompt: str, max_tokens: int = 500) -> Optional[str]:
    client = get_llm_client()
    if not client:
        return "Could not generate OSINT summary: LLM client not configured."

    try:
        response = call_llm_with_fallback(
            client=client,
            model=get_llm_model(),
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.0,
            max_tokens=max_tokens,
        )
        if response.choices:
            return getattr(response.choices[0].message, "content", "") or ""
    except Exception as e:
        print(f"[osint] Groq OSINT API error: {e}")
    return None


# ─── 8. Google Fact Check Tools API ──────────────────────────────────────────

def verify_via_google_factcheck(claims: List[str]) -> Dict[str, Any]:
    """
    Query Google Fact Check Tools API for claims and return authoritative IFCN debunks.
    """
    from shared.api_keys import get_api_key_manager
    api_key = os.environ.get("GOOGLE_FACTCHECK_API_KEY", "").strip() or get_api_key_manager().get_google_factcheck_key() or ""
    if not api_key:
        return {
            "fact_checks_found": [],
            "debunked_count": 0,
            "verified_true_count": 0,
            "manipulated_count": 0,
            "total_reviews": 0,
            "factcheck_summary": "Google Fact Check API key not configured.",
        }

    fact_checks = []
    debunked_count = 0
    verified_true_count = 0
    manipulated_count = 0

    from shared.news_client import condense_search_query
    for claim in claims[:3]:
        query = condense_search_query(claim, max_words=4)
        if len(query) < 3:
            continue
        try:
            def _fetch_api(q_str: str):
                encoded_q = urllib.parse.quote(q_str)
                url = f"https://factchecktools.googleapis.com/v1alpha1/claims:search?query={encoded_q}&key={api_key}&languageCode=en"
                req = urllib.request.Request(url, headers={"User-Agent": "FactChecker/1.0"})
                with urllib.request.urlopen(req, timeout=6) as resp:
                    return json.loads(resp.read().decode("utf-8"))

            data = _fetch_api(query)
            api_claims = data.get("claims", [])
            if not api_claims and len(query.split()) > 2:
                data = _fetch_api(" ".join(query.split()[:2]))
                api_claims = data.get("claims", [])

            for ac in api_claims[:2]:
                reviews = ac.get("claimReview", [])
                for cr in reviews:
                    rating = (cr.get("textualRating") or "").strip()
                    rating_lower = rating.lower()
                    publisher = cr.get("publisher", {}).get("name", "Certified Fact-Checker")
                    review_url = cr.get("url", "")
                    title = cr.get("title") or ac.get("text", "")

                    is_debunk = any(w in rating_lower for w in ["false", "fake", "hoax", "incorrect", "pants on fire", "myth", "debunked"])
                    is_manipulated = any(w in rating_lower for w in ["manipulated", "altered", "out of context", "misleading", "partly false", "recycled"])
                    is_true = any(w in rating_lower for w in ["true", "correct", "verified", "accurate"])

                    if is_debunk:
                        debunked_count += 1
                    elif is_manipulated:
                        manipulated_count += 1
                    elif is_true:
                        verified_true_count += 1

                    fact_checks.append({
                        "claim_queried": query[:80],
                        "publisher": publisher,
                        "review_url": review_url,
                        "title": title[:100],
                        "rating": rating,
                        "is_debunk": is_debunk or is_manipulated,
                    })
        except Exception as e:
            print(f"[osint] Google Fact Check API error for '{query[:30]}': {e}")

    summary = (
        f"Google Fact Check API: Found {len(fact_checks)} authoritative reviews. "
        f"Debunked: {debunked_count}, Manipulated: {manipulated_count}, True: {verified_true_count}."
        if fact_checks else "No matching reviews found in Google Fact Check Tools database."
    )

    return {
        "fact_checks_found": fact_checks,
        "debunked_count": debunked_count,
        "manipulated_count": manipulated_count,
        "verified_true_count": verified_true_count,
        "total_reviews": len(fact_checks),
        "factcheck_summary": summary,
    }


# ─── 7. Source Authority Check (Wayback & WHOIS) ─────────────────────────────

def _check_wayback_machine(url: str) -> bool:
    """Check if URL exists in Wayback Machine (Internet Archive)."""
    if not url:
        return False
    try:
        api_url = f"https://archive.org/wayback/available?url={urllib.parse.quote(url)}"
        req = urllib.request.Request(api_url, headers={"User-Agent": "FactChecker/1.0"})
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            snapshots = data.get("archived_snapshots", {})
            return "closest" in snapshots
    except Exception as e:
        print(f"[osint] Wayback fetch error for {url}: {e}")
    return False

def _check_domain_age(domain: str) -> str:
    """Basic WHOIS check for domain age (mocked fallback if API fails)."""
    if not domain:
        return "unknown"
    # A real WHOIS API would be called here. We'll use a placeholder logic for now
    # that flags domains typically associated with temporary/fake sites.
    suspicious_tlds = [".xyz", ".top", ".club", ".online", ".site", ".tk", ".cf"]
    if any(domain.endswith(t) for t in suspicious_tlds):
        return "suspiciously_new"
    return "established"

def verify_source_authority(urls: List[str]) -> Dict[str, Any]:
    wayback_hits = 0
    suspicious_domains = []
    
    from concurrent.futures import ThreadPoolExecutor

    urls_to_check = urls[:5]
    if urls_to_check:
        with ThreadPoolExecutor(max_workers=len(urls_to_check)) as executor:
            wayback_results = list(executor.map(_check_wayback_machine, urls_to_check))
            wayback_hits = sum(1 for r in wayback_results if r)
        
    for url in urls_to_check:
        domain = url.split("//")[-1].split("/")[0].lstrip("www.")
        if _check_domain_age(domain) == "suspiciously_new":
            suspicious_domains.append(domain)
            
    return {
        "wayback_archived_count": wayback_hits,
        "suspicious_domains": suspicious_domains,
        "source_authority_summary": f"{wayback_hits} sources archived in Wayback Machine. " +
                                    (f"⚠️ {len(suspicious_domains)} suspicious domains detected." if suspicious_domains else "No highly suspicious domains found.")
    }


# ─── 1. News Verification ────────────────────────────────────────────────────

def _newsapi_search_osint(query: str, page_size: int = 10, topic: str = "") -> List[Dict]:
    """Fetch recent news articles from NewsAPI for OSINT verification."""
    articles = search_newsapi(query, page_size=page_size, topic=topic or query)
    results = []
    for art in articles:
        if is_junk_news_domain(art.get("url", "")):
            continue
        results.append({
            "url": art["url"],
            "title": art["title"],
            "snippet": art.get("snippet", "")[:250],
            "domain": art.get("domain", ""),
            "domain_trust": _get_domain_trust(art["url"]),
            "published_date": art.get("published_date", ""),
        })
    return results


def verify_via_news(claims: List[str], transcript_snippet: str) -> Dict[str, Any]:
    """
    Search for news coverage of the key claims/topics.
    Uses NewsAPI (single NEWS_API_KEY) + DuckDuckGo, enhanced by Groq analysis.
    """
    news_results = []
    contradiction_count = 0
    support_count = 0

    # Build focused topic from claims (not raw transcript words)
    main_topic = build_search_topic(claims, transcript_snippet)
    print(f"[osint] News search topic: '{main_topic}'")

    if not claims:
        print("[osint] No claims yet — skipping news verification until claims are extracted.")
        return {
            "news_results": [],
            "total_news_found": 0,
            "high_trust_sources": 0,
            "fact_check_sources": 0,
            "contradiction_count": 0,
            "support_count": 0,
            "groq_news_analysis": "",
            "news_summary": "News verification pending — waiting for claim extraction.",
        }

    print("[osint] Querying News APIs for news verification...")

    from concurrent.futures import ThreadPoolExecutor

    from shared.news_client import condense_search_query

    tasks = []

    # 1. News searches for each claim using condensed query
    for claim in claims[:3]:
        condensed_claim = condense_search_query(claim, max_words=4)
        if condensed_claim:
            tasks.append((_newsapi_search_osint, condensed_claim, 6, condensed_claim))

    # 2. Main topic news search
    if main_topic:
        tasks.append((_newsapi_search_osint, main_topic, 8, main_topic))

    # 3. DuckDuckGo news for main topic
    if main_topic:
        tasks.append((_ddg_search, f"{main_topic} news", 5, True))

    # 4. DuckDuckGo fact-check for top claim
    if claims:
        condensed_top = condense_search_query(claims[0], max_words=4)
        if condensed_top:
            tasks.append((_ddg_search, f"{condensed_top} fact check", 4, False))

    futures = []
    with ThreadPoolExecutor(max_workers=min(len(tasks) or 1, 3)) as executor:
        for t in tasks:
            func, q, size = t[0], t[1], t[2]
            if func is _ddg_search:
                news_flag = t[3] if len(t) > 3 else False
                futures.append(executor.submit(func, q, size, news_flag))
            else:
                topic = t[3] if len(t) > 3 else q
                futures.append(executor.submit(func, q, size, topic))

        for future in futures:
            try:
                res = future.result()
                if res:
                    for r in res:
                        url = r.get("url", "")
                        if is_junk_news_domain(url):
                            continue
                        snippet_lower = r.get("snippet", "").lower()
                        if any(w in snippet_lower for w in ["false", "debunked", "misinformation", "incorrect", "misleading", "fake", "myth", "not recommended"]):
                            contradiction_count += 1
                        elif any(w in snippet_lower for w in ["confirmed", "true", "verified", "correct", "accurate", "recommended"]):
                            support_count += 1
                    news_results.extend(res)
            except Exception as e:
                print(f"[osint] Concurrent search task failed: {e}")

    # Deduplicate and filter by relevance to main topic
    seen = set()
    unique_results = []
    for r in news_results:
        url = r.get("url", "")
        if url and url not in seen and not is_junk_news_domain(url):
            seen.add(url)
            unique_results.append(r)

    unique_results = filter_relevant_news(
        [{"url": r["url"], "title": r.get("title", ""), "snippet": r.get("snippet", ""), **r} for r in unique_results],
        main_topic,
        min_jaccard=0.02,
    )
    # Restore full dict structure after filter
    unique_results = [
        {**r, "domain": r.get("domain", r["url"].split("//")[-1].split("/")[0]), "domain_trust": _get_domain_trust(r["url"])}
        for r in unique_results
    ]

    high_trust = [r for r in unique_results if r["domain_trust"] == "high"]
    fact_check_sources = [r for r in unique_results if any(
        fc in r["domain"] for fc in ["snopes", "factcheck", "politifact", "fullfact", "reuters",
                                     "apnews", "boomlive", "factchecker", "vishvasnews"]
    )]

    # Groq-enhanced news analysis on top results
    groq_support = 0
    groq_contradict = 0
    groq_summary = ""
    primary_claim = claims[0] if claims else main_topic
    if unique_results and primary_claim:
        groq_analysis = groq_analyze_news_for_claim(primary_claim, unique_results[:15])
        groq_support = groq_analysis.get("support_count", 0)
        groq_contradict = groq_analysis.get("contradiction_count", 0)
        groq_summary = groq_analysis.get("groq_summary", "")
        # Merge Groq stance into results
        scored_map = {a["url"]: a for a in groq_analysis.get("scored_articles", [])}
        for r in unique_results:
            meta = scored_map.get(r.get("url", ""))
            if meta:
                r["groq_stance"] = meta.get("groq_stance")
                r["groq_relevance"] = meta.get("groq_relevance")

    total_support = support_count + groq_support
    total_contradict = contradiction_count + groq_contradict

    return {
        "news_results": unique_results[:20],
        "total_news_found": len(unique_results),
        "high_trust_sources": len(high_trust),
        "fact_check_sources": len(fact_check_sources),
        "contradiction_count": total_contradict,
        "support_count": total_support,
        "groq_news_analysis": groq_summary,
        "news_summary": (
            f"Found {len(unique_results)} news sources "
            f"({len(high_trust)} high-trust, {len(fact_check_sources)} fact-check). "
            f"{total_contradict} sources contradict claims, {total_support} support them. "
            + (groq_summary if groq_summary else "")
        ),
    }


# ─── 2. Social Media Signals ─────────────────────────────────────────────────

SOCIAL_PLATFORMS = ["twitter", "reddit", "facebook", "instagram", "tiktok"]


def collect_social_signals(claims: List[str], topic: str) -> Dict[str, Any]:
    """
    Search for social media discussion around the claims/topic.
    """
    social_results = []
    viral_indicators = []

    # Search Reddit for discussions
    reddit_query = f"site:reddit.com {topic[:50]}"
    reddit_results = _ddg_search(reddit_query, max_results=3)
    for r in reddit_results:
        r["platform"] = "Reddit"
    social_results.extend(reddit_results)

    # Search Twitter/X discussions
    twitter_query = f"site:twitter.com OR site:x.com {topic[:40]}"
    twitter_results = _ddg_search(twitter_query, max_results=2)
    for r in twitter_results:
        r["platform"] = "Twitter/X"
    social_results.extend(twitter_results)

    # Check for virality signals in snippets
    for r in social_results:
        snippet = r.get("snippet", "").lower()
        if any(w in snippet for w in ["viral", "trending", "millions of views", "shared widely"]):
            viral_indicators.append(r.get("title", "")[:60])

    # Assess social media manipulation indicators
    manipulation_keywords = ["bot", "astroturfing", "coordinated", "troll", "fake accounts", "brigading"]
    manipulation_signals = []
    for r in social_results:
        snippet = r.get("snippet", "").lower()
        found = [kw for kw in manipulation_keywords if kw in snippet]
        if found:
            manipulation_signals.append(f"'{', '.join(found)}' mentioned in: {r.get('title', '')[:50]}")

    return {
        "social_results": social_results[:6],
        "platforms_found": list(set(r.get("platform", "Web") for r in social_results)),
        "viral_indicators": viral_indicators[:3],
        "manipulation_signals": manipulation_signals[:3],
        "total_social_found": len(social_results),
        "social_summary": (
            f"Social media: {len(social_results)} discussions found. "
            + (f"Viral indicators: {len(viral_indicators)}. " if viral_indicators else "")
            + (f"Manipulation signals: {len(manipulation_signals)}." if manipulation_signals else "No manipulation signals detected.")
        ),
    }


# ─── 3. Reverse Search Hints ─────────────────────────────────────────────────

RECYCLED_FOOTAGE_KEYWORDS = [
    "old video", "recycled footage", "years old", "from 2014", "from 2015",
    "from 2016", "from 2017", "from 2018", "from 2019", "from 2020", "from 2021", "from 2022",
    "archive video", "original footage", "recycled", "out of context", "unrelated incident",
    "staged clip", "shared as recent", "falsely shared as", "not from", "actually happened in",
]


def build_reverse_search_queries(video_url: str, transcript_snippet: str, locations: List[str]) -> Dict[str, Any]:
    """
    Build reverse image/video search query suggestions and perform web searches
    to verify if the video content has been misrepresented or recycled from older events.
    """
    queries = []
    search_results = []

    # Build reverse video search queries
    location_str = " ".join(locations[:2]) if locations else ""
    topic_words = " ".join(transcript_snippet.split()[:8])

    queries.append(f'"{topic_words}" original video source')
    if location_str:
        queries.append(f'"{location_str}" video original footage')
    queries.append(f'"{topic_words}" old footage OR archive')
    queries.append(f'"{topic_words}" fact check recycled OR "old video"')

    # Perform searches
    for q in queries[:3]:
        results = _ddg_search(q, max_results=3)
        search_results.extend(results)

    # Check for "old video" reuse patterns
    old_video_signals = []
    for r in search_results:
        text_to_check = (r.get("title", "") + " " + r.get("snippet", "")).lower()
        matched = [kw for kw in RECYCLED_FOOTAGE_KEYWORDS if kw in text_to_check]
        if matched:
            old_video_signals.append(f"Match [{', '.join(matched[:2])}] in: {r.get('title', '')[:60]}")

    recycled_detected = len(old_video_signals) > 0

    return {
        "suggested_queries": queries,
        "reverse_search_results": search_results[:6],
        "old_video_reuse_signals": old_video_signals,
        "potential_recycled_content": recycled_detected,
        "recycled_footage_detected": recycled_detected,
        "reverse_search_summary": (
            f"Reverse search: {len(search_results)} results. "
            + (f"⚠️ {len(old_video_signals)} recycled/old footage reuse signals detected!" if recycled_detected
               else "No evidence of recycled/reused footage detected.")
        ),
    }


# ─── 4. Geolocation Verification ─────────────────────────────────────────────

def verify_geolocation(locations: List[str], claims: List[str]) -> Dict[str, Any]:
    """
    Verify geographic claims by cross-referencing with web sources.
    """
    geo_verifications = []

    for loc in locations[:3]:
        query = f'"{loc}" {" ".join(claims[:1])[:50]} fact check'
        results = _ddg_search(query, max_results=2)
        for r in results:
            snippet_lower = r.get("snippet", "").lower()
            supports = any(w in snippet_lower for w in ["confirmed", "verified", "happened in", "took place in", loc.lower()])
            contradicts = any(w in snippet_lower for w in ["not in", "false location", "wrong country", "actually in"])
            geo_verifications.append({
                "location": loc,
                "source": r.get("title", "")[:60],
                "url": r.get("url", ""),
                "domain_trust": r.get("domain_trust", "medium"),
                "geo_supports": supports,
                "geo_contradicts": contradicts,
            })

    contradictions = [g for g in geo_verifications if g["geo_contradicts"]]
    return {
        "geo_verifications": geo_verifications[:6],
        "geo_contradictions": contradictions,
        "geo_contradiction_count": len(contradictions),
        "geo_summary": (
            f"Geolocation verification: {len(geo_verifications)} results across {len(locations)} locations. "
            + (f"⚠️ {len(contradictions)} geographic contradictions found." if contradictions
               else "Geographic claims appear consistent.")
        ),
    }


# ─── 5. Timestamp Verification ───────────────────────────────────────────────

def verify_timestamps(date_refs: List[str], years: List[int], claims: List[str]) -> Dict[str, Any]:
    """
    Cross-check date and time references in the video against web sources.
    """
    timestamp_issues = []
    verifications = []
    current_year = datetime.datetime.now().year

    # Check for future dates
    future_years = [y for y in years if y > current_year]
    if future_years:
        timestamp_issues.append(f"Future years referenced: {future_years}")

    # Very old events presented as recent
    old_years = [y for y in years if y < current_year - 10]
    if old_years and len(old_years) >= 2:
        timestamp_issues.append(f"Multiple old dates referenced ({old_years[:3]}) — potential old footage")

    # Search to verify key date claims
    if date_refs and claims:
        date_query = f"{date_refs[0] if date_refs else ''} {claims[0][:40] if claims else ''} timeline"
        date_results = _ddg_search(date_query, max_results=2)
        for r in date_results:
            verifications.append({
                "query": date_query[:60],
                "source": r.get("title", "")[:60],
                "url": r.get("url", ""),
                "domain_trust": r.get("domain_trust", "medium"),
            })

    return {
        "timestamp_issues": timestamp_issues,
        "date_verifications": verifications,
        "issue_count": len(timestamp_issues),
        "timestamp_summary": (
            f"Timestamp verification: "
            + (f"⚠️ Issues found: {'; '.join(timestamp_issues)}" if timestamp_issues
               else "No significant timestamp inconsistencies detected.")
        ),
    }


# ─── 6. Weather Verification ─────────────────────────────────────────────────

WEATHER_KEYWORDS = ["raining", "storm", "flood", "drought", "snowstorm", "blizzard",
                    "tornado", "hurricane", "heatwave", "cold wave", "earthquake",
                    "typhoon", "cyclone", "monsoon", "rainfall", "temperature"]


def verify_weather_claims(transcript: str, locations: List[str], date_refs: List[str]) -> Dict[str, Any]:
    """
    Detect and verify weather-related claims in the transcript.
    """
    transcript_lower = transcript.lower()
    weather_claims = [kw for kw in WEATHER_KEYWORDS if kw in transcript_lower]

    if not weather_claims:
        return {
            "weather_claims_found": [],
            "weather_verifications": [],
            "weather_summary": "No weather-related claims detected in transcript.",
        }

    verifications = []
    for weather_type in weather_claims[:2]:
        loc = locations[0] if locations else ""
        date = date_refs[0] if date_refs else str(datetime.datetime.now().year)
        query = f"{weather_type} {loc} {date} weather report"
        results = _ddg_search(query, max_results=2)
        for r in results:
            verifications.append({
                "weather_claim": weather_type,
                "location": loc,
                "source": r.get("title", "")[:60],
                "url": r.get("url", ""),
                "domain_trust": r.get("domain_trust", "medium"),
                "snippet": r.get("snippet", "")[:100],
            })

    return {
        "weather_claims_found": weather_claims,
        "weather_verifications": verifications[:4],
        "weather_summary": (
            f"Weather claims detected: {', '.join(weather_claims[:4])}. "
            f"Found {len(verifications)} verification sources."
        ),
    }


# ─── Master OSINT Orchestrator ────────────────────────────────────────────────

def run_osint_pipeline(
    transcript: str,
    video_url: str,
    claim_items: List[Dict],
    forensics_report: Dict,
) -> Dict[str, Any]:
    """
    Run the complete OSINT collection pipeline.
    """
    # Extract basic info from forensics report
    locations = forensics_report.get("geolocation", {}).get("countries", [])
    cities = forensics_report.get("geolocation", {}).get("cities", [])
    all_locations = locations + cities
    date_refs = forensics_report.get("temporal_analysis", {}).get("date_references", [])
    years = forensics_report.get("temporal_analysis", {}).get("years_mentioned", [])

    # Extract claims text safely
    claims_text = []
    for item in claim_items:
        if isinstance(item, dict):
            if "claim" in item:
                c = item["claim"]
                if isinstance(c, dict):
                    claims_text.append(c.get("normalized_text") or c.get("raw_text") or "")
                else:
                    claims_text.append(str(c))
            elif "normalized_text" in item:
                claims_text.append(item["normalized_text"])
            elif "claim_text" in item:
                claims_text.append(item["claim_text"])
            else:
                claims_text.append(str(item.get("claim", "")))
        else:
            claims_text.append(str(item))
    claims_text = [c for c in claims_text if c]

    transcript_snippet = transcript[:300]
    topic = " ".join(transcript_snippet.split()[:6])

    print("[osint] Running OSINT sub-tasks concurrently...")
    from concurrent.futures import ThreadPoolExecutor

    with ThreadPoolExecutor(max_workers=6) as executor:
        fut_gfc = executor.submit(verify_via_google_factcheck, claims_text)
        fut_news = executor.submit(verify_via_news, claims_text, transcript_snippet)
        fut_social = executor.submit(collect_social_signals, claims_text, topic)
        fut_reverse = executor.submit(build_reverse_search_queries, video_url, transcript_snippet, all_locations)
        fut_geo = executor.submit(verify_geolocation, all_locations, claims_text) if all_locations else None
        fut_timestamp = executor.submit(verify_timestamps, date_refs, years, claims_text)
        fut_weather = executor.submit(verify_weather_claims, transcript, all_locations, date_refs)

        try:
            google_factcheck = fut_gfc.result(timeout=15)
        except Exception as e:
            print(f"[osint] Google Fact Check failed: {e}")
            google_factcheck = {"fact_checks_found": [], "debunked_count": 0, "manipulated_count": 0, "verified_true_count": 0, "total_reviews": 0, "factcheck_summary": f"Error: {e}"}

        try:
            news = fut_news.result(timeout=20)
        except Exception as e:
            print(f"[osint] News verification failed: {e}")
            news = {"news_results": [], "total_news_found": 0, "high_trust_sources": 0, "fact_check_sources": 0, "contradiction_count": 0, "support_count": 0, "groq_news_analysis": "", "news_summary": f"Error: {e}"}

        try:
            social = fut_social.result(timeout=15)
        except Exception as e:
            print(f"[osint] Social signals failed: {e}")
            social = {"social_results": [], "platforms_found": [], "viral_indicators": [], "manipulation_signals": [], "total_social_found": 0, "social_summary": f"Error: {e}"}

        try:
            reverse = fut_reverse.result(timeout=15)
        except Exception as e:
            print(f"[osint] Reverse search failed: {e}")
            reverse = {"suggested_queries": [], "reverse_search_results": [], "old_video_reuse_signals": [], "potential_recycled_content": False, "recycled_footage_detected": False, "reverse_search_summary": f"Error: {e}"}

        if fut_geo:
            try:
                geo_verification = fut_geo.result(timeout=15)
            except Exception as e:
                print(f"[osint] Geolocation verification failed: {e}")
                geo_verification = {"geo_verifications": [], "geo_contradictions": [], "geo_contradiction_count": 0, "geo_summary": f"Error: {e}"}
        else:
            geo_verification = {"geo_verifications": [], "geo_contradictions": [], "geo_contradiction_count": 0, "geo_summary": "No geographic references to verify."}

        try:
            timestamp = fut_timestamp.result(timeout=15)
        except Exception as e:
            print(f"[osint] Timestamp verification failed: {e}")
            timestamp = {"timestamp_issues": [], "date_verifications": [], "issue_count": 0, "timestamp_summary": f"Error: {e}"}

        try:
            weather = fut_weather.result(timeout=15)
        except Exception as e:
            print(f"[osint] Weather verification failed: {e}")
            weather = {"weather_claims_found": [], "weather_verifications": [], "weather_summary": f"Error: {e}"}

    print("[osint] Verifying source authority (Wayback/WHOIS)...")
    source_urls = [r.get("url") for r in news.get("news_results", []) if r.get("url")]
    source_authority = verify_source_authority(source_urls)

    # Compute OSINT confidence score incorporating Google Fact Check
    google_contradictions = (google_factcheck.get("debunked_count", 0) + google_factcheck.get("manipulated_count", 0)) * 3
    google_supports = google_factcheck.get("verified_true_count", 0) * 3

    contradiction_signals = (
        news["contradiction_count"]
        + geo_verification.get("geo_contradiction_count", 0)
        + timestamp["issue_count"]
        + len(reverse.get("old_video_reuse_signals", []))
        + len(social.get("manipulation_signals", []))
        + len(source_authority.get("suspicious_domains", []))
        + google_contradictions
    )
    support_signals = news["support_count"] + news["high_trust_sources"] + google_supports
    total_contradiction_count = contradiction_signals

    raw_score = max(0, support_signals * 15 - contradiction_signals * 20)
    osint_score = round(max(20.0, min(95.0, 60.0 + raw_score)), 1)

    # ── Multi-Modal OSINT Veto Determination ──
    recycled_detected = reverse.get("recycled_footage_detected", False)
    osint_veto = {"veto": False, "verdict": None, "reason": None}

    if recycled_detected:
        osint_veto = {
            "veto": True,
            "verdict": "Manipulated",
            "reason": f"Recycled / out-of-context footage detected: {'; '.join(reverse.get('old_video_reuse_signals', [])[:2])}",
        }
        osint_score = min(osint_score, 30.0)
    elif google_factcheck.get("debunked_count", 0) >= 1:
        osint_veto = {
            "veto": True,
            "verdict": "Fake",
            "reason": f"Directly debunked by certified fact-checkers in Google Fact Check database ({google_factcheck.get('total_reviews')} reviews)",
        }
        osint_score = min(osint_score, 25.0)
    elif google_factcheck.get("manipulated_count", 0) >= 1:
        osint_veto = {
            "veto": True,
            "verdict": "Manipulated",
            "reason": "Certified fact-checkers flagged content as manipulated / misleading context",
        }
        osint_score = min(osint_score, 35.0)
    elif geo_verification.get("geo_contradiction_count", 0) >= 2:
        osint_veto = {
            "veto": True,
            "verdict": "Manipulated",
            "reason": f"Severe geographic misattribution ({geo_verification.get('geo_contradiction_count')} contradictions found)",
        }
        osint_score = min(osint_score, 35.0)

    return {
        "osint_score": osint_score,
        "contradiction_count": total_contradiction_count,
        "support_count": support_signals,
        "news_verification": news,
        "google_factcheck": google_factcheck,
        "social_signals": social,
        "reverse_search": reverse,
        "geo_verification": geo_verification,
        "timestamp_verification": timestamp,
        "weather_verification": weather,
        "source_authority": source_authority,
        "potential_recycled_content": recycled_detected,
        "recycled_footage_detected": recycled_detected,
        "osint_veto": osint_veto,
        "summary": (
            f"OSINT collection complete: {news['total_news_found']} news sources, "
            f"{google_factcheck.get('total_reviews', 0)} Google Fact Check reviews, "
            f"{social['total_social_found']} social discussions, "
            f"{contradiction_signals} contradiction signals, "
            f"{support_signals} support signals. "
            f"OSINT confidence score: {osint_score}/100."
            + (f" ⚠️ [VETO] {osint_veto['reason']}" if osint_veto.get("veto") else "")
        ),
    }
