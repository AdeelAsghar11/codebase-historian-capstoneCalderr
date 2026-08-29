"""
Integration tests for Streamlit Dashboard and graph visualization helpers.
"""

from pathlib import Path

import pytest
from typer.testing import CliRunner

from codebase_historian.cli.main import app as cli_app
from codebase_historian.dashboard.graph_view import generate_graph_html
from codebase_historian.service import HistorianService


@pytest.fixture
def dashboard_service(tmp_path: Path):
    service = HistorianService(
        repo_path=".",
        db_path=str(tmp_path / "dash_test.db"),
        chroma_path=str(tmp_path / "dash_chroma"),
    )
    service.ingest(".")
    return service


def test_generate_graph_html(dashboard_service):
    html = generate_graph_html(dashboard_service.knowledge_graph, max_nodes=50)

    assert "<!DOCTYPE html>" in html
    assert "vis-network" in html
    assert "nodes: new vis.DataSet(" in html
    assert "edges: new vis.DataSet(" in html
    assert "forceAtlas2Based" in html


def test_dashboard_cli_help():
    runner = CliRunner()
    result = runner.invoke(cli_app, ["dashboard", "--help"])
    assert result.exit_code == 0
    assert "Launch the interactive Streamlit" in result.output
    assert "--port" in result.output


def test_dashboard_app_syntax():
    """Verify that app.py compiles cleanly as valid Python code."""
    app_path = Path(__file__).parent.parent.parent / "src" / "codebase_historian" / "dashboard" / "app.py"
    assert app_path.exists()
    content = app_path.read_text(encoding="utf-8")
    compiled = compile(content, str(app_path), "exec")
    assert compiled is not None
