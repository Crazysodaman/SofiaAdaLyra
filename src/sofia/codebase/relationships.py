from sofia.codebase.model import (
    ModuleRelationship,
    PythonModule,
)


class CodebaseRelationshipAnalyzer:
    """Derives module relationships from observed imports."""

    def analyze(
        self,
        modules: tuple[PythonModule, ...],
    ) -> tuple[ModuleRelationship, ...]:
        if not isinstance(modules, tuple):
            raise TypeError(
                "modules must be a tuple."
            )

        known_modules = {
            module.module_name
            for module in modules
        }

        relationships: list[ModuleRelationship] = []

        for module in modules:
            for imported in module.imports:
                target = self._resolve_target(
                    imported,
                    known_modules,
                )

                if target is None:
                    continue

                relationships.append(
                    ModuleRelationship(
                        source_module=module.module_name,
                        target_module=target,
                        relationship="imports",
                    )
                )

        relationships.sort(
            key=lambda relationship: (
                relationship.source_module,
                relationship.target_module,
                relationship.relationship,
            )
        )

        return tuple(relationships)

    @staticmethod
    def _resolve_target(
        imported: str,
        known_modules: set[str],
    ) -> str | None:
        if imported in known_modules:
            return imported

        candidates = [
            module
            for module in known_modules
            if imported.startswith(module + ".")
            or module.startswith(imported + ".")
        ]

        if not candidates:
            return None

        return sorted(
            candidates,
            key=len,
            reverse=True,
        )[0]