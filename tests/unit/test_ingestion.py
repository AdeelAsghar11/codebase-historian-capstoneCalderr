"""
Unit tests for the ingestion pipeline, git extraction, and AST parsing.
"""

from pathlib import Path
import git
import pytest

from codebase_historian.ingestion.ast_parser import ASTParser
from codebase_historian.ingestion.git_extractor import GitExtractor
from codebase_historian.ingestion.pipeline import IngestionPipeline


SAMPLE_CODE = '''"""Sample module docstring."""

from typing import List, Optional
import os
import sys as system
from .local_helper import util_fn

class BaseWorker:
    """Base worker class docstring."""
    def __init__(self, name: str):
        self.name = name

    def execute(self) -> bool:
        """Execute task."""
        return True

class AsyncWorker(BaseWorker):
    async def run_async(self) -> str:
        """Asynchronous execution."""
        return "done"

def standalone_function(x: int) -> int:
    """Computes square."""
    return x * x
'''


def test_ast_parser_extracts_symbols():
    record = ASTParser.parse_source(SAMPLE_CODE, "sample.py")

    assert record.docstring == "Sample module docstring."
    assert record.path == "sample.py"
    assert len(record.classes) == 2
    assert len(record.functions) == 1

    # Check standalone function
    fn = record.functions[0]
    assert fn.name == "standalone_function"
    assert fn.qualname == "standalone_function"
    assert fn.docstring == "Computes square."
    assert not fn.is_async

    # Check BaseWorker class
    cls_base = record.classes[0]
    assert cls_base.name == "BaseWorker"
    assert cls_base.docstring == "Base worker class docstring."
    assert len(cls_base.methods) == 2
    method_names = [m.name for m in cls_base.methods]
    assert "__init__" in method_names
    assert "execute" in method_names
    assert cls_base.methods[1].qualname == "BaseWorker.execute"

    # Check AsyncWorker inheritance and async method
    cls_async = record.classes[1]
    assert cls_async.name == "AsyncWorker"
    assert "BaseWorker" in cls_async.base_classes
    assert len(cls_async.methods) == 1
    assert cls_async.methods[0].name == "run_async"
    assert cls_async.methods[0].is_async is True

    # Check imports
    direct_imports = [imp for imp in record.imports if imp.import_kind == "direct"]
    from_imports = [imp for imp in record.imports if imp.import_kind in ("from", "relative")]

    assert any(imp.module == "os" for imp in direct_imports)
    assert any(imp.module == "sys" and imp.alias_map.get("sys") == "system" for imp in direct_imports)
    assert any(imp.module == "typing" and "List" in imp.names for imp in from_imports)
    assert any(imp.level == 1 and imp.module == "local_helper" for imp in from_imports)


def test_ast_parser_syntax_error_fallback():
    invalid_code = "def broken_syntax(:"
    record = ASTParser.parse_source(invalid_code, "bad.py")
    assert record.raw_content == invalid_code
    assert record.classes == []
    assert record.functions == []


def test_ast_parser_dependency_resolution():
    code_a = "from pkg.service_b import helper\n"
    code_b = "def helper(): pass\n"

    rec_a = ASTParser.parse_source(code_a, "src/pkg/service_a.py")
    rec_b = ASTParser.parse_source(code_b, "src/pkg/service_b.py")

    deps = ASTParser.resolve_dependencies([rec_a, rec_b])
    assert len(deps) == 1
    src, target, kind = deps[0]
    assert src == "src/pkg/service_a.py"
    assert target == "src/pkg/service_b.py"
    assert kind == "from"


@pytest.fixture
def temp_git_repo(tmp_path: Path):
    """Fixture that initializes a temporary Git repository with sample commits."""
    repo = git.Repo.init(tmp_path)
    
    # Configure git author for the temporary repo
    with repo.config_writer() as config:
        config.set_value("user", "name", "Test Historian")
        config.set_value("user", "email", "historian@example.com")

    file1 = tmp_path / "module_a.py"
    file2 = tmp_path / "module_b.py"

    # Commit 1: Add module_a.py
    file1.write_text("def func_a():\n    return 1\n", encoding="utf-8")
    repo.index.add([str(file1)])
    c1 = repo.index.commit("feat: initial commit with module_a")

    # Commit 2: Co-change module_a.py and module_b.py
    file1.write_text("def func_a():\n    return 2\n", encoding="utf-8")
    file2.write_text("import module_a\ndef func_b():\n    return module_a.func_a()\n", encoding="utf-8")
    repo.index.add([str(file1), str(file2)])
    c2 = repo.index.commit("feat: update module_a and add module_b")

    return tmp_path, [c1.hexsha, c2.hexsha]


def test_git_extractor_extracts_commits_and_co_changes(temp_git_repo):
    repo_path, shas = temp_git_repo
    extractor = GitExtractor(repo_path)

    commits = extractor.extract_commits()
    assert len(commits) == 2
    assert commits[0].sha == shas[0]
    assert commits[1].sha == shas[1]
    assert commits[0].author.display_name == "Test Historian"
    assert commits[0].author.id == "historian@example.com"
    assert commits[1].parent_shas == [shas[0]]

    # Check modifications in commit 2
    c2_mods = commits[1].modifications
    mod_paths = {m.path for m in c2_mods}
    assert "module_a.py" in mod_paths
    assert "module_b.py" in mod_paths

    # Check co-change computation
    co_changes = extractor.compute_co_changes(commits)
    assert len(co_changes) == 1
    assert co_changes[0].file_a == "module_a.py"
    assert co_changes[0].file_b == "module_b.py"
    assert co_changes[0].co_change_count == 1
    assert co_changes[0].last_co_change_commit == shas[1]


def test_ingestion_pipeline_run(temp_git_repo):
    repo_path, shas = temp_git_repo
    pipeline = IngestionPipeline(repo_path)
    result = pipeline.run()

    assert result.repo_path == str(repo_path)
    assert result.last_indexed_commit_sha == shas[1]
    assert len(result.commits) == 2
    assert len(result.co_changes) == 1
    assert len(result.file_structures) == 2
    assert result.stats["total_commits"] == 2
    assert result.stats["total_python_files"] == 2
