import json
import os
import socket
import subprocess
import sys
import time
from contextlib import contextmanager, nullcontext
from pathlib import Path
from types import SimpleNamespace
from urllib.error import URLError
from urllib.request import OpenerDirector

import httpx
import pytest

from icd10_mcp.catalog import configured_catalog
from icd10_mcp.service import ICDService


@pytest.mark.corpus
def test_source_only_demo_build_prepares_verified_read_only_catalogs(
    tmp_path, cdc_downloads, pytestconfig
):
    fy2027 = pytestconfig.getoption("--fy2027-downloads")
    if fy2027 is None:
        pytest.skip("Requires --fy2027-downloads PATH")
    output = tmp_path / "prepared"
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "icd10_mcp.demo_build",
            "--april-downloads",
            str(cdc_downloads),
            "--fy2027-downloads",
            fy2027,
            "--output",
            str(output),
        ],
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    report = json.loads(result.stdout)
    assert report["status"] == "prepared"
    assert report["network_downloads"] is False
    service = ICDService(configured_catalog("", output / "catalogs.json"))
    assert service.search("C78.31", "2026-09-30")["status"] == "abstain"
    assert service.search("C78.31", "2026-10-01")["candidates"][0]["code"] == "C78.31"
    assert service.search("E11.9", "2026-04-01")["catalog_scope"] == "full_cdc_corpus"
    assert (output / "catalog.sqlite3").stat().st_mode & 0o222 == 0
    assert (output / "releases/2027/catalog.sqlite3").stat().st_mode & 0o222 == 0

    with socket.socket() as reservation:
        reservation.bind(("127.0.0.1", 0))
        port = reservation.getsockname()[1]
    token = "synthetic-demo-build-client-token-1234567890"
    env = {
        **os.environ,
        "ICD10_CATALOGS": str(output / "catalogs.json"),
        "ICD10_DEMO_HOSTNAME": "127.0.0.1",
        "ICD10_DEMO_TOKEN": token,
        "PORT": str(port),
    }
    process = subprocess.Popen(
        [sys.executable, "-m", "icd10_mcp.demo"],
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        with httpx.Client(base_url=f"http://127.0.0.1:{port}", trust_env=False) as client:
            for _ in range(100):
                assert process.poll() is None, "Demo exited instead of starting on loopback"
                try:
                    assert client.get("/readyz", timeout=1).status_code == 200
                    break
                except httpx.ConnectError:
                    time.sleep(0.05)
            else:
                raise AssertionError("Demo startup timed out")
            assert client.post("/mcp", json={}).status_code == 401
        checked = subprocess.run(
            [
                sys.executable,
                "-m",
                "icd10_mcp.demo_client",
                "--url",
                f"http://127.0.0.1:{port}/mcp",
                "--date",
                "2026-10-01",
            ],
            env=env,
            cwd=tmp_path,
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert checked.returncode == 0, checked.stdout + checked.stderr
        assert json.loads(checked.stdout)["release"]["id"] == "icd10cm-2026-10-01"
        assert token not in checked.stdout + checked.stderr
    finally:
        process.terminate()
        stdout, stderr = process.communicate(timeout=10)
    assert token not in stdout + stderr


def test_failed_external_source_download_never_publishes_a_ready_configuration(
    tmp_path, monkeypatch
):
    from icd10_mcp.demo_build import build_demo_catalogs

    def offline(self, *args, **kwargs):
        raise URLError("Synthetic external source failure")

    # External HTTP I/O, not an owned importer/catalog collaborator.
    monkeypatch.setattr(OpenerDirector, "open", offline)
    output = tmp_path / "prepared"
    with pytest.raises(URLError):
        build_demo_catalogs(output, download=True)
    assert not (output / "catalogs.json").exists()


def test_demo_build_refuses_existing_directory_without_touching_user_files(tmp_path):
    marker = tmp_path / "user-work.md"
    marker.write_text("Do not replace this")
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "icd10_mcp.demo_build",
            "--april-downloads",
            str(tmp_path),
            "--fy2027-downloads",
            str(tmp_path),
            "--output",
            str(tmp_path),
        ],
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert result.returncode == 2
    assert json.loads(result.stdout) == {"status": "failed", "reason": "catalog_build_failed"}
    assert marker.read_text() == "Do not replace this"
    assert not (tmp_path / "catalogs.json").exists()


def test_demo_build_rejects_changed_archive_before_publishing_configuration(tmp_path):
    sources = tmp_path / "sources"
    sources.mkdir()
    (sources / "icd10cm-table-and-index-April-1-2026.zip").write_bytes(b"not approved CDC bytes")
    output = tmp_path / "prepared"
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "icd10_mcp.demo_build",
            "--april-downloads",
            str(sources),
            "--fy2027-downloads",
            str(sources),
            "--output",
            str(output),
        ],
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert result.returncode == 2
    assert not (output / "catalogs.json").exists()
    assert not (output / "catalog.sqlite3").exists()


@pytest.mark.corpus
def test_download_mode_verifies_real_archive_bytes_through_external_http_adapter(
    tmp_path, cdc_downloads, pytestconfig, monkeypatch
):
    from icd10_mcp.demo_build import build_demo_catalogs

    fy2027 = pytestconfig.getoption("--fy2027-downloads")
    if fy2027 is None:
        pytest.skip("Requires --fy2027-downloads PATH")
    sources = {
        "https://ftp.cdc.gov/pub/Health_Statistics/NCHS/Publications/ICD10CM/"
        "2026-update/icd10cm-table-and-index-April-1-2026.zip": cdc_downloads
        / "icd10cm-table-and-index-April-1-2026.zip",
        "https://ftp.cdc.gov/pub/Health_Statistics/NCHS/Publications/ICD10CM/"
        "2026-update/icd10cm-April-1-2026-XML.zip": cdc_downloads / "icd10cm-April-1-2026-XML.zip",
        "https://ftp.cdc.gov/pub/Health_Statistics/NCHS/Publications/ICD10CM/"
        "2027/icd10cm-code-descriptions-2027.zip": Path(fy2027)
        / "icd10cm-code-descriptions-2027.zip",
        "https://ftp.cdc.gov/pub/Health_Statistics/NCHS/Publications/ICD10CM/"
        "2027/icd10cm-table-and-index-2027.zip": Path(fy2027) / "icd10cm-table-and-index-2027.zip",
    }

    @contextmanager
    def public_archive(self, request, **kwargs):
        with sources[request.full_url].open("rb") as source:
            yield SimpleNamespace(status=200, read=source.read)

    monkeypatch.setattr(OpenerDirector, "open", public_archive)
    output = tmp_path / "prepared"
    report = build_demo_catalogs(output, download=True)
    assert report["network_downloads"] is True
    assert [len(item["checks"]) for item in report["catalogs"]] == [28, 28]
    service = ICDService(configured_catalog("", output / "catalogs.json"))
    assert service.search("C78.31", "2026-10-01")["candidates"][0]["code"] == "C78.31"


def test_download_mode_bounds_untrusted_response_size_without_publishing_ready_artifacts(
    tmp_path, monkeypatch
):
    from icd10_mcp.demo_build import build_demo_catalogs

    chunk = b"x" * 1_048_576

    def endless_response(self, request, **kwargs):
        return nullcontext(SimpleNamespace(status=200, read=lambda size: chunk))

    monkeypatch.setattr(OpenerDirector, "open", endless_response)
    output = tmp_path / "prepared"
    with pytest.raises(ValueError, match="build limit"):
        build_demo_catalogs(output, download=True)
    assert not (output / "catalogs.json").exists()
