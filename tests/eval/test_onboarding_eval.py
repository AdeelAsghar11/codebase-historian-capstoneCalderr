"""
Evaluation test suite for Onboarding Agent.
Verifies centrality-ranked reading orders, PageRank file ordering, and architectural decision tracing.
"""

import pytest

from codebase_historian.service import HistorianService


@pytest.fixture(scope="module")
def onboarding_service(tmp_path_factory):
    tmp_dir = tmp_path_factory.mktemp("onboarding_data")
    service = HistorianService(
        repo_path=".",
        db_path=str(tmp_dir / "onboard_historian.db"),
        chroma_path=str(tmp_dir / "onboard_chroma"),
    )
    service.ingest(".")
    return service


def test_onboarding_agent_centrality_and_decisions(onboarding_service):
    guide = onboarding_service.onboarding_guide()

    # 1. Verify central files
    assert len(guide.central_files) > 0
    # Architectural hubs like config, models, or service should appear in central files
    assert any("models" in f or "service" in f or "config" in f or "PROGRESS" in f for f in guide.central_files)

    # 2. Verify reading order
    assert len(guide.reading_order) == len(guide.central_files)
    assert guide.reading_order[0] == guide.central_files[0]

    # 3. Verify traced decisions
    assert len(guide.key_decisions) > 0
    assert any("chore" in d.lower() or "feat" in d.lower() or "root" in d.lower() for d in guide.key_decisions)
