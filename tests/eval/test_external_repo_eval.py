"""
Phase 3 Evaluation: Validation against a second, external repository never seen during development.
Validates ingestion, knowledge graph, hybrid retrieval, and agent reasoning generalize without tuning.
"""

from pathlib import Path

import git
import pytest

from codebase_historian.service import HistorianService
from tests.eval.eval_runner import run_faithfulness_eval


@pytest.fixture(scope="module")
def external_repo(tmp_path_factory):
    """
    Creates an external fixture repository never seen during development
    with multi-commit git history and realistic AST dependencies.
    """
    repo_dir = tmp_path_factory.mktemp("external_repo")
    repo = git.Repo.init(repo_dir)

    author = git.Actor("External Contributor", "contributor@external.dev")

    # Commit 1: Initial task queue and router
    (repo_dir / "queue.py").write_text(
        '"""Task queue implementation for asynchronous message processing."""\n\n'
        'class TaskQueue:\n'
        '    def __init__(self):\n'
        '        self.items = []\n'
        '    def push(self, item):\n'
        '        self.items.append(item)\n',
        encoding="utf-8",
    )
    (repo_dir / "router.py").write_text(
        '"""Task router directing tasks to available queues."""\n'
        'from queue import TaskQueue\n\n'
        'class TaskRouter:\n'
        '    def __init__(self):\n'
        '        self.queue = TaskQueue()\n',
        encoding="utf-8",
    )
    repo.index.add(["queue.py", "router.py"])
    repo.index.commit("feat: initial commit of task queue and base router", author=author, committer=author)

    # Commit 2: Worker pool and error handling
    (repo_dir / "worker.py").write_text(
        '"""Async worker pool processing tasks from queue."""\n'
        'from queue import TaskQueue\n\n'
        'class TaskWorker:\n'
        '    def __init__(self, queue: TaskQueue):\n'
        '        self.queue = queue\n'
        '    def run(self):\n'
        '        pass\n',
        encoding="utf-8",
    )
    (repo_dir / "errors.py").write_text(
        '"""Error definitions for task routing."""\n'
        'class TaskTimeoutError(Exception):\n'
        '    pass\n',
        encoding="utf-8",
    )
    repo.index.add(["worker.py", "errors.py"])
    repo.index.commit("feat: implement async worker pool and error handler", author=author, committer=author)

    # Commit 3: Priority queue optimization
    (repo_dir / "priority.py").write_text(
        '"""Priority heap algorithm for high-urgency tasks."""\n'
        'import heapq\n\n'
        'class PriorityScheduler:\n'
        '    def __init__(self):\n'
        '        self.heap = []\n',
        encoding="utf-8",
    )
    (repo_dir / "router.py").write_text(
        '"""Task router directing tasks to available queues with priority scheduling."""\n'
        'from queue import TaskQueue\n'
        'from priority import PriorityScheduler\n\n'
        'class TaskRouter:\n'
        '    def __init__(self):\n'
        '        self.queue = TaskQueue()\n'
        '        self.scheduler = PriorityScheduler()\n',
        encoding="utf-8",
    )
    repo.index.add(["priority.py", "router.py"])
    repo.index.commit("refactor: optimize task scheduling with priority heap", author=author, committer=author)

    # Commit 4: Worker timeout bugfix
    (repo_dir / "worker.py").write_text(
        '"""Async worker pool processing tasks from queue with timeout safety."""\n'
        'from queue import TaskQueue\n'
        'from errors import TaskTimeoutError\n\n'
        'class TaskWorker:\n'
        '    def __init__(self, queue: TaskQueue):\n'
        '        self.queue = queue\n'
        '    def run_safe(self, timeout=30):\n'
        '        pass\n',
        encoding="utf-8",
    )
    repo.index.add(["worker.py"])
    repo.index.commit("fix: handle connection timeout in worker pool", author=author, committer=author)

    return repo_dir


@pytest.fixture(scope="module")
def external_service(external_repo, tmp_path_factory):
    """Initializes a clean HistorianService pointed at the second repository."""
    data_dir = tmp_path_factory.mktemp("external_service_data")
    service = HistorianService(
        repo_path=str(external_repo),
        db_path=str(data_dir / "external_historian.db"),
        chroma_path=str(data_dir / "external_chroma"),
    )
    service.ingest(str(external_repo))
    return service


def test_external_repository_faithfulness_eval(external_service, external_repo):
    """
    Reruns the full faithfulness evaluation against the unseen second repository.
    Asserts >= 80% faithfulness target is satisfied.
    """
    eval_set_path = Path(__file__).parent / "external_eval_set.json"
    assert eval_set_path.exists(), "External eval set JSON missing"

    results = run_faithfulness_eval(
        service=external_service,
        eval_set_path=eval_set_path,
        repo_path=external_repo,
    )

    print(f"\nExternal Repo Faithfulness: {results['faithfulness_rate'] * 100:.1f}%")
    for d in results["details"]:
        print(f"[{'PASS' if d['faithful'] else 'FAIL'}] {d['case_id']} - {d['target']} (Grounded: {d['grounded_in_git']}, Citations: {d['citations_count']})")

    assert results["total_cases"] == 4
    assert results["target_met"] is True, f"Faithfulness {results['faithfulness_rate']} < 0.80 target"
    assert results["faithfulness_rate"] >= 0.80


def test_external_repository_agents_generalization(external_service):
    """
    Asserts that Impact and Onboarding agents function correctly on the external repository.
    """
    # 1. Onboarding Guide
    onboarding = external_service.onboarding_guide()
    assert len(onboarding.central_files) > 0
    assert "queue.py" in onboarding.central_files or "router.py" in onboarding.central_files

    # 2. Impact Prediction on queue.py
    impact = external_service.impact(
        change_description="Modify TaskQueue push method signature in queue.py",
        target="queue.py",
    )
    assert len(impact.affected_files) > 0
    assert any("worker.py" in f or "router.py" in f for f in impact.affected_files)
