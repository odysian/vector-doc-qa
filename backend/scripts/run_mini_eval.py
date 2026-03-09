from __future__ import annotations

import argparse
import asyncio
import json
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.database import AsyncSessionLocal
from app.models.base import Chunk, Document, DocumentStatus
from app.services.anthropic_service import generate_answer
from app.services.embedding_service import generate_embedding
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession


@dataclass(frozen=True)
class EvalCase:
    case_id: str
    question: str
    target_document: str
    expected_facts: list[str]


def _is_valid_rate(value: float) -> bool:
    return 0.0 <= value <= 1.0


def _elapsed_ms(start_time: float) -> int:
    return int((time.perf_counter() - start_time) * 1000)


def _parse_fixture_case(raw_case: dict[str, Any], index: int) -> EvalCase:
    case_id = raw_case.get("case_id")
    if not isinstance(case_id, str) or not case_id.strip():
        raise ValueError(f"Fixture case {index} is missing non-empty 'case_id'")

    question = raw_case.get("question")
    if not isinstance(question, str) or not question.strip():
        raise ValueError(f"Fixture case '{case_id}' is missing non-empty 'question'")

    target_document = raw_case.get("target_document")
    if not isinstance(target_document, str) or not target_document.strip():
        raise ValueError(f"Fixture case '{case_id}' is missing non-empty 'target_document'")

    raw_facts = raw_case.get("expected_facts")
    if not isinstance(raw_facts, list) or not raw_facts:
        raise ValueError(f"Fixture case '{case_id}' is missing non-empty 'expected_facts' list")

    expected_facts: list[str] = []
    for fact in raw_facts:
        if not isinstance(fact, str) or not fact.strip():
            raise ValueError(
                f"Fixture case '{case_id}' has invalid expected_facts value: {fact!r}"
            )
        expected_facts.append(fact.strip())

    return EvalCase(
        case_id=case_id.strip(),
        question=question.strip(),
        target_document=target_document.strip(),
        expected_facts=expected_facts,
    )


def load_eval_cases(path: Path) -> list[EvalCase]:
    raw_payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw_payload, dict):
        raise ValueError("Fixture must be a JSON object")

    raw_cases = raw_payload.get("cases")
    if not isinstance(raw_cases, list) or not raw_cases:
        raise ValueError("Fixture must define a non-empty 'cases' array")

    cases = [_parse_fixture_case(raw_case=raw_case, index=index) for index, raw_case in enumerate(raw_cases, start=1)]

    # Stable ordering keeps output deterministic for PR diffs.
    return sorted(cases, key=lambda case: case.case_id)


async def _resolve_document_id(
    db: AsyncSession,
    target_document: str,
    user_id: int | None,
) -> int:
    stmt = select(Document.id).where(
        Document.filename == target_document,
        Document.status == DocumentStatus.COMPLETED,
    )
    if user_id is not None:
        stmt = stmt.where(Document.user_id == user_id)

    stmt = stmt.order_by(Document.id.asc())
    matches = (await db.scalars(stmt)).all()

    if not matches:
        scoped_to_user = f" for user_id={user_id}" if user_id is not None else ""
        raise ValueError(
            f"No completed document found for target_document='{target_document}'{scoped_to_user}. "
            "Upload and process the target document before running eval."
        )
    if len(matches) > 1:
        scoped_to_user = f" for user_id={user_id}" if user_id is not None else ""
        raise ValueError(
            f"Multiple completed documents found for target_document='{target_document}' "
            f"{scoped_to_user} (ids={matches}). "
            "Use --user-id to scope the run or use unique filenames."
        )
    return matches[0]


async def _search_chunks_from_embedding(
    *,
    db: AsyncSession,
    document_id: int,
    query_embedding: list[float],
    top_k: int,
) -> list[dict[str, Any]]:
    distance_expr = Chunk.embedding.cosine_distance(query_embedding).label("distance")
    stmt = (
        select(
            Chunk.id,
            Chunk.content,
            Chunk.chunk_index,
            distance_expr,
        )
        .where(Chunk.document_id == document_id)
        .where(Chunk.embedding.isnot(None))
        .order_by(distance_expr)
        .limit(top_k)
    )

    rows = (await db.execute(stmt)).all()
    results: list[dict[str, Any]] = []
    for chunk_id, content, chunk_index, distance in rows:
        similarity = round(1 - float(distance), 4)
        results.append(
            {
                "chunk_id": chunk_id,
                "content": content,
                "similarity": similarity,
                "chunk_index": chunk_index,
            }
        )
    return results


