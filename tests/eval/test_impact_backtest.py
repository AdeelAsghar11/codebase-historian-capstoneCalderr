"""
Historical backtest evaluation test suite.
Evaluates whether Impact / Risk agent blast radius predictions achieve Precision >= 0.60.
"""

from pathlib import Path

import pytest

from codebase_historian.service import HistorianService
from tests.eval.backtest_runner import run_impact_backtest


@pytest.fixture(scope="module")
def backtest_service(tmp_path_factory):
    tmp_dir = tmp_path_factory.mktemp("backtest_data")
    service = HistorianService(
        repo_path=".",
        db_path=str(tmp_dir / "backtest_historian.db"),
        chroma_path=str(tmp_dir / "backtest_chroma"),
    )
    service.ingest(".")
    return service


def test_impact_risk_agent_historical_backtest(backtest_service):
    backtest_set_path = Path(__file__).parent / "impact_backtest_set.json"
    assert backtest_set_path.exists(), "Impact backtest JSON missing"

    results = run_impact_backtest(
        service=backtest_service,
        backtest_set_path=backtest_set_path,
    )

    print(f"\nImpact Backtest Precision: {results['avg_precision'] * 100:.1f}%, Recall: {results['avg_recall'] * 100:.1f}%")
    for d in results["details"]:
        print(f"[{d['case_id']}] Precision: {d['precision']:.2f}, Recall: {d['recall']:.2f}, Predicted: {d['predicted_count']}, Overlap: {d['overlap_count']}")

    assert results["total_cases"] == 5
    assert results["target_met"] is True, f"Average precision {results['avg_precision']} < 0.60 target"
    assert results["avg_precision"] >= 0.60
