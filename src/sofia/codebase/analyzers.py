from pathlib import Path
from typing import Protocol

from sofia.codebase.model import (
    CodebaseFile,
    PythonModule,
    SourceFileKind,
)


class CodebaseAnalyzer(Protocol):
    """
    Contract implemented by language-specific codebase analyzers.

    An analyzer is read-only. It determines whether it can analyze
    a source artifact and, when selected, produces structured evidence.
    """

    @property
    def name(self) -> str:
        """Return the stable analyzer name."""

    @property
    def source_file_kind(self) -> SourceFileKind:
        """Return the source-file classification used by the core."""

    def supports(
        self,
        path: Path,
    ) -> bool:
        """Return whether this analyzer can analyze the supplied path."""

    def analyze(
        self,
        path: Path,
        module_name: str,
    ) -> object:
        """Analyze an authorized source artifact."""


class CodebaseAnalyzerRegistry:
    """
    Registry of language-specific codebase analyzers.

    The registry is intentionally independent of any particular
    programming language. The core codebase inspector depends on
    this contract rather than on a concrete analyzer implementation.
    """

    def __init__(
        self,
        analyzers: tuple[CodebaseAnalyzer, ...] = (),
    ) -> None:
        if not isinstance(analyzers, tuple):
            raise TypeError(
                "analyzers must be a tuple."
            )

        self._analyzers: list[CodebaseAnalyzer] = []

        for analyzer in analyzers:
            self.register(analyzer)

    @property
    def analyzers(self) -> tuple[CodebaseAnalyzer, ...]:
        """Return the registered analyzers in registration order."""
        return tuple(self._analyzers)

    def register(
        self,
        analyzer: CodebaseAnalyzer,
    ) -> None:
        """
        Register one analyzer.

        Analyzer names are stable identifiers and must be unique.
        """
        if not isinstance(
            analyzer.name,
            str,
        ):
            raise TypeError(
                "analyzer.name must be a string."
            )

        if not analyzer.name.strip():
            raise ValueError(
                "analyzer.name must not be empty."
            )

        if not isinstance(
            analyzer.source_file_kind,
            SourceFileKind,
        ):
            raise TypeError(
                "analyzer.source_file_kind must be a "
                "SourceFileKind."
            )

        if not callable(analyzer.supports):
            raise TypeError(
                "analyzer.supports must be callable."
            )

        if not callable(analyzer.analyze):
            raise TypeError(
                "analyzer.analyze must be callable."
            )

        if any(
            existing.name == analyzer.name
            for existing in self._analyzers
        ):
            raise ValueError(
                f"Analyzer already registered: "
                f"{analyzer.name}"
            )

        self._analyzers.append(analyzer)

    def analyzer_for(
        self,
        path: Path,
    ) -> CodebaseAnalyzer | None:
        """
        Return the first registered analyzer supporting the path.

        Returning None is meaningful. It means no language-specific
        analyzer currently claims the artifact.
        """
        if not isinstance(path, Path):
            raise TypeError(
                "path must be a Path."
            )

        for analyzer in self._analyzers:
            if analyzer.supports(path):
                return analyzer

        return None

    def classify(
        self,
        path: Path,
    ) -> SourceFileKind:
        """
        Classify a source artifact using the registered analyzers.

        Artifacts without a language-specific analyzer remain OTHER.
        """
        analyzer = self.analyzer_for(path)

        if analyzer is None:
            return SourceFileKind.OTHER

        return analyzer.source_file_kind


def create_default_analyzer_registry() -> CodebaseAnalyzerRegistry:
    """
    Create Sofía's built-in analyzer registry.

    Python is currently the first language-specific analyzer.
    Additional analyzers can be registered without modifying the
    core CodebaseInspector.
    """
    from sofia.codebase.python import PythonAnalyzer

    return CodebaseAnalyzerRegistry(
        analyzers=(
            PythonAnalyzer(),
        ),
    )


def python_module_from_analysis(
    result: object,
) -> PythonModule | None:
    """
    Extract Python evidence from an analyzer result.

    This compatibility boundary lets the current evidence model
    continue exposing PythonModule while the analyzer architecture
    remains language-neutral.
    """
    if isinstance(result, PythonModule):
        return result

    return None


def file_from_path(
    path: Path,
    analyzer_registry: CodebaseAnalyzerRegistry,
) -> CodebaseFile:
    """
    Create core file metadata using the analyzer registry.
    """
    if not isinstance(path, Path):
        raise TypeError(
            "path must be a Path."
        )

    if not isinstance(
        analyzer_registry,
        CodebaseAnalyzerRegistry,
    ):
        raise TypeError(
            "analyzer_registry must be a "
            "CodebaseAnalyzerRegistry."
        )

    try:
        size = path.stat().st_size
    except OSError as exc:
        raise OSError(
            f"Unable to inspect source file metadata: {path}"
        ) from exc

    return CodebaseFile(
        path=path,
        kind=analyzer_registry.classify(path),
        size_bytes=size,
    )