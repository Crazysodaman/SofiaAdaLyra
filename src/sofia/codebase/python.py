import ast
from pathlib import Path

from sofia.codebase.model import (
    PythonModule,
    PythonSymbol,
)


class PythonInspectionError(Exception):
    """Raised when Python source inspection cannot be performed."""


class PythonInspector:
    """Read-only structural inspection of Python source files."""

    def inspect(
        self,
        path: Path,
        module_name: str,
    ) -> PythonModule:
        if not isinstance(path, Path):
            raise TypeError("path must be a Path.")

        if not module_name.strip():
            raise ValueError(
                "module_name must not be empty."
            )

        try:
            content = path.read_text(
                encoding="utf-8"
            )
        except OSError as exc:
            raise PythonInspectionError(
                f"Unable to read Python source: {path}"
            ) from exc

        try:
            tree = ast.parse(
                content,
                filename=str(path),
            )
        except SyntaxError as exc:
            return PythonModule(
                path=path,
                module_name=module_name,
                symbols=(),
                imports=(),
                parse_error=str(exc),
            )

        symbols: list[PythonSymbol] = []
        imports: list[str] = []

        for node in ast.walk(tree):
            if isinstance(
                node,
                (
                    ast.FunctionDef,
                    ast.AsyncFunctionDef,
                ),
            ):
                symbols.append(
                    PythonSymbol(
                        name=node.name,
                        kind=(
                            "async_function"
                            if isinstance(
                                node,
                                ast.AsyncFunctionDef,
                            )
                            else "function"
                        ),
                        line=node.lineno,
                        end_line=getattr(
                            node,
                            "end_lineno",
                            None,
                        ),
                    )
                )

            elif isinstance(node, ast.ClassDef):
                symbols.append(
                    PythonSymbol(
                        name=node.name,
                        kind="class",
                        line=node.lineno,
                        end_line=getattr(
                            node,
                            "end_lineno",
                            None,
                        ),
                    )
                )

            elif isinstance(node, ast.Import):
                imports.extend(
                    alias.name
                    for alias in node.names
                )

            elif isinstance(node, ast.ImportFrom):
                if node.module is not None:
                    imports.append(node.module)

        symbols.sort(
            key=lambda symbol: (
                symbol.line,
                symbol.name,
            )
        )

        return PythonModule(
            path=path,
            module_name=module_name,
            symbols=tuple(symbols),
            imports=tuple(sorted(set(imports))),
        )