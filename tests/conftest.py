"""Small, hand-authored synthetic catalog; no CDC corpus or patient fixtures."""

from __future__ import annotations

from itertools import count
from pathlib import Path

import pytest

from icd10_mcp.catalog import Catalog
from icd10_mcp.importer import (
    CODES,
    INDEXES,
    ORDER,
    TABULAR,
    TEXT_ARCHIVE,
    XML_ARCHIVE,
    build_catalog,
    digest,
)
from icd10_mcp.service import ICDService

ROWS = [
    ("A00", 0, "Synthetic infection category"),
    ("A001", 1, "Synthetic infection"),
    ("B00", 0, "Synthetic underlying category"),
    ("B001", 1, "Synthetic underlying condition"),
    ("E11", 0, "Synthetic diabetes category"),
    ("E119", 1, "Synthetic type 2 diabetes without complications"),
    ("G00", 0, "Synthetic manifestation category"),
    ("G001", 1, "Synthetic manifestation"),
    ("J18", 0, "Synthetic pneumonia category"),
    ("J189", 1, "Synthetic pneumonia, unspecified"),
    ("M00", 0, "Synthetic pain category"),
    ("M001", 1, "Right synthetic wrist pain"),
    ("QA0", 0, "Synthetic alphanumeric category"),
    ("QA00101", 1, "Synthetic gene related condition"),
    ("T36", 0, "Synthetic injury category"),
    ("T360", 0, "Synthetic injury"),
    ("T360X1A", 1, "Synthetic injury, initial encounter"),
    ("T360X1D", 1, "Synthetic injury, subsequent encounter"),
    ("T360X1S", 1, "Synthetic injury, sequela"),
    ("Z00", 0, "Synthetic exclusion category"),
    ("Z001", 1, "Synthetic excluded condition"),
    ("Z002", 1, "Synthetic coexistence condition"),
]
EXPECTED = (sum(row[1] for row in ROWS), sum(not row[1] for row in ROWS))

TABULAR_XML = """<ICD10CM.tabular><version>2026</version>
<introduction><introSection><title>Test instruction</title>
<instruction><note>Synthetic only</note></instruction></introSection></introduction>
<chapter><name>1</name><desc>Synthetic chapter</desc>
<notes><note>Inherited chapter instruction</note></notes>
<section id="A00-Z99"><desc>Synthetic section</desc>
<includes><note>Inherited section instruction</note></includes>
<diag><name>A00</name><desc>Synthetic infection category</desc>
 <excludes1><note>Synthetic excluded condition (Z00.1)</note></excludes1>
 <excludes2><note>Synthetic coexistence condition (Z00.2)</note></excludes2>
 <diag><name>A00.1</name><desc>Synthetic infection</desc>
  <inclusionTerm><note>Test infection</note></inclusionTerm>
 </diag>
</diag>
<diag><name>B00</name><desc>Synthetic underlying category</desc>
 <useAdditionalCode><note>manifestation (G00.1)</note></useAdditionalCode>
 <diag><name>B00.1</name><desc>Synthetic underlying condition</desc></diag>
</diag>
<diag><name>E11</name><desc>Synthetic diabetes category</desc>
 <diag><name>E11.9</name><desc>Synthetic type 2 diabetes without complications</desc></diag>
</diag>
<diag><name>G00</name><desc>Synthetic manifestation category</desc>
 <codeFirst><note>underlying condition (B00.1)</note></codeFirst>
 <codeAlso><note>if applicable, excluded condition (Z00.1)</note></codeAlso>
 <diag><name>G00.1</name><desc>Synthetic manifestation</desc></diag>
</diag>
<diag><name>J18</name><desc>Synthetic pneumonia category</desc>
 <diag><name>J18.9</name><desc>Synthetic pneumonia, unspecified</desc></diag>
</diag>
<diag><name>M00</name><desc>Synthetic pain category</desc>
 <diag><name>M00.1</name><desc>Right synthetic wrist pain</desc>
  <inclusionTerm><note>Wrist syndrome</note></inclusionTerm>
 </diag>
</diag>
<diag><name>QA0</name><desc>Synthetic alphanumeric category</desc>
 <diag><name>QA0.0101</name><desc>Synthetic gene related condition</desc></diag>
</diag>
<diag><name>T36</name><desc>Synthetic injury category</desc>
 <sevenChrNote><note>Assign a seventh character; use placeholder X.</note></sevenChrNote>
 <sevenChrDef><extension char="A">initial encounter</extension>
 <extension char="D">subsequent encounter</extension><extension char="S">sequela</extension>
 </sevenChrDef>
 <diag><name>T36.0</name><desc>Synthetic injury</desc></diag>
</diag>
<diag><name>Z00</name><desc>Synthetic exclusion category</desc>
 <diag><name>Z00.1</name><desc>Synthetic excluded condition</desc></diag>
 <diag><name>Z00.2</name><desc>Synthetic coexistence condition</desc></diag>
</diag>
</section></chapter></ICD10CM.tabular>"""

