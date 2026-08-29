"""
Integration tests for FastAPI REST API and Typer CLI.
"""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from typer.testing import CliRunner

from codebase_historian.api import app, set_service
from codebase_historian.cli.main import app as cli_app
from codebase_historian.service import HistorianService


@pytest.fixture
def integration_service(tmp_path: Path):
    """Initializes a clean HistorianService for integration testing."""
    service = HistorianService(
        repo_path=".",
        db_path=str(tmp_path / "test_historian.db"),
        chroma_path=str(tmp_path / "test_chroma"),
    )
    # Run initial ingestion of local repo
    service.ingest(".")
    return service


def test_rest_api_endpoints(integration_service):
    # Wire service into API
    set_service(integration_service)
    client = TestClient(app)

    # 1. GET / (public root endpoint)
    res_root = client.get("/")
    assert res_root.status_code == 200
    assert "version" in res_root.json()

    # 2. Test 401 Unauthorized without API key on /v1
    res_unauth = client.get("/v1/health")
    assert res_unauth.status_code == 401
    assert "Missing API key" in res_unauth.json()["detail"]

    # 3. Test 401 Unauthorized with invalid API key
    res_bad_key = client.get("/v1/health", headers={"Authorization": "Bearer invalid-key"})
    assert res_bad_key.status_code == 401
    assert "Invalid API key" in res_bad_key.json()["detail"]

    # Auth headers for remaining tests
    headers = {"Authorization": "Bearer test-key-historian"}

    # 4. GET /v1/health with valid key
    res_health = client.get("/v1/health", headers=headers)
    assert res_health.status_code == 200
    health_data = res_health.json()
    assert health_data["status"] == "healthy"
    assert health_data["graph_node_count"] > 0

    # 5. POST /v1/explain
    res_explain = client.post(
        "/v1/explain",
        json={"target": "src/codebase_historian/config.py"},
        headers=headers,
    )
    assert res_explain.status_code == 200
    explain_data = res_explain.json()
    assert "answer" in explain_data
    assert explain_data["confidence"] > 0

    # 6. POST /v1/impact
    res_impact = client.post(
        "/v1/impact",
        json={"change_description": "Modify src/codebase_historian/config.py settings schema"},
        headers=headers,
    )
    assert res_impact.status_code == 200
    impact_data = res_impact.json()
    assert "affected_files" in impact_data
    assert "confidence" in impact_data

    # 7. POST /v1/refactor/suggest
    res_refactor = client.post(
        "/v1/refactor/suggest",
        json={"target": "src/codebase_historian/config.py"},
        headers=headers,
    )
    assert res_refactor.status_code == 200
    refactor_data = res_refactor.json()
    assert refactor_data["status"] == "pending_human_review"
    assert "proposal" in refactor_data
    assert "critic_verdict" in refactor_data

    # 8. POST /v1/onboarding/guide
    res_onboard = client.post("/v1/onboarding/guide", json={}, headers=headers)
    assert res_onboard.status_code == 200
    onboard_data = res_onboard.json()
    assert "central_files" in onboard_data

    # 9. Verify structured audit logs in SQLite
    audit_entries = integration_service.memory_store.list_audit_logs(limit=20)
    assert len(audit_entries) >= 5
    assert any(log.caller_id == "client_test-key" for log in audit_entries)
    assert any(log.tool_name == "explain" for log in audit_entries)
    assert all(log.latency_ms >= 0 and log.status_code in (200, 401) for log in audit_entries)


def test_cli_commands():
    runner = CliRunner()

    # 1. Health Command
    r_health = runner.invoke(cli_app, ["health"])
    assert r_health.exit_code == 0
    assert "System Health & Index Status" in r_health.output

    # 2. Explain Command
    r_explain = runner.invoke(cli_app, ["explain", "src/codebase_historian/config.py"])
    assert r_explain.exit_code == 0
    assert "Historian Explanation" in r_explain.output

    # 3. Impact Command
    r_impact = runner.invoke(cli_app, ["impact", "Change src/codebase_historian/config.py"])
    assert r_impact.exit_code == 0

    # 4. Onboard Command
    r_onboard = runner.invoke(cli_app, ["onboard"])
    assert r_onboard.exit_code == 0
    assert "Contributor Onboarding Guide" in r_onboard.output

    # 5. Refactor Command with Human Confirmation 'y'
    r_refactor = runner.invoke(cli_app, ["refactor", "src/codebase_historian/config.py"], input="y\n")
    assert r_refactor.exit_code == 0
    assert "Refactoring Proposal" in r_refactor.output
    assert "Critic Adversarial Review" in r_refactor.output
    assert "Human approval granted" in r_refactor.output
