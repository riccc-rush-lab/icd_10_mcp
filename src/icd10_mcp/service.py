"""Application workflows, callable directly without MCP or any cloud dependency."""

from __future__ import annotations

from .catalog import (
    CODE_PATTERN,
    DISCLAIMER,
    Catalog,
    CatalogSet,
    compact_code,
    looks_like_code,
    words,
)
from .matching import clauses, evidence_for, resolve_document, retrieve
from .rules import documentation, set_findings, structural_check

MAX_TEXT = 20_000


class ICDService:
    def __init__(self, catalog: Catalog | CatalogSet):
        self.catalog = catalog

    def begin(self, service_date: str):
        catalog, metadata, error = self.catalog.for_date(service_date)
        if error:
            return None, None, {**error, "disclaimer": DISCLAIMER}
        return catalog, metadata, None

    @staticmethod
    def envelope(metadata, service_date):
        return {
            "release": metadata["release"],
            "service_date": service_date,
            "disclaimer": DISCLAIMER,
            "source_manifest": metadata["sources"],
            "catalog_scope": metadata["scope"],
        }

    @staticmethod
    def invalid(message):
        return {"status": "invalid_request", "message": message, "disclaimer": DISCLAIMER}

    def search(self, query: str, service_date: str, limit: int = 10) -> dict:
        catalog, metadata, error = self.begin(service_date)
        if error:
            return error
        if not query.strip() or len(query) > 500 or not 1 <= limit <= 25:
            return self.invalid("Supply a nonempty query (max 500 characters) and limit 1..25.")
        with catalog.connect() as db:
            candidates, index_matches = {}, []
            reference_issues = {}
            direct = CODE_PATTERN.fullmatch(query.strip().upper())
            if direct or looks_like_code(query):
                validity, row, instructions = structural_check(catalog, db, query)
                if row is None:
                    return {
                        **self.envelope(metadata, service_date),
                        "status": "needs_clarification"
                        if validity["status"] == "invalid_format"
                        else "abstain",
                        "candidates": [],
                        "index_matches": [],
                        "code_validity": validity,
                        "instructions": instructions,
                        "clarifications": [
                            "Verify the code, placeholders, and required characters."
                        ],
                    }
                docs = [
                    {
                        "code": row["code"],
                        "entry_id": None,
                        "kind": "code_input",
                        "label": query,
                        "source": "query",
                        "source_path": "",
                        "retrieval_score": 15,
                    }
                ]
            else:
                docs = retrieve(db, query)
                exact = [doc for doc in docs if words(doc["label"]) == words(query)]
                # Never replace an unresolved exact index entry with a loose, unrelated match.
                if exact:
                    docs = exact
            for doc in docs:
                resolved, entries = resolve_document(db, doc)
                for entry in entries:
                    for reference in entry.get("cross_reference_results", []):
                        if reference["status"] != "resolved":
                            key = (
                                entry["source"],
                                entry["source_path"],
                                reference["kind"],
                                reference["value"],
                                reference["status"],
                            )
                            reference_issues[key] = {
                                **reference,
                                "source": entry["source"],
                                "source_path": entry["source_path"],
                            }
                if entries and len(index_matches) < limit:
                    index_matches.extend(entries[: limit - len(index_matches)])
                for item in resolved:
                    row = item["row"]
                    if row["code"] in candidates:
                        continue
                    identity = catalog.identity(db, row)
                    children = (
                        [
                            {
                                "code": child["code"],
                                "description": child["description"],
                                "is_assignable": bool(child["assignable"]),
                            }
                            for child in db.execute(
                                """SELECT code,description,assignable FROM codes
                               WHERE code LIKE ? AND code<>? ORDER BY order_number LIMIT 12""",
                                (row["code"] + "%", row["code"]),
                            )
                        ]
                        if not row["assignable"]
                        else []
                    )
                    ev = evidence_for(query, doc["label"])
                    candidates[row["code"]] = {
                        **identity,
                        "retrieval_score": doc["retrieval_score"],
                        "matched_label": doc["label"],
                        "match_kind": doc["kind"],
                        "source_evidence": {
                            "source": doc["source"],
                            "source_path": doc["source_path"],
                        },
                        "evidence_spans": [ev] if ev else [],
                        "index_path": item["via"],
                        "child_examples": children,
                        "child_examples_truncated": bool(children and len(children) == 12),
                        "assessments": {
                            "code_validity": "valid"
                            if row["assignable"]
                            else "header_not_assignable",
                            "documentation_support": "not_assessed",
                            "completeness": "not_assessed",
                        },
                        "missing_details": (
                            []
                            if row["assignable"]
                            else ["Select a complete assignable descendant."]
                        ),
                    }
                if len(candidates) >= limit:
                    break
            return {
                **self.envelope(metadata, service_date),
                "status": "candidates"
                if candidates
                else "needs_clarification"
                if index_matches
                else "abstain",
                "candidates": list(candidates.values())[:limit],
                "index_matches": index_matches,
                "reference_issues": list(reference_issues.values()),
                "clarifications": []
                if candidates
                else [
                    "Use a more specific diagnosis, index term, or exact code; "
                    "review index references."
                ],
                "ranking": "Deterministic lexical ranking, not clinical confidence.",
            }

    def suggest(self, note: str, service_date: str, limit: int = 10) -> dict:
        catalog, metadata, error = self.begin(service_date)
        if error:
            return error
        if not note.strip() or len(note) > MAX_TEXT or not 1 <= limit <= 25:
            return self.invalid("Supply synthetic note text (1..20000 characters) and limit 1..25.")
        candidates, excluded, seen = {}, [], set()
        with catalog.connect() as db:
            for offset, clause in clauses(note):
                for doc in retrieve(db, clause):
                    evidence = evidence_for(clause, doc["label"], offset)
                    if evidence is None:
                        continue
                    key = (evidence["start"], evidence["end"], evidence["context"])
                    if evidence["context"] != "affirmed":
                        if key not in seen:
                            excluded.append({**evidence, "matched_label": doc["label"]})
                            seen.add(key)
                        continue
                    resolved, _ = resolve_document(db, doc)
                    # Table cells need column/intent information, not six simultaneous suggestions.
                    if any(
                        ref["kind"] == "cell"
                        for item in resolved
                        for entry in item["via"]
                        for ref in entry["references"]
                    ):
                        continue
                    for item in resolved:
                        row = item["row"]
                        if row["code"] in candidates or len(candidates) >= limit:
                            continue
                        support, spans, missing = documentation(db, note, row)
                        if support["status"] == "conflicting_details":
                            continue
                        # Cross-reference source is retained even when target has no note alias.
                        if not spans:
                            spans = [
                                {
                                    **evidence,
                                    "match_kind": "index_cross_reference",
                                    "matched_label": doc["label"],
                                }
                            ]
                            support = {"status": "partial"}
                            missing = ["Confirm target diagnosis and all code-specific details."]
                        candidates[row["code"]] = {
                            **catalog.identity(db, row),
                            "evidence_spans": spans,
                            "index_path": item["via"],
                            "assessments": {
                                "code_validity": "valid"
                                if row["assignable"]
                                else "header_not_assignable",
                                "documentation_support": support["status"],
                                "completeness": "needs_review",
                            },
                            "missing_details": missing
                            + ([] if row["assignable"] else ["Select an assignable descendant."]),
                        }
        return {
            **self.envelope(metadata, service_date),
            "status": "needs_clarification" if candidates else "abstain",
            "candidates": list(candidates.values()),
            "excluded_mentions": excluded[:50],
            "clarifications": [
                "Review diagnosis specificity, Tabular instructions, and encounter context."
            ]
            if candidates
            else ["No affirmative lexical candidate found; clarify the diagnosis."],
            "completeness": "Not assessed for the whole note; "
            "absence of a match is not absence of disease.",
        }

    def validate(
        self,
        codes: list[str],
        service_date: str,
        note: str | None = None,
    ) -> dict:
        catalog, metadata, error = self.begin(service_date)
        if error:
            return error
        if not codes or len(codes) > 50 or any(len(code) > 20 for code in codes):
            return self.invalid("Supply 1..50 selected codes, each at most 20 characters.")
        if note is not None and len(note) > MAX_TEXT:
            return self.invalid("Synthetic note text must be at most 20000 characters.")
        selected = [compact_code(code) for code in codes]
        results = []
        with catalog.connect() as db:
            for position, value in enumerate(codes):
                validity, row, instructions = structural_check(catalog, db, value)
                findings = set_findings(selected[position], instructions, selected, position)
                if selected.count(selected[position]) > 1:
                    findings.append(
                        {
                            "kind": "duplicate",
                            "status": "duplicate_selected_code",
                            "severity": "review",
                        }
                    )
                support, spans, missing = (
                    documentation(db, note, row)
                    if row
                    else ({"status": "not_assessed"}, [], ["Supply a valid assignable code."])
                )
                if row and not row["assignable"]:
                    missing.append("Select a complete assignable descendant.")
                if any(f["severity"] == "review" for f in findings):
                    missing.append(
                        "Resolve applicable exclusions, additional-code, and sequencing notes."
                    )
                results.append(
                    {
                        "selected_code": value,
                        **(catalog.identity(db, row) if row else {"release": metadata["release"]}),
                        "code_validity": validity,
                        "documentation_support": support,
                        "completeness": {
                            "status": "needs_clarification" if missing else "not_assessed",
                            "message": "No encounter-level completeness certification.",
                        },
                        "evidence_spans": spans,
                        "instructions": instructions,
                        "findings": findings,
                        "missing_details": missing,
                    }
                )
        return {
            **self.envelope(metadata, service_date),
            "status": "review_required",
            "selected_order": codes,
            "results": results,
            "ordering_assumption": "Input order is proposed code order, "
            "not a principal-diagnosis determination.",
        }
