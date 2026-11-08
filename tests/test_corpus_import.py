from zipfile import ZipFile

import pytest

from icd10_mcp.catalog import Catalog
from icd10_mcp.importer import CODES, INDEXES, TABULAR, TEXT_ARCHIVE, XML_ARCHIVE, import_corpus
from icd10_mcp.service import ICDService


@pytest.mark.corpus
def test_public_full_corpus_import_supports_lookup_and_provenance(tmp_path, cdc_downloads):
    destination = tmp_path / "catalog.sqlite3"
    metadata = import_corpus(cdc_downloads, destination)
    assert metadata["counts"]["assignable_codes"] == 74719
    assert metadata["counts"]["headers"] == 23467
    service = ICDService(Catalog(destination))
    result = service.search("E11.9", "2026-04-01", limit=1)
    assert [item["code"] for item in result["candidates"]] == ["E11.9"]
    assert result["catalog_scope"] == "full_cdc_corpus"
    assert result["release"]["effective_through"] == "2026-09-30"
    code_source = next(source for source in result["source_manifest"] if source["member"] == CODES)
    # Independently established with /usr/bin/shasum -a 256, not production digest().
    assert code_source["sha256"] == (
        "a7e2a77e4627ed55c8afe2b8a7ae22efcbab6b6b162d96cf145213772c1246ba"
    )
    for query, expected in [("Abnormity", "Q89.9"), ("Abscess mastoid", "H70.00")]:
        lookup = service.search(query, "2026-04-01", limit=1)
        assert [item["code"] for item in lookup["candidates"]] == [expected]


@pytest.mark.corpus
def test_public_full_corpus_rejects_wrong_xml_release_atomically(tmp_path, cdc_downloads):
    downloads = tmp_path / "wrong-release"
    downloads.mkdir()
    (downloads / TEXT_ARCHIVE).symlink_to(cdc_downloads / TEXT_ARCHIVE)
    with ZipFile(cdc_downloads / XML_ARCHIVE) as original:
        with ZipFile(downloads / XML_ARCHIVE, "w") as changed:
            for member in [TABULAR, *INDEXES.values()]:
                data = original.read(member)
                if member == TABULAR:
                    data = data.replace(b"<version>2026</version>", b"<version>2027</version>", 1)
                changed.writestr(member, data)
    destination = tmp_path / "catalog.sqlite3"
    with pytest.raises(ValueError, match="Unexpected XML release"):
        import_corpus(downloads, destination)
    assert not destination.exists()
    assert not list(tmp_path.glob(".catalog-*"))
