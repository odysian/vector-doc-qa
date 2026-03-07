# Mini Eval Harness

This repository includes a small eval runner for tracking retrieval quality, answer quality, and latency trends on a fixed prompt set.

## Run

From repo root:

```bash
make backend-mini-eval
```

Artifacts are written to:

- `backend/reports/mini_eval/report.json`
- `backend/reports/mini_eval/report.md`

The Markdown report is intended for easy PR diffs.

Optional CLI overrides:

```bash
cd backend
PYTHONPATH=. .venv/bin/python scripts/run_mini_eval.py \
  --fixture scripts/fixtures/mini_eval_cases.json \
  --output-dir reports/mini_eval \
  --top-k 5 \
  --user-id 1 \
  --min-answer-fact-recall 0.8 \
  --high-confidence-precision-target 0.9 \
  --medium-confidence-precision-target 0.7 \
  --db-connect-timeout-seconds 10 \
  --case-timeout-seconds 60
```

## Fixture File

Default fixture path:

`backend/scripts/fixtures/mini_eval_cases.json`

Each case must include:

- `case_id`: stable unique id (used for deterministic ordering)
- `question`: user prompt
- `target_document`: exact `documents.filename` value in the database
- `expected_facts`: list of expected keywords/short fact phrases

Example:

```json
{
  "case_id": "case-001-q4-revenue",
  "question": "What was the Q4 revenue in this report?",
  "target_document": "acme-q4-report.pdf",
  "expected_facts": ["Q4 revenue", "$5M"]
}
```

## Metrics Collected

- Latency: `embed_ms`, `retrieval_ms`, `llm_ms`, `total_ms`
- Retrieval proxies: `top_similarity`, `avg_similarity`, `chunks_retrieved`
- Quality proxy: expected fact recall in answer text and retrieved chunk text
- Confidence calibration recommendations:
  - Computes `high` and `medium` suggested `top_similarity` cutoffs from observed eval outcomes.
  - Treats a case as "correct" when `answer.fact_recall >= --min-answer-fact-recall`.
  - Chooses thresholds that maximize coverage while meeting each precision target when possible.

## Extending Cases

1. Upload and process the target document so it exists with `status=completed`.
2. Add a new case object to `backend/scripts/fixtures/mini_eval_cases.json`.
3. Keep `case_id` stable and unique.
4. Use short, explicit `expected_facts` strings that should appear in answers.
5. Re-run `make backend-mini-eval` and compare `report.md`/`report.json`.

## Notes

- The harness is deterministic in case order and retrieval config (`top_k=5` by default).
- It does not change production schema or runtime API contracts.
- Use `--user-id` when multiple users may have documents with the same filename.
- Fact matching is case-insensitive substring matching; keep `expected_facts` specific enough to avoid accidental partial matches.
- Each case runs in a separate database session for isolation.
- If a target document is missing or ambiguous, that case is marked as `error` in the report.
- Report summary includes a `confidence_calibration` block in JSON and a Markdown table with:
  - recommended minimum `top_similarity` for `high` and `medium` bands
  - observed precision/coverage at those thresholds
