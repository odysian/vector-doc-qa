import json
import sys
from typing import Any

import pytest

from scripts.run_mini_eval import (
    _build_summary,
    _build_threshold_gate,
    _fact_match_metrics,
    _parse_args,
    _recommend_threshold,
    _to_markdown,
    load_eval_cases,
)


def test_load_eval_cases_sorts_by_case_id_and_strips_fields(tmp_path) -> None:
    fixture_path = tmp_path / "mini_eval_cases.json"
    fixture_payload = {
        "cases": [
            {
                "case_id": "case-b",
                "question": "  Second question?  ",
                "target_document": " doc-b.pdf ",
                "expected_facts": [" Fact B "],
            },
            {
                "case_id": "case-a",
                "question": " First question? ",
                "target_document": "doc-a.pdf",
                "expected_facts": ["Fact A"],
            },
        ]
    }
    fixture_path.write_text(json.dumps(fixture_payload), encoding="utf-8")

    cases = load_eval_cases(path=fixture_path)

    assert [case.case_id for case in cases] == ["case-a", "case-b"]
    assert cases[0].question == "First question?"
    assert cases[1].target_document == "doc-b.pdf"
    assert cases[1].expected_facts == ["Fact B"]


def test_load_eval_cases_raises_for_missing_expected_facts(tmp_path) -> None:
    fixture_path = tmp_path / "mini_eval_cases.json"
    fixture_payload = {
        "cases": [
            {
                "case_id": "case-a",
                "question": "Question?",
                "target_document": "doc-a.pdf",
            }
        ]
    }
    fixture_path.write_text(json.dumps(fixture_payload), encoding="utf-8")

    with pytest.raises(ValueError, match="expected_facts"):
        load_eval_cases(path=fixture_path)


def test_fact_match_metrics_is_case_insensitive() -> None:
    metrics = _fact_match_metrics(
        expected_facts=["Q4 Revenue", "customer growth"],
        text="q4 revenue increased while Customer Growth slowed.",
    )

    assert metrics["fact_hits"] == 2
    assert metrics["fact_total"] == 2
    assert metrics["fact_recall"] == 1.0
    assert metrics["missing_facts"] == []


def test_build_summary_uses_successful_cases_only() -> None:
    case_results: list[dict[str, Any]] = [
        {
            "status": "ok",
            "metrics": {
                "embed_ms": 10,
                "retrieval_ms": 20,
                "llm_ms": 300,
                "total_ms": 330,
                "top_similarity": 0.9,
                "avg_similarity": 0.8,
                "chunks_retrieved": 5,
            },
            "quality": {
                "answer": {"fact_recall": 0.5},
                "retrieval": {"fact_recall": 1.0},
            },
        },
        {
            "status": "error",
            "error": "missing document",
        },
    ]

    summary = _build_summary(case_results=case_results)

    assert summary["cases_total"] == 2
    assert summary["cases_ok"] == 1
    assert summary["cases_error"] == 1
    assert summary["avg_answer_fact_recall"] == 0.5
    assert summary["avg_retrieval_fact_recall"] == 1.0
    assert summary["avg_total_ms"] == 330.0
    assert summary["avg_top_similarity"] == 0.9
    calibration = summary["confidence_calibration"]
    assert calibration["sample_size"] == 1
    assert calibration["recommended"]["high_min_top_similarity"] == 0.9
    assert calibration["recommended"]["medium_min_top_similarity"] == 0.9


def test_build_summary_calibrates_thresholds_from_quality_labels() -> None:
    case_results: list[dict[str, Any]] = [
        {
            "status": "ok",
            "metrics": {
                "embed_ms": 10,
                "retrieval_ms": 20,
                "llm_ms": 300,
                "total_ms": 330,
                "top_similarity": 0.9,
                "avg_similarity": 0.8,
                "chunks_retrieved": 5,
            },
            "quality": {
                "answer": {"fact_recall": 1.0},
                "retrieval": {"fact_recall": 1.0},
            },
        },
        {
            "status": "ok",
            "metrics": {
                "embed_ms": 11,
                "retrieval_ms": 21,
                "llm_ms": 301,
                "total_ms": 333,
                "top_similarity": 0.8,
                "avg_similarity": 0.7,
                "chunks_retrieved": 5,
            },
            "quality": {
                "answer": {"fact_recall": 1.0},
                "retrieval": {"fact_recall": 1.0},
            },
        },
        {
            "status": "ok",
            "metrics": {
                "embed_ms": 12,
                "retrieval_ms": 22,
                "llm_ms": 302,
                "total_ms": 336,
                "top_similarity": 0.6,
                "avg_similarity": 0.6,
                "chunks_retrieved": 5,
            },
            "quality": {
                "answer": {"fact_recall": 0.0},
                "retrieval": {"fact_recall": 0.5},
            },
        },
        {
            "status": "ok",
            "metrics": {
                "embed_ms": 13,
                "retrieval_ms": 23,
                "llm_ms": 303,
                "total_ms": 339,
                "top_similarity": 0.5,
                "avg_similarity": 0.5,
                "chunks_retrieved": 5,
            },
            "quality": {
                "answer": {"fact_recall": 1.0},
                "retrieval": {"fact_recall": 1.0},
            },
        },
    ]

    summary = _build_summary(case_results=case_results)

    calibration = summary["confidence_calibration"]
    assert calibration["sample_size"] == 4
    assert calibration["positive_cases"] == 3
    assert calibration["recommended"]["high_min_top_similarity"] == 0.8
    assert calibration["recommended"]["medium_min_top_similarity"] == 0.5
    assert calibration["high_band"]["target_met"] is True
    assert calibration["medium_band"]["target_met"] is True


