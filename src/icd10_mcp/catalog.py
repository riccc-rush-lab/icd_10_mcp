"""Read-only catalog access and strict release selection, independent of MCP."""

from __future__ import annotations

import json
import re
import sqlite3
from contextlib import contextmanager
from datetime import date
from pathlib import Path
from typing import Any

from .releases import APRIL_ID, get_profile

RELEASE = {
    "id": "icd10cm-2026-04-01",
    "system": "ICD-10-CM",
    "fiscal_year": 2026,
    "effective_from": "2026-04-01",
    "effective_through": "2026-09-30",
}
SCHEMA_VERSION = 2
DISCLAIMER = (
    "Coder-review candidates only, not final assignments. Local prototype; "
    "not production- or PHI-ready. No claim submission or encounter-completeness guarantee."
)
CODE_PATTERN = re.compile(r"^(?![A-Z]{3})[A-Z][A-Z0-9]{2}(?:\.?[A-Z0-9]{1,4})?$")
CODE_LIKE_PATTERN = re.compile(r"^[A-Z](?:[0-9]|[A-Z][0-9]|\.)[A-Z0-9./_-]*$")


def compact_code(value: str) -> str:
    return value.strip().upper().replace(".", "")


def display_code(value: str) -> str:
    value = compact_code(value)
    return value[:3] + ("." + value[3:] if len(value) > 3 else "")


def words(value: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", value.lower())


def looks_like_code(value: str) -> bool:
    value = value.strip().upper()
    # Multi-letter words belong to phrase lookup; X runs can be code placeholders.
    suffixes = re.findall(r"[A-Z]+", value)[1:]
    return bool(CODE_LIKE_PATTERN.fullmatch(value)) and all(
        len(part) == 1 or re.fullmatch(r"X{1,3}[A-Z]?", part) for part in suffixes
    )


class Catalog:
    def __init__(self, path: Path | str, *, release_id: str = APRIL_ID):
        self.path = Path(path).expanduser().resolve()
        self.release = dict(get_profile(release_id)["release"])

    def for_date(self, service_date):
        metadata, error = self.select_release(service_date)
        return self, metadata, error

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.path.as_uri() + "?mode=ro", uri=True)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA query_only=ON")
        try:
            yield db
        finally:
            db.close()

    def select_release(self, service_date: str) -> tuple[dict[str, Any] | None, dict | None]:
        try:
            parsed = date.fromisoformat(service_date)
            if parsed.isoformat() != service_date:
                raise ValueError
        except (ValueError, TypeError):
            return None, {"status": "invalid_request", "message": "Use a YYYY-MM-DD service_date."}
        if not self.release["effective_from"] <= service_date <= self.release["effective_through"]:
            return None, {
                "status": "release_unavailable",
                "service_date": service_date,
                "available_releases": [dict(self.release)],
            }
        try:
            with self.connect() as db:
                metadata = json.loads(db.execute("SELECT value FROM metadata").fetchone()[0])
                for table, columns in {
                    "codes": "code,assignable,description,short_description,order_number,node_id,"
                    "order_source,order_line,codes_source,codes_line",
                    "nodes": "id,parent_id,kind,name,description,source,source_path",
                    "instructions": "id,node_id,kind,text,data,source,source_path",
                    "index_entries": "id,parent_id,kind,title,label,path,source,source_path",
                    "index_refs": "id,entry_id,kind,value,column_label",
                    "documents": "id,code,entry_id,kind,label,body,source,source_path",
                    "labels": "rowid,label,labels",
                    "search": "rowid,body,search",
                }.items():
                    db.execute(f"SELECT {columns} FROM {table} LIMIT 0")
                for table in ["labels", "search"]:
                    db.execute(
                        f"SELECT rowid FROM {table} WHERE {table} MATCH ? LIMIT 1",
                        ('"catalogreadinessprobe"',),
                    ).fetchone()
            if metadata["schema_version"] != SCHEMA_VERSION or metadata["release"] != self.release:
                raise ValueError("catalog identity mismatch")
            if not isinstance(metadata["sources"], list) or not metadata["sources"]:
                raise ValueError("missing source manifest")
            for source in metadata["sources"]:
                if not isinstance(source, dict):
                    raise ValueError("invalid source manifest entry")
                member, checksum, size = (
                    source.get("member"),
                    source.get("sha256"),
                    source.get("bytes"),
                )
                if (
                    not isinstance(member, str)
                    or not member.strip()
                    or not isinstance(checksum, str)
                    or not re.fullmatch(r"[0-9a-fA-F]{64}", checksum)
                    or type(size) is not int
                    or size < 0
                ):
                    raise ValueError("invalid source provenance")
                if metadata["scope"] == "full_cdc_corpus" or (
                    "archive" in source or "archive_sha256" in source
                ):
                    archive, archive_hash = source.get("archive"), source.get("archive_sha256")
                    if (
                        not isinstance(archive, str)
                        or not archive.strip()
                        or not isinstance(archive_hash, str)
                        or not re.fullmatch(r"[0-9a-fA-F]{64}", archive_hash)
                    ):
                        raise ValueError("invalid archive provenance")
            if metadata["scope"] not in {"full_cdc_corpus", "synthetic"}:
                raise ValueError("invalid catalog scope")
        except (sqlite3.Error, ValueError, KeyError, TypeError):
            return None, {
                "status": "catalog_unavailable",
                "message": "Import the configured complete release before using tools.",
            }
        return metadata, None

    @staticmethod
    def code(db: sqlite3.Connection, value: str) -> dict | None:
        row = db.execute("SELECT * FROM codes WHERE code=?", (compact_code(value),)).fetchone()
        return dict(row) if row else None

    @staticmethod
    def lineage(db: sqlite3.Connection, node_id: int | None) -> list[dict]:
        result = []
        while node_id is not None:
            row = db.execute("SELECT * FROM nodes WHERE id=?", (node_id,)).fetchone()
            if row is None:
                break
            item = dict(row)
            result.append(item)
            node_id = item["parent_id"]
        return result

    def instructions(self, db: sqlite3.Connection, row: dict) -> list[dict]:
        result = []
        for node in self.lineage(db, row["node_id"]):
            for instruction in db.execute(
                "SELECT * FROM instructions WHERE node_id=? ORDER BY id", (node["id"],)
            ):
                item = dict(instruction)
                item["origin"] = node["name"]
                item["inherited"] = compact_code(node["name"]) != row["code"]
                item["data"] = json.loads(item["data"])
                result.append(item)
        return result

    def identity(self, db: sqlite3.Connection, row: dict) -> dict:
        return {
            "code": display_code(row["code"]),
            "description": row["description"],
            "short_description": row["short_description"],
            "is_assignable": bool(row["assignable"]),
            "release": dict(self.release),
            "tabular_hierarchy": self.lineage(db, row["node_id"])[::-1],
            "instructions": self.instructions(db, row),
            "catalog_provenance": {
                "order_source": row["order_source"],
                "order_line": row["order_line"],
                "codes_source": row["codes_source"],
                "codes_line": row["codes_line"],
            },
        }


