import json
from hashlib import sha256
from zipfile import ZipFile

import pytest
from conftest import EXPECTED

from icd10_mcp.catalog import Catalog
from icd10_mcp.importer import (
    CODES,
    INDEXES,
    ORDER,
    TABULAR,
    TEXT_ARCHIVE,
    XML_ARCHIVE,
    build_catalog,
    read_sources,
)
from icd10_mcp.service import ICDService


def test_counts_provenance_and_intro(catalog_path):
    catalog = Catalog(catalog_path)
    with catalog.connect() as db:
        meta = json.loads(db.execute("SELECT value FROM metadata").fetchone()[0])
        assert meta["counts"]["assignable_codes"] == EXPECTED[0]
        assert meta["counts"]["headers"] == EXPECTED[1]
        assert meta["tabular_introduction"][0]["text"] == "Synthetic only"
        assert all(len(source["sha256"]) == 64 for source in meta["sources"])
        assert not db.execute("SELECT code FROM codes WHERE node_id IS NULL").fetchall()
        assert not db.execute("PRAGMA foreign_key_check").fetchall()
        assert {row[0] for row in db.execute("SELECT DISTINCT kind FROM index_entries")} == {
            "diseases",
            "external_causes",
            "drugs",
            "neoplasms",
        }


def test_catalog_is_read_only(catalog_path):
    import sqlite3

    with Catalog(catalog_path).connect() as db:
        with pytest.raises(sqlite3.OperationalError):
            db.execute("DELETE FROM codes")


def test_no_overwrite(catalog_path, source_files):
    before = catalog_path.read_bytes()
    with pytest.raises(FileExistsError):
        build_catalog(source_files, [], catalog_path, expected_counts=EXPECTED)
    assert catalog_path.read_bytes() == before


def test_incomplete_corpus_rejected_atomically(tmp_path, source_files):
    target = tmp_path / "catalog.sqlite3"
    with pytest.raises(ValueError, match="Incomplete corpus"):
        build_catalog(source_files, [], target)
    assert not target.exists()
    assert not list(tmp_path.glob(".catalog-*"))


def test_code_order_disagreement(tmp_path, source_files):
    source_files[CODES] = source_files[CODES].replace(b"Synthetic infection\n", b"Wrong title\n")
    with pytest.raises(ValueError, match="disagreement"):
        build_catalog(source_files, [], tmp_path / "bad.sqlite3", expected_counts=EXPECTED)


def test_wrong_xml_release_rejected(tmp_path, source_files):
    source_files[TABULAR] = source_files[TABULAR].replace(b"2026", b"2027")
    with pytest.raises(ValueError, match="Unexpected XML release"):
        build_catalog(source_files, [], tmp_path / "bad.sqlite3", expected_counts=EXPECTED)


def test_external_entities_rejected(tmp_path, source_files):
    from defusedxml.common import DefusedXmlException

    source_files[TABULAR] = (
        b'<!DOCTYPE x [<!ENTITY external SYSTEM "file:///nonexistent">]>'
        + source_files[TABULAR].replace(b"Synthetic chapter", b"&external;")
    )
    with pytest.raises(DefusedXmlException):
        build_catalog(source_files, [], tmp_path / "bad.sqlite3", expected_counts=EXPECTED)


def test_exact_members_only_no_2027_addendum(tmp_path, source_files):
    for archive, members in [
        (TEXT_ARCHIVE, [CODES, ORDER]),
        (XML_ARCHIVE, [TABULAR, *INDEXES.values()]),
    ]:
        with ZipFile(tmp_path / archive, "w") as zipped:
            for member in members:
                zipped.writestr(member, source_files[member])
            zipped.writestr("2027-addenda.xml", "<unexpected/>")
    (tmp_path / "2027-icd-10-cm-addendum.zip").write_bytes(b"ignored")
    files, manifest = read_sources(tmp_path)
    assert files == source_files
    assert len(manifest) == 7
    for source in manifest:
        assert source["sha256"] == sha256(source_files[source["member"]]).hexdigest()
        assert (
            source["archive_sha256"]
            == sha256((tmp_path / source["archive"]).read_bytes()).hexdigest()
        )
        assert "2027" not in source["member"]


def test_missing_complete_file_fails(tmp_path):
    with ZipFile(tmp_path / TEXT_ARCHIVE, "w") as zipped:
        zipped.writestr("2027-addenda.txt", "not a complete corpus")
    with pytest.raises(ValueError, match="Missing or ambiguous"):
        read_sources(tmp_path)


def test_missing_catalog_returns_structured_error(tmp_path):
    service = ICDService(Catalog(tmp_path / "missing.sqlite3"))
    assert service.search("A00.1", "2026-04-01")["status"] == "catalog_unavailable"
    assert service.search("A00.1", "2026-10-01")["status"] == "release_unavailable"
    assert not (tmp_path / "missing.sqlite3").exists()


def test_metadata_identity_mismatch_rejected(catalog_path):
    import sqlite3

    with sqlite3.connect(catalog_path) as db:
        db.execute("UPDATE metadata SET value=?", ('{"schema_version": 999}',))
    assert (
        ICDService(Catalog(catalog_path)).search("A001", "2026-04-01")["status"]
        == "catalog_unavailable"
    )


def test_instruction_group_and_xml_preserved(service):
    instructions = service.search("T36.0X1A", "2026-04-01")["candidates"][0]["instructions"]
    extension = next(i for i in instructions if i["kind"] == "sevenChrDef")
    assert extension["data"]["extensions"]["A"] == "initial encounter"
    assert '<extension char="A">' in extension["data"]["xml"]
    assert extension["data"]["group_path"].endswith("/sevenChrDef[1]")
