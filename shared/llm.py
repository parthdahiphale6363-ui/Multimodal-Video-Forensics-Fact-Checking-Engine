"""
llm.py — LLM Client with Multi-Key Rotation
=============================================
Uses APIKeyManager for Groq key rotation:
  - Round-robin across multiple GROQ_API_KEY values
  - Automatic failover when a key hits 429 rate limit
  - Keys marked invalid on 401/403 authentication failures
  - Existing throttling + retry logic preserved
"""

import os
import re
import time
import threading
from typing import Any, Optional

try:
    from groq import Groq
except ImportError:
    Groq = None

from shared.api_keys import get_api_key_manager

# Serialize Groq calls to avoid TPM rate-limit bursts
_groq_lock = threading.Lock()
_last_groq_call = 0.0
_MIN_GROQ_INTERVAL = float(os.getenv("GROQ_MIN_INTERVAL_SEC", "1.0"))


def get_llm_client() -> Optional[Any]:
    """Returns a Groq client using the next available key from rotation."""
    if not Groq:
        return None
    manager = get_api_key_manager()
    key = manager.get_groq_key()
    if key:
        return Groq(api_key=key)
    return None


def get_llm_client_with_key() -> tuple:
    """Returns (Groq client, key_string) for tracking which key was used."""
    if not Groq:
        return None, None
    manager = get_api_key_manager()
    key = manager.get_groq_key()
    if key:
        return Groq(api_key=key), key
    return None, None


def get_groq_fallback_client() -> Optional[Any]:
    return get_llm_client()


def get_llm_model() -> str:
    return os.getenv("GROQ_MODEL", "openai/gpt-oss-120b")


def get_fallback_llm_model() -> str:
    return os.getenv("GROQ_FALLBACK_MODEL", "openai/gpt-oss-20b")


def get_groq_model() -> str:
    return get_llm_model()


def _parse_retry_seconds(error_msg: str) -> float:
    """Extract wait time from Groq 429 error message."""
    match = re.search(r"try again in ([\d.]+)s", str(error_msg), re.I)
    if match:
        return float(match.group(1)) + 0.5
    match = re.search(r"retry.?after[:\s]+([\d.]+)", str(error_msg), re.I)
    if match:
        return float(match.group(1)) + 0.5
    return 0.0


def _is_rate_limit_error(error: Exception) -> bool:
    msg = str(error).lower()
    return "429" in msg or "rate limit" in msg or "too many requests" in msg


def _is_auth_error(error: Exception) -> bool:
    msg = str(error).lower()
    return "401" in msg or "403" in msg or "invalid api key" in msg or "authentication" in msg


def _throttle_groq():
    global _last_groq_call
    with _groq_lock:
        elapsed = time.time() - _last_groq_call
        if elapsed < _MIN_GROQ_INTERVAL:
            time.sleep(_MIN_GROQ_INTERVAL - elapsed)
        _last_groq_call = time.time()


def _create_completion(client: Any, kwargs: dict, max_retries: int = 5) -> Any:
    """Call Groq with throttling and automatic 429 retry."""
    for attempt in range(max_retries):
        _throttle_groq()
        try:
            return client.chat.completions.create(**kwargs)
        except Exception as e:
            if _is_rate_limit_error(e) and attempt < max_retries - 1:
                wait = _parse_retry_seconds(str(e)) or (2 ** attempt * 3 + 2)
                print(f"[llm] Rate limited — waiting {wait:.1f}s (attempt {attempt + 1}/{max_retries})...")
                time.sleep(wait)
                continue
            raise


def call_llm_with_fallback(client: Any, **kwargs) -> Any:
    """
    Calls Groq chat completions with throttling, 429 retry, multi-key rotation,
    and model fallback.

    Flow:
    1. Try primary model with current key
    2. On rate limit → rotate to next key and retry
    3. On auth failure → mark key invalid, rotate to next key
    4. On other errors → try fallback model
    """
    manager = get_api_key_manager()
    primary_model = kwargs.get("model") or get_llm_model()
    fallback_model = get_fallback_llm_model()

    # Extract the key from the current client (if possible) for tracking
    current_key = getattr(client, '_api_key', None) or getattr(getattr(client, '_client', None), 'api_key', None)

    run_kwargs = kwargs.copy()
    run_kwargs["model"] = primary_model

    try:
        result = _create_completion(client, run_kwargs)
        if current_key:
            manager.record_groq_success(current_key)
        return result
    except Exception as e:
        if _is_auth_error(e):
            # Mark this key as permanently invalid and try next key
            if current_key:
                manager.record_groq_auth_failure(current_key)
            print(f"[llm] Auth failure on key — rotating to next key...")
            next_client, next_key = get_llm_client_with_key()
            if next_client and next_key != current_key:
                try:
                    result = _create_completion(next_client, run_kwargs, max_retries=3)
                    manager.record_groq_success(next_key)
                    return result
                except Exception as e2:
                    print(f"[llm] Next key also failed: {e2}")
                    raise e2
            raise e

        if _is_rate_limit_error(e):
            # Rate limit — mark current key cooling, rotate to next key
            cooldown = _parse_retry_seconds(str(e)) or 60.0
            if current_key:
                manager.record_groq_rate_limit(current_key, cooldown)

            # Try next available key
            next_client, next_key = get_llm_client_with_key()
            if next_client and next_key != current_key:
                print(f"[llm] Rotating to next Groq key after rate limit...")
                try:
                    result = _create_completion(next_client, run_kwargs, max_retries=3)
                    manager.record_groq_success(next_key)
                    return result
                except Exception as e2:
                    if _is_rate_limit_error(e2):
                        # All keys rate limited — wait for shortest cooldown
                        wait = _parse_retry_seconds(str(e)) or 15.0
                        print(f"[llm] All keys rate limited — waiting {wait:.1f}s...")
                        time.sleep(wait)
                        final_client, final_key = get_llm_client_with_key()
                        if final_client:
                            try:
                                result = _create_completion(final_client, run_kwargs, max_retries=3)
                                manager.record_groq_success(final_key)
                                return result
                            except Exception as e3:
                                raise e3
                    raise e2
            else:
                # No other key available — wait and retry same key
                wait = _parse_retry_seconds(str(e)) or 15.0
                print(f"[llm] Single key rate limited — final retry after {wait:.1f}s...")
                time.sleep(wait)
                try:
                    return _create_completion(client, run_kwargs, max_retries=3)
                except Exception as e2:
                    raise e2

        # Non-rate-limit, non-auth error — try fallback model
        print(f"[llm] Primary model ({primary_model}) failed: {e}. Trying fallback ({fallback_model})...")
        fallback_kwargs = kwargs.copy()
        fallback_kwargs["model"] = fallback_model
        try:
            return _create_completion(client, fallback_kwargs, max_retries=3)
        except Exception as e2:
            print(f"[llm] Fallback model ({fallback_model}) also failed: {e2}")
            raise e2


def get_redis_client() -> Optional[Any]:
    try:
        import redis
    except ImportError:
        return None

    redis_url = os.getenv("REDIS_URL")
    if redis_url:
        try:
            client = redis.from_url(redis_url, decode_responses=True)
            client.ping()
            return client
        except Exception as e:
            print(f"[Redis] Could not connect via REDIS_URL: {e}")

    redis_host = os.getenv("REDIS_HOST", "localhost")
    redis_port = int(os.getenv("REDIS_PORT", 6379))
    try:
        client = redis.Redis(host=redis_host, port=redis_port, decode_responses=True)
        client.ping()
        return client
    except Exception as e:
        print(f"[Redis] Could not connect to {redis_host}:{redis_port}: {e}")
    return None
