from dataclasses import dataclass
from enum import Enum
from pathlib import Path


class CodebaseEvidenceKind(str, Enum):
    OBSERVED = "observed"
    INFERRED = "inferred"
    UNKNOWN = "unknown"


class SourceFileKind(str, Enum):
    PYTHON = "python"
    OTHER = "other"


@dataclass(frozen=True)
class CodebaseFile:
    path: Path
    kind: SourceFileKind
    size_bytes: int

    def __post_init__(self) -> None:
        if not isinstance(self.path, Path):
            raise TypeError("path must be a Path.")

        if not isinstance(self.kind, SourceFileKind):
            raise TypeError(
                "kind must be a SourceFileKind."
            )

        if not isinstance(self.size_bytes, int):
            raise TypeError(
                "size_bytes must be an int."
            )

        if self.size_bytes < 0:
            raise ValueError(
                "size_bytes must not be negative."
            )


@dataclass(frozen=True)
class PythonSymbol:
    name: str
    kind: str
    line: int
    end_line: int | None = None

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ValueError(
                "Python symbol name must not be empty."
            )

        if not self.kind.strip():
            raise ValueError(
                "Python symbol kind must not be empty."
            )

        if self.line < 1:
            raise ValueError(
                "Python symbol line must be positive."
            )

        if (
            self.end_line is not None
            and self.end_line < self.line
        ):
            raise ValueError(
                "Python symbol end_line cannot precede line."
            )


@dataclass(frozen=True)
class PythonModule:
    path: Path
    module_name: str
    symbols: tuple[PythonSymbol, ...]
    imports: tuple[str, ...]
    parse_error: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.path, Path):
            raise TypeError("path must be a Path.")

        if not self.module_name.strip():
            raise ValueError(
                "module_name must not be empty."
            )

        if not isinstance(self.symbols, tuple):
            raise TypeError(
                "symbols must be a tuple."
            )

        if not isinstance(self.imports, tuple):
            raise TypeError(
                "imports must be a tuple."
            )

        if (
            self.parse_error is not None
            and not isinstance(self.parse_error, str)
        ):
            raise TypeError(
                "parse_error must be a string or None."
            )


@dataclass(frozen=True)
class ModuleRelationship:
    source_module: str
    target_module: str
    relationship: str

    def __post_init__(self) -> None:
        if not self.source_module.strip():
            raise ValueError(
                "source_module must not be empty."
            )

        if not self.target_module.strip():
            raise ValueError(
                "target_module must not be empty."
            )

        if not self.relationship.strip():
            raise ValueError(
                "relationship must not be empty."
            )


@dataclass(frozen=True)
class CodebaseInspectionEvidence:
    root: Path
    files: tuple[CodebaseFile, ...]
    python_modules: tuple[PythonModule, ...]
    relationships: tuple[ModuleRelationship, ...]
    evidence_kind: CodebaseEvidenceKind = (
        CodebaseEvidenceKind.OBSERVED
    )

    def __post_init__(self) -> None:
        if not isinstance(self.root, Path):
            raise TypeError("root must be a Path.")

        if not isinstance(self.files, tuple):
            raise TypeError(
                "files must be a tuple."
            )

        if not isinstance(self.python_modules, tuple):
            raise TypeError(
                "python_modules must be a tuple."
            )

        if not isinstance(self.relationships, tuple):
            raise TypeError(
                "relationships must be a tuple."
            )

        if not isinstance(
            self.evidence_kind,
            CodebaseEvidenceKind,
        ):
            raise TypeError(
                "evidence_kind must be a CodebaseEvidenceKind."
            )