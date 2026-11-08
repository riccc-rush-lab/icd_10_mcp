import json
import subprocess
import sys

import pytest


def test_exploratory_metrics_expose_deliberately_wrong_code_without_claiming_review(service):
    from icd10_mcp.evaluation import evaluate

    cases = [
        ("correct", "A00.1", ["A00.1"]),
        ("deliberate-mismatch", "A00.1", ["B00.1"]),
        ("abstain", "zzzzzzzz", []),
        ("phrase", "Pneumonia", ["J18.9"]),
    ]
    benchmark = {
        "schema_version": 1,
        "synthetic": True,
        "id": "synthetic-fixture",
        "cases": [
            {
                "id": name,
                "workflow": "lookup",
                "text": text,
                "service_date": "2026-04-01",
                "expected_codes": codes,
                "exhaustive": True,
                "slice": "fixture",
                "review": {"status": "unreviewed"},
                "source": {"reference": "hand-authored synthetic specification"},
            }
            for name, text, codes in cases
        ],
    }
    result = evaluate(service, benchmark)
    assert result["status"] == "review_required"
    assert result["ready_for_clinical_use"] is False
    assert result["reviewed_metrics"] is None
    metrics = result["exploratory_metrics"]
    assert metrics["cases"] == 4
    assert metrics["top1_match"] == pytest.approx(2 / 3)
    assert metrics["recall_at_k"] == pytest.approx(2 / 3)
    assert metrics["wrong_code_rate"] == pytest.approx(1 / 3)
    assert metrics["abstention_rate"] == 0.25
    assert metrics["top1_denominator"] == 3
    assert result["results"][1]["unexpected_codes"] == ["A00.1"]
    assert result["slices"]["fixture"]["cases"] == 4


def test_duplicate_case_ids_cannot_hide_a_benchmark_result(service):
    from icd10_mcp.evaluation import evaluate

    case = {
        "id": "duplicate",
        "workflow": "lookup",
        "text": "A00.1",
        "service_date": "2026-04-01",
        "expected_codes": ["A00.1"],
        "exhaustive": True,
        "slice": "fixture",
        "review": {"status": "unreviewed"},
        "source": {"reference": "synthetic specification"},
    }
    with pytest.raises(ValueError, match="unique"):
        evaluate(
            service,
            {
                "schema_version": 1,
                "synthetic": True,
                "id": "fixture",
                "cases": [case, case],
            },
        )


def test_evaluate_cli_emits_review_packet_not_a_clinical_pass(tmp_path, catalog_path):
    benchmark = tmp_path / "draft.json"
    benchmark.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "synthetic": True,
                "id": "cli-fixture",
                "cases": [
                    {
                        "id": "exact",
                        "workflow": "lookup",
                        "text": "A00.1",
                        "service_date": "2026-04-01",
                        "expected_codes": ["A00.1"],
                        "exhaustive": True,
                        "slice": "exact",
                        "review": {"status": "unreviewed"},
                        "source": {"reference": "synthetic specification"},
                    }
                ],
            }
        )
    )
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "icd10_mcp.cli",
            "evaluate",
            str(benchmark),
            "--database",
            str(catalog_path),
        ],
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert result.returncode == 0, result.stderr
    output = json.loads(result.stdout)
    assert output["exploratory_metrics"]["top1_match"] == 1
    assert output["reviewed_cases"] == 0
    assert output["ready_for_clinical_use"] is False


@pytest.mark.parametrize(
    "field,value",
    [
        ("expected_codes", "A00.1"),
        ("expected_codes", ["A00.1", "A00.1"]),
        ("exhaustive", "false"),
        ("review", None),
        ("source", {}),
    ],
)
def test_malformed_labels_are_rejected_instead_of_distorting_denominators(service, field, value):
    from icd10_mcp.evaluation import evaluate

    case = {
        "id": "bad-label",
        "workflow": "lookup",
        "text": "A00.1",
        "service_date": "2026-04-01",
        "expected_codes": ["A00.1"],
        "exhaustive": True,
        "slice": "fixture",
        "review": {"status": "unreviewed"},
        "source": {"reference": "synthetic specification"},
    }
    case[field] = value
    with pytest.raises(ValueError):
        evaluate(
            service,
            {
                "schema_version": 1,
                "synthetic": True,
                "id": "malformed-fixture",
                "cases": [case],
            },
        )


def test_explicitly_unsafe_output_is_visible_even_with_nonexhaustive_labels(service):
    from icd10_mcp.evaluation import evaluate

    result = evaluate(
        service,
        {
            "schema_version": 1,
            "synthetic": True,
            "id": "unsafe-negative-control",
            "cases": [
                {
                    "id": "deliberately-forbidden",
                    "workflow": "lookup",
                    "text": "A00.1",
                    "service_date": "2026-04-01",
                    "expected_codes": [],
                    "forbidden_codes": ["A00.1"],
                    "exhaustive": False,
                    "slice": "fixture",
                    "review": {"status": "unreviewed"},
                    "source": {"reference": "deliberate synthetic evaluator negative control"},
                }
            ],
        },
    )
    assert result["results"][0]["unsafe_codes"] == ["A00.1"]
    assert result["exploratory_metrics"]["unsafe_code_count"] == 1
    assert result["exploratory_metrics"]["wrong_code_rate"] is None


def test_optional_evaluation_cli_reports_missing_models_as_errors_not_abstention(
    tmp_path,
    catalog_path,
):
    path = tmp_path / "openmed.json"
    path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "synthetic": True,
                "id": "missing-runtime",
                "cases": [
                    {
                        "id": "affirmed",
                        "workflow": "openmed",
                        "text": "Pneumonia.",
                        "service_date": "2026-04-01",
                        "expected_codes": ["J18.9"],
                        "exhaustive": True,
                        "slice": "fixture",
                        "review": {"status": "unreviewed"},
                        "source": {"reference": "synthetic pneumonia J18.9"},
                    }
                ],
            }
        )
    )
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "icd10_mcp.cli",
            "evaluate",
            str(path),
            "--database",
            str(catalog_path),
            "--models",
            str(tmp_path / "missing"),
            "--nlp-python",
            sys.executable,
        ],
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert result.returncode == 0, result.stderr
    metrics = json.loads(result.stdout)["exploratory_metrics"]
    assert metrics["error_count"] == 1
    assert metrics["abstention_rate"] == 0
    assert metrics["coverage"] == 0