def test_build_summary_marks_fallback_when_targets_unmet() -> None:
    case_results: list[dict[str, Any]] = [
        {
            "status": "ok",
            "metrics": {
                "embed_ms": 10,
                "retrieval_ms": 20,
                "llm_ms": 300,
                "total_ms": 330,
                "top_similarity": 0.95,
                "avg_similarity": 0.8,
                "chunks_retrieved": 5,
            },
            "quality": {
                "answer": {"fact_recall": 0.0},
                "retrieval": {"fact_recall": 1.0},
            },
        },
        {
            "status": "ok",
            "metrics": {
                "embed_ms": 11,
                "retrieval_ms": 21,
                "llm_ms": 301,
                "total_ms": 333,
                "top_similarity": 0.9,
                "avg_similarity": 0.7,
                "chunks_retrieved": 5,
            },
            "quality": {
                "answer": {"fact_recall": 0.0},
                "retrieval": {"fact_recall": 1.0},
            },
        },
        {
            "status": "ok",
            "metrics": {
                "embed_ms": 12,
                "retrieval_ms": 22,
                "llm_ms": 302,
                "total_ms": 335,
                "top_similarity": 0.8,
                "avg_similarity": 0.6,
                "chunks_retrieved": 5,
            },
            "quality": {
                "answer": {"fact_recall": 1.0},
                "retrieval": {"fact_recall": 1.0},
            },
        },
        {
            "status": "ok",
            "metrics": {
                "embed_ms": 13,
                "retrieval_ms": 23,
                "llm_ms": 303,
                "total_ms": 336,
                "top_similarity": 0.75,
                "avg_similarity": 0.6,
                "chunks_retrieved": 5,
            },
            "quality": {
                "answer": {"fact_recall": 0.0},
                "retrieval": {"fact_recall": 1.0},
            },
        },
    ]

    summary = _build_summary(
        case_results=case_results,
        high_precision_target=1.0,
        medium_precision_target=0.99,
    )
    calibration = summary["confidence_calibration"]

    assert calibration["sample_size"] == 4
    assert calibration["positive_cases"] == 1
    assert calibration["recommended"]["high_min_top_similarity"] == 0.8
    assert calibration["high_band"]["target_met"] is False
    assert calibration["medium_band"]["target_met"] is False


def test_recommend_threshold_falls_back_to_best_precision_when_unmet() -> None:
    scored_cases: list[tuple[float, bool]] = [
        (0.9, False),
        (0.8, True),
        (0.7, False),
    ]

    recommendation = _recommend_threshold(
        scored_cases=scored_cases,
        target_precision=0.95,
    )

    assert recommendation is not None
    assert recommendation["target_met"] is False
    assert recommendation["threshold"] == 0.8
    assert recommendation["precision"] == 0.5
    assert recommendation["coverage"] == 0.6667


def test_build_threshold_gate_pass_and_fail() -> None:
    case_results: list[dict[str, Any]] = [
        {
            "status": "ok",
            "metrics": {
                "embed_ms": 10,
                "retrieval_ms": 20,
                "llm_ms": 300,
                "total_ms": 330,
                "top_similarity": 0.75,
                "avg_similarity": 0.7,
                "chunks_retrieved": 5,
            },
            "quality": {
                "answer": {"fact_recall": 0.8},
                "retrieval": {"fact_recall": 0.9},
            },
        }
    ]
    summary = _build_summary(case_results=case_results)

    passing_gate = _build_threshold_gate(
        summary=summary,
        min_answer_recall=0.6,
        min_retrieval_recall=0.7,
        min_top_similarity=0.7,
    )
    assert passing_gate["verdict"] == "PASS"
    assert passing_gate["passed"] is True
    assert passing_gate["breached_metrics"] == []

    failing_gate = _build_threshold_gate(
        summary=summary,
        min_answer_recall=0.85,
        min_retrieval_recall=0.7,
        min_top_similarity=0.8,
    )
    assert failing_gate["verdict"] == "FAIL"
    assert failing_gate["passed"] is False
    assert failing_gate["breached_metrics"] == [
        "avg_answer_fact_recall",
        "avg_top_similarity",
    ]


