"""
MCP Server implementation using the official Model Context Protocol (FastMCP/MCPServer) SDK.
Exposes explain_code, trace_impact, suggest_refactor, and onboarding_guide as MCP tools.
"""

import time
from typing import Any, Dict, Optional

from mcp.server.mcpserver import MCPServer

from codebase_historian.service import HistorianService

# Export FastMCP alias per TECH_STACK.md and ROADMAP.md
FastMCP = MCPServer


def create_mcp_server(service: Optional[HistorianService] = None) -> MCPServer:
    """Create and configure the Codebase Historian MCP server."""
    historian_service = service or HistorianService()

    mcp = MCPServer(
        name="Codebase Historian",
        version="0.1.0",
        description="Multi-agent GraphRAG platform providing codebase intelligence, blast radius prediction, and reviewed refactors.",
    )

    @mcp.tool()
    def explain_code(target: str, repo_url: str = "") -> Dict[str, Any]:
        """
        Explain why a file, function, or pattern exists in the codebase.
        Cites verifiable historical commits, pull requests, and discussions.
        """
        start = time.perf_counter()
        resp = historian_service.explain(target=target, repo_url=repo_url or None)
        latency = int((time.perf_counter() - start) * 1000)

        # Record structured audit log
        if historian_service.memory_store:
            historian_service.memory_store.log_audit(
                caller_id="mcp_client",
                tool_name="explain_code",
                endpoint="mcp:explain_code",
                latency_ms=latency,
                status_code=200,
            )

        return resp.model_dump()

    @mcp.tool()
    def trace_impact(change_description: str, repo_url: str = "") -> Dict[str, Any]:
        """
        Predict blast radius and affected downstream files for a proposed change.
        Traverses historical co-change coupling and AST dependency graphs.
        """
        start = time.perf_counter()
        resp = historian_service.impact(change_description=change_description, repo_url=repo_url or None)
        latency = int((time.perf_counter() - start) * 1000)

        # Record structured audit log
        if historian_service.memory_store:
            historian_service.memory_store.log_audit(
                caller_id="mcp_client",
                tool_name="trace_impact",
                endpoint="mcp:trace_impact",
                latency_ms=latency,
                status_code=200,
            )

        return resp.model_dump()

    @mcp.tool()
    def suggest_refactor(target: str, repo_url: str = "") -> Dict[str, Any]:
        """
        Draft a concrete refactoring proposal under adversarial Critic review.
        NON-NEGOTIABLE SAFETY: Status is strictly 'pending_human_review'. Changes are never auto-committed.
        """
        start = time.perf_counter()
        resp = historian_service.suggest_refactor(target=target, repo_url=repo_url or None)
        latency = int((time.perf_counter() - start) * 1000)

        # Record structured audit log
        if historian_service.memory_store:
            historian_service.memory_store.log_audit(
                caller_id="mcp_client",
                tool_name="suggest_refactor",
                endpoint="mcp:suggest_refactor",
                latency_ms=latency,
                status_code=200,
            )

        return resp.model_dump()

    @mcp.tool()
    def onboarding_guide(repo_url: str = "") -> Dict[str, Any]:
        """
        Generate a contributor onboarding guide for the repository.
        Returns reading order, PageRank-central architectural files, and traced decisions.
        """
        start = time.perf_counter()
        resp = historian_service.onboarding_guide(repo_url=repo_url or None)
        latency = int((time.perf_counter() - start) * 1000)

        # Record structured audit log
        if historian_service.memory_store:
            historian_service.memory_store.log_audit(
                caller_id="mcp_client",
                tool_name="onboarding_guide",
                endpoint="mcp:onboarding_guide",
                latency_ms=latency,
                status_code=200,
            )

        return resp.model_dump()

    return mcp


# Default module-level MCP server instance
server = create_mcp_server()


def run_stdio():
    """Run MCP server in stdio transport mode (for CLI and editor integration)."""
    server.run()
