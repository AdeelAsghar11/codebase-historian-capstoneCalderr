"""
Integration tests for webhook receiver and incremental re-indexing.
"""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from codebase_historian.api import app, set_service
from codebase_historian.service import HistorianService


@pytest.fixture
def webhook_service(tmp_path: Path):
    """Initializes a connected service for webhook testing."""
    service = HistorianService(
        repo_path=".",
        db_path=str(tmp_path / "webhook_historian.db"),
        chroma_path=str(tmp_path / "webhook_chroma"),
    )
    service.ingest(".")
    return service


def test_incremental_reindex_service(webhook_service):
    # Running incremental immediately should detect no new commits
    res = webhook_service.reindex_incremental()
    assert res["reindexed"] is False
    assert res["new_commits_count"] == 0
    assert "No new commits" in res["message"]


def test_github_webhook_endpoint(webhook_service):
    set_service(webhook_service)
    client = TestClient(app)

    headers = {"Authorization": "Bearer test-key-historian"}
    payload = {
        "ref": "refs/heads/main",
        "before": "0000000000000000000000000000000000000000",
        "after": "72e54237c6457d09623939a00c6483123456789a",
        "commits": [
            {
                "id": "72e54237c6457d09623939a00c6483123456789a",
                "message": "feat: test webhook commit",
                "author": {"name": "Adeel", "email": "adeel@example.com"},
            }
        ],
        "repository": {
            "name": "codebase-historian-capstoneCalderr",
            "full_name": "AdeelAsghar11/codebase-historian-capstoneCalderr",
        },
    }

    res = client.post("/v1/webhook/github", json=payload, headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "received"
    assert data["action"] == "incremental_reindex"
    assert "reindex" in data

    # Verify audit log entry for webhook
    logs = webhook_service.memory_store.list_audit_logs(limit=5)
    assert any(entry.endpoint == "/v1/webhook/github" for entry in logs)
