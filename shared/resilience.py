import time
import random
import urllib.error
from typing import Callable, Any, Dict, List, Tuple

class CircuitBreaker:
    def __init__(self, name: str, failure_threshold: int = 5, recovery_time: float = 30.0):
        self.name = name
        self.failure_threshold = failure_threshold
        self.recovery_time = recovery_time
        self.failure_count = 0
        self.state = "CLOSED"  # CLOSED, OPEN, HALF-OPEN
        self.last_state_change = 0.0

    def record_success(self):
        self.failure_count = 0
        self.state = "CLOSED"

    def record_failure(self):
        self.failure_count += 1
        if self.failure_count >= self.failure_threshold:
            self.state = "OPEN"
            self.last_state_change = time.time()
            print(f"[Resilience] Circuit breaker {self.name} tripped to OPEN. Cooldown for {self.recovery_time}s.")

    def trip(self, cooldown: float = 600.0, reason: str = ""):
        self.state = "OPEN"
        self.last_state_change = time.time()
        self.recovery_time = cooldown
        reason_str = f" ({reason})" if reason else ""
        print(f"[Resilience] Circuit breaker {self.name} tripped to OPEN{reason_str}. Skipping requests for {int(cooldown)}s.")

    def can_execute(self) -> bool:
        if self.state == "OPEN":
            if time.time() - self.last_state_change > self.recovery_time:
                self.state = "HALF-OPEN"
                print(f"[Resilience] Circuit breaker {self.name} entered HALF-OPEN state.")
                return True
            return False
        return True


import urllib.request
import json

# Global circuit breakers
breakers: Dict[str, CircuitBreaker] = {}

def get_breaker(name: str) -> CircuitBreaker:
    if name not in breakers:
        breakers[name] = CircuitBreaker(name)
    return breakers[name]


def execute_with_resilience(source_name: str, func: Callable, *args, **kwargs) -> Tuple[Any, bool]:
    """
    Executes a callable with retries, exponential backoff, and circuit breaking.
    Returns (result, is_success).
    If the circuit breaker is OPEN, it skips execution and returns (None, False).
    """
    breaker = get_breaker(source_name)
    if not breaker.can_execute():
        return None, False

    retries = 3
    backoff = 1.5
    for attempt in range(retries):
        try:
            res = func(*args, **kwargs)
            breaker.record_success()
            return res, True
        except Exception as e:
            # Check if this is an HTTP error and classify
            is_transient = True
            if isinstance(e, urllib.error.HTTPError):
                # 400 (Bad Request) and 404 (Not Found) are query-specific syntax/entity misses,
                # NOT downstream service outages. Do not retry and do NOT trip the breaker.
                if e.code in (400, 404):
                    return None, False
                # Auth issues (401, 403) and exhausted quotas (429) are non-transient for this request.
                if e.code in (401, 403, 429):
                    is_transient = False
            
            # Check for non-HTTP rate limits or bot blockers (e.g. DDG 403 Ratelimit string)
            err_str = str(e).lower()
            if "ratelimit" in err_str or "rate limit" in err_str or "403" in err_str:
                # If rate-limited, back off slightly but do not endlessly loop
                if attempt == retries - 1:
                    print(f"[Resilience] {source_name} rate limit reached on final attempt: {e}")
                    breaker.trip(cooldown=300.0, reason=str(e))
                    return None, False

            if not is_transient:
                # For non-transient HTTP errors:
                # 429 = rate limit / daily quota exceeded
                # 401/403 = invalid API key or permission denied
                if isinstance(e, urllib.error.HTTPError) and e.code in (429, 401, 403):
                    cooldown = 600.0 if e.code == 429 else 1800.0
                    reason_msg = f"HTTP Error {e.code}: {e.reason if hasattr(e, 'reason') else 'Quota/Auth'}"
                    breaker.trip(cooldown=cooldown, reason=reason_msg)
                else:
                    print(f"[Resilience] Non-transient failure for {source_name}: {e}")
                    breaker.record_failure()
                return None, False

            print(f"[Resilience] Call to {source_name} failed: {e}. Attempt {attempt+1}/{retries}. Backing off.")
            if attempt < retries - 1:
                sleep_time = (backoff ** attempt) + random.uniform(0.1, 0.4)
                time.sleep(sleep_time)
            else:
                breaker.record_failure()
                return None, False

    return None, False


def resilient_http_fetch(source_name: str, url: str, headers: dict = None, timeout: float = 10.0) -> Tuple[Any, bool]:
    """Fetches a URL and returns JSON decoded dict/list with circuit breaking and retries."""
    def _fetch():
        req = urllib.request.Request(url, headers=headers or {})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            content = resp.read().decode("utf-8")
            if not content.strip():
                return {}
            return json.loads(content)
    return execute_with_resilience(source_name, _fetch)

