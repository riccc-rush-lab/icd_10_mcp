"""Atomic import of complete, explicitly profiled CDC releases, never addenda."""

from __future__ import annotations

import hashlib
import json
import os
import re
import sqlite3
import tempfile
from contextlib import closing
from pathlib import Path
from xml.etree.ElementTree import tostring
from zipfile import ZipFile

from defusedxml import ElementTree as ET

from .catalog import SCHEMA_VERSION, compact_code
from .releases import APRIL_ID, get_profile

TEXT_ARCHIVE = "icd10cm-table-and-index-April-1-2026.zip"
XML_ARCHIVE = "icd10cm-April-1-2026-XML.zip"
ORDER = "icd10cm-order-April-1-2026.txt"
CODES = "icd10cm-codes-April-1-2026.txt"
TABULAR = "icd10c-tabular-April-1-2026.xml"
INDEXES = {
    "diseases": "icd10cm-index-April-1-2026-XML.xml",
    "external_causes": "icd10cm-eindex-April-1-2026-XML.xml",
    "drugs": "icd10cm-drug-April-1-2026-XML.xml",
    "neoplasms": "icd10cm-neoplasm-April-1-2026-XML.xml",
}
INSTRUCTION_TAGS = {
    "includes",
    "inclusionTerm",
    "excludes1",
    "excludes2",
    "codeFirst",
    "codeAlso",
    "useAdditionalCode",
    "sevenChrNote",
    "sevenChrDef",
    "notes",
    "visualImpairment",
}
SCHEMA = """
PRAGMA foreign_keys=ON;
CREATE TABLE metadata(value TEXT NOT NULL);
CREATE TABLE nodes(
 id INTEGER PRIMARY KEY, parent_id INTEGER REFERENCES nodes(id), kind TEXT NOT NULL,
 name TEXT NOT NULL, description TEXT NOT NULL, source TEXT NOT NULL, source_path TEXT NOT NULL
);
CREATE TABLE codes(
 code TEXT PRIMARY KEY, assignable INTEGER NOT NULL, description TEXT NOT NULL,
 short_description TEXT NOT NULL, order_number INTEGER NOT NULL,
 node_id INTEGER REFERENCES nodes(id), order_source TEXT NOT NULL, order_line INTEGER NOT NULL,
 codes_source TEXT, codes_line INTEGER
);
CREATE TABLE instructions(
 id INTEGER PRIMARY KEY, node_id INTEGER NOT NULL REFERENCES nodes(id), kind TEXT NOT NULL,
 text TEXT NOT NULL, data TEXT NOT NULL, source TEXT NOT NULL, source_path TEXT NOT NULL
);
CREATE TABLE index_entries(
 id INTEGER PRIMARY KEY, parent_id INTEGER REFERENCES index_entries(id), kind TEXT NOT NULL,
 title TEXT NOT NULL, label TEXT NOT NULL, path TEXT NOT NULL,
 source TEXT NOT NULL, source_path TEXT NOT NULL
);
CREATE TABLE index_refs(
 id INTEGER PRIMARY KEY, entry_id INTEGER NOT NULL REFERENCES index_entries(id),
 kind TEXT NOT NULL, value TEXT NOT NULL, column_label TEXT
);
CREATE TABLE documents(
 id INTEGER PRIMARY KEY, code TEXT, entry_id INTEGER REFERENCES index_entries(id),
 kind TEXT NOT NULL, label TEXT NOT NULL, body TEXT NOT NULL,
 source TEXT NOT NULL, source_path TEXT NOT NULL
);
CREATE VIRTUAL TABLE search USING fts5(body, content='documents', content_rowid='id');
CREATE VIRTUAL TABLE labels USING fts5(label, content='documents', content_rowid='id');
CREATE INDEX instruction_node ON instructions(node_id);
CREATE INDEX refs_entry ON index_refs(entry_id);
CREATE INDEX refs_code ON index_refs(replace(upper(value),'.',''));
CREATE INDEX docs_code ON documents(code);
CREATE INDEX docs_label ON documents(lower(label));
CREATE INDEX nodes_parent ON nodes(parent_id);
"""


def text(element) -> str:
    return " ".join(" ".join(element.itertext()).split()) if element is not None else ""


def title_without_nemod(element) -> str:
    if element is None:
        return ""
    return " ".join(((element.text or "") + "".join(child.tail or "" for child in element)).split())


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def read_sources(
    downloads: Path, *, release_id: str = APRIL_ID
) -> tuple[dict[str, bytes], list[dict]]:
    profile = get_profile(release_id)
    files, provenance = {}, []
    for archive, members in [
        (profile["text_archive"], [profile["order"], profile["codes"]]),
        (profile["xml_archive"], [profile["tabular"], *profile["indexes"].values()]),
    ]:
        path = downloads / archive
        with path.open("rb") as stream:
            archive_hash = hashlib.file_digest(stream, "sha256").hexdigest()
        with ZipFile(path) as zipped:
            for name in members:
                if zipped.namelist().count(name) != 1:
                    raise ValueError(f"Missing or ambiguous required member: {name}")
                if zipped.getinfo(name).file_size > 100_000_000:
                    raise ValueError(f"Oversized member: {name}")
                data = zipped.read(name)
                files[name] = data
                provenance.append(
                    {
                        "archive": archive,
                        "archive_sha256": archive_hash,
                        "member": name,
                        "sha256": digest(data),
                        "bytes": len(data),
                    }
                )
    return files, provenance


