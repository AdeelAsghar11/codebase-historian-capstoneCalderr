"""
Impact / Risk agent.
Predicts blast radius for proposed changes based on co-change patterns and AST dependency graphs.
"""

import re
from pathlib import Path
from typing import Any

from codebase_historian.agents.schemas import ImpactResponse
from codebase_historian.agents.state import AgentState
from codebase_historian.graph.graph import CodebaseKnowledgeGraph


class ImpactAgent:
    """Predicts blast radius and risk for proposed code changes."""

    def __init__(self, knowledge_graph: CodebaseKnowledgeGraph | None = None):
        self.kg = knowledge_graph

    def predict_impact(self, change_description: str, target: str | None = None) -> ImpactResponse:
        """Analyze change description and return predicted affected files with evidence."""
        targets = set()
        if target:
            targets.add(target.replace("\\", "/"))

        # Look for file paths inside change_description
        matches = re.findall(r"[\w/\\]+\.(?:py|md|json|ts|js|html|css)\b", change_description)
        for m in matches:
            targets.add(m.replace("\\", "/"))

        if not targets and self.kg:
            # Fallback: check if any graph file name is in description
            for node_id, data in self.kg.g.nodes(data=True):
                if data.get("type") == "File":
                    path = data.get("path", "")
                    if path and (path in change_description or Path(path).name in change_description):
                        targets.add(path)

        if not targets or not self.kg:
            return ImpactResponse(
                affected_files=[],
                confidence=0.5,
                evidence="co-change",
            )

        blast = self.kg.get_blast_radius(list(targets))

        # Filter for high-confidence affected files (>= 0.75) to exclude diluted broad changes
        filtered_blast = [b for b in blast if b["confidence"] >= 0.75]
        if not filtered_blast:
            filtered_blast = blast[:5]

        affected_files = [b["file"] for b in filtered_blast]
        evidences = [b["evidence"] for b in filtered_blast]

        primary_evidence = "both" if "both" in evidences else ("dependency" if "dependency" in evidences else "co-change")
        avg_confidence = (
            sum(b["confidence"] for b in filtered_blast) / len(filtered_blast) if filtered_blast else 0.75
        )

        return ImpactResponse(
            affected_files=affected_files,
            confidence=round(avg_confidence, 2),
            evidence=primary_evidence,
        )

    def __call__(self, state: AgentState) -> dict[str, Any]:
        """LangGraph node execution for Impact agent."""
        desc = state.get("query", "")
        target = state.get("target")
        response = self.predict_impact(desc, target)
        return {
            "impact_response": response,
            "status": "impact_completed",
        }
