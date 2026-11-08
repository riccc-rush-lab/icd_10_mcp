import os
import shutil
import subprocess
from pathlib import Path

import pytest


@pytest.fixture
def staged_assets(pytestconfig):
    models = pytestconfig.getoption("--openmed-models")
    python = pytestconfig.getoption("--openmed-python")
    if models is None and python is None:
        pytest.skip("Requires staged models and isolated runtime")
    assert models and python, "Both OpenMed integration options are required"
    return Path(models).resolve(), Path(python).absolute()


@pytest.mark.openmed
def test_staged_model_with_an_unmanifested_artifact_fails_closed(staged_assets, tmp_path, service):
    from icd10_mcp.nlp import LocalNLP

    models, python = staged_assets
    ner = tmp_path / "ner"
    shutil.copytree(models / "ner", ner)
    (ner / "unapproved.txt").write_text("Synthetic admission negative control.")
    output = LocalNLP(python=python, ner_dir=ner, pii_dir=models / "pii").analyze(
        "Pneumonia.",
        service,
        "2026-04-01",
        synthetic=True,
    )
    assert output["status"] == "nlp_unavailable"
    assert output["reason"] == "models_not_verified"
    assert output["pii_scan_completed"] is False
    assert output["safe_to_upload"] is False
    assert output["candidates"] == []
    assert service.search("Pneumonia", "2026-04-01")["candidates"][0]["code"] == "J18.9"


@pytest.mark.openmed
def test_documented_staging_cli_is_available_and_refuses_overwrite_offline(staged_assets, tmp_path):
    _, python = staged_assets
    root = Path(__file__).resolve().parents[1]
    command = [str(python), str(root / "scripts" / "stage_openmed.py")]
    env = {
        "PATH": os.defpath,
        "PYTHONPATH": str(root / "src"),
        "OPENMED_OFFLINE": "1",
        "HF_HUB_OFFLINE": "1",
        "HF_HUB_DISABLE_TELEMETRY": "1",
        "DO_NOT_TRACK": "1",
        "PYTHONDONTWRITEBYTECODE": "1",
    }
    result = subprocess.run(
        [*command, "--help"],
        env=env,
        cwd=root,
        capture_output=True,
        text=True,
        timeout=15,
    )
    assert result.returncode == 0, result.stderr
    assert "--output" in result.stdout
    destination = tmp_path / "ner"
    destination.mkdir()
    result = subprocess.run(
        [*command, "--output", str(tmp_path)],
        env=env,
        cwd=root,
        capture_output=True,
        text=True,
        timeout=15,
    )
    assert result.returncode != 0
    assert "Refusing to replace staged model artifacts" in result.stderr
    assert list(destination.iterdir()) == []
