import hashlib
import json
import subprocess
import sys
from pathlib import Path

import pytest


def test_missing_local_models_fail_closed_without_claiming_a_pii_scan(tmp_path, service):
    from icd10_mcp.nlp import LocalNLP

    result = LocalNLP(
        python=sys.executable,
        ner_dir=tmp_path / "ner",
        pii_dir=tmp_path / "pii",
    ).analyze("Pneumonia.", service, "2026-04-01", synthetic=True)
    assert result["status"] == "nlp_unavailable"
    assert result["pii_scan_completed"] is False
    assert result["candidates"] == []
    assert result["safe_to_upload"] is False
    assert service.search("Pneumonia", "2026-04-01")["candidates"][0]["code"] == "J18.9"


def test_malformed_model_config_fails_closed_before_inference(tmp_path, service):
    from icd10_mcp.nlp import LocalNLP

    ner = tmp_path / "ner"
    ner.mkdir()
    files = {
        "config.json": b"[]",
        "tokenizer_config.json": b"{}",
        "model.safetensors": b"intentionally invalid artifact; must never reach inference",
    }
    for name, data in files.items():
        (ner / name).write_bytes(data)
    (ner / "manifest.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "role": "ner",
                "repo": "OpenMed/OpenMed-NER-DiseaseDetect-TinyMed-135M",
                "revision": "dcb346697f933cea9d9c9cb27b58a1faf8f08f5e",
                "license": "apache-2.0",
                "files": [
                    {"name": name, "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}
                    for name, data in files.items()
                ],
            }
        )
    )
    result = LocalNLP(
        python=sys.executable,
        ner_dir=ner,
        pii_dir=tmp_path / "missing",
    ).analyze("Pneumonia.", service, "2026-04-01", synthetic=True)
    assert result["status"] == "nlp_unavailable"
    assert result["reason"] == "models_not_verified"
    assert result["pii_scan_completed"] is False


@pytest.fixture
def real_nlp(pytestconfig):
    from icd10_mcp.nlp import LocalNLP

    models = pytestconfig.getoption("--openmed-models")
    python = pytestconfig.getoption("--openmed-python")
    if models is None and python is None:
        pytest.skip("Requires staged models and isolated runtime")
    assert models and python, "Both OpenMed integration options are required"
    return LocalNLP(python=python, ner_dir=Path(models) / "ner", pii_dir=Path(models) / "pii")


@pytest.mark.openmed
def test_real_model_offsets_refer_to_original_whitespace_not_trimmed_copy(real_nlp, service):
    result = real_nlp.analyze("  Pneumonia.\n", service, "2026-04-01", synthetic=True)
    assert result["status"] == "review_required", result
    mention = next(item for item in result["mentions"] if item["label"] == "DISEASE")
    assert mention["start"] == 2
    assert mention["end"] == 11
    assert mention["text"] == "Pneumonia"


@pytest.mark.openmed
@pytest.mark.parametrize("text", ["  Diagnosis: pneumonia.", "é Diagnosis: pneumonia."])
def test_candidate_evidence_uses_original_note_unicode_offsets(real_nlp, service, text):
    output = real_nlp.analyze(text, service, "2026-04-01", synthetic=True)
    assert output["status"] == "review_required", output
    candidate = next(item for item in output["candidates"] if item["code"] == "J18.9")
    assert [(span["start"], span["end"], span["text"]) for span in candidate["evidence_spans"]] == [
        (13, 22, "pneumonia")
    ]
    assert output["offset_basis"] == "original_input"


@pytest.mark.openmed
def test_repeated_mentions_keep_both_source_spans_when_code_is_deduplicated(real_nlp, service):
    output = real_nlp.analyze(
        "Pneumonia. Pneumonia.",
        service,
        "2026-04-01",
        synthetic=True,
    )
    assert output["status"] == "review_required", output
    assert [item["code"] for item in output["candidates"]] == ["J18.9"]
    candidate = output["candidates"][0]
    assert [(span["start"], span["end"], span["text"]) for span in candidate["evidence_spans"]] == [
        (0, 9, "Pneumonia"),
        (11, 20, "Pneumonia"),
    ]


@pytest.mark.openmed
def test_unspecified_candidate_retains_validity_and_exposes_documentation_review(real_nlp, service):
    output = real_nlp.analyze(
        "  Diagnosis: pneumonia.",
        service,
        "2026-04-01",
        synthetic=True,
    )
    assert output["status"] == "review_required", output
    candidate = next(item for item in output["candidates"] if item["code"] == "J18.9")
    assert candidate["assessments"] == {
        "code_validity": "valid",
        "documentation_support": "partial",
        "completeness": "needs_clarification",
    }
    assert "Check whether more specific documentation is available." in candidate["missing_details"]
    assert (
        "Confirm code-specific details; an index alias is not full support."
        in (candidate["missing_details"])
    )
    assert output["is_final_assignment"] is False
    assert output["safe_to_upload"] is False


