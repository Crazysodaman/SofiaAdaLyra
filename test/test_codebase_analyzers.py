from pathlib import Path

import pytest

from sofia.codebase import (
    CodebaseAnalyzerRegistry,
    CodebaseInspector,
    PythonAnalyzer,
    PythonInspector,
    SourceFileKind,
)


def test_default_registry_contains_python_analyzer():
    from sofia.codebase import (
        create_default_analyzer_registry,
    )

    registry = create_default_analyzer_registry()

    assert len(registry.analyzers) == 1

    analyzer = registry.analyzers[0]

    assert isinstance(
        analyzer,
        PythonAnalyzer,
    )

    assert analyzer.name == "python"
    assert (
        analyzer.source_file_kind
        is SourceFileKind.PYTHON
    )


def test_python_analyzer_supports_python_files():
    analyzer = PythonAnalyzer()

    assert analyzer.supports(
        Path("example.py")
    )

    assert analyzer.supports(
        Path("example.PY")
    )

    assert not analyzer.supports(
        Path("example.java")
    )


def test_registry_selects_python_analyzer():
    registry = CodebaseAnalyzerRegistry(
        analyzers=(
            PythonAnalyzer(),
        ),
    )

    analyzer = registry.analyzer_for(
        Path("example.py")
    )

    assert isinstance(
        analyzer,
        PythonAnalyzer,
    )


def test_registry_returns_none_when_no_analyzer_supports_file():
    registry = CodebaseAnalyzerRegistry(
        analyzers=(
            PythonAnalyzer(),
        ),
    )

    assert (
        registry.analyzer_for(
            Path("example.java")
        )
        is None
    )


def test_registry_classifies_unknown_language_as_other():
    registry = CodebaseAnalyzerRegistry(
        analyzers=(
            PythonAnalyzer(),
        ),
    )

    assert (
        registry.classify(
            Path("example.java")
        )
        is SourceFileKind.OTHER
    )


def test_registry_rejects_duplicate_analyzer_names():
    registry = CodebaseAnalyzerRegistry(
        analyzers=(
            PythonAnalyzer(),
        ),
    )

    with pytest.raises(
        ValueError,
        match="Analyzer already registered",
    ):
        registry.register(
            PythonAnalyzer()
        )


def test_python_analyzer_delegates_to_injected_inspector(
    tmp_path: Path,
):
    source = tmp_path / "example.py"

    source.write_text(
        """
class Example:
    pass
""".strip(),
        encoding="utf-8",
    )

    inspector = PythonInspector()
    analyzer = PythonAnalyzer(
        inspector=inspector,
    )

    result = analyzer.analyze(
        source,
        "example",
    )

    assert result.module_name == "example"
    assert result.path == source
    assert result.symbols[0].name == "Example"


def test_codebase_inspector_accepts_custom_analyzer_registry(
    tmp_path: Path,
):
    source = tmp_path / "example.py"

    source.write_text(
        """
def example():
    return 1
""".strip(),
        encoding="utf-8",
    )

    registry = CodebaseAnalyzerRegistry(
        analyzers=(
            PythonAnalyzer(),
        ),
    )

    inspector = CodebaseInspector(
        tmp_path,
        analyzer_registry=registry,
    )

    evidence = inspector.inspect()

    assert len(evidence.python_modules) == 1
    assert (
        evidence.python_modules[0].module_name
        == "example"
    )


def test_codebase_inspector_does_not_require_python_analyzer(
    tmp_path: Path,
):
    source = tmp_path / "example.py"

    source.write_text(
        """
def example():
    return 1
""".strip(),
        encoding="utf-8",
    )

    registry = CodebaseAnalyzerRegistry()

    inspector = CodebaseInspector(
        tmp_path,
        analyzer_registry=registry,
    )

    evidence = inspector.inspect()

    assert len(evidence.files) == 1
    assert (
        evidence.files[0].kind
        is SourceFileKind.OTHER
    )
    assert evidence.python_modules == ()


def test_custom_analyzer_can_be_added_without_changing_inspector():
    class TextAnalyzer:
        name = "text"
        source_file_kind = SourceFileKind.OTHER

        def supports(
            self,
            path: Path,
        ) -> bool:
            return path.suffix.lower() == ".txt"

        def analyze(
            self,
            path: Path,
            module_name: str,
        ) -> object:
            return {
                "path": path,
                "module_name": module_name,
            }

    registry = CodebaseAnalyzerRegistry(
        analyzers=(
            PythonAnalyzer(),
            TextAnalyzer(),
        ),
    )

    analyzer = registry.analyzer_for(
        Path("notes.txt")
    )

    assert analyzer is not None
    assert analyzer.name == "text"