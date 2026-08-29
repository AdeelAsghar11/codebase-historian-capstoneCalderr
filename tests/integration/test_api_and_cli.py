"""
Integration tests for FastAPI REST API and Typer CLI.
"""

from pathlib import Path
from fastapi.testclient import TestClient
import pytest
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

    # 1. GET /
    res_root = client.get("/")
    assert res_root.status_code == 200
    assert "version" in res_root.json()

    # 2. GET /v1/health
    res_health = client.get("/v1/health")
    assert res_health.status_code == 200
    health_data = res_health.json()
    assert health_data["status"] == "healthy"
    assert health_data["graph_node_count"] > 0

    # 3. POST /v1/explain
    res_explain = client.post(
        "/v1/explain",
        json={"target": "src/codebase_historian/config.py"},
    )
    assert res_explain.status_code == 200
    explain_data = res_explain.json()
    assert "answer" in explain_data
    assert explain_data["confidence"] > 0

    # 4. POST /v1/impact
    res_impact = client.post(
        "/v1/impact",
        json={"change_description": "Modify src/codebase_historian/config.py settings schema"},
    )
    assert res_impact.status_code == 200
    impact_data = res_impact.json()
    assert "affected_files" in impact_data
    assert "confidence" in impact_data

    # 5. POST /v1/refactor/suggest
    res_refactor = client.post(
        "/v1/refactor/suggest",
        json={"target": "src/codebase_historian/config.py"},
    )
    assert res_refactor.status_code == 200
    refactor_data = res_refactor.json()
    assert refactor_data["status"] == "pending_human_review"
    assert "proposal" in refactor_data
    assert "critic_verdict" in refactor_data

    # 6. POST /v1/onboarding/guide
    res_onboard = client.post("/v1/onboarding/guide", json={})
    assert res_onboard.status_code == 200
    onboard_data = res_onboard.json()
    assert "central_files" in onboard_data


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
