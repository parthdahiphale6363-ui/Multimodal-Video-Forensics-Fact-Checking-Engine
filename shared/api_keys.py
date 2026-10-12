"""
api_keys.py — Centralized API Key Manager
==========================================
Manages all external API keys with:
  - Multi-key rotation for Groq (round-robin + failover on rate limit)
  - Health validation for every configured API
  - Status tracking (active / cooling_down / invalid / missing)
  - Startup diagnostics
"""

import os
import time
import json
import threading
import urllib.request
import urllib.parse
from typing import Any, Dict, List, Optional, Tuple


# ─── Key Status Constants ─────────────────────────────────────────────────────

STATUS_ACTIVE = "active"
STATUS_COOLING = "cooling_down"
STATUS_INVALID = "invalid"
STATUS_MISSING = "missing"
STATUS_OK = "ok"
STATUS_DEGRADED = "degraded"
STATUS_UNAVAILABLE = "unavailable"


# ─── Single Key Tracker ──────────────────────────────────────────────────────

class KeyState:
    """Tracks the health of a single API key."""
    __slots__ = ("key", "status", "fail_count", "last_used", "cooldown_until")

    def __init__(self, key: str):
        self.key = key
        self.status: str = STATUS_ACTIVE
        self.fail_count: int = 0
        self.last_used: float = 0.0
        self.cooldown_until: float = 0.0

    def is_available(self) -> bool:
        if self.status == STATUS_INVALID:
            return False
        if self.status == STATUS_COOLING and time.time() < self.cooldown_until:
            return False
        if self.status == STATUS_COOLING and time.time() >= self.cooldown_until:
            # Cooldown expired — mark active again
            self.status = STATUS_ACTIVE
            self.fail_count = 0
        return True

    def record_success(self):
        self.status = STATUS_ACTIVE
        self.fail_count = 0
        self.last_used = time.time()

    def record_rate_limit(self, cooldown_seconds: float = 60.0):
        self.fail_count += 1
        self.status = STATUS_COOLING
        self.cooldown_until = time.time() + cooldown_seconds
        self.last_used = time.time()

    def record_auth_failure(self):
        self.status = STATUS_INVALID
        self.fail_count += 1
        self.last_used = time.time()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "status": self.status,
            "fail_count": self.fail_count,
            "last_used": self.last_used,
            "key_prefix": self.key[:8] + "..." if len(self.key) > 12 else "***",
        }


# ─── API Key Manager (Singleton) ─────────────────────────────────────────────