class CatalogSet:
    """Explicit path configuration; selecting a request never mutates a catalog."""

    def __init__(self, paths: dict[str, Path | str]):
        if not isinstance(paths, dict) or not paths:
            raise ValueError("Configure at least one release catalog")
        self.catalogs = {
            release_id: Catalog(path, release_id=release_id) for release_id, path in paths.items()
        }

    def for_date(self, service_date):
        try:
            parsed = date.fromisoformat(service_date)
            if parsed.isoformat() != service_date:
                raise ValueError
        except (ValueError, TypeError):
            return (
                None,
                None,
                {
                    "status": "invalid_request",
                    "message": "Use a YYYY-MM-DD service_date.",
                },
            )
        for catalog in self.catalogs.values():
            release = catalog.release
            if release["effective_from"] <= service_date <= release["effective_through"]:
                return catalog.for_date(service_date)
        return (
            None,
            None,
            {
                "status": "release_unavailable",
                "service_date": service_date,
                "available_releases": [dict(item.release) for item in self.catalogs.values()],
            },
        )


def configured_catalog(path: Path | str, config: Path | str | None = None, *, release_id=APRIL_ID):
    """Relative paths in a JSON release-to-file map resolve beside that config."""
    if config is None:
        return Catalog(path, release_id=release_id)
    config = Path(config).expanduser().resolve()
    paths = json.loads(config.read_text())
    if (
        not isinstance(paths, dict)
        or not paths
        or any(not isinstance(value, str) or not value.strip() for value in paths.values())
    ):
        raise ValueError("Catalog config must map release IDs to nonempty file paths")
    return CatalogSet(
        {key: config.parent / Path(value).expanduser() for key, value in paths.items()}
    )