def _fact_match_metrics(*, expected_facts: list[str], text: str) -> dict[str, Any]:
    normalized_text = text.casefold()
    matched: list[str] = []
    missing: list[str] = []
    for fact in expected_facts:
        if fact.casefold() in normalized_text:
            matched.append(fact)
        else:
            missing.append(fact)

    fact_total = len(expected_facts)
    fact_hits = len(matched)
    fact_recall = round(fact_hits / fact_total, 4) if fact_total else 0.0
    return {
        "fact_hits": fact_hits,
        "fact_total": fact_total,
        "fact_recall": fact_recall,
        "matched_facts": matched,
        "missing_facts": missing,
    }


async def _run_case(
    *,
    db: AsyncSession,
    eval_case: EvalCase,
    top_k: int,
    user_id: int | None,
) -> dict[str, Any]:
    document_id = await _resolve_document_id(
        db=db,
        target_document=eval_case.target_document,
        user_id=user_id,
    )

    pipeline_start = time.perf_counter()

    embedding_start = time.perf_counter()
    query_embedding = await generate_embedding(eval_case.question)
    embed_ms = _elapsed_ms(embedding_start)

    retrieval_start = time.perf_counter()
    search_results = await _search_chunks_from_embedding(
        db=db,
        document_id=document_id,
        query_embedding=query_embedding,
        top_k=top_k,
    )
    retrieval_ms = _elapsed_ms(retrieval_start)

    llm_start = time.perf_counter()
    answer = await generate_answer(query=eval_case.question, chunks=search_results)
    llm_ms = _elapsed_ms(llm_start)
    total_ms = _elapsed_ms(pipeline_start)

    similarities = [result["similarity"] for result in search_results]
    top_similarity = max(similarities) if similarities else 0.0
    avg_similarity = round(sum(similarities) / len(similarities), 4) if similarities else 0.0

    answer_quality = _fact_match_metrics(expected_facts=eval_case.expected_facts, text=answer)
    retrieval_text = "\n".join(chunk["content"] for chunk in search_results)
    retrieval_quality = _fact_match_metrics(expected_facts=eval_case.expected_facts, text=retrieval_text)

    return {
        "case_id": eval_case.case_id,
        "question": eval_case.question,
        "target_document": eval_case.target_document,
        "document_id": document_id,
        "status": "ok",
        "metrics": {
            "embed_ms": embed_ms,
            "retrieval_ms": retrieval_ms,
            "llm_ms": llm_ms,
            "total_ms": total_ms,
            "top_similarity": round(top_similarity, 4),
            "avg_similarity": avg_similarity,
            "chunks_retrieved": len(search_results),
        },
        "quality": {
            "answer": answer_quality,
            "retrieval": retrieval_quality,
        },
        "answer": answer,
    }


def _avg_metric(case_results: list[dict[str, Any]], metric_name: str) -> float:
    values = [case["metrics"][metric_name] for case in case_results if case["status"] == "ok"]
    if not values:
        return 0.0
    return round(float(sum(values)) / float(len(values)), 4)


def _threshold_stats(
    *,
    scored_cases: list[tuple[float, bool]],
    threshold: float,
) -> dict[str, Any]:
    selected = [is_positive for score, is_positive in scored_cases if score >= threshold]
    selected_cases = len(selected)
    positive_cases = sum(1 for is_positive in selected if is_positive)
    precision = round(positive_cases / selected_cases, 4) if selected_cases else 0.0
    coverage = round(selected_cases / len(scored_cases), 4) if scored_cases else 0.0
    return {
        "selected_cases": selected_cases,
        "positive_cases": positive_cases,
        "precision": precision,
        "coverage": coverage,
    }


