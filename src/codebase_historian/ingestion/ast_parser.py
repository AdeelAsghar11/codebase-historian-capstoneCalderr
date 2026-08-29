"""
Python AST parser using standard library `ast`.
Extracts structure, docstrings, classes, functions, and import dependencies from Python source files.
"""

import ast
from pathlib import Path

from codebase_historian.ingestion.models import (
    ASTClassRecord,
    ASTFunctionRecord,
    ASTImportRecord,
    FileStructureRecord,
)


class ASTParser:
    """Parses Python source code to extract structural symbols, docstrings, and dependencies."""

    @staticmethod
    def parse_source(source_code: str, file_path: str = "") -> FileStructureRecord:
        """Parse source code string into a structured FileStructureRecord."""
        try:
            tree = ast.parse(source_code)
        except SyntaxError:
            # If source has syntax errors, return record with raw_content but empty symbols
            return FileStructureRecord(
                path=file_path.replace("\\", "/"),
                raw_content=source_code,
            )

        module_doc = ast.get_docstring(tree)
        functions: list[ASTFunctionRecord] = []
        classes: list[ASTClassRecord] = []
        imports: list[ASTImportRecord] = []

        for node in tree.body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                functions.append(ASTParser._extract_function(node, parent_qualname=""))
            elif isinstance(node, ast.ClassDef):
                classes.append(ASTParser._extract_class(node))
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    alias_map = {alias.name: alias.asname} if alias.asname else {}
                    imports.append(
                        ASTImportRecord(
                            module=alias.name,
                            names=[alias.name],
                            alias_map=alias_map,
                            import_kind="direct",
                            level=0,
                        )
                    )
            elif isinstance(node, ast.ImportFrom):
                names = [alias.name for alias in node.names]
                alias_map = {
                    alias.name: alias.asname for alias in node.names if alias.asname
                }
                kind = "relative" if (node.level and node.level > 0) else "from"
                imports.append(
                    ASTImportRecord(
                        module=node.module,
                        names=names,
                        alias_map=alias_map,
                        import_kind=kind,
                        level=node.level or 0,
                    )
                )

        return FileStructureRecord(
            path=file_path.replace("\\", "/"),
            language="python",
            classes=classes,
            functions=functions,
            imports=imports,
            docstring=module_doc,
            raw_content=source_code,
        )

    @staticmethod
    def parse_file(file_path: str | Path) -> FileStructureRecord | None:
        """Read and parse a Python file from disk."""
        path = Path(file_path)
        if not path.is_file() or path.suffix != ".py":
            return None

        try:
            content = path.read_text(encoding="utf-8", errors="replace")
            return ASTParser.parse_source(content, str(path))
        except Exception:
            return None

    @staticmethod
    def _extract_function(
        node: ast.FunctionDef | ast.AsyncFunctionDef,
        parent_qualname: str = "",
    ) -> ASTFunctionRecord:
        name = node.name
        qualname = f"{parent_qualname}.{name}" if parent_qualname else name
        docstring = ast.get_docstring(node)
        start_line = getattr(node, "lineno", 1)
        end_line = getattr(node, "end_lineno", start_line)

        return ASTFunctionRecord(
            name=name,
            qualname=qualname,
            docstring=docstring,
            start_line=start_line,
            end_line=end_line,
            is_async=isinstance(node, ast.AsyncFunctionDef),
        )

    @staticmethod
    def _extract_class(node: ast.ClassDef) -> ASTClassRecord:
        name = node.name
        qualname = name
        docstring = ast.get_docstring(node)
        start_line = getattr(node, "lineno", 1)
        end_line = getattr(node, "end_lineno", start_line)

        base_classes: list[str] = []
        for base in node.bases:
            if isinstance(base, ast.Name):
                base_classes.append(base.id)
            elif isinstance(base, ast.Attribute):
                base_classes.append(f"{ast.unparse(base)}")

        methods: list[ASTFunctionRecord] = []
        for item in node.body:
            if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                methods.append(ASTParser._extract_function(item, parent_qualname=qualname))

        return ASTClassRecord(
            name=name,
            qualname=qualname,
            docstring=docstring,
            start_line=start_line,
            end_line=end_line,
            methods=methods,
            base_classes=base_classes,
        )

    @staticmethod
    def resolve_dependencies(
        records: list[FileStructureRecord],
        repo_root: str | Path | None = None,
    ) -> list[tuple[str, str, str]]:
        """
        Resolve import statements across parsed file structures to discover File -> File DEPENDS_ON relations.
        Returns a list of tuples: (source_file, target_file, import_kind).
        """
        # Create lookup mapping of module names to file paths
        module_to_file: dict[str, str] = {}
        for rec in records:
            norm_path = rec.path.replace("\\", "/")
            # Handle typical python layouts: src/pkg/foo.py or pkg/foo.py
            clean = norm_path
            clean = clean.removeprefix("src/")
            clean = clean.removesuffix(".py")
            mod_key = clean.replace("/", ".")
            module_to_file[mod_key] = norm_path
            # Also register package __init__
            if mod_key.endswith(".__init__"):
                pkg_key = mod_key[:-9]
                module_to_file[pkg_key] = norm_path

        dependencies: list[tuple[str, str, str]] = []
        for rec in records:
            source_path = rec.path.replace("\\", "/")
            for imp in rec.imports:
                target_file = None
                if imp.module:
                    # Check exact match
                    if imp.module in module_to_file:
                        target_file = module_to_file[imp.module]
                    else:
                        # Check prefix matches (e.g. from foo.bar.baz import x where foo.bar is a module)
                        parts = imp.module.split(".")
                        for i in range(len(parts) - 1, 0, -1):
                            prefix = ".".join(parts[:i])
                            if prefix in module_to_file:
                                target_file = module_to_file[prefix]
                                break

                # Check if imported names match submodules
                if not target_file and imp.module:
                    for name in imp.names:
                        submodule = f"{imp.module}.{name}"
                        if submodule in module_to_file:
                            target_file = module_to_file[submodule]
                            break

                if target_file and target_file != source_path:
                    dependencies.append((source_path, target_file, imp.import_kind))

        return dependencies