@pytest.mark.parametrize(
    ("flag", "value"),
    [
        ("--min-answer-fact-recall", "1.2"),
        ("--high-confidence-precision-target", "-0.1"),
        ("--medium-confidence-precision-target", "2.0"),
    ],
)
def test_parse_args_rejects_out_of_range_rates(flag: str, value: str) -> None:
    monkeypatch_argv = ["run_mini_eval.py", flag, value]
    with pytest.raises(ValueError, match="must be between 0.0 and 1.0"):
        with pytest.MonkeyPatch.context() as monkeypatch:
            monkeypatch.setattr(sys, "argv", monkeypatch_argv)
            _parse_args()


def test_markdown_includes_threshold_gate_verdict_and_config() -> None:
    case_results: list[dict[str, Any]] = [
        {
            "case_id": "case-a",
            "target_document": "doc-a.pdf",
            "status": "ok",
            "metrics": {
                "embed_ms": 10,
                "retrieval_ms": 20,
                "llm_ms": 300,
                "total_ms": 330,
                "top_similarity": 0.8,
                "avg_similarity": 0.7,
                "chunks_retrieved": 5,
            },
            "quality": {
                "answer": {"fact_hits": 1, "fact_total": 1, "fact_recall": 1.0},
                "retrieval": {"fact_hits": 1, "fact_total": 1, "fact_recall": 1.0},
            },
        }
    ]
    summary = _build_summary(case_results=case_results)
    threshold_gate = _build_threshold_gate(
        summary=summary,
        min_answer_recall=0.6,
        min_retrieval_recall=0.7,
        min_top_similarity=0.7,
    )
    report = {
        "generated_at": "2026-03-09T00:00:00+00:00",
        "fixture_path": "scripts/fixtures/mini_eval_cases.json",
        "cases": case_results,
        "summary": summary,
        "threshold_gate": threshold_gate,
    }

    markdown = _to_markdown(report)

    assert "## Threshold Gate" in markdown
    assert "| PASS | 0.6 | 0.7 | 0.7 |" in markdown
    assert "| avg_answer_fact_recall | 1.0 | 0.6 | pass |" in markdown


def test_markdown_renders_confidence_calibration_shape() -> None:
    case_results: list[dict[str, Any]] = [
        {
            "case_id": "case-a",
            "target_document": "doc-a.pdf",
            "status": "ok",
            "metrics": {
                "embed_ms": 10,
                "retrieval_ms": 20,
                "llm_ms": 300,
                "total_ms": 330,
                "top_similarity": 0.75,
                "avg_similarity": 0.7,
                "chunks_retrieved": 5,
            },
            "quality": {
                "answer": {"fact_hits": 1, "fact_total": 1, "fact_recall": 1.0},
                "retrieval": {"fact_hits": 1, "fact_total": 1, "fact_recall": 1.0},
            },
        },
        {
            "case_id": "case-b",
            "target_document": "doc-b.pdf",
            "status": "error",
            "error": "fixture mismatch",
        },
    ]
    summary = _build_summary(
        case_results=case_results,
        min_answer_fact_recall=0.8,
        high_precision_target=0.9,
        medium_precision_target=0.7,
    )
    threshold_gate = _build_threshold_gate(
        summary=summary,
        min_answer_recall=0.6,
        min_retrieval_recall=0.7,
        min_top_similarity=0.7,
    )
    report = {
        "generated_at": "2026-03-10T00:00:00+00:00",
        "fixture_path": "scripts/fixtures/mini_eval_cases.json",
        "cases": case_results,
        "summary": summary,
        "threshold_gate": threshold_gate,
    }

    markdown = _to_markdown(report)

    assert "## Confidence Calibration" in markdown
    assert "| band | target_precision | recommended_min_top_similarity | observed_precision | coverage | selected_cases |" in markdown
    assert "| high | 0.9 | 0.75 | 1.0 | 1.0 | 1 |" in markdown
    assert "| medium | 0.7 | 0.75 | 1.0 | 1.0 | 1 |" in markdown
