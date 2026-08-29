"""
Historical backtest evaluation runner for the Impact / Risk agent.
Hides a historical commit and evaluates whether blast-radius prediction matches actual co-changed files.
Target: Precision >= 0.60 per PRD.md and TESTING.md.
"""

import json
from pathlib import Path
from typing import Any, Dict, List

from codebase_historian.service import HistorianService


def run_impact_backtest(
    service: HistorianService,
    backtest_set_path: str | Path,
) -> Dict[str, Any]:
    """
    Run historical backtest against curated multi-file commits.
    Compares predicted affected files against actual ground truth changes.
    """
    path = Path(backtest_set_path)
    cases: List[Dict[str, Any]] = json.loads(path.read_text(encoding="utf-8"))

    results = []
    precisions: List[float] = []
    recalls: List[float] = []

    for case in cases:
        case_id = case["id"]
        trigger_file = case["trigger_file"]
        message = case.get("commit_message", "")
        actual = set(case["actual_affected_files"])

        # Call Impact / Risk agent
        resp = service.impact(change_description=message, target=trigger_file)
        predicted = set(resp.affected_files)

        # Calculate True Positives, Precision, and Recall
        tp = len(predicted & actual)
        precision = tp / len(predicted) if predicted else 0.0
        recall = tp / len(actual) if actual else 0.0

        precisions.append(precision)
        recalls.append(recall)

        results.append(
            {
                "case_id": case_id,
                "trigger_file": trigger_file,
                "predicted_count": len(predicted),
                "actual_count": len(actual),
                "overlap_count": tp,
                "precision": round(precision, 4),
                "recall": round(recall, 4),
                "evidence": resp.evidence,
                "confidence": resp.confidence,
            }
        )

    avg_precision = sum(precisions) / len(precisions) if precisions else 0.0
    avg_recall = sum(recalls) / len(recalls) if recalls else 0.0

    return {
        "total_cases": len(cases),
        "avg_precision": round(avg_precision, 4),
        "avg_recall": round(avg_recall, 4),
        "target_met": avg_precision >= 0.60,
        "details": results,
    }


if __name__ == "__main__":
    service = HistorianService()
    service.ingest(".")
    eval_path = Path(__file__).parent / "impact_backtest_set.json"
    report = run_impact_backtest(service, eval_path)
    print(json.dumps(report, indent=2))