def _recommend_threshold(
    *,
    scored_cases: list[tuple[float, bool]],
    target_precision: float,
    max_threshold: float | None = None,
) -> dict[str, Any] | None:
    if not scored_cases:
        return None

    candidates = sorted(
        {
            score
            for score, _ in scored_cases
            if max_threshold is None or score <= max_threshold
        },
        reverse=True,
    )
    if not candidates:
        return None

    best_meeting_target: dict[str, Any] | None = None
    for threshold in candidates:
        stats = _threshold_stats(scored_cases=scored_cases, threshold=threshold)
        if stats["precision"] < target_precision:
            continue
        candidate = {
            "threshold": round(threshold, 4),
            "target_met": True,
            **stats,
        }
        if best_meeting_target is None:
            best_meeting_target = candidate
            continue
        if candidate["coverage"] > best_meeting_target["coverage"]:
            best_meeting_target = candidate
            continue
        if (
            candidate["coverage"] == best_meeting_target["coverage"]
            and candidate["threshold"] < best_meeting_target["threshold"]
        ):
            best_meeting_target = candidate

    if best_meeting_target is not None:
        return best_meeting_target

    fallback: dict[str, Any] | None = None
    for threshold in candidates:
        stats = _threshold_stats(scored_cases=scored_cases, threshold=threshold)
        candidate = {
            "threshold": round(threshold, 4),
            "target_met": False,
            **stats,
        }
        if fallback is None:
            fallback = candidate
            continue
        if candidate["precision"] > fallback["precision"]:
            fallback = candidate
            continue
        if (
            candidate["precision"] == fallback["precision"]
            and candidate["coverage"] > fallback["coverage"]
        ):
            fallback = candidate

    return fallback


def _build_confidence_calibration(
    *,
    successful_cases: list[dict[str, Any]],
    min_answer_fact_recall: float,
    high_precision_target: float,
    medium_precision_target: float,
) -> dict[str, Any]:
    scored_cases: list[tuple[float, bool]] = []
    for case in successful_cases:
        metrics = case.get("metrics", {})
        quality = case.get("quality", {})
        answer_quality = quality.get("answer", {})
        top_similarity = metrics.get("top_similarity")
        answer_recall = answer_quality.get("fact_recall")
        if not isinstance(top_similarity, (int, float)):
            continue
        if not isinstance(answer_recall, (int, float)):
            continue
        scored_cases.append(
            (
                float(top_similarity),
                float(answer_recall) >= min_answer_fact_recall,
            )
        )

    positive_cases = sum(1 for _, is_positive in scored_cases if is_positive)
    high_band = _recommend_threshold(
        scored_cases=scored_cases,
        target_precision=high_precision_target,
    )
    medium_band = _recommend_threshold(
        scored_cases=scored_cases,
        target_precision=medium_precision_target,
        max_threshold=high_band["threshold"] if high_band is not None else None,
    )

    return {
        "metric": "top_similarity",
        "min_answer_fact_recall": round(min_answer_fact_recall, 4),
        "high_precision_target": round(high_precision_target, 4),
        "medium_precision_target": round(medium_precision_target, 4),
        "sample_size": len(scored_cases),
        "positive_cases": positive_cases,
        "recommended": {
            "high_min_top_similarity": (
                high_band["threshold"] if high_band is not None else None
            ),
            "medium_min_top_similarity": (
                medium_band["threshold"] if medium_band is not None else None
            ),
        },
        "high_band": high_band,
        "medium_band": medium_band,
    }


def _build_summary(
    case_results: list[dict[str, Any]],
    *,
    min_answer_fact_recall: float = 0.8,
    high_precision_target: float = 0.9,
    medium_precision_target: float = 0.7,
) -> dict[str, Any]:
    successful_cases = [case for case in case_results if case["status"] == "ok"]
    failed_cases = [case for case in case_results if case["status"] != "ok"]

    answer_recalls = [
        case["quality"]["answer"]["fact_recall"] for case in successful_cases
    ]
    retrieval_recalls = [
        case["quality"]["retrieval"]["fact_recall"] for case in successful_cases
    ]

    return {
        "cases_total": len(case_results),
        "cases_ok": len(successful_cases),
        "cases_error": len(failed_cases),
        "avg_answer_fact_recall": (
            round(sum(answer_recalls) / len(answer_recalls), 4) if answer_recalls else 0.0
        ),
        "avg_retrieval_fact_recall": (
            round(sum(retrieval_recalls) / len(retrieval_recalls), 4)
            if retrieval_recalls
            else 0.0
        ),
        "avg_embed_ms": _avg_metric(successful_cases, "embed_ms"),
        "avg_retrieval_ms": _avg_metric(successful_cases, "retrieval_ms"),
        "avg_llm_ms": _avg_metric(successful_cases, "llm_ms"),
        "avg_total_ms": _avg_metric(successful_cases, "total_ms"),
        "avg_top_similarity": _avg_metric(successful_cases, "top_similarity"),
        "avg_avg_similarity": _avg_metric(successful_cases, "avg_similarity"),
        "avg_chunks_retrieved": _avg_metric(successful_cases, "chunks_retrieved"),
        "confidence_calibration": _build_confidence_calibration(
            successful_cases=successful_cases,
            min_answer_fact_recall=min_answer_fact_recall,
            high_precision_target=high_precision_target,
            medium_precision_target=medium_precision_target,
        ),
    }


