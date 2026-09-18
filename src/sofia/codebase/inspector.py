from pathlib import Path

from sofia.codebase.analyzers import (
    CodebaseAnalyzerRegistry,
    create_default_analyzer_registry,
)
from sofia.codebase.model import (
    CodebaseEvidenceKind,
    CodebaseFile,
    CodebaseInspectionEvidence,
    PythonModule,
)
from sofia.codebase.relationships import (
    CodebaseRelationshipAnalyzer,
)


class CodebaseInspectionError(Exception):
    """Raised when codebase inspection cannot be completed."""


class CodebaseInspector:
    """
    Read-only bounded structural inspection of a codebase.

    Language-specific analysis is delegated to the configured
    CodebaseAnalyzerRegistry.

    This inspector does not modify, execute, or import source code.
    """

    MAX_FILES = 1_000
    MAX_FILE_BYTES = 5 * 1024 * 1024

    def __init__(
        self,
        root: Path,
        analyzer_registry: CodebaseAnalyzerRegistry | None = None,
    ) -> None:
        if not isinstance(root, Path):
            raise TypeError(
                "CodebaseInspector root must be a Path."
            )

        if analyzer_registry is None:
            analyzer_registry = (
                create_default_analyzer_registry()
            )

        if not isinstance(
            analyzer_registry,
            CodebaseAnalyzerRegistry,
        ):
            raise TypeError(
                "CodebaseInspector analyzer_registry must be "
                "a CodebaseAnalyzerRegistry or None."
            )

        self._root = root.resolve()
        self._analyzer_registry = analyzer_registry
        self._relationships = (
            CodebaseRelationshipAnalyzer()
        )

    @property
    def root(self) -> Path:
        return self._root

    @property
    def analyzer_registry(
        self,
    ) -> CodebaseAnalyzerRegistry:
        return self._analyzer_registry

    def inspect(self) -> CodebaseInspectionEvidence:
        if not self._root.exists():
            raise CodebaseInspectionError(
                f"Codebase root does not exist: {self._root}"
            )

        if not self._root.is_dir():
            raise CodebaseInspectionError(
                f"Codebase root is not a directory: {self._root}"
            )

        files = self._discover_files()

        python_modules: list[PythonModule] = []

        for file in files:
            analyzer = (
                self._analyzer_registry.analyzer_for(
                    file.path
                )
            )

            if analyzer is None:
                continue

            module_name = self._module_name(
                file.path
            )

            result = analyzer.analyze(
                file.path,
                module_name,
            )

            if isinstance(result, PythonModule):
                python_modules.append(result)

        python_modules.sort(
            key=lambda module: module.module_name
        )

        modules = tuple(python_modules)

        relationships = (
            self._relationships.analyze(modules)
        )

        return CodebaseInspectionEvidence(
            root=self._root,
            files=tuple(files),
            python_modules=modules,
            relationships=relationships,
            evidence_kind=(
                CodebaseEvidenceKind.OBSERVED
            ),
        )

    def _discover_files(
        self,
    ) -> list[CodebaseFile]:
        discovered: list[CodebaseFile] = []

        for path in sorted(
            self._root.rglob("*"),
            key=lambda item: str(item).casefold(),
        ):
            if len(discovered) >= self.MAX_FILES:
                break

            if not path.is_file():
                continue

            if self._is_ignored(path):
                continue

            try:
                size = path.stat().st_size
            except OSError:
                continue

            if size > self.MAX_FILE_BYTES:
                continue

            kind = self._analyzer_registry.classify(
                path
            )

            discovered.append(
                CodebaseFile(
                    path=path,
                    kind=kind,
                    size_bytes=size,
                )
            )

        return discovered

    def _module_name(
        self,
        path: Path,
    ) -> str:
        relative = path.relative_to(
            self._root
        )

        parts = list(relative.parts)

        if parts[-1] == "__init__.py":
            parts = parts[:-1]
        else:
            parts[-1] = Path(
                parts[-1]
            ).stem

        if not parts:
            return self._root.name

        return ".".join(parts)

    @staticmethod
    def _is_ignored(
        path: Path,
    ) -> bool:
        ignored = {
            ".git",
            ".venv",
            "venv",
            "__pycache__",
            ".pytest_cache",
            "node_modules",
        }

        return any(
            part in ignored
            for part in path.parts
        )