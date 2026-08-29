"""
Faithfulness evaluation test suite.
Verifies that Historian answers achieve >= 80% faithfulness against ground truth citations.
"""

from pathlib import Path

import pytest

from codebase_historian.service import HistorianService
from tests.eval.eval_runner import run_faithfulness_eval


@pytest.fixture(scope="module")
def eval_service(tmp_path_factory):
    tmp_dir = tmp_path_factory.mktemp("eval_data")
    service = HistorianService(
        repo_path=".",
        db_path=str(tmp_dir / "eval_historian.db"),
        chroma_path=str(tmp_dir / "eval_chroma"),
    )
    service.ingest(".")
    return service


def test_reference_repository_faithfulness_eval(eval_service):
    eval_set_path = Path(__file__).parent / "reference_eval_set.json"
    assert eval_set_path.exists(), "Reference eval set JSON missing"

    results = run_faithfulness_eval(
        service=eval_service,
        eval_set_path=eval_set_path,
        repo_path=".",
    )

    print(f"\nFaithfulness Evaluation Results: {results['faithfulness_rate'] * 100:.1f}%")
    for d in results["details"]:
        status_str = "PASS" if d["faithful"] else "FAIL"
        print(f"[{status_str}] {d['case_id']} - {d['target']} (Grounded: {d['grounded_in_git']}, Citations: {d['citations_count']})")

    assert results["total_cases"] == 5
    assert results["target_met"] is True, f"Faithfulness rate {results['faithfulness_rate']} < 0.80 target"
    assert results["faithfulness_rate"] >= 0.80