def add_document(db, code, entry_id, kind, label, body, source, source_path):
    db.execute(
        "INSERT INTO documents VALUES(NULL,?,?,?,?,?,?,?)",
        (code, entry_id, kind, label, body, source, source_path),
    )


def load_text(db, files, expected_counts, profile):
    codes_source, order_source = profile["codes"], profile["order"]
    descriptions = {}
    for number, line in enumerate(files[codes_source].decode("utf-8-sig").splitlines(), 1):
        if not line.strip():
            continue
        code, description = line.split(maxsplit=1)
        if code in descriptions or not re.fullmatch(r"(?![A-Z]{3})[A-Z][A-Z0-9]{2,6}", code):
            raise ValueError(f"Invalid/duplicate complete-code row {number}")
        descriptions[code] = (description.strip(), number)
    assignable_count = header_count = 0
    for number, line in enumerate(files[order_source].decode("utf-8-sig").splitlines(), 1):
        if not line.strip():
            continue
        order, code, flag = int(line[:5]), line[6:13].strip(), line[14:15]
        short, description = line[16:76].strip(), line[77:].strip()
        if flag not in {"0", "1"} or not description:
            raise ValueError(f"Invalid order row {number}")
        assignable = int(flag)
        listed = descriptions.get(code)
        if assignable and (listed is None or listed[0] != description):
            raise ValueError(f"Code/order disagreement: {code}")
        if not assignable and listed is not None:
            raise ValueError(f"Header incorrectly in complete-code file: {code}")
        assignable_count += assignable
        header_count += not assignable
        db.execute(
            "INSERT INTO codes VALUES(?,?,?,?,?,NULL,?,?,?,?)",
            (
                code,
                assignable,
                description,
                short,
                order,
                order_source,
                number,
                codes_source if listed else None,
                listed[1] if listed else None,
            ),
        )
        add_document(
            db, code, None, "description", description, description, order_source, f"line:{number}"
        )
    counts = (assignable_count, header_count)
    if counts != expected_counts or len(descriptions) != assignable_count:
        raise ValueError(f"Incomplete corpus: codes/headers {counts}, expected {expected_counts}")
    return {"assignable_codes": assignable_count, "headers": header_count}


def parse_xml(files, name, expected_root, profile):
    root = ET.fromstring(files[name])
    if root.tag != expected_root or root.findtext("version") != str(
        profile["release"]["fiscal_year"]
    ):
        raise ValueError(f"Unexpected XML release or root: {name}")
    return root


def load_tabular(db, files, profile):
    tabular = profile["tabular"]
    root = parse_xml(files, tabular, "ICD10CM.tabular", profile)
    node_for_code = {}
    intro = [
        {"title": text(section.find("title")), "text": text(section.find("instruction"))}
        for section in root.findall("./introduction/introSection")
    ]

    def visit(element, parent_id, path):
        name = element.findtext("name") or element.get("id") or ""
        if not name:
            raise ValueError(f"Unnamed Tabular node: {path}")
        cursor = db.execute(
            "INSERT INTO nodes VALUES(NULL,?,?,?,?,?,?)",
            (parent_id, element.tag, name, text(element.find("desc")), tabular, path),
        )
        node_id = cursor.lastrowid
        if element.tag == "diag":
            code = compact_code(name)
            if code in node_for_code:
                raise ValueError(f"Duplicate Tabular diagnosis: {name}")
            node_for_code[code] = node_id
        for tag in sorted(INSTRUCTION_TAGS):
            for i, instruction in enumerate(element.findall(tag), 1):
                data = {
                    "group_path": f"{path}/{tag}[{i}]",
                    "xml": tostring(instruction, encoding="unicode"),
                }
                if tag == "sevenChrDef":
                    data["extensions"] = {
                        ext.get("char"): text(ext) for ext in instruction.findall("extension")
                    }
                notes = instruction.findall("note")
                for j, note in enumerate(notes or [instruction], 1):
                    instruction_path = f"{path}/{tag}[{i}]/note[{j}]"
                    db.execute(
                        "INSERT INTO instructions VALUES(NULL,?,?,?,?,?,?)",
                        (node_id, tag, text(note), json.dumps(data), tabular, instruction_path),
                    )
                    if tag == "inclusionTerm" and element.tag == "diag":
                        add_document(
                            db,
                            compact_code(name),
                            None,
                            "inclusion",
                            text(note),
                            text(note),
                            tabular,
                            instruction_path,
                        )
        for tag in ["chapter", "section", "diag"]:
            for i, child in enumerate(element.findall(tag), 1):
                visit(child, node_id, f"{path}/{tag}[{i}]")

    for i, chapter in enumerate(root.findall("chapter"), 1):
        visit(chapter, None, f"/ICD10CM.tabular/chapter[{i}]")
    for row in db.execute("SELECT code FROM codes").fetchall():
        code = row[0]
        # Seventh-character expansions appear in order text, not as separate XML diagnoses.
        ancestor = next(
            (node_for_code[code[:n]] for n in range(len(code), 2, -1) if code[:n] in node_for_code),
            None,
        )
        if ancestor is None:
            raise ValueError(f"No Tabular ancestor for {code}")
        db.execute("UPDATE codes SET node_id=? WHERE code=?", (ancestor, code))
    return intro


