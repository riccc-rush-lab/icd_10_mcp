import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from icd10_mcp.importer import import_corpus


@pytest.mark.parametrize("contents", [None, "{}", "[]", "not-json"])
def test_trial_check_reports_invalid_configuration_without_private_paths(tmp_path, contents):
    private_config = tmp_path / "PRIVATE-CONFIG-MARKER.json"
    if contents is not None:
        private_config.write_text(contents)
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "icd10_mcp.cli",
            "trial-check",
            "--catalog-config",
            str(private_config),
        ],
        capture_output=True,
        text=True,
        timeout=15,
    )
    assert result.returncode == 2
    report = json.loads(result.stdout)
    assert report["status"] == "not_ready"
    assert report["reason"] == "catalog_configuration_unavailable"
    assert report["ready_for_clinical_use"] is False
    assert "PRIVATE-CONFIG-MARKER" not in result.stdout + result.stderr
    assert private_config.exists() is (contents is not None)


@pytest.fixture(scope="module")
def full_trial_config(tmp_path_factory, cdc_downloads, pytestconfig):
    fy2027 = pytestconfig.getoption("--fy2027-downloads")
    if fy2027 is None:
        pytest.skip("Requires --fy2027-downloads PATH")
    tmp_path = tmp_path_factory.mktemp("full-trial")
    import_corpus(cdc_downloads, tmp_path / "april.sqlite3")
    import_corpus(
        Path(fy2027),
        tmp_path / "fy2027.sqlite3",
        release_id="icd10cm-2026-10-01",
    )
    config = tmp_path / "catalogs.json"
    config.write_text(
        json.dumps(
            {
                "icd10cm-2026-04-01": "april.sqlite3",
                "icd10cm-2026-10-01": "fy2027.sqlite3",
            }
        )
    )
    return config


@pytest.mark.corpus
def test_trial_check_verifies_both_full_catalogs_and_real_stdio_mcp(full_trial_config):
    config = full_trial_config
    catalogs = [config.parent / "april.sqlite3", config.parent / "fy2027.sqlite3"]
    modified_before = [path.stat().st_mtime_ns for path in catalogs]
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "icd10_mcp.cli",
            "trial-check",
            "--catalog-config",
            str(config),
        ],
        cwd=config.parent,
        env={
            **os.environ,
            "ICD10_TRANSPORT": "streamable-http",
            "ICD10_PORT": "PRIVATE-INVALID-PORT",
            "ICD10_CATALOGS": "PRIVATE-WRONG-CONFIG",
        },
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    report = json.loads(result.stdout)
    assert report["status"] == "ready_for_local_trial"
    assert report["ready_for_clinical_use"] is False
    assert report["ready_for_patient_data"] is False
    assert report["optional_nlp"] == "not_checked"
    assert [
        (item["release"]["id"], item["status"], len(item["checks"])) for item in report["catalogs"]
    ] == [
        ("icd10cm-2026-04-01", "passed", 28),
        ("icd10cm-2026-10-01", "passed", 28),
    ]
    assert report["mcp"]["status"] == "passed"
    assert report["mcp"]["transport"] == "stdio"
    assert report["mcp"]["tools"] == [
        "phrase_search",
        "suggest_candidates",
        "validate_selected_codes",
    ]
    assert report["mcp"]["checks"] == [
        "tool_listing",
        "april_exact_code",
        "fy2027_exact_code",
        "phrase_lookup",
        "header_not_assignable",
        "fy2027_only_code",
        "april_rejects_future_code",
        "malformed_code_clarification",
        "unavailable_release",
        "selected_code_validity",
    ]
    assert "PRIVATE-" not in result.stdout + result.stderr
    assert [path.stat().st_mtime_ns for path in catalogs] == modified_before


@pytest.mark.parametrize("both_releases", [False, True])
def test_trial_check_rejects_incomplete_or_synthetic_catalogs(
    tmp_path, catalog_path, both_releases
):
    paths = {"icd10cm-2026-04-01": str(catalog_path)}
    if both_releases:
        paths["icd10cm-2026-10-01"] = str(catalog_path)
    config = tmp_path / "catalogs.json"
    config.write_text(json.dumps(paths))
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "icd10_mcp.cli",
            "trial-check",
            "--catalog-config",
            str(config),
        ],
        capture_output=True,
        text=True,
        timeout=15,
    )
    assert result.returncode == 2
    report = json.loads(result.stdout)
    assert report["status"] == "not_ready"
    assert report["reason"] == (
        "full_catalog_check_failed" if both_releases else "both_releases_required"
    )
    assert "mcp" not in report


@pytest.mark.corpus
def test_trial_check_rejects_swapped_full_release_catalogs(tmp_path, full_trial_config):
    config = tmp_path / "catalogs.json"
    config.write_text(
        json.dumps(
            {
                "icd10cm-2026-04-01": str(full_trial_config.parent / "fy2027.sqlite3"),
                "icd10cm-2026-10-01": str(full_trial_config.parent / "april.sqlite3"),
            }
        )
    )
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "icd10_mcp.cli",
            "trial-check",
            "--catalog-config",
            str(config),
        ],
        capture_output=True,
        text=True,
        timeout=15,
    )
    assert result.returncode == 2
    report = json.loads(result.stdout)
    assert report["reason"] == "full_catalog_check_failed"
    assert report["failed_release"] == "icd10cm-2026-04-01"
    assert "mcp" not in report
