#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

python3 - "${ROOT_DIR}" <<'PY'
import ast
import sys
from pathlib import Path


INTEGRATION_SERVICE_MODULES = {
    "app.services.anthropic_service",
    "app.services.embedding_service",
    "app.services.queue_service",
    "app.services.search_service",
    "app.services.storage_service",
    "app.services.document_service",
}


def iter_imports(tree: ast.AST) -> list[tuple[str, int]]:
    imports: list[tuple[str, int]] = []

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                module = alias.name
                if module.startswith("app."):
                    imports.append((module, node.lineno))

        if isinstance(node, ast.ImportFrom):
            if not node.module or not node.module.startswith("app."):
                continue

            if node.module == "app.services":
                for alias in node.names:
                    imports.append((f"{node.module}.{alias.name}", node.lineno))
                continue

            imports.append((node.module, node.lineno))

    return imports


def check_api_file(path: Path, imports: list[tuple[str, int]]) -> list[str]:
    violations: list[str] = []

    for module, lineno in imports:
        if module.startswith("app.repositories."):
            violations.append(
                f"{path}:{lineno}: API layer cannot import repositories ({module})"
            )
            continue

        if module in INTEGRATION_SERVICE_MODULES:
            violations.append(
                f"{path}:{lineno}: API layer cannot import integration/worker services ({module})"
            )

    return violations


def check_service_file(path: Path, imports: list[tuple[str, int]]) -> list[str]:
    violations: list[str] = []

    for module, lineno in imports:
        if module.startswith("app.api."):
            violations.append(
                f"{path}:{lineno}: Service layer cannot import API layer ({module})"
            )

    return violations


def check_repository_file(path: Path, imports: list[tuple[str, int]]) -> list[str]:
    violations: list[str] = []

    for module, lineno in imports:
        if module.startswith("app.api."):
            violations.append(
                f"{path}:{lineno}: Repository layer cannot import API layer ({module})"
            )
            continue

        if module.startswith("app.services."):
            violations.append(
                f"{path}:{lineno}: Repository layer cannot import services ({module})"
            )

    return violations


def main() -> int:
    root = Path(sys.argv[1]).resolve()
    app_root = root / "backend" / "app"

    api_root = app_root / "api"
    services_root = app_root / "services"
    repositories_root = app_root / "repositories"

    violations: list[str] = []

    for py_file in sorted(api_root.rglob("*.py")):
        tree = ast.parse(py_file.read_text(encoding="utf-8"), filename=str(py_file))
        violations.extend(check_api_file(py_file, iter_imports(tree)))

    for py_file in sorted(services_root.rglob("*.py")):
        tree = ast.parse(py_file.read_text(encoding="utf-8"), filename=str(py_file))
        violations.extend(check_service_file(py_file, iter_imports(tree)))

    for py_file in sorted(repositories_root.rglob("*.py")):
        tree = ast.parse(py_file.read_text(encoding="utf-8"), filename=str(py_file))
        violations.extend(check_repository_file(py_file, iter_imports(tree)))

    if violations:
        print("Backend boundary check failed:")
        for violation in violations:
            print(f" - {violation}")
        return 1

    print("Backend boundary check passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
PY
