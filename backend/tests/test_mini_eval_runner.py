import json
from typing import Any

import pytest

from scripts.run_mini_eval import _build_summary, _fact_match_metrics, load_eval_cases


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
