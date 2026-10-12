from urllib.parse import urlparse


# ─── Tier 1: Highest Trust ──────────────────────────────────────────────────
# Wire services, government, academic, established encyclopaedias, major fact-checkers
_TIER1 = [
    ".gov", ".edu", ".mil",
    "reuters.com", "apnews.com", "ap.org",
    "who.int", "un.org", "cdc.gov", "nih.gov", "pubmed.ncbi.nlm.nih.gov",
    "bbc.com", "bbc.co.uk", "npr.org", "pbs.org",
    "nature.com", "sciencemag.org", "thelancet.com", "bmj.com",
    "wikipedia.org",          # Real encyclopedia with citations
    "britannica.com",         # Encyclopaedia Britannica
    "snopes.com",             # Fact-checker
    "politifact.com",         # Fact-checker
    "factcheck.org",          # Fact-checker
    "fullfact.org",           # Fact-checker (UK)
    "boomlive.in",            # Fact-checker (India)
    "altnews.in",             # Fact-checker (India)
    "vishvasnews.com",        # Fact-checker (India)
]

# ─── Tier 2: High Trust ─────────────────────────────────────────────────────
# Established international/national news outlets
_TIER2 = [
    "cnn.com", "theguardian.com", "nytimes.com", "washingtonpost.com",
    "forbes.com", "time.com", "aljazeera.com", "foxnews.com",
    "thehindu.com", "ndtv.com", "hindustantimes.com", "indiatoday.in",
    "livemint.com", "timesofindia.com", "telegraphindia.com",
    "wired.com", "techcrunch.com", "arstechnica.com",
    "scientificamerican.com", "newscientist.com",
    "theatlantic.com", "economist.com", "ft.com",
    "abcnews.go.com", "cbsnews.com", "nbcnews.com", "usatoday.com",
    "businessinsider.com", "bloomberg.com",
    "newsweek.com", "independent.co.uk", "telegraph.co.uk",
]


def get_domain_trust_tier(url: str) -> int:
    """
    Return an explicit trust tier for a domain.

    Tier 1 = highest (wire services, .gov/.edu, encyclopaedias, major fact-checkers)
    Tier 2 = established national/international news outlets
    Tier 3 = everything else (included but down-weighted)
    """
    if not url:
        return 3

    hostname = urlparse(url).netloc.lower()
    if not hostname:
        return 3

    if any(token in hostname for token in _TIER1):
        return 1

    if any(token in hostname for token in _TIER2):
        return 2

    return 3
