from collections import Counter

from sofia.codebase.model import (
    CodebaseInspectionEvidence,
)


_MAX_FILE_SAMPLE = 30
_MAX_MODULE_SAMPLE = 30
_MAX_RELATIONSHIP_SAMPLE = 30


def _relative(evidence: CodebaseInspectionEvidence, path) -> str:
    try:
        return str(path.relative_to(evidence.root))
    except ValueError:
        return str(path)


def format_codebase_evidence(
    evidence: CodebaseInspectionEvidence,
) -> str:
    """Format a bounded structural overview for model context.

    The canonical evidence object may contain hundreds of modules and
    relationships. Dumping all of them into one tool result can overwhelm the
    model context and make a broad repository question accidentally look like a
    review of whichever tail section survived truncation. This projection keeps
    observed totals, exposes whether discovery hit its safety cap, and provides
    bounded representative indexes. Exact source remains available through
    filesystem.inspect.
    """
    lines = [
        "CODEBASE INSPECTION EVIDENCE",
        (
            "The following information was produced by read-only structural "
            "codebase inspection."
        ),
        (
            "Treat this information as observed evidence. Do not claim "
            "observations that are not present."
        ),
        (
            "This is a bounded structural overview, not a full file-content "
            "review. Use filesystem.inspect for exact source and inspect the "
            "repository package-by-package when an exhaustive review is requested."
        ),
        "",
        f"Root: {evidence.root}",
        f"Evidence kind: {evidence.evidence_kind.value}",
        f"Files discovered: {len(evidence.files)}",
        f"Python modules: {len(evidence.python_modules)}",
        f"Relationships: {len(evidence.relationships)}",
        (
            "File discovery limit reached: "
            + ("yes" if evidence.file_limit_reached else "no")
        ),
    ]

    if evidence.file_limit_reached:
        lines.append(
            "IMPORTANT: additional eligible files exist beyond the inspector "
            "limit. Do not describe this evidence as an exhaustive repository review."
        )

    if evidence.files:
        top_level = Counter()
        for file in evidence.files:
            try:
                relative = file.path.relative_to(evidence.root)
            except ValueError:
                relative = file.path
            # Root-level filenames are one bucket, not 1 unbounded label per
            # file. Otherwise this summary leaks the complete tail of a large
            # root directory before the deliberately bounded file sample.
            name = relative.parts[0] if len(relative.parts) > 1 else "."
            top_level[name] += 1
        lines.extend(("", "TOP-LEVEL FILE COUNTS"))
        for name, count in sorted(
            top_level.items(),
            key=lambda item: (-item[1], item[0].casefold()),
        ):
            lines.append(f"- {name}: {count}")

        shown = evidence.files[:_MAX_FILE_SAMPLE]
        lines.extend(
            (
                "",
                f"FILE SAMPLE ({len(shown)} of {len(evidence.files)})",
            )
        )
        for file in shown:
            lines.append(
                f"- {_relative(evidence, file.path)} "
                f"[{file.kind.value}, {file.size_bytes} bytes]"
            )
        omitted = len(evidence.files) - len(shown)
        if omitted:
            lines.append(
                f"- ... {omitted} additional discovered files omitted from "
                "this model-context projection."
            )

    if evidence.python_modules:
        shown_modules = evidence.python_modules[:_MAX_MODULE_SAMPLE]
        lines.extend(
            (
                "",
                (
                    "PYTHON MODULE SAMPLE "
                    f"({len(shown_modules)} of {len(evidence.python_modules)})"
                ),
            )
        )
        for module in shown_modules:
            detail = (
                f"- {module.module_name}: {_relative(evidence, module.path)} "
                f"[symbols={len(module.symbols)}, imports={len(module.imports)}]"
            )
            if module.parse_error:
                detail += f" [parse_error={module.parse_error}]"
            lines.append(detail)
        omitted = len(evidence.python_modules) - len(shown_modules)
        if omitted:
            lines.append(
                f"- ... {omitted} additional Python modules omitted from "
                "this model-context projection."
            )

    if evidence.relationships:
        shown_relationships = evidence.relationships[:_MAX_RELATIONSHIP_SAMPLE]
        lines.extend(
            (
                "",
                (
                    "MODULE RELATIONSHIP SAMPLE "
                    f"({len(shown_relationships)} of {len(evidence.relationships)})"
                ),
            )
        )
        for relationship in shown_relationships:
            lines.append(
                f"- {relationship.source_module} "
                f"--{relationship.relationship}--> "
                f"{relationship.target_module}"
            )
        omitted = len(evidence.relationships) - len(shown_relationships)
        if omitted:
            lines.append(
                f"- ... {omitted} additional module relationships omitted "
                "from this model-context projection."
            )

    return "\n".join(lines)
