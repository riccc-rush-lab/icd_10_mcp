from zipfile import ZipFile

import pytest

from icd10_mcp.importer import (
    CODES,
    INDEXES,
    ORDER,
    TABULAR,
    TEXT_ARCHIVE,
    XML_ARCHIVE,
    import_corpus,
)


@pytest.fixture
def source_archives(tmp_path, source_files):
    downloads = tmp_path / "downloads"
    downloads.mkdir()
    for archive, members in [
        (TEXT_ARCHIVE, [ORDER, CODES]),
        (XML_ARCHIVE, [TABULAR, *INDEXES.values()]),
    ]:
        with ZipFile(downloads / archive, "w") as zipped:
            for member in members:
                zipped.writestr(member, source_files[member])
    return downloads


def test_public_import_rejects_missing_complete_member_without_publication(tmp_path):
    downloads = tmp_path / "downloads"
    downloads.mkdir()
    with ZipFile(downloads / TEXT_ARCHIVE, "w") as zipped:
        zipped.writestr("2027-addenda.txt", "not a complete corpus")
    destination = tmp_path / "catalog.sqlite3"
    with pytest.raises(ValueError, match="Missing or ambiguous required member"):
        import_corpus(downloads, destination)
    assert not destination.exists()


def test_public_import_rejects_incomplete_release_atomically(tmp_path, source_archives):
    destination = tmp_path / "catalog.sqlite3"
    with pytest.raises(ValueError, match="Incomplete corpus"):
        import_corpus(source_archives, destination)
    assert not destination.exists()
    assert not list(tmp_path.glob(".catalog-*"))


def test_public_import_does_not_replace_existing_destination(tmp_path, source_archives):
    destination = tmp_path / "catalog.sqlite3"
    destination.write_bytes(b"existing local data")
    with pytest.raises(FileExistsError):
        import_corpus(source_archives, destination)
    assert destination.read_bytes() == b"existing local data"
