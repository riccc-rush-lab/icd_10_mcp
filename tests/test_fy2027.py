import hashlib
import json
import subprocess
import sys
from pathlib import Path
from xml.etree.ElementTree import tostring
from zipfile import ZipFile

import pytest
from defusedxml import ElementTree as ET

from icd10_mcp.catalog import Catalog
from icd10_mcp.importer import import_corpus
from icd10_mcp.service import ICDService


@pytest.fixture
def fy2027_catalog(tmp_path, source_files):
    from icd10_mcp.importer import build_catalog

    table_root = "icd10cm-table-and-index-2027"
    names = {
        "icd10cm-codes-April-1-2026.txt": "icd10cm-code-descriptions-2027/icd10cm-codes-2027.txt",
        "icd10cm-order-April-1-2026.txt": "icd10cm-code-descriptions-2027/icd10cm-order-2027.txt",
        "icd10c-tabular-April-1-2026.xml": "icd10cm-table-and-index-2027/icd10cm-tabular_-2027.xml",
        **{
            f"icd10cm-{kind}-April-1-2026-XML.xml": f"{table_root}/icd10cm-{kind}-2027.xml"
            for kind in ["index", "eindex", "drug", "neoplasm"]
        },
    }
    files = {
        names[name]: data.replace(b"<version>2026</version>", b"<version>2027</version>")
        for name, data in source_files.items()
    }
    path = tmp_path / "synthetic-fy2027.sqlite3"
    build_catalog(
        files,
        [
            {"member": name, "sha256": hashlib.sha256(data).hexdigest(), "bytes": len(data)}
            for name, data in files.items()
        ],
        path,
        expected_counts=(12, 10),
        release_id="icd10cm-2026-10-01",
    )
    return path


def test_date_selection_is_request_local_across_both_catalogs(catalog_path, fy2027_catalog):
    from icd10_mcp.catalog import CatalogSet

    service = ICDService(
        CatalogSet(
            {
                "icd10cm-2026-04-01": catalog_path,
                "icd10cm-2026-10-01": fy2027_catalog,
            }
        )
    )
    for day, expected in [
        ("2026-09-30", "icd10cm-2026-04-01"),
        ("2026-10-01", "icd10cm-2026-10-01"),
        ("2026-04-01", "icd10cm-2026-04-01"),
        ("2027-09-30", "icd10cm-2026-10-01"),
    ]:
        for result in [
            service.search("A00.1", day),
            service.suggest("Pneumonia", day),
            service.validate(["A00.1"], day),
        ]:
            assert result["release"]["id"] == expected
    assert service.search("A00.1", "2027-10-01")["status"] == "release_unavailable"
    assert service.search("A00.1", "20261001")["status"] == "invalid_request"


def test_lookup_cli_uses_explicit_release_config(tmp_path, catalog_path, fy2027_catalog):
    config = tmp_path / "catalogs.json"
    config.write_text(
        json.dumps(
            {
                "icd10cm-2026-04-01": str(catalog_path),
                "icd10cm-2026-10-01": str(fy2027_catalog),
            }
        )
    )
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "icd10_mcp.cli",
            "lookup",
            "A00.1",
            "--date",
            "2026-10-01",
            "--catalog-config",
            str(config),
        ],
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert result.returncode == 0, result.stderr
    output = json.loads(result.stdout)
    assert output["release"]["id"] == "icd10cm-2026-10-01"
    assert output["candidates"][0]["code"] == "A00.1"


def test_wrong_catalog_never_falls_back_to_another_release(catalog_path):
    from icd10_mcp.catalog import CatalogSet

    service = ICDService(
        CatalogSet(
            {
                "icd10cm-2026-04-01": catalog_path,
                "icd10cm-2026-10-01": catalog_path,
            }
        )
    )
    assert service.search("A00.1", "2026-10-01")["status"] == "catalog_unavailable"
    assert service.search("A00.1", "2026-09-30")["status"] == "candidates"


