import json
import shutil
import sqlite3
from itertools import count

import pytest

from icd10_mcp.catalog import Catalog
from icd10_mcp.service import ICDService

DAY = "2026-04-01"


@pytest.fixture
def damaged_catalog(tmp_path, catalog_path):
    sequence = count()

    def create(transform, *, raw=False, missing_table=None):
        path = tmp_path / f"damaged-{next(sequence)}.sqlite3"
        shutil.copyfile(catalog_path, path)
        with sqlite3.connect(path) as db:
            metadata = json.loads(db.execute("SELECT value FROM metadata").fetchone()[0])
            if transform is None:
                db.execute("DELETE FROM metadata")
            else:
                value = transform(metadata)
                db.execute("UPDATE metadata SET value=?", (value if raw else json.dumps(value),))
            if missing_table:
                db.execute(f"DROP TABLE {missing_table}")
        return ICDService(Catalog(path))

    return create


def test_lookup_rejects_catalog_without_source_manifest(damaged_catalog):
    service = damaged_catalog(
        lambda metadata: {key: value for key, value in metadata.items() if key != "sources"}
    )
    result = service.search("zzzzzzzz", DAY)
    assert result["status"] == "catalog_unavailable"
    assert "candidates" not in result


@pytest.mark.parametrize(
    "entry",
    [
        None,
        {},
        {"member": "", "sha256": "a" * 64, "bytes": 1},
        {"member": "source", "sha256": "not-a-hash", "bytes": 1},
        {"member": "source", "sha256": "a" * 64, "bytes": -1},
        {"member": "source", "sha256": "a" * 64, "bytes": True},
    ],
)
def test_lookup_rejects_invalid_manifest_entry(damaged_catalog, entry):
    service = damaged_catalog(lambda metadata: {**metadata, "sources": [entry]})
    assert service.search("A00.1", DAY)["status"] == "catalog_unavailable"


@pytest.mark.parametrize(
    "transform,raw",
    [
        (lambda metadata: {key: value for key, value in metadata.items() if key != "scope"}, False),
        (lambda metadata: {**metadata, "scope": []}, False),
        (lambda metadata: {**metadata, "sources": []}, False),
        (lambda metadata: {**metadata, "sources": {}}, False),
        (lambda metadata: [], False),
        (lambda metadata: "{", True),
        (None, False),
    ],
)
def test_lookup_rejects_missing_or_malformed_metadata(damaged_catalog, transform, raw):
    service = damaged_catalog(transform, raw=raw)
    assert service.search("A00.1", DAY)["status"] == "catalog_unavailable"
    assert service.search("A00.1", "2026-10-01")["status"] == "release_unavailable"


@pytest.mark.parametrize(
    "table",
    [
        "codes",
        "nodes",
        "instructions",
        "index_entries",
        "index_refs",
        "documents",
        "labels",
        "search",
    ],
)
def test_lookup_rejects_incomplete_catalog_schema(damaged_catalog, table):
    service = damaged_catalog(lambda metadata: metadata, missing_table=table)
    assert service.search("A00.1", DAY)["status"] == "catalog_unavailable"


@pytest.mark.parametrize("table", ["search_idx", "labels_idx"])
def test_lookup_rejects_unusable_search_index(damaged_catalog, table):
    service = damaged_catalog(lambda metadata: metadata, missing_table=table)
    assert service.search("Pneumonia", DAY, limit=1)["status"] == "catalog_unavailable"
    assert service.search("Pneumonia", "2026-10-01")["status"] == "release_unavailable"


@pytest.mark.parametrize(
    "fields",
    [
        {"archive": ["invalid"], "archive_sha256": "not-a-hash"},
        {"archive": "source.zip"},
        {"archive_sha256": "a" * 64},
        {"archive": "source.zip", "archive_sha256": "not-a-hash"},
    ],
)
def test_lookup_rejects_malformed_archive_provenance(damaged_catalog, fields):
    service = damaged_catalog(
        lambda metadata: {
            **metadata,
            "sources": [{**metadata["sources"][0], **fields}, *metadata["sources"][1:]],
        }
    )
    assert service.search("Pneumonia", DAY)["status"] == "catalog_unavailable"
