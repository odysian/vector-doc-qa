#!/usr/bin/env python3
from __future__ import annotations

import ast
import sys
from dataclasses import dataclass
from pathlib import Path

LAYER_ROOTS = ("app.api", "app.services", "app.repositories")
ALLOWED_API_SERVICE_MODULES = (
    "app.services.auth_commands_service",
    "app.services.auth_query_service",
    "app.services.document_commands_service",
    "app.services.document_query_service",
    "app.services.workspace_service",
)


@dataclass(frozen=True)
class ImportRef:
    module: str
    lineno: int
    is_wildcard: bool = False


def is_module_or_submodule(module: str, root: str) -> bool:
    return module == root or module.startswith(f"{root}.")


def iter_imports(tree: ast.AST) -> list[ImportRef]:
    imports: list[ImportRef] = []

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.startswith("app."):
                    imports.append(ImportRef(module=alias.name, lineno=node.lineno))

        if not isinstance(node, ast.ImportFrom):
            continue
        if not node.module:
            continue

        if node.module == "app":
            for alias in node.names:
                if alias.name == "*":
                    imports.append(
                        ImportRef(module="app", lineno=node.lineno, is_wildcard=True)
                    )
                else:
                    imports.append(
                        ImportRef(module=f"app.{alias.name}", lineno=node.lineno)
                    )
            continue

        if not node.module.startswith("app."):
            continue

        for alias in node.names:
            if alias.name == "*":
                imports.append(
                    ImportRef(module=node.module, lineno=node.lineno, is_wildcard=True)
                )
            else:
                imports.append(
                    ImportRef(module=f"{node.module}.{alias.name}", lineno=node.lineno)
                )

    return imports


def validate_layer_root_and_wildcard(
    path: Path, layer_name: str, ref: ImportRef
) -> str | None:
    if ref.is_wildcard and (
        ref.module == "app"
        or any(is_module_or_submodule(ref.module, root) for root in LAYER_ROOTS)
    ):
        return (
            f"{path}:{ref.lineno}: {layer_name} layer cannot use wildcard import for "
            f"layer module namespace ({ref.module}.*)"
        )

    if ref.module in LAYER_ROOTS:
        return (
            f"{path}:{ref.lineno}: {layer_name} layer must import concrete submodules, "
            f"not layer root module ({ref.module})"
        )

    return None


def check_api_file(path: Path, imports: list[ImportRef]) -> list[str]:
    violations: list[str] = []

    for ref in imports:
        root_or_wildcard_violation = validate_layer_root_and_wildcard(
            path=path, layer_name="API", ref=ref
        )
        if root_or_wildcard_violation:
            violations.append(root_or_wildcard_violation)
            continue

        if is_module_or_submodule(ref.module, "app.repositories"):
            violations.append(
                f"{path}:{ref.lineno}: API layer cannot import repositories ({ref.module})"
            )
            continue

        if is_module_or_submodule(ref.module, "app.services") and not any(
            is_module_or_submodule(ref.module, allowed)
            for allowed in ALLOWED_API_SERVICE_MODULES
        ):
            violations.append(
                f"{path}:{ref.lineno}: API layer cannot import non-orchestration "
                f"service module ({ref.module})"
            )

    return violations


def check_service_file(path: Path, imports: list[ImportRef]) -> list[str]:
    violations: list[str] = []

    for ref in imports:
        root_or_wildcard_violation = validate_layer_root_and_wildcard(
            path=path, layer_name="Service", ref=ref
        )
        if root_or_wildcard_violation:
            violations.append(root_or_wildcard_violation)
            continue

        if is_module_or_submodule(ref.module, "app.api"):
            violations.append(
                f"{path}:{ref.lineno}: Service layer cannot import API layer ({ref.module})"
            )

    return violations


def check_repository_file(path: Path, imports: list[ImportRef]) -> list[str]:
    violations: list[str] = []

    for ref in imports:
        root_or_wildcard_violation = validate_layer_root_and_wildcard(
            path=path, layer_name="Repository", ref=ref
        )
        if root_or_wildcard_violation:
            violations.append(root_or_wildcard_violation)
            continue

        if is_module_or_submodule(ref.module, "app.api"):
            violations.append(
                f"{path}:{ref.lineno}: Repository layer cannot import API layer "
                f"({ref.module})"
            )
            continue

        if is_module_or_submodule(ref.module, "app.services"):
            violations.append(
                f"{path}:{ref.lineno}: Repository layer cannot import services "
                f"({ref.module})"
            )

    return violations


def violations_for_source(layer: str, source_text: str, path: Path) -> list[str]:
    tree = ast.parse(source_text, filename=str(path))
    imports = iter_imports(tree)

    if layer == "api":
        return check_api_file(path, imports)
    if layer == "services":
        return check_service_file(path, imports)
    if layer == "repositories":
        return check_repository_file(path, imports)

    raise ValueError(f"Unsupported layer: {layer}")


def scan_backend_layers(root: Path) -> list[str]:
    app_root = root / "backend" / "app"
    api_root = app_root / "api"
    services_root = app_root / "services"
    repositories_root = app_root / "repositories"

    violations: list[str] = []

    for py_file in sorted(api_root.rglob("*.py")):
        source_text = py_file.read_text(encoding="utf-8")
        violations.extend(violations_for_source("api", source_text, py_file))

    for py_file in sorted(services_root.rglob("*.py")):
        source_text = py_file.read_text(encoding="utf-8")
        violations.extend(violations_for_source("services", source_text, py_file))

    for py_file in sorted(repositories_root.rglob("*.py")):
        source_text = py_file.read_text(encoding="utf-8")
        violations.extend(violations_for_source("repositories", source_text, py_file))

    return violations


def main(argv: list[str]) -> int:
    if len(argv) > 2:
        print("Usage: check_backend_boundaries.py [repo-root]", file=sys.stderr)
        return 2

    if len(argv) == 2:
        root = Path(argv[1]).resolve()
    else:
        root = Path(__file__).resolve().parents[1]

    violations = scan_backend_layers(root)
    if violations:
        print("Backend boundary check failed:")
        for violation in violations:
            print(f" - {violation}")
        return 1

    print("Backend boundary check passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