def _build_threshold_gate(
    *,
    summary: dict[str, Any],
    min_answer_recall: float,
    min_retrieval_recall: float,
    min_top_similarity: float,
) -> dict[str, Any]:
    checks = {
        "avg_answer_fact_recall": {
            "actual": summary["avg_answer_fact_recall"],
            "minimum": round(min_answer_recall, 4),
        },
        "avg_retrieval_fact_recall": {
            "actual": summary["avg_retrieval_fact_recall"],
            "minimum": round(min_retrieval_recall, 4),
        },
        "avg_top_similarity": {
            "actual": summary["avg_top_similarity"],
            "minimum": round(min_top_similarity, 4),
        },
    }

    breached_metrics: list[str] = []
    for metric_name, metric_check in checks.items():
        metric_check["actual"] = round(float(metric_check["actual"]), 4)
        metric_check["passed"] = metric_check["actual"] >= metric_check["minimum"]
        if not metric_check["passed"]:
            breached_metrics.append(metric_name)

    passed = not breached_metrics
    return {
        "verdict": "PASS" if passed else "FAIL",
        "passed": passed,
        "thresholds": {
            "min_answer_recall": round(min_answer_recall, 4),
            "min_retrieval_recall": round(min_retrieval_recall, 4),
            "min_top_similarity": round(min_top_similarity, 4),
        },
        "checks": checks,
        "breached_metrics": breached_metrics,
    }


def _to_markdown(report: dict[str, Any]) -> str:
    lines: list[str] = []
    lines.append("# Mini Eval Report")
    lines.append("")
    lines.append(f"- Generated at: `{report['generated_at']}`")
    lines.append(f"- Fixture: `{report['fixture_path']}`")
    lines.append("")
    lines.append("## Summary")
    lines.append("")
    summary = report["summary"]
    lines.append(
        "| cases_total | cases_ok | cases_error | avg_answer_fact_recall | avg_retrieval_fact_recall | avg_total_ms |"
    )
    lines.append("|---|---|---|---|---|---|")
    lines.append(
        f"| {summary['cases_total']} | {summary['cases_ok']} | {summary['cases_error']} | "
        f"{summary['avg_answer_fact_recall']} | {summary['avg_retrieval_fact_recall']} | "
        f"{summary['avg_total_ms']} |"
    )
    lines.append("")
    lines.append("## Threshold Gate")
    lines.append("")
    threshold_gate = report["threshold_gate"]
    thresholds = threshold_gate["thresholds"]
    lines.append("| verdict | min_answer_recall | min_retrieval_recall | min_top_similarity |")
    lines.append("|---|---|---|---|")
    lines.append(
        f"| {threshold_gate['verdict']} | {thresholds['min_answer_recall']} | "
        f"{thresholds['min_retrieval_recall']} | {thresholds['min_top_similarity']} |"
    )
    lines.append("")
    lines.append("| metric | actual | minimum | status |")
    lines.append("|---|---|---|---|")
    for metric_name, metric_check in threshold_gate["checks"].items():
        status = "pass" if metric_check["passed"] else "fail"
        lines.append(
            f"| {metric_name} | {metric_check['actual']} | {metric_check['minimum']} | {status} |"
        )
    lines.append("")
    lines.append("## Confidence Calibration")
    lines.append("")
    calibration = summary["confidence_calibration"]
    lines.append(
        f"- Correctness label: `answer.fact_recall >= {calibration['min_answer_fact_recall']}`"
    )
    lines.append(
        f"- Sample size: `{calibration['sample_size']}` "
        f"(positives: `{calibration['positive_cases']}`)"
    )
    lines.append("")
    lines.append(
        "| band | target_precision | recommended_min_top_similarity | observed_precision | coverage | selected_cases |"
    )
    lines.append("|---|---|---|---|---|---|")
    for band_name, target_key in (
        ("high", "high_precision_target"),
        ("medium", "medium_precision_target"),
    ):
        band = calibration[f"{band_name}_band"]
        if band is None:
            lines.append(f"| {band_name} | {calibration[target_key]} | - | - | - | - |")
            continue
        lines.append(
            f"| {band_name} | {calibration[target_key]} | {band['threshold']} | "
            f"{band['precision']} | {band['coverage']} | {band['selected_cases']} |"
        )
    lines.append("")
    lines.append("## Per-case Results")
    lines.append("")
    lines.append(
        "| case_id | document | answer_facts | retrieval_facts | top_similarity | avg_similarity | chunks | embed_ms | retrieval_ms | llm_ms | total_ms | status |"
    )
    lines.append("|---|---|---|---|---|---|---|---|---|---|---|---|")
    for case in report["cases"]:
        if case["status"] != "ok":
            lines.append(
                f"| {case['case_id']} | {case['target_document']} | - | - | - | - | - | - | - | - | - | error |"
            )
            continue

        answer_quality = case["quality"]["answer"]
        retrieval_quality = case["quality"]["retrieval"]
        metrics = case["metrics"]
        lines.append(
            f"| {case['case_id']} | {case['target_document']} | "
            f"{answer_quality['fact_hits']}/{answer_quality['fact_total']} | "
            f"{retrieval_quality['fact_hits']}/{retrieval_quality['fact_total']} | "
            f"{metrics['top_similarity']} | {metrics['avg_similarity']} | "
            f"{metrics['chunks_retrieved']} | {metrics['embed_ms']} | "
            f"{metrics['retrieval_ms']} | {metrics['llm_ms']} | "
            f"{metrics['total_ms']} | ok |"
        )
    lines.append("")
    return "\n".join(lines)