def test_optional_note_cli_reports_unavailable_without_breaking_core(tmp_path, catalog_path):
    note = tmp_path / "synthetic-note"
    note.write_text("Pneumonia.")
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "icd10_mcp.cli",
            "match-note",
            "--file",
            str(note),
            "--synthetic",
            "--date",
            "2026-04-01",
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
    assert result.returncode == 2, result.stderr
    output = json.loads(result.stdout)
    assert output["status"] == "nlp_unavailable"
    assert output["pii_scan_completed"] is False


def test_note_assistance_requires_explicit_synthetic_input(tmp_path, service):
    from icd10_mcp.nlp import LocalNLP

    output = LocalNLP(
        python=sys.executable,
        ner_dir=tmp_path / "ner",
        pii_dir=tmp_path / "pii",
    ).analyze("Pneumonia.", service, "2026-04-01")
    assert output["status"] == "invalid_request"
    assert output["pii_scan_completed"] is False


@pytest.mark.openmed
@pytest.mark.parametrize(
    "text",
    [
        "No pneumonia.",
        "Possible pneumonia.",
        "History of pneumonia.",
        "Family history of pneumonia.",
    ],
)
def test_real_context_cues_do_not_become_active_disease_candidates(real_nlp, service, text):
    output = real_nlp.analyze(text, service, "2026-04-01", synthetic=True)
    assert output["status"] == "review_required", output
    assert output["mentions"]
    assert output["candidates"] == []
    assert all(item["lookup_status"] == "context_review_required" for item in output["mentions"])


@pytest.mark.openmed
def test_overlength_note_is_rejected_instead_of_silently_truncated(real_nlp, service):
    output = real_nlp.analyze("pneumonia " * 600, service, "2026-04-01", synthetic=True)
    assert output["status"] == "nlp_unavailable"
    assert output["reason"] == "token_limit_exceeded"
    assert output["pii_scan_completed"] is False
    assert output["candidates"] == []


@pytest.mark.openmed
def test_real_nlp_evaluation_is_separate_exploratory_and_records_model_pins(real_nlp, service):
    from icd10_mcp.evaluation import evaluate

    benchmark = {
        "schema_version": 1,
        "synthetic": True,
        "id": "real-model-synthetic-contrast",
        "cases": [
            {
                "id": identifier,
                "workflow": "openmed",
                "text": text,
                "service_date": "2026-04-01",
                "expected_codes": codes,
                "forbidden_codes": forbidden,
                "exhaustive": True,
                "slice": identifier,
                "review": {"status": "unreviewed"},
                "source": {"reference": "synthetic contrast; fixture pneumonia J18.9"},
            }
            for identifier, text, codes, forbidden in [
                ("affirmed", "Pneumonia.", ["J18.9"], []),
                ("negated", "No pneumonia.", [], ["J18.9"]),
            ]
        ],
    }
    result = evaluate(service, benchmark, nlp=real_nlp, limit=1)
    assert result["exploratory_metrics"]["top1_match"] == 1
    assert result["exploratory_metrics"]["abstention_rate"] == 0.5
    assert result["exploratory_metrics"]["unsafe_code_count"] == 0
    assert result["reviewed_metrics"] is None
    assert result["results"][0]["models"]["ner"]["revision"] == (
        "dcb346697f933cea9d9c9cb27b58a1faf8f08f5e"
    )
    assert result["ready_for_clinical_use"] is False


@pytest.mark.openmed
def test_real_offline_models_link_synthetic_disease_and_show_pii_preview(service, pytestconfig):
    from icd10_mcp.nlp import LocalNLP

    models = pytestconfig.getoption("--openmed-models")
    python = pytestconfig.getoption("--openmed-python")
    if models is None and python is None:
        pytest.skip("Requires --openmed-models PATH and --openmed-python PATH")
    assert models and python, "Both OpenMed integration options are required"
    root = Path(models)
    text = "Patient Avery Example. Email: avery@example.invalid. Diagnosis: pneumonia."
    output = LocalNLP(
        python=python,
        ner_dir=root / "ner",
        pii_dir=root / "pii",
    ).analyze(text, service, "2026-04-01", synthetic=True)
    assert output["status"] == "review_required", output
    assert output["pii_scan_completed"] is True
    assert output["safe_to_upload"] is False
    assert "avery@example.invalid" not in output["redacted_preview"]
    assert "@example.invalid" not in output["redacted_preview"]
    assert any(item["text"].lower() == "pneumonia" for item in output["mentions"])
    for item in output["mentions"]:
        assert text[item["start"] : item["end"]] == item["text"]
    assert any(item["code"] == "J18.9" for item in output["candidates"])
    assert output["models"]["ner"]["revision"] == "dcb346697f933cea9d9c9cb27b58a1faf8f08f5e"
    assert output["models"]["pii"]["revision"] == "2ea947130eb28d610ceb96472af0b694fce9c344"
    assert output["runtime"]["openmed"] == "3.1.0"
