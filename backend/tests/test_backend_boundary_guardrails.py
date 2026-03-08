"""Targeted tests for boundary guardrail import normalization edge cases."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType


def _load_guardrail_module() -> ModuleType:
    script_path = (
        Path(__file__).resolve().parents[2] / "scripts" / "check_backend_boundaries.py"
    )
    spec = importlib.util.spec_from_file_location(
        "check_backend_boundaries", script_path
    )
    if spec is None or spec.loader is None:
        raise AssertionError("Failed to load boundary guardrail script module")

    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_api_detects_root_repository_import() -> None:
    module = _load_guardrail_module()
    violations = module.violations_for_source(  # type: ignore[attr-defined]
        layer="api",
        source_text="import app.repositories",
        path=Path("backend/app/api/sample.py"),
    )

    assert any(
        "layer root module (app.repositories)" in violation for violation in violations
    )


def test_api_rejects_wildcard_service_import() -> None:
    module = _load_guardrail_module()
    violations = module.violations_for_source(  # type: ignore[attr-defined]
        layer="api",
        source_text="from app.services import *",
        path=Path("backend/app/api/sample.py"),
    )

    assert any("wildcard import" in violation for violation in violations)


def test_repository_detects_from_app_import_services_pattern() -> None:
    module = _load_guardrail_module()
    violations = module.violations_for_source(  # type: ignore[attr-defined]
        layer="repositories",
        source_text="from app import services",
        path=Path("backend/app/repositories/sample.py"),
    )

    assert any(
        "layer root module (app.services)" in violation for violation in violations
    )


def test_service_detects_root_api_import() -> None:
    module = _load_guardrail_module()
    violations = module.violations_for_source(  # type: ignore[attr-defined]
        layer="services",
        source_text="import app.api",
        path=Path("backend/app/services/sample.py"),
    )

    assert any("layer root module (app.api)" in violation for violation in violations)


def test_api_allows_orchestration_service_import() -> None:
    module = _load_guardrail_module()
    violations = module.violations_for_source(  # type: ignore[attr-defined]
        layer="api",
        source_text="from app.services.document_query_service import query_document",
        path=Path("backend/app/api/sample.py"),
    )

    assert violations == []