def _parse_args() -> argparse.Namespace:
    default_fixture = Path(__file__).resolve().parent / "fixtures" / "mini_eval_cases.json"
    parser = argparse.ArgumentParser(
        description=(
            "Run mini eval cases for retrieval/answer quality and latency snapshots."
        )
    )
    parser.add_argument(
        "--fixture",
        type=Path,
        default=default_fixture,
        help="Path to eval fixture JSON file.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("reports/mini_eval"),
        help="Directory for JSON/Markdown report artifacts.",
    )
    parser.add_argument(
        "--top-k",
        type=int,
        default=5,
        help="Number of chunks to retrieve per case.",
    )
    parser.add_argument(
        "--db-connect-timeout-seconds",
        type=float,
        default=10.0,
        help="Timeout for the initial database connectivity check.",
    )
    parser.add_argument(
        "--case-timeout-seconds",
        type=float,
        default=60.0,
        help="Timeout for each eval case run.",
    )
    parser.add_argument(
        "--user-id",
        type=int,
        default=None,
        help="Optional document owner scope when resolving target_document filenames.",
    )
    parser.add_argument(
        "--min-answer-recall",
        type=float,
        default=0.6,
        help="Pass/fail floor for summary avg_answer_fact_recall.",
    )
    parser.add_argument(
        "--min-retrieval-recall",
        type=float,
        default=0.7,
        help="Pass/fail floor for summary avg_retrieval_fact_recall.",
    )
    parser.add_argument(
        "--min-top-similarity",
        type=float,
        default=0.55,
        help="Pass/fail floor for summary avg_top_similarity.",
    )
    parser.add_argument(
        "--min-answer-fact-recall",
        type=float,
        default=0.8,
        help="Fact-recall cutoff used to mark an eval case as correct.",
    )
    parser.add_argument(
        "--high-confidence-precision-target",
        type=float,
        default=0.9,
        help="Target precision for the recommended high-confidence threshold.",
    )
    parser.add_argument(
        "--medium-confidence-precision-target",
        type=float,
        default=0.7,
        help="Target precision for the recommended medium-confidence threshold.",
    )
    args = parser.parse_args()

    for arg_name in (
        "min_answer_recall",
        "min_retrieval_recall",
        "min_top_similarity",
        "min_answer_fact_recall",
        "high_confidence_precision_target",
        "medium_confidence_precision_target",
    ):
        value = float(getattr(args, arg_name))
        if not _is_valid_rate(value):
            raise ValueError(f"--{arg_name.replace('_', '-')} must be between 0.0 and 1.0")
    return args


