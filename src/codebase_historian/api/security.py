"""
Authentication and rate limiting security layer for FastAPI endpoints.
Implements API-key verification and in-memory token-bucket rate limiting.
"""

import time
from threading import Lock
from typing import Dict, Optional, Tuple

from fastapi import HTTPException, Request, Security
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from codebase_historian.config import settings

bearer_scheme = HTTPBearer(auto_error=False)


class TokenBucketRateLimiter:
    """Thread-safe in-memory Token Bucket rate limiter per caller."""

    def __init__(self, capacity: int = 60, refill_rate: float = 1.0):
        self.capacity = capacity
        self.refill_rate = refill_rate
        self.buckets: Dict[str, float] = {}
        self.last_refill: Dict[str, float] = {}
        self.lock = Lock()

    def consume(self, key: str, tokens: float = 1.0) -> Tuple[bool, float]:
        """
        Attempt to consume tokens for the given key.
        Returns (allowed: bool, retry_after_seconds: float).
        """
        with self.lock:
            now = time.time()
            if key not in self.buckets:
                self.buckets[key] = float(self.capacity)
                self.last_refill[key] = now

            # Refill tokens based on elapsed time
            elapsed = now - self.last_refill[key]
            self.last_refill[key] = now
            self.buckets[key] = min(float(self.capacity), self.buckets[key] + (elapsed * self.refill_rate))

            if self.buckets[key] >= tokens:
                self.buckets[key] -= tokens
                return True, 0.0

            # Rate limit exceeded: calculate wait time
            missing = tokens - self.buckets[key]
            retry_after = missing / self.refill_rate if self.refill_rate > 0 else 1.0
            return False, round(retry_after, 2)

    def reset(self) -> None:
        """Clear all rate limit state (useful in tests)."""
        with self.lock:
            self.buckets.clear()
            self.last_refill.clear()


rate_limiter = TokenBucketRateLimiter(
    capacity=settings.rate_limit_capacity,
    refill_rate=settings.rate_limit_refill_rate,
)


def verify_api_key(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Security(bearer_scheme),
) -> str:
    """
    FastAPI security dependency validating API key and enforcing token-bucket rate limiting.
    Accepts 'Authorization: Bearer <key>' or 'X-API-Key: <key>' header.
    """
    if not settings.auth_enabled:
        request.state.caller_id = "anonymous"
        return "anonymous"

    api_key: Optional[str] = None
    if credentials and credentials.scheme.lower() == "bearer":
        api_key = credentials.credentials
    else:
        api_key = request.headers.get("X-API-Key")

    if not api_key:
        raise HTTPException(
            status_code=401,
            detail="Missing API key. Provide Authorization: Bearer <api_key> or X-API-Key header.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if api_key not in settings.api_keys:
        raise HTTPException(
            status_code=401,
            detail="Invalid API key.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    caller_id = f"client_{api_key[:8]}"
    request.state.caller_id = caller_id

    # Enforce Token Bucket Rate Limiting
    allowed, retry_after = rate_limiter.consume(caller_id)
    if not allowed:
        raise HTTPException(
            status_code=429,
            detail=f"Rate limit exceeded. Try again in {retry_after} seconds.",
            headers={"Retry-After": str(int(retry_after) + 1)},
        )

    return caller_id
