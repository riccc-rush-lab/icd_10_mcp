"""Synthetic-only evaluation. Draft labels never become clinical validation."""

from __future__ import annotations

import hashlib
import json
from collections import defaultdict


def _metrics(rows):
    positives = [row for row in rows if row["expected_codes"]]
    exhaustive = [row for row in rows if row["exhaustive"]]
    returned = sum(len(row["codes"]) for row in exhaustive)
    relevant = sum(len(row["expected_codes"]) for row in positives)
    return {
        "cases": len(rows),
        "top1_match": sum(row["top1_match"] for row in positives) / len(positives)
        if positives
        else None,
        "top1_denominator": len(positives),
        "recall_at_k": sum(len(row["hits"]) for row in positives) / relevant if relevant else None,
        "recall_denominator": relevant,
        "wrong_code_rate": sum(len(row["unexpected_codes"]) for row in exhaustive) / returned
        if returned
        else None,
        "wrong_code_denominator": returned,
        "unsafe_code_count": sum(len(row["unsafe_codes"]) for row in rows),
        "abstention_rate": sum(row["abstained"] for row in rows) / len(rows) if rows else None,
        "coverage": sum(bool(row["codes"]) for row in rows) / len(rows) if rows else None,
        "error_count": sum(
            row["status"]
            in {"invalid_request", "release_unavailable", "catalog_unavailable", "nlp_unavailable"}
            for row in rows
        ),
    }


def evaluate(service, benchmark: dict, *, limit: int = 10, nlp=None) -> dict:
    if (
        not isinstance(benchmark, dict)
        or type(benchmark.get("schema_version")) is not int
        or benchmark.get("schema_version") != 1
        or benchmark.get("synthetic") is not True
    ):
        raise ValueError("Only schema 1 synthetic benchmarks are accepted")
    if not isinstance(benchmark.get("id"), str) or not benchmark["id"].strip():
        raise ValueError("Supply a benchmark ID")
    cases = benchmark.get("cases")
    if not isinstance(cases, list) or not cases or len(cases) > 1000:
        raise ValueError("Supply 1..1000 synthetic cases")
    if type(limit) is not int or not 1 <= limit <= 25:
        raise ValueError("Evaluation limit must be 1..25")
    if not all(isinstance(case, dict) for case in cases):
        raise ValueError("Each benchmark case must be an object")
    identifiers = [case.get("id") for case in cases]
    if any(not isinstance(value, str) or not value for value in identifiers) or (
        len(set(identifiers)) != len(identifiers)
    ):
        raise ValueError("Benchmark case IDs must be nonempty and unique")
    results, groups = [], defaultdict(list)
    for case in cases:
        if not all(
            isinstance(case.get(key), str) and case[key].strip()
            for key in ["workflow", "text", "service_date", "slice"]
        ):
            raise ValueError("Cases require workflow, text, service_date and slice strings")
        expected = case.get("expected_codes")
        forbidden = case.get("forbidden_codes", [])
        if (
            not isinstance(expected, list)
            or not all(isinstance(code, str) and code.strip() for code in expected)
            or len(set(expected)) != len(expected)
            or not isinstance(forbidden, list)
            or not all(isinstance(code, str) and code.strip() for code in forbidden)
            or len(set(forbidden)) != len(forbidden)
            or type(case.get("exhaustive")) is not bool
        ):
            raise ValueError("Labels require unique code strings and a boolean exhaustive flag")
        if set(expected) & set(forbidden):
            raise ValueError("Expected and forbidden labels must not overlap")
        source = case.get("source")
        if (
            not isinstance(source, dict)
            or not isinstance(source.get("reference"), str)
            or not source["reference"].strip()
        ):
            raise ValueError("Supply a source reference for every case")
        workflow = case["workflow"]
        if workflow not in {"lookup", "suggest", "openmed"}:
            raise ValueError("Unknown benchmark workflow")
        review = case.get("review")
        if (
            not isinstance(review, dict)
            or not isinstance(review.get("status"), str)
            or review["status"] not in {"unreviewed", "reviewed"}
        ):
            raise ValueError("Unknown review status")
        if review["status"] == "reviewed" and not all(
            isinstance(review.get(key), str) and review[key].strip()
            for key in ["reviewer", "reviewed_at", "evidence"]
        ):
            raise ValueError("Reviewed labels require a reviewer, date and evidence")
        if workflow == "openmed":
            if nlp is None:
                raise ValueError(
                    "OpenMed benchmarks require an explicitly configured local runtime"
                )
            output = nlp.analyze(case["text"], service, case["service_date"], synthetic=True)
        else:
            method = service.search if workflow == "lookup" else service.suggest
            output = method(case["text"], case["service_date"], limit)
        codes = list(dict.fromkeys(item["code"] for item in output.get("candidates", [])))[:limit]
        hits = [code for code in codes if code in expected]
        row = {
            "id": case["id"],
            "workflow": workflow,
            "review": review,
            "source": case["source"],
            "release": output.get("release"),
            "status": output["status"],
            "codes": codes,
            "expected_codes": expected,
            "exhaustive": case["exhaustive"],
            "forbidden_codes": forbidden,
            "unsafe_codes": [code for code in codes if code in forbidden],
            "hits": hits,
            "top1_match": bool(codes and codes[0] in expected),
            "unexpected_codes": [code for code in codes if code not in expected]
            if case["exhaustive"]
            else [],
            "abstained": not codes
            and (
                output["status"] in {"abstain", "needs_clarification"}
                or (workflow == "openmed" and output["status"] == "review_required")
            ),
            "expected_status": case.get("expected_status"),
            "status_match": output["status"] == case["expected_status"]
            if "expected_status" in case
            else None,
        }
        if workflow == "openmed":
            row.update(
                {
                    "models": output.get("models"),
                    "runtime": output.get("runtime"),
                    "reason": output.get("reason"),
                }
            )
        results.append(row)
        groups[case["slice"]].append(row)
    reviewed = [row for row in results if row["review"]["status"] == "reviewed"]
    return {
        "status": "review_required",
        "ready_for_clinical_use": False,
        "benchmark_id": benchmark["id"],
        "benchmark_sha256": hashlib.sha256(
            json.dumps(benchmark, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest(),
        "label_warning": "Draft metrics are exploratory; review metadata is an attestation, "
        "not verified reviewer qualifications or clinical approval.",
        "limit": limit,
        "exploratory_metrics": _metrics(results),
        "reviewed_metrics": _metrics(reviewed) if reviewed else None,
        "reviewed_cases": len(reviewed),
        "slices": {key: _metrics(rows) for key, rows in sorted(groups.items())},
        "results": results,
    }