@pytest.mark.corpus
def test_fy2027_import_and_smoke_cli(tmp_path, pytestconfig):
    directory = pytestconfig.getoption("--fy2027-downloads")
    if directory is None:
        pytest.skip("Requires --fy2027-downloads PATH")
    path = tmp_path / "cli-fy2027.sqlite3"
    for arguments in [
        ["import", "--downloads", directory],
        ["smoke"],
    ]:
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "icd10_mcp.cli",
                *arguments,
                "--database",
                str(path),
                "--release",
                "icd10cm-2026-10-01",
            ],
            capture_output=True,
            text=True,
            timeout=40,
        )
        assert result.returncode == 0, result.stderr
        output = json.loads(result.stdout)
        assert output["release"]["id"] == "icd10cm-2026-10-01"
        assert output["counts"]["assignable_codes"] == 74879
    assert output["status"] == "passed"


@pytest.mark.corpus
def test_complete_fy2027_import_and_public_lookup(tmp_path, pytestconfig):
    directory = pytestconfig.getoption("--fy2027-downloads")
    if directory is None:
        pytest.skip("Requires --fy2027-downloads PATH")
    path = tmp_path / "fy2027.sqlite3"
    metadata = import_corpus(Path(directory), path, release_id="icd10cm-2026-10-01")
    assert metadata["counts"]["assignable_codes"] == 74879
    assert metadata["counts"]["headers"] == 23524
    service = ICDService(Catalog(path, release_id="icd10cm-2026-10-01"))
    result = service.search("E11.9", "2026-10-01", limit=1)
    assert result["release"] == {
        "id": "icd10cm-2026-10-01",
        "system": "ICD-10-CM",
        "fiscal_year": 2027,
        "effective_from": "2026-10-01",
        "effective_through": "2027-09-30",
    }
    assert [item["code"] for item in result["candidates"]] == ["E11.9"]
    assert result["candidates"][0]["release"] == result["release"]
    assert result["catalog_scope"] == "full_cdc_corpus"
    assert (
        next(
            source["archive_sha256"]
            for source in result["source_manifest"]
            if source["member"].endswith("/icd10cm-codes-2027.txt")
        )
        == "93e3ad6004badf470c55bfe679b748ae88fd9b2b421851e409eec382c7713b9a"
    )
    assert service.search("E11.9", "2027-09-30")["status"] == "candidates"
    assert service.search("E11.9", "2026-09-30")["status"] == "release_unavailable"


@pytest.mark.corpus
@pytest.mark.parametrize("truncation", ["empty-index", "removed-tabular-diagnosis"])
def test_full_fy2027_import_rejects_well_formed_partial_xml_atomically(
    tmp_path,
    pytestconfig,
    truncation,
):
    directory = pytestconfig.getoption("--fy2027-downloads")
    if directory is None:
        pytest.skip("Requires --fy2027-downloads PATH")
    downloads = tmp_path / "partial-sources"
    downloads.mkdir()
    source = Path(directory)
    text_archive = "icd10cm-code-descriptions-2027.zip"
    xml_archive = "icd10cm-table-and-index-2027.zip"
    (downloads / text_archive).symlink_to((source / text_archive).resolve())
    names = [
        "icd10cm-table-and-index-2027/icd10cm-tabular_-2027.xml",
        *[
            f"icd10cm-table-and-index-2027/icd10cm-{name}-2027.xml"
            for name in ["index", "eindex", "drug", "neoplasm"]
        ],
    ]
    with (
        ZipFile(source / xml_archive) as original,
        ZipFile(downloads / xml_archive, "w") as changed,
    ):
        for name in names:
            data = original.read(name)
            if truncation == "empty-index" and name.endswith("/icd10cm-index-2027.xml"):
                data = b"<ICD10CM.index><version>2027</version></ICD10CM.index>"
            if truncation == "removed-tabular-diagnosis" and name.endswith(
                "/icd10cm-tabular_-2027.xml"
            ):
                root = ET.fromstring(data)
                removed = 0
                for parent in root.iter():
                    for child in list(parent):
                        if child.tag == "diag" and child.findtext("name") == "J18.9":
                            parent.remove(child)
                            removed += 1
                assert removed == 1
                data = tostring(root, encoding="utf-8")
            changed.writestr(name, data)
    destination = tmp_path / "partial.sqlite3"
    with pytest.raises(ValueError, match="Source snapshot mismatch"):
        import_corpus(downloads, destination, release_id="icd10cm-2026-10-01")
    assert not destination.exists()
    assert not list(tmp_path.glob(".catalog-*"))
