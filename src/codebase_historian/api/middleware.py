"""
Audit logging middleware for FastAPI.
Intercepts all requests, calculates latency, and records structured audit logs in SQLite.
"""

import time

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from codebase_historian.api.routers import get_service


class AuditLoggingMiddleware(BaseHTTPMiddleware):
    """Logs every HTTP request, caller, latency, and status code into SQLite audit_log table."""

    async def dispatch(self, request: Request, call_next) -> Response:
        start_time = time.perf_counter()

        response = await call_next(request)

        latency_ms = int((time.perf_counter() - start_time) * 1000)
        caller_id = getattr(request.state, "caller_id", "anonymous")
        endpoint = request.url.path

        # Determine tool/operation name from endpoint
        tool_name = "http_request"
        if "/explain" in endpoint:
            tool_name = "explain"
        elif "/impact" in endpoint:
            tool_name = "impact"
        elif "/refactor" in endpoint:
            tool_name = "refactor"
        elif "/onboarding" in endpoint:
            tool_name = "onboard"
        elif "/health" in endpoint:
            tool_name = "health"
        elif "/ingest" in endpoint:
            tool_name = "ingest"

        try:
            service = get_service()
            if service and service.memory_store:
                service.memory_store.log_audit(
                    caller_id=caller_id,
                    tool_name=tool_name,
                    endpoint=endpoint,
                    latency_ms=latency_ms,
                    status_code=response.status_code,
                )
        except Exception:
            # Failsafe: audit logging should never prevent returning HTTP responses
            pass

        return response
