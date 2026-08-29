"""
Supervisor routing agent.
Analyzes user requests and routes execution to the appropriate specialist agent.
"""

import re
from typing import Any, Dict, Optional, Tuple

from codebase_historian.agents.state import AgentState


class SupervisorAgent:
    """Supervisor router that inspects queries and routes to the appropriate specialist."""

    def __init__(self, llm: Optional[Any] = None):
        self.llm = llm

    def route_query(self, query: str, target: Optional[str] = None) -> Tuple[str, Optional[str]]:
        """
        Classify query intent and return (route, target).
        Available routes:
        - "historian": "why", "who", "when", "explain", "history", "blame"
        - "impact": "impact", "blast radius", "affect", "break", "dependencies"
        - "refactor": "refactor", "improve", "clean up", "restructure", "optimize"
        - "onboarding": "onboard", "guide", "overview", "start", "architecture"
        """
        q_lower = query.lower()

        # 1. Onboarding patterns
        if any(w in q_lower for w in ["onboard", "contributor guide", "reading order", "getting started", "codebase overview"]):
            return "onboarding", target

        # 2. Refactor patterns
        if any(w in q_lower for w in ["refactor", "propose change", "clean up", "improve structure", "restructure"]):
            extracted_target = target or self._extract_target(query)
            return "refactor", extracted_target

        # 3. Impact / Risk patterns
        if any(w in q_lower for w in ["impact", "blast radius", "what would change", "affect", "break", "risk"]):
            extracted_target = target or self._extract_target(query)
            return "impact", extracted_target

        # 4. Default / Historian patterns ("why", "explain", "history", "who made")
        extracted_target = target or self._extract_target(query)
        return "historian", extracted_target

    def _extract_target(self, query: str) -> Optional[str]:
        """Try to extract a file path or symbol name mentioned in the query."""
        # Check for paths with extensions like .py, .md, .json, .ts
        path_match = re.search(r"[\w/\\]+\.(?:py|md|json|ts|js|html|css|yaml|yml)\b", query)
        if path_match:
            return path_match.group(0).replace("\\", "/")

        # Check for quoted names like 'func_name' or `ClassName`
        quoted_match = re.search(r"[`'\"]([A-Za-z_][A-Za-z0-9_.]*)[`'\"]", query)
        if quoted_match:
            return quoted_match.group(1)

        return None

    def __call__(self, state: AgentState) -> Dict[str, Any]:
        """LangGraph node function for supervisor routing."""
        query = state.get("query", "")
        existing_target = state.get("target")

        route, target = self.route_query(query, existing_target)

        return {
            "route": route,
            "target": target,
            "status": f"routed_to_{route}",
        }