DISEASES_XML = """<ICD10CM.index><version>2026</version><letter><title>T</title>
<mainTerm><title>Test infection<nemod>(synthetic)</nemod></title><code>A00.1</code></mainTerm>
<mainTerm><title>Pneumonia<nemod>(synthetic) (test) (fixture) (not real)</nemod></title>
 <code>J18.9</code></mainTerm>
<mainTerm><title>Diabetes</title><term level="1"><title>type 2</title><code>E11.9</code></term>
</mainTerm>
<mainTerm><title>Infection alias</title><see>Test infection</see></mainTerm>
<mainTerm><title>Loop one</title><see>Loop two</see></mainTerm>
<mainTerm><title>Loop two</title><see>Loop one</see></mainTerm>
<mainTerm><title>Missing alias</title><see>Missing target</see></mainTerm>
<mainTerm><title>Test injury</title><code>T36.0-</code><subcat>T36.0</subcat></mainTerm>
<mainTerm><title>Synthetic manifestation</title><manif>G00.1</manif></mainTerm>
</letter></ICD10CM.index>"""


@pytest.fixture
def source_files():
    files = {
        CODES: "".join(f"{code:<8}{desc}\n" for code, flag, desc in ROWS if flag).encode(),
        ORDER: "".join(
            f"{n:05d} {code:<7} {flag} {desc[:60]:<60} {desc}\n"
            for n, (code, flag, desc) in enumerate(ROWS, 1)
        ).encode(),
        TABULAR: TABULAR_XML.encode(),
        INDEXES["diseases"]: DISEASES_XML.encode(),
        INDEXES["external_causes"]: b"""<ICD10CM.index><version>2026</version>
        <letter><title>T</title><mainTerm><title>Test external cause</title>
        <code>T36.0</code></mainTerm></letter></ICD10CM.index>""",
        INDEXES["drugs"]: b"""<ICD10CM.index><version>2026</version>
        <indexHeading><head col="2">Accidental poisoning</head></indexHeading>
        <letter><title>T</title><mainTerm><title>Test drug</title>
        <cell col="2">T36.0</cell></mainTerm></letter></ICD10CM.index>""",
        INDEXES["neoplasms"]: b"""<ICD10CM.index><version>2026</version>
        <indexHeading><head col="2">Benign</head></indexHeading>
        <letter><title>T</title><mainTerm><title>Test neoplasm</title>
        <cell col="2">Z00.1</cell></mainTerm></letter></ICD10CM.index>""",
    }
    return files


@pytest.fixture
def catalog_path(tmp_path: Path, source_files):
    path = tmp_path / "catalog.sqlite3"
    provenance = [
        {"member": name, "sha256": digest(data), "bytes": len(data)}
        for name, data in source_files.items()
    ]
    build_catalog(source_files, provenance, path, expected_counts=EXPECTED)
    return path


@pytest.fixture
def service(catalog_path):
    return ICDService(Catalog(catalog_path))


@pytest.fixture
def service_with_index(tmp_path, source_files):
    sequence = count()

    def create(entries):
        files = {
            **source_files,
            INDEXES["diseases"]: (
                "<ICD10CM.index><version>2026</version><letter><title>T</title>"
                + entries
                + "</letter></ICD10CM.index>"
            ).encode(),
        }
        path = tmp_path / f"lookup-{next(sequence)}.sqlite3"
        provenance = [
            {"member": name, "sha256": digest(data), "bytes": len(data)}
            for name, data in files.items()
        ]
        build_catalog(files, provenance, path, expected_counts=EXPECTED)
        return ICDService(Catalog(path))

    return create


def pytest_addoption(parser):
    parser.addoption(
        "--cdc-downloads", help="Enable full-corpus tests using this archive directory."
    )
    parser.addoption("--fy2027-downloads", help="Enable complete FY2027 archive integration.")
    parser.addoption("--openmed-models", help="Opt in to staged real OpenMed model checks.")
    parser.addoption("--openmed-python", help="Python executable in the isolated OpenMed runtime.")


@pytest.fixture(scope="session")
def cdc_downloads(pytestconfig):
    value = pytestconfig.getoption("--cdc-downloads")
    if value is None:
        pytest.skip("Full-corpus import test requires --cdc-downloads PATH.")
    path = Path(value).expanduser().resolve()
    for archive in [TEXT_ARCHIVE, XML_ARCHIVE]:
        if not (path / archive).is_file():
            pytest.fail(f"Requested CDC corpus is missing {archive}")
    return path
