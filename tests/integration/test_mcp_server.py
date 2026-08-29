"""
Integration tests for the FastMCP / MCPServer tools interface.
Validates tool schemas, live tool calls, human review safety, and structured audit logs.
"""

from pathlib import Path

import pytest

from codebase_historian.mcp_server.server import create_mcp_server
from codebase_historian.service import HistorianService


@pytest.fixture
def mcp_service(tmp_path: Path):
    """Initializes a connected HistorianService for MCP testing."""
    service = HistorianService(
        repo_path=".",
        db_path=str(tmp_path / "mcp_historian.db"),
        chroma_path=str(tmp_path / "mcp_chroma"),
    )
    service.ingest(".")
    return service


@pytest.mark.asyncio
async def test_mcp_server_tools_registered(mcp_service):
    server = create_mcp_server(mcp_service)

    tools = await server.list_tools()
    tool_names = [t.name for t in tools]

    # Verify all 4 required MCP tools are present
    assert "explain_code" in tool_names
    assert "trace_impact" in tool_names
    assert "suggest_refactor" in tool_names
    assert "onboarding_guide" in tool_names


@pytest.mark.asyncio
async def test_mcp_server_tool_executions(mcp_service):
    server = create_mcp_server(mcp_service)

    # 1. explain_code
    res_explain = await server.call_tool(
        "explain_code",
        {"target": "src/codebase_historian/config.py"},
    )
    assert not res_explain.is_error
    assert len(res_explain.content) > 0
    explain_data = res_explain.structured_content.get("result", {})
    assert "answer" in explain_data
    assert explain_data.get("confidence", 0) > 0

    # 2. trace_impact
    res_impact = await server.call_tool(
        "trace_impact",
        {"change_description": "Modify src/codebase_historian/config.py settings"},
    )
    assert not res_impact.is_error
    impact_data = res_impact.structured_content.get("result", {})
    assert "affected_files" in impact_data
    assert "evidence" in impact_data

    # 3. suggest_refactor (MUST be strictly pending_human_review)
    res_refactor = await server.call_tool(
        "suggest_refactor",
        {"target": "src/codebase_historian/config.py"},
    )
    assert not res_refactor.is_error
    refactor_data = res_refactor.structured_content.get("result", {})
    assert refactor_data.get("status") == "pending_human_review"
    assert "proposal" in refactor_data
    assert "critic_verdict" in refactor_data

    # 4. onboarding_guide
    res_onboard = await server.call_tool("onboarding_guide", {})
    assert not res_onboard.is_error
    onboard_data = res_onboard.structured_content.get("result", {})
    assert "central_files" in onboard_data

    # 5. Verify MCP audit logs were recorded in SQLite
    audit_logs = mcp_service.memory_store.list_audit_logs(limit=10)
    assert len(audit_logs) >= 4
    mcp_callers = [log.caller_id for log in audit_logs]
    assert all(c == "mcp_client" for c in mcp_callers[:4])
    mcp_tools = [log.tool_name for log in audit_logs]
    assert "explain_code" in mcp_tools
    assert "trace_impact" in mcp_tools
    assert "suggest_refactor" in mcp_tools
    assert "onboarding_guide" in mcp_tools
