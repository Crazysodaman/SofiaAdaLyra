from sofia.codebase.model import (
    CodebaseInspectionEvidence,
)


def format_codebase_evidence(
    evidence: CodebaseInspectionEvidence,
) -> str:
    lines = [
        "CODEBASE INSPECTION EVIDENCE",
        (
            "The following information was produced by "
            "read-only structural codebase inspection."
        ),
        (
            "Treat this information as observed evidence. "
            "Do not claim observations that are not present."
        ),
        "",
        f"Root: {evidence.root}",
        f"Evidence kind: {evidence.evidence_kind.value}",
        f"Files discovered: {len(evidence.files)}",
        f"Python modules: {len(evidence.python_modules)}",
        f"Relationships: {len(evidence.relationships)}",
    ]

    if evidence.files:
        lines.extend(
            [
                "",
                "FILES",
            ]
        )

        for file in evidence.files:
            lines.append(
                f"- {file.path} "
                f"[{file.kind.value}, "
                f"{file.size_bytes} bytes]"
            )

    if evidence.python_modules:
        lines.extend(
            [
                "",
                "PYTHON MODULES",
            ]
        )

        for module in evidence.python_modules:
            lines.append(
                f"- {module.module_name}: "
                f"{module.path}"
            )

            if module.parse_error:
                lines.append(
                    f"  Parse error: {module.parse_error}"
                )

            for symbol in module.symbols:
                lines.append(
                    f"  - {symbol.kind}: "
                    f"{symbol.name} "
                    f"(line {symbol.line})"
                )

            for imported in module.imports:
                lines.append(
                    f"  - imports: {imported}"
                )

    if evidence.relationships:
        lines.extend(
            [
                "",
                "MODULE RELATIONSHIPS",
            ]
        )

        for relationship in evidence.relationships:
            lines.append(
                f"- {relationship.source_module} "
                f"--{relationship.relationship}--> "
                f"{relationship.target_module}"
            )

    return "\n".join(lines)