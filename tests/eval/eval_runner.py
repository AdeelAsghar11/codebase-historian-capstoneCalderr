"""
Faithfulness evaluation harness.
Evaluates Historian citations against git history ground truth.
Target: Faithfulness >= 80% per PRD.md.
"""

import json
from pathlib import Path
from typing import Any

import git

from codebase_historian.service import HistorianService


def run_faithfulness_eval(
    service: HistorianService,
    eval_set_path: str | Path,
    repo_path: str | Path = ".",
) -> dict[str, Any]:
    """
    Run faithfulness evaluation against a curated ground-truth question set.
    Validates whether citations reference real commits and match historical keywords.
    """
    path = Path(eval_set_path)
    cases: list[dict[str, Any]] = json.loads(path.read_text(encoding="utf-8"))

    repo = git.Repo(Path(repo_path).resolve())
    # Retrieve all valid commit SHAs from repo
    valid_shas = {c.hexsha for c in repo.iter_commits("HEAD", max_count=50)}

    results = []
    correct_count = 0

    for case in cases:
        target = case["target"]
        min_citations = case.get("min_citations", 1)
        expected_keywords = [k.lower() for k in case.get("expected_keywords", [])]

        response = service.explain(target)

        # 1. Check citation count
        has_citations = len(response.citations) >= min_citations

        # 2. Check citation verifiability (SHA exists in git history)
        valid_citations = [
            c for c in response.citations
            if c.commit_sha and c.commit_sha in valid_shas
        ]
        is_grounded = len(valid_citations) > 0

        # 3. Check relevance of answer text against historical keywords
        full_text = (response.answer + " " + " ".join([c.excerpt for c in response.citations])).lower()
        keyword_match = any(k in full_text for k in expected_keywords)

        is_faithful = has_citations and is_grounded and keyword_match
        if is_faithful:
            correct_count += 1

        results.append(
            {
                "case_id": case["id"],
                "target": target,
                "faithful": is_faithful,
                "has_citations": has_citations,
                "grounded_in_git": is_grounded,
                "keyword_match": keyword_match,
                "confidence": response.confidence,
                "citations_count": len(response.citations),
            }
        )

    total_cases = len(cases)
    faithfulness_rate = correct_count / total_cases if total_cases > 0 else 0.0

    return {
        "total_cases": total_cases,
        "correct_count": correct_count,
        "faithfulness_rate": round(faithfulness_rate, 4),
        "target_met": faithfulness_rate >= 0.80,
        "details": results,
    }


if __name__ == "__main__":
    service = HistorianService()
    service.ingest(".")
    eval_set = Path(__file__).parent / "reference_eval_set.json"
    report = run_faithfulness_eval(service, eval_set)
    print(json.dumps(report, indent=2))
