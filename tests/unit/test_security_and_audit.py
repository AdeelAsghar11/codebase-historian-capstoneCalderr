"""
Unit tests for API key authentication, Token Bucket rate limiting, and structured audit logging.
"""

import time

import pytest
from fastapi import HTTPException
from starlette.requests import Request

from codebase_historian.api.security import TokenBucketRateLimiter, verify_api_key
from codebase_historian.memory.store import SQLiteMemoryStore


def test_token_bucket_rate_limiter_burst_and_refill():
    # Capacity = 3, refill_rate = 10 tokens/sec
    limiter = TokenBucketRateLimiter(capacity=3, refill_rate=10.0)

    # 1. 3 rapid requests allowed
    ok1, _ = limiter.consume("client_1")
    ok2, _ = limiter.consume("client_1")
    ok3, _ = limiter.consume("client_1")
    assert ok1 is True
    assert ok2 is True
    assert ok3 is True

    # 2. 4th immediate request exceeds capacity
    ok4, retry_after = limiter.consume("client_1")
    assert ok4 is False
    assert retry_after > 0

    # 3. Another client has their own independent bucket
    ok_other, _ = limiter.consume("client_2")
    assert ok_other is True

    # 4. Wait for refill
    time.sleep(0.15)
    ok_refilled, _ = limiter.consume("client_1")
    assert ok_refilled is True


def test_verify_api_key_bearer_and_header():
    def make_mock_request(headers: dict) -> Request:
        scope = {
            "type": "http",
            "method": "GET",
            "path": "/v1/health",
            "headers": [(k.lower().encode("latin-1"), v.encode("latin-1")) for k, v in headers.items()],
        }
        return Request(scope)

    # 1. Missing API key raises 401
    req_empty = make_mock_request({})
    with pytest.raises(HTTPException) as exc_info:
        verify_api_key(req_empty, None)
    assert exc_info.value.status_code == 401
    assert "Missing API key" in exc_info.value.detail

    # 2. Invalid API key raises 401
    req_bad = make_mock_request({"X-API-Key": "wrong-key"})
    with pytest.raises(HTTPException) as exc_info:
        verify_api_key(req_bad, None)
    assert exc_info.value.status_code == 401
    assert "Invalid API key" in exc_info.value.detail

    # 3. Valid X-API-Key header succeeds
    req_good = make_mock_request({"X-API-Key": "test-key-historian"})
    caller = verify_api_key(req_good, None)
    assert caller == "client_test-key"
    assert req_good.state.caller_id == caller


def test_sqlite_audit_logging():
    store = SQLiteMemoryStore(db_path=":memory:")

    # Log several audit entries
    store.log_audit("client_alice", "explain", "/v1/explain", 120, 200)
    store.log_audit("client_bob", "impact", "/v1/impact", 45, 200)
    store.log_audit("client_mallory", "unknown", "/v1/admin", 5, 401)

    logs = store.list_audit_logs(limit=10)
    assert len(logs) == 3

    # Check newest first
    assert logs[0].caller_id == "client_mallory"
    assert logs[0].status_code == 401

    assert logs[1].tool_name == "impact"
    assert logs[1].latency_ms == 45

    assert logs[2].caller_id == "client_alice"
    assert logs[2].endpoint == "/v1/explain"
