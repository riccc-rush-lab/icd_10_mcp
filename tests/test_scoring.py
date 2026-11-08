import json
import subprocess
import sys


def test_scoring_cli_cannot_claim_or_calculate_an_unvalidated_score():
    result = subprocess.run(
        [sys.executable, "-m", "icd10_mcp.cli", "scoring-status"],
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert result.returncode == 0, result.stderr
    output = json.loads(result.stdout)
    assert output["status"] == "not_configured"
    assert output["calculation_enabled"] is False
    assert output["available_methods"] == []
    assert "score" not in output
    assert "method_version" in output["required_evidence"]
    assert "independent_worked_examples" in output["required_evidence"]