def load_indexes(db, files, profile):
    for kind, name in profile["indexes"].items():
        root = parse_xml(files, name, "ICD10CM.index", profile)
        headings = {h.get("col"): text(h) for h in root.findall("./indexHeading/head")}

        def visit(
            element,
            parent_id,
            parents,
            labels,
            source_path,
            *,
            kind=kind,
            name=name,
            headings=headings,
        ):
            title = text(element.find("title"))
            label = title_without_nemod(element.find("title"))
            path = " > ".join([*parents, title])
            match_label = " ".join([*labels, label])
            entry_id = db.execute(
                "INSERT INTO index_entries VALUES(NULL,?,?,?,?,?,?,?)",
                (parent_id, kind, title, label, path, name, source_path),
            ).lastrowid
            for child in element:
                if child.tag not in {"title", "term"}:
                    db.execute(
                        "INSERT INTO index_refs VALUES(NULL,?,?,?,?)",
                        (entry_id, child.tag, text(child), headings.get(child.get("col"))),
                    )
            add_document(db, None, entry_id, "index", match_label, path, name, source_path)
            for i, child in enumerate(element.findall("term"), 1):
                visit(
                    child, entry_id, [*parents, title], [*labels, label], f"{source_path}/term[{i}]"
                )

        for letter_n, letter in enumerate(root.findall("letter"), 1):
            for term_n, term in enumerate(letter.findall("mainTerm"), 1):
                visit(term, None, [], [], f"/ICD10CM.index/letter[{letter_n}]/mainTerm[{term_n}]")


def build_catalog(
    files: dict[str, bytes],
    provenance: list[dict],
    destination: Path,
    *,
    expected_counts: tuple[int, int] | None = None,
    release_id: str = APRIL_ID,
) -> dict:
    """Atomic build; expected_counts override is for synthetic test fixtures only."""
    profile = get_profile(release_id)
    synthetic = expected_counts is not None
    expected_counts = expected_counts if synthetic else profile["counts"]
    destination = destination.expanduser().resolve()
    if destination.exists():
        raise FileExistsError("Catalog exists; build to a new path and verify before switching.")
    destination.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=".catalog-", suffix=".sqlite3", dir=destination.parent)
    os.close(fd)
    try:
        with closing(sqlite3.connect(temporary)) as db, db:
            db.executescript(SCHEMA)
            counts = load_text(db, files, expected_counts, profile)
            intro = load_tabular(db, files, profile)
            load_indexes(db, files, profile)
            if not synthetic:
                members = {
                    "codes": profile["codes"],
                    "order": profile["order"],
                    "tabular": profile["tabular"],
                    **profile["indexes"],
                }
                for role, name in members.items():
                    if digest(files[name]) != profile["member_sha256"][role]:
                        raise ValueError(f"Source snapshot mismatch: {name}")
            db.execute("INSERT INTO search(search) VALUES('rebuild')")
            db.execute("INSERT INTO labels(labels) VALUES('rebuild')")
            for table in ["nodes", "instructions", "index_entries", "index_refs", "documents"]:
                counts[table] = db.execute(f"SELECT count(*) FROM {table}").fetchone()[0]
            metadata = {
                "schema_version": SCHEMA_VERSION,
                "release": profile["release"],
                "sources": provenance,
                "counts": counts,
                "tabular_introduction": intro,
                "scope": "synthetic" if synthetic else "full_cdc_corpus",
            }
            db.execute("INSERT INTO metadata VALUES(?)", (json.dumps(metadata, sort_keys=True),))
            if db.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
                raise ValueError("SQLite integrity check failed")
            if db.execute("PRAGMA foreign_key_check").fetchall():
                raise ValueError("Foreign-key check failed")
        # Hard link is atomic and cannot overwrite a destination created concurrently.
        os.link(temporary, destination)
        return metadata
    finally:
        Path(temporary).unlink(missing_ok=True)


def import_corpus(downloads: Path, destination: Path, *, release_id: str = APRIL_ID) -> dict:
    files, provenance = read_sources(downloads.expanduser().resolve(), release_id=release_id)
    return build_catalog(files, provenance, destination, release_id=release_id)
