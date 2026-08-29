"""FastAPI API package."""

from codebase_historian.api.app import app, create_app
from codebase_historian.api.middleware import AuditLoggingMiddleware
from codebase_historian.api.routers import get_service, router, set_service
from codebase_historian.api.security import (
    TokenBucketRateLimiter,
    rate_limiter,
    verify_api_key,
)

__all__ = [
    "AuditLoggingMiddleware",
    "TokenBucketRateLimiter",
    "app",
    "create_app",
    "get_service",
    "rate_limiter",
    "router",
    "set_service",
    "verify_api_key",
]