class APIKeyManager:
    """
    Singleton that manages all external API keys.
    Supports multi-key rotation for Groq and health checks for all services.
    """
    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._initialized = True
        self._groq_keys: List[KeyState] = []
        self._groq_index: int = 0
        self._groq_lock = threading.Lock()
        self._newsapi_key: Optional[str] = None
        self._newsdata_key: Optional[str] = None
        self._google_fc_key: Optional[str] = None
        self._load_keys()

    def _load_keys(self):
        """Load all API keys from environment variables."""
        # Groq: support comma-separated list of keys
        groq_raw = os.getenv("GROQ_API_KEY", "").strip()
        if groq_raw:
            keys = [k.strip() for k in groq_raw.split(",") if k.strip()]
            self._groq_keys = [KeyState(k) for k in keys]
            print(f"[APIKeyManager] Loaded {len(self._groq_keys)} Groq API key(s)")
        else:
            self._groq_keys = []
            print("[APIKeyManager] [!] No GROQ_API_KEY configured")

        # NewsAPI.org
        self._newsapi_key = os.getenv("NEWS_API_KEY", "").strip() or None
        if self._newsapi_key:
            print(f"[APIKeyManager] NewsAPI.org key loaded (len={len(self._newsapi_key)})")
        else:
            print("[APIKeyManager] [!] No NEWS_API_KEY configured -- NewsAPI.org disabled")

        # NewsData.io
        self._newsdata_key = os.getenv("NEWSDATA_API_KEY", "").strip() or None
        if self._newsdata_key:
            print(f"[APIKeyManager] NewsData.io key loaded (prefix={self._newsdata_key[:6]}...)")
        else:
            print("[APIKeyManager] [!] No NEWSDATA_API_KEY configured -- NewsData.io disabled")

        # Google Fact Check Tools
        self._google_fc_key = os.getenv("GOOGLE_FACTCHECK_API_KEY", "").strip() or None
        if self._google_fc_key:
            print(f"[APIKeyManager] Google Fact Check key loaded")
        else:
            print("[APIKeyManager] [!] No GOOGLE_FACTCHECK_API_KEY configured -- limited Fact Check API access")

    def reload_keys(self):
        """Re-read keys from environment (useful after .env changes)."""
        self._initialized = False
        self.__init__()

    # ─── Groq Key Rotation ────────────────────────────────────────────────────

    def get_groq_key(self) -> Optional[str]:
        """
        Get the next available Groq API key using round-robin rotation.
        Skips keys that are cooling down or invalid.
        Returns None if no keys are available.
        """
        if not self._groq_keys:
            return None

        with self._groq_lock:
            n = len(self._groq_keys)
            for _ in range(n):
                idx = self._groq_index % n
                self._groq_index = (self._groq_index + 1) % n
                ks = self._groq_keys[idx]
                if ks.is_available():
                    return ks.key

            # All keys exhausted — try the one with shortest cooldown remaining
            cooling = [ks for ks in self._groq_keys if ks.status == STATUS_COOLING]
            if cooling:
                soonest = min(cooling, key=lambda k: k.cooldown_until)
                wait = max(0, soonest.cooldown_until - time.time())
                if wait < 120:  # Only wait if < 2 minutes
                    print(f"[APIKeyManager] All Groq keys cooling — waiting {wait:.1f}s for next available key")
                    time.sleep(wait + 0.5)
                    soonest.status = STATUS_ACTIVE
                    soonest.fail_count = 0
                    return soonest.key

        return None

    def record_groq_success(self, key: str):
        """Mark a Groq key as successfully used."""
        for ks in self._groq_keys:
            if ks.key == key:
                ks.record_success()
                break

    def record_groq_rate_limit(self, key: str, cooldown_seconds: float = 60.0):
        """Mark a Groq key as rate-limited with cooldown."""
        for ks in self._groq_keys:
            if ks.key == key:
                ks.record_rate_limit(cooldown_seconds)
                active_count = sum(1 for k in self._groq_keys if k.is_available())
                print(
                    f"[APIKeyManager] Groq key {key[:8]}... rate-limited, cooling for {cooldown_seconds:.0f}s. "
                    f"{active_count}/{len(self._groq_keys)} keys still active."
                )
                break

    def record_groq_auth_failure(self, key: str):
        """Mark a Groq key as permanently invalid (401/403)."""
        for ks in self._groq_keys:
            if ks.key == key:
                ks.record_auth_failure()
                active_count = sum(1 for k in self._groq_keys if k.is_available())
                print(
                    f"[APIKeyManager] [X] Groq key {key[:8]}... INVALID (auth failure). "
                    f"{active_count}/{len(self._groq_keys)} keys remaining."
                )
                break

    # ─── Simple Key Getters ───────────────────────────────────────────────────

    def get_newsapi_key(self) -> Optional[str]:
        return self._newsapi_key

    def get_newsdata_key(self) -> Optional[str]:
        return self._newsdata_key

    def get_google_factcheck_key(self) -> Optional[str]:
        return self._google_fc_key

    @property
    def groq_key_count(self) -> int:
        return len(self._groq_keys)

    @property
    def groq_active_count(self) -> int:
        return sum(1 for k in self._groq_keys if k.is_available())

    # ─── Health Check / Validation ────────────────────────────────────────────

    def validate_all_keys(self) -> Dict[str, Any]:
        """
        Test all configured API keys with lightweight requests.
        Returns a comprehensive status report.
        """
        report = {
            "status": STATUS_OK,
            "apis": {},
            "warnings": [],
        }

        # 1. Groq
        groq_status = self._validate_groq()
        report["apis"]["groq"] = groq_status
        if groq_status["status"] != STATUS_OK:
            report["warnings"].append(f"Groq LLM: {groq_status.get('error', 'issues detected')}")

        # 2. NewsAPI.org
        newsapi_status = self._validate_newsapi()
        report["apis"]["newsapi_org"] = newsapi_status
        if newsapi_status["status"] == STATUS_MISSING:
            report["warnings"].append("NEWS_API_KEY not configured — NewsAPI.org search disabled")

        # 3. NewsData.io
        newsdata_status = self._validate_newsdata()
        report["apis"]["newsdata_io"] = newsdata_status
        if newsdata_status["status"] == STATUS_MISSING:
            report["warnings"].append("NEWSDATA_API_KEY not configured — NewsData.io search disabled")

        # 4. Google Fact Check
        gfc_status = self._validate_google_factcheck()
        report["apis"]["google_factcheck"] = gfc_status
        if gfc_status["status"] == STATUS_MISSING:
            report["warnings"].append("GOOGLE_FACTCHECK_API_KEY not configured — limited Fact Check API access")

        # 5. DuckDuckGo (no key needed)
        report["apis"]["duckduckgo"] = {"status": STATUS_OK, "no_key_required": True}

        # 6. Wikipedia (no key needed)
        report["apis"]["wikipedia"] = {"status": STATUS_OK, "no_key_required": True}

        # 7. Redis
        redis_status = self._validate_redis()
        report["apis"]["redis"] = redis_status
        if redis_status["status"] != STATUS_OK:
            report["warnings"].append("Redis not connected — using in-memory fallback (verdict cache, job queue)")

        # Groq key count warning
        if len(self._groq_keys) == 1:
            report["warnings"].append("Only 1 Groq key configured — consider adding more for rate limit resilience")

        # Overall status
        critical_apis = [report["apis"]["groq"]]
        if any(a["status"] == STATUS_UNAVAILABLE for a in critical_apis):
            report["status"] = STATUS_UNAVAILABLE
        elif report["warnings"]:
            report["status"] = STATUS_DEGRADED

        return report

    def _validate_groq(self) -> Dict[str, Any]:
        if not self._groq_keys:
            return {"status": STATUS_MISSING, "keys_configured": 0, "keys_active": 0}

        try:
            from groq import Groq
        except ImportError:
            return {
                "status": STATUS_UNAVAILABLE,
                "error": "groq package not installed",
                "keys_configured": len(self._groq_keys),
                "keys_active": 0,
            }

        active = 0
        invalid = 0
        model = os.getenv("GROQ_MODEL", "openai/gpt-oss-120b")

        for ks in self._groq_keys:
            if ks.status == STATUS_INVALID:
                invalid += 1
                continue
            try:
                client = Groq(api_key=ks.key)
                resp = client.chat.completions.create(
                    model=model,
                    messages=[{"role": "user", "content": "Hi"}],
                    max_tokens=2,
                    temperature=0.0,
                )
                if resp.choices:
                    ks.record_success()
                    active += 1
            except Exception as e:
                err_msg = str(e).lower()
                if "401" in err_msg or "403" in err_msg or "invalid" in err_msg or "authentication" in err_msg:
                    ks.record_auth_failure()
                    invalid += 1
                else:
                    # Might be rate limit or transient — don't mark invalid
                    active += 1  # Assume it might work later

        status = STATUS_OK if active > 0 else STATUS_UNAVAILABLE
        return {
            "status": status,
            "keys_configured": len(self._groq_keys),
            "keys_active": active,
            "keys_invalid": invalid,
            "model": model,
        }

    def _validate_newsapi(self) -> Dict[str, Any]:
        if not self._newsapi_key:
            return {"status": STATUS_MISSING, "key_configured": False}

        try:
            params = urllib.parse.urlencode({
                "q": "test",
                "language": "en",
                "pageSize": 1,
                "apiKey": self._newsapi_key,
            })
            url = f"https://newsapi.org/v2/everything?{params}"
            req = urllib.request.Request(url, headers={"User-Agent": "FactChecker/2.0"})
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                if data.get("status") == "ok":
                    return {"status": STATUS_OK, "key_configured": True}
                else:
                    return {
                        "status": STATUS_UNAVAILABLE,
                        "key_configured": True,
                        "error": data.get("message", "Unknown error"),
                    }
        except Exception as e:
            err = str(e)
            if "401" in err or "apiKey" in err.lower():
                return {"status": STATUS_INVALID, "key_configured": True, "error": "Invalid API key"}
            return {"status": STATUS_UNAVAILABLE, "key_configured": True, "error": str(e)[:100]}

    def _validate_newsdata(self) -> Dict[str, Any]:
        if not self._newsdata_key:
            return {"status": STATUS_MISSING, "key_configured": False}

        try:
            params = urllib.parse.urlencode({
                "apikey": self._newsdata_key,
                "q": "test",
                "language": "en",
                "size": 1,
            })
            url = f"https://newsdata.io/api/1/news?{params}"
            req = urllib.request.Request(url, headers={"User-Agent": "FactChecker/2.0"})
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                if data.get("status") == "success":
                    return {"status": STATUS_OK, "key_configured": True}
                else:
                    return {
                        "status": STATUS_UNAVAILABLE,
                        "key_configured": True,
                        "error": data.get("message", str(data.get("results", {}).get("message", "Unknown"))),
                    }
        except Exception as e:
            err = str(e)
            if "401" in err or "403" in err:
                return {"status": STATUS_INVALID, "key_configured": True, "error": "Invalid API key"}
            return {"status": STATUS_UNAVAILABLE, "key_configured": True, "error": str(e)[:100]}

    def _validate_google_factcheck(self) -> Dict[str, Any]:
        if not self._google_fc_key:
            return {"status": STATUS_MISSING, "key_configured": False}

        try:
            params = {"query": "test"}
            params["key"] = self._google_fc_key
            url = (
                "https://factchecktools.googleapis.com/v1alpha1/claims:search?"
                + urllib.parse.urlencode(params)
            )
            req = urllib.request.Request(url, headers={"User-Agent": "FactChecker/2.0"})
            with urllib.request.urlopen(req, timeout=10) as resp:
                json.loads(resp.read().decode("utf-8"))
                return {"status": STATUS_OK, "key_configured": True}
        except Exception as e:
            err = str(e)
            if "403" in err or "401" in err:
                return {"status": STATUS_INVALID, "key_configured": True, "error": "Invalid API key"}
            if "400" in err:
                # 400 = bad request, but key itself is valid
                return {"status": STATUS_OK, "key_configured": True}
            return {"status": STATUS_UNAVAILABLE, "key_configured": True, "error": str(e)[:100]}

    def _validate_redis(self) -> Dict[str, Any]:
        try:
            import redis as redis_lib
        except ImportError:
            return {"status": STATUS_UNAVAILABLE, "using_fallback": True, "error": "redis package not installed"}

        redis_url = os.getenv("REDIS_URL", "")
        if not redis_url:
            # Try default localhost
            try:
                client = redis_lib.Redis(host="localhost", port=6379, decode_responses=True)
                client.ping()
                return {"status": STATUS_OK, "using_fallback": False}
            except Exception:
                return {"status": STATUS_UNAVAILABLE, "using_fallback": True}

        try:
            client = redis_lib.from_url(redis_url, decode_responses=True)
            client.ping()
            return {"status": STATUS_OK, "using_fallback": False}
        except Exception:
            return {"status": STATUS_UNAVAILABLE, "using_fallback": True}

    # ─── Startup Status Table ─────────────────────────────────────────────────

    def print_startup_status(self):
        """Print a formatted status table to the console at startup."""
        report = self.validate_all_keys()

        lines = [
            "",
            "+----------------------------------------------+",
            "|    Video Fact-Checker -- API Key Status       |",
            "+----------------------------------------------+",
        ]

        api_display = [
            ("Groq LLM", "groq", lambda a: f"{a.get('keys_active', 0)}/{a.get('keys_configured', 0)} keys active" if a["status"] != STATUS_MISSING else "Not configured"),
            ("NewsAPI.org", "newsapi_org", lambda a: "Connected" if a["status"] == STATUS_OK else a.get("error", a["status"])),
            ("NewsData.io", "newsdata_io", lambda a: "Connected" if a["status"] == STATUS_OK else a.get("error", "Not configured")),
            ("Google FactCheck", "google_factcheck", lambda a: "Connected" if a["status"] == STATUS_OK else a.get("error", "Not configured")),
            ("DuckDuckGo", "duckduckgo", lambda _: "No key required"),
            ("Wikipedia", "wikipedia", lambda _: "No key required"),
            ("Redis", "redis", lambda a: "Connected" if a["status"] == STATUS_OK else "Not connected (in-memory fallback)"),
        ]

        for display_name, key, detail_fn in api_display:
            api_info = report["apis"].get(key, {})
            status = api_info.get("status", STATUS_MISSING)
            icon = "[OK]" if status == STATUS_OK else "[! ]" if status in (STATUS_MISSING, STATUS_DEGRADED) else "[X ]"
            detail = detail_fn(api_info)
            line = f"| {icon} {display_name:<16}: {detail:<23} |"
            lines.append(line)

        lines.append("+----------------------------------------------+")

        if report["warnings"]:
            lines.append("")
            lines.append("Warnings:")
            for w in report["warnings"]:
                lines.append(f"  [!] {w}")

        lines.append("")
        print("\n".join(lines))
        return report


# ─── Module-Level Singleton ───────────────────────────────────────────────────

_manager: Optional[APIKeyManager] = None


def get_api_key_manager() -> APIKeyManager:
    """Get or create the singleton APIKeyManager."""
    global _manager
    if _manager is None:
        _manager = APIKeyManager()
    return _manager
