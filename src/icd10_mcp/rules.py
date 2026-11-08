"""Conservative structural and selected-set checks; no clinical coding inference."""

from __future__ import annotations

from .catalog import CODE_PATTERN, Catalog, compact_code, display_code
from .matching import clauses, note_evidence, reference_matches, terms


def documentation(db, note: str | None, row: dict) -> tuple[dict, list[dict], list[str]]:
    if note is None:
        return {"status": "not_assessed"}, [], ["Documentation was not supplied."]
    evidence, _ = note_evidence(db, note, row)
    affirmed = [item for item in evidence if item["context"] == "affirmed"]
    if not affirmed:
        return (
            {
                "status": "negated_or_noncurrent" if evidence else "not_found",
                "message": "No affirmative current documentation match; "
                "do not infer the diagnosis.",
            },
            evidence,
            ["Confirm an affirmative, current diagnosis and code-specific details."],
        )
    # Only the complete official description/inclusion is lexical support.
    # An index default alone cannot establish all documentation requirements.
    direct = any(item["match_kind"] in {"description", "inclusion"} for item in affirmed)
    missing = (
        [] if direct else ["Confirm code-specific details; an index alias is not full support."]
    )
    description = row["description"].lower()
    for required, opposite in [("right", "left"), ("left", "right")]:
        if required not in terms(description):
            continue
        for offset, clause in clauses(note):
            if any(offset <= ev["start"] < offset + len(clause) for ev in affirmed):
                if opposite in terms(clause) and required not in terms(clause):
                    return (
                        {
                            "status": "conflicting_details",
                            "message": "Affirmative mention conflicts with "
                            "selected-code laterality.",
                        },
                        evidence,
                        [f"Resolve {required}/{opposite} laterality discrepancy."],
                    )
    if any(term in description for term in ["unspecified", "not otherwise specified"]):
        missing.append("Check whether more specific documentation is available.")
    if any(
        term in description for term in ["initial encounter", "subsequent encounter", "sequela"]
    ):
        missing.append("Confirm encounter character from treatment phase, not visit count.")
    # Laterality and other modifiers must occur in the affirmative evidence itself.
    for modifier in ["right", "left", "bilateral", "acute", "chronic"]:
        if modifier in terms(description) and not any(
            modifier in terms(item["text"]) for item in affirmed
        ):
            missing.append(f"Confirm {modifier} specificity.")
    return (
        {
            "status": "lexical_support" if direct else "partial",
            "message": "Lexical evidence only; "
            "provider documentation and coding review still required.",
        },
        evidence,
        missing,
    )


def structural_check(catalog: Catalog, db, value: str) -> tuple[dict, dict | None, list[dict]]:
    if not CODE_PATTERN.fullmatch(value.strip().upper()):
        return {"status": "invalid_format", "is_assignable": False}, None, []
    code = compact_code(value)
    row = catalog.code(db, code)
    if row:
        return (
            {
                "status": "valid" if row["assignable"] else "header_not_assignable",
                "is_assignable": bool(row["assignable"]),
                "basis": "Exact membership in the selected release's complete code/order files.",
            },
            row,
            catalog.instructions(db, row),
        )
    # Diagnostics only: never repair an invalid code or silently choose an extension.
    ancestor = next(
        (found for n in range(len(code) - 1, 2, -1) if (found := catalog.code(db, code[:n]))),
        None,
    )
    instructions = catalog.instructions(db, ancestor) if ancestor else []
    extensions = {}
    for instruction in instructions:
        if instruction["kind"] == "sevenChrDef":
            extensions = instruction["data"].get("extensions", {})
            break
    reason = "not_in_release"
    if extensions:
        reason = "seventh_character_or_placeholder_invalid"
    return (
        {
            "status": "invalid_code",
            "is_assignable": False,
            "reason": reason,
            "required_length": 7 if extensions else None,
            "allowed_seventh_characters": extensions,
            "message": "Use exact catalog membership; do not auto-fill X or encounter characters.",
        },
        None,
        instructions,
    )


def set_findings(
    code: str, instructions: list[dict], selected: list[str], position: int
) -> list[dict]:
    findings = []
    for instruction in instructions:
        kind = instruction["kind"]
        if kind not in {"excludes1", "excludes2", "codeFirst", "useAdditionalCode", "codeAlso"}:
            continue
        matches = [
            (i, other)
            for i, other in enumerate(selected)
            if i != position and reference_matches(instruction["text"], other)
        ]
        common = {
            "kind": kind,
            "text": instruction["text"],
            "origin": instruction["origin"],
            "source": instruction["source"],
            "source_path": instruction["source_path"],
            "related_selected_codes": [display_code(other) for _, other in matches],
        }
        if kind == "excludes1":
            if matches:
                findings.append(
                    {
                        **common,
                        "status": "potential_excludes1_conflict",
                        "severity": "review",
                        "message": "Review conditions and any unrelated-condition exception; "
                        "this is not an automatic code-invalidity decision.",
                    }
                )
        elif kind == "excludes2":
            if matches:
                findings.append(
                    {
                        **common,
                        "status": "coexistence_permitted",
                        "severity": "info",
                        "message": "Excludes2 does not itself prohibit reporting both codes.",
                    }
                )
        elif kind == "codeFirst":
            status = (
                "sequencing_review"
                if matches and not any(i < position for i, _ in matches)
                else "referenced_code_present"
                if matches
                else "underlying_code_review"
            )
            findings.append({**common, "status": status, "severity": "review"})
        elif kind == "useAdditionalCode":
            status = (
                "sequencing_review"
                if matches and not any(i > position for i, _ in matches)
                else "referenced_code_present"
                if matches
                else "additional_code_review"
            )
            findings.append({**common, "status": status, "severity": "review"})
        else:
            findings.append(
                {
                    **common,
                    "status": "code_also_review",
                    "severity": "review",
                    "message": "Applicability is conditional; this instruction does not set order.",
                }
            )
    return findings
