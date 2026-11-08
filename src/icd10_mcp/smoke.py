"""Read-only full-corpus checks, with assertions that also run outside pytest."""

from __future__ import annotations

from datetime import date, timedelta

from .catalog import Catalog
from .releases import get_profile
from .service import ICDService


def smoke_check(catalog: Catalog) -> dict:
    day = catalog.release["effective_from"]
    expected_codes, expected_headers = get_profile(catalog.release["id"])["counts"]
    metadata, error = catalog.select_release(day)
    if error:
        raise ValueError(error["status"])
    if metadata["scope"] != "full_cdc_corpus":
        raise ValueError("Smoke check requires the full CDC corpus, not synthetic fixtures.")
    service = ICDService(catalog)
    checks = []

    def check(condition, name):
        if not condition:
            raise ValueError(f"Corpus smoke check failed: {name}")
        checks.append(name)

    with catalog.connect() as db:
        check(db.execute("PRAGMA integrity_check").fetchone()[0] == "ok", "sqlite_integrity")
        check(not db.execute("PRAGMA foreign_key_check").fetchall(), "foreign_keys")
        check(
            db.execute("SELECT count(*) FROM codes WHERE assignable=1").fetchone()[0]
            == expected_codes,
            f"{expected_codes}_assignable_codes",
        )
        check(
            db.execute("SELECT count(*) FROM codes WHERE assignable=0").fetchone()[0]
            == expected_headers,
            f"{expected_headers}_headers",
        )
        check(
            db.execute("SELECT count(*) FROM codes WHERE node_id IS NULL").fetchone()[0] == 0,
            "all_codes_have_tabular_ancestors",
        )
        check(
            db.execute("SELECT count(DISTINCT kind) FROM index_entries").fetchone()[0] == 4,
            "all_four_indexes",
        )
        check(len(metadata["sources"]) == 7, "seven_hashed_source_members")
        check(
            all(
                len(source["sha256"]) == 64 and len(source["archive_sha256"]) == 64
                for source in metadata["sources"]
            ),
            "source_hashes_present",
        )
        for kind in [
            "excludes1",
            "excludes2",
            "codeFirst",
            "useAdditionalCode",
            "sevenChrDef",
            "sevenChrNote",
            "inclusionTerm",
        ]:
            check(
                db.execute("SELECT count(*) FROM instructions WHERE kind=?", (kind,)).fetchone()[0]
                > 0,
                f"instructions_{kind}",
            )
    lookup = service.search("E11.9", day)
    check(lookup["candidates"][0]["code"] == "E11.9", "exact_code_lookup")
    check(lookup["candidates"][0]["is_assignable"], "leaf_assignable")
    header = service.search("E11", day)
    check(not header["candidates"][0]["is_assignable"], "header_not_assignable")
    check(bool(header["candidates"][0]["child_examples"]), "header_refinement")
    phrase = service.search("pneumonia", day)
    check(any(item["code"] == "J18.9" for item in phrase["candidates"]), "phrase_index_to_tabular")
    redirect = service.search("Abdominalgia", day)
    check(bool(redirect["candidates"]) and bool(redirect["index_matches"]), "see_cross_reference")
    injury = service.validate(["T36.0X1A", "T36.01A"], day)["results"]
    check(injury[0]["code_validity"]["status"] == "valid", "seventh_character_valid")
    check(injury[1]["code_validity"]["status"] == "invalid_code", "missing_placeholder_invalid")
    check(any(item["inherited"] for item in injury[0]["instructions"]), "inherited_instructions")
    note = "No pneumonia. History of cholera. Possible diabetes."
    excluded = service.suggest(note, day)
    check(not excluded["candidates"], "noncurrent_note_abstains")
    check(bool(excluded["excluded_mentions"]), "noncurrent_evidence_retained")
    for day in [
        (date.fromisoformat(catalog.release["effective_from"]) - timedelta(days=1)).isoformat(),
        (date.fromisoformat(catalog.release["effective_through"]) + timedelta(days=1)).isoformat(),
    ]:
        check(
            service.search("E11.9", day)["status"] == "release_unavailable",
            f"release_unavailable_{day}",
        )
    return {
        "status": "passed",
        "checks": checks,
        "counts": metadata["counts"],
        "release": metadata["release"],
    }