async def _run_eval(args: argparse.Namespace) -> dict[str, Any]:
    cases = load_eval_cases(path=args.fixture)
    case_results: list[dict[str, Any]] = []

    try:
        async with AsyncSessionLocal() as db:
            await asyncio.wait_for(
                db.execute(select(1)),
                timeout=args.db_connect_timeout_seconds,
            )
    except TimeoutError:
        error = (
            "Database connectivity check timed out after "
            f"{args.db_connect_timeout_seconds} seconds."
        )
        case_results = [
            {
                "case_id": eval_case.case_id,
                "question": eval_case.question,
                "target_document": eval_case.target_document,
                "status": "error",
                "error": error,
            }
            for eval_case in cases
        ]
        summary = _build_summary(
            case_results,
            min_answer_fact_recall=args.min_answer_fact_recall,
            high_precision_target=args.high_confidence_precision_target,
            medium_precision_target=args.medium_confidence_precision_target,
        )
        threshold_gate = _build_threshold_gate(
            summary=summary,
            min_answer_recall=args.min_answer_recall,
            min_retrieval_recall=args.min_retrieval_recall,
            min_top_similarity=args.min_top_similarity,
        )
        return {
            "generated_at": datetime.now(UTC).replace(microsecond=0).isoformat(),
            "fixture_path": str(args.fixture),
            "cases": case_results,
            "summary": summary,
            "threshold_gate": threshold_gate,
        }

    for eval_case in cases:
        try:
            async with AsyncSessionLocal() as db:
                case_result = await asyncio.wait_for(
                    _run_case(
                        db=db,
                        eval_case=eval_case,
                        top_k=args.top_k,
                        user_id=args.user_id,
                    ),
                    timeout=args.case_timeout_seconds,
                )
        except TimeoutError:
            case_result = {
                "case_id": eval_case.case_id,
                "question": eval_case.question,
                "target_document": eval_case.target_document,
                "status": "error",
                "error": f"Case timed out after {args.case_timeout_seconds} seconds.",
            }
        except Exception as exc:
            case_result = {
                "case_id": eval_case.case_id,
                "question": eval_case.question,
                "target_document": eval_case.target_document,
                "status": "error",
                "error": str(exc),
            }
        case_results.append(case_result)

    generated_at = datetime.now(UTC).replace(microsecond=0).isoformat()
    summary = _build_summary(
        case_results,
        min_answer_fact_recall=args.min_answer_fact_recall,
        high_precision_target=args.high_confidence_precision_target,
        medium_precision_target=args.medium_confidence_precision_target,
    )
    threshold_gate = _build_threshold_gate(
        summary=summary,
        min_answer_recall=args.min_answer_recall,
        min_retrieval_recall=args.min_retrieval_recall,
        min_top_similarity=args.min_top_similarity,
    )
    return {
        "generated_at": generated_at,
        "fixture_path": str(args.fixture),
        "cases": case_results,
        "summary": summary,
        "threshold_gate": threshold_gate,
    }


def _write_artifacts(*, report: dict[str, Any], output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "report.json"
    markdown_path = output_dir / "report.md"

    json_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    markdown_path.write_text(_to_markdown(report) + "\n", encoding="utf-8")

    print(f"Wrote JSON report: {json_path}")
    print(f"Wrote Markdown report: {markdown_path}")


def main() -> None:
    args = _parse_args()
    report = asyncio.run(_run_eval(args))
    _write_artifacts(report=report, output_dir=args.output_dir)

    summary = report["summary"]
    print(
        "Summary:",
        f"cases_ok={summary['cases_ok']}",
        f"cases_error={summary['cases_error']}",
        f"avg_answer_fact_recall={summary['avg_answer_fact_recall']}",
        f"avg_retrieval_fact_recall={summary['avg_retrieval_fact_recall']}",
        f"avg_top_similarity={summary['avg_top_similarity']}",
        f"avg_total_ms={summary['avg_total_ms']}",
    )

    threshold_gate = report["threshold_gate"]
    print("Threshold gate:", f"verdict={threshold_gate['verdict']}")
    if not threshold_gate["passed"]:
        print("Breached metrics:", ", ".join(threshold_gate["breached_metrics"]))
        raise SystemExit(1)


if __name__ == "__main__":
    main()
