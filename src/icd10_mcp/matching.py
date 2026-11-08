"""Deterministic lexical retrieval, index traversal, and conservative mention context."""

from __future__ import annotations

import re
import sqlite3

from .catalog import Catalog, compact_code, words

STOP = {"a", "an", "the", "of", "and", "with", "to", "in", "for", "due", "by"}
NONCURRENT = [
    ("family_history", r"\bfamily\s+(?:history|hx)\s*(?:of|:)?"),
    (
        "historical",
        r"\b(?:history|hx)(?:\s+of\b|\s*:)|\bpmh\s*:|"
        r"\b(?:previous(?:ly)?|remote|prior|past|resolved)\b",
    ),
    (
        "uncertain",
        r"\b(?:possible|possibly|suspected|suspect|probable|questionable|"
        r"rule[ -]?out|r/o|concern for|cannot exclude|not excluded|may have|"
        r"could have|evaluate for|at risk for)\b",
    ),
    ("negated", r"\b(?:no|not|without|denies|denied|negative for|absence of)\b"),
]


def terms(value: str) -> list[str]:
    return [word for word in words(value) if word not in STOP]


def retrieve(db: sqlite3.Connection, query: str, limit: int = 160) -> list[dict]:
    tokens = list(dict.fromkeys(terms(query)))[:24]
    if not tokens:
        return []
    expression = " OR ".join(f'"{token}"' for token in tokens)
    exact_rows = db.execute(
        "SELECT d.*, 0 AS rank FROM documents d WHERE lower(label)=lower(?) ORDER BY id LIMIT ?",
        (query.strip(), limit),
    ).fetchall()
    rows = []
    for table in ["labels", "search"]:
        for operator in [" AND ", " OR "]:
            expression = operator.join(f'"{token}"' for token in tokens)
            rows.extend(
                db.execute(
                    f"""SELECT d.*, bm25({table}) AS rank FROM {table}
                    JOIN documents d ON d.id={table}.rowid WHERE {table} MATCH ?
                    ORDER BY rank, d.id LIMIT ?""",
                    (expression, limit),
                ).fetchall()
            )
    query_terms = set(tokens)
    ranked, seen = [], set()
    for row in [*exact_rows, *rows]:
        item = dict(row)
        if item["id"] in seen:
            continue
        seen.add(item["id"])
        label_terms = set(terms(item["label"]))
        common = query_terms & label_terms
        if not common:
            continue
        coverage = len(common) / len(query_terms)
        precision = len(common) / max(len(label_terms), 1)
        exact = words(query) == words(item["label"])
        item["retrieval_score"] = round(coverage * 4 + precision * 3 + exact * 8, 6)
        ranked.append(item)
    return sorted(ranked, key=lambda x: (-x["retrieval_score"], x["id"]))


def index_entry(db, entry_id: int) -> dict:
    entry = dict(db.execute("SELECT * FROM index_entries WHERE id=?", (entry_id,)).fetchone())
    entry["references"] = [
        dict(ref)
        for ref in db.execute(
            "SELECT kind,value,column_label FROM index_refs WHERE entry_id=? ORDER BY id",
            (entry_id,),
        )
    ]
    return entry


def reference_targets(db, value: str, source: str) -> tuple[list[dict], str]:
    target_words = words(value)
    exact = [
        doc
        for doc in retrieve(db, value, 80)
        if doc["kind"] == "index"
        and doc["source"] == source
        and words(doc["label"]) == target_words
    ]
    if exact:
        return (exact, "resolved") if len(exact) == 1 else ([], "ambiguous_review_required")

    parent_id = None
    for heading in value.split(","):
        siblings = [
            dict(row)
            for row in db.execute(
                """SELECT d.*, e.label AS heading FROM index_entries e
                   JOIN documents d ON d.entry_id=e.id
                   WHERE e.source=? AND e.parent_id IS ? ORDER BY e.id""",
                (source, parent_id),
            )
        ]
        exact = [doc for doc in siblings if words(doc["heading"]) == words(heading)]
        aliases = [
            doc
            for doc in siblings
            if any(words(alias) == words(heading) for alias in doc["heading"].split(","))
        ]
        matches = exact or aliases
        if len(matches) != 1:
            status = "ambiguous_review_required" if matches else "unresolved_review_required"
            return [], status
        target = matches[0]
        parent_id = target["entry_id"]
    return [target], "resolved"


def resolve_document(
    db, document: dict, *, depth: int = 0, visited=()
) -> tuple[list[dict], list[dict]]:
    """Resolve exact references only. Prefixes remain headers/stems, never guessed leaf codes."""
    if document["code"]:
        row = Catalog.code(db, document["code"])
        return ([{"row": row, "via": []}] if row else []), []
    entry_id = document["entry_id"]
    if entry_id is None or entry_id in visited or depth > 4:
        return [], []
    entry = index_entry(db, entry_id)
    resolved, details = [], [entry]
    for ref in entry["references"]:
        if ref["kind"] in {"code", "manif", "subcat", "seecat", "cell"}:
            row = Catalog.code(db, ref["value"].rstrip("-"))
            target = {
                **ref,
                "resolved_code": row["code"] if row else None,
                "status": "tabular_resolved" if row else "requires_tabular_refinement",
            }
            entry.setdefault("lookup_results", []).append(target)
            if row:
                resolved.append({"row": row, "via": [entry]})
        elif ref["kind"] in {"see", "seeAlso"}:
            targets, status = reference_targets(db, ref["value"], entry["source"])
            if any(target["entry_id"] in (*visited, entry_id) for target in targets):
                targets, status = [], "cycle_review_required"
            elif targets and depth >= 4:
                targets, status = [], "depth_limit_review_required"
            entry.setdefault("cross_reference_results", []).append(
                {
                    "kind": ref["kind"],
                    "value": ref["value"],
                    "status": status,
                }
            )
            for target in targets:
                items, refs = resolve_document(
                    db,
                    target,
                    depth=depth + 1,
                    visited=(*visited, entry_id),
                )
                for item in items:
                    item["via"] = [entry, *item["via"]]
                resolved.extend(items)
                details.extend(refs)
    return resolved, details


def clauses(note: str):
    """Offsets are Python Unicode character offsets, end-exclusive."""
    boundary = re.compile(r"(?<!\d)[.!?](?!\d)|[;\n]|\b(?:but|however|although)\b", re.I)
    start = 0
    for match in boundary.finditer(note):
        if note[start : match.start()].strip():
            end = match.end() if match.group() == "?" else match.start()
            yield start, note[start:end]
        start = match.end()
    if note[start:].strip():
        yield start, note[start:]


def evidence_for(text: str, label: str, offset: int = 0) -> dict | None:
    required = set(terms(label))
    tokens = list(re.finditer(r"[a-z0-9]+", text.lower()))
    matches = [token for token in tokens if token.group() in required]
    if not required or {token.group() for token in matches} != required:
        return None
    start, end = matches[0].start(), matches[-1].end()
    # A lexical bag match over a long sentence is not a useful mention.
    if end - start > max(160, len(label) * 3):
        return None
    prefix = text[:start].lower()
    suffix = text[end:].lower()
    context = "affirmed"
    if "?" in suffix:
        context = "uncertain"
    elif re.search(r"\b(?:resolved|ruled out|absent|not present|not confirmed)\b", suffix[:45]):
        context = "negated"
    else:
        for status, expression in NONCURRENT:
            if re.search(expression, prefix):
                context = status
                break
    return {
        "start": offset + start,
        "end": offset + end,
        "text": text[start:end],
        "context": context,
    }


def note_evidence(db, note: str, row: dict) -> tuple[list[dict], list[str]]:
    """Require a full description/inclusion or index alias for this exact code."""
    documents = [
        dict(doc)
        for doc in db.execute("SELECT * FROM documents WHERE code=? ORDER BY id", (row["code"],))
    ]
    # Indexed paths can refer to a header, but must not support a more specific leaf.
    entries = db.execute(
        """SELECT DISTINCT d.* FROM index_refs r
           JOIN documents d ON d.entry_id=r.entry_id
           WHERE replace(upper(r.value),'.','')=? AND r.kind IN ('code','cell') LIMIT 300""",
        (row["code"],),
    ).fetchall()
    documents.extend(dict(doc) for doc in entries)
    result, labels = [], []
    for offset, clause in clauses(note):
        for doc in documents:
            ev = evidence_for(clause, doc["label"], offset)
            if ev:
                ev.update(
                    {
                        "match_kind": doc["kind"],
                        "matched_label": doc["label"],
                        "source": doc["source"],
                        "source_path": doc["source_path"],
                    }
                )
                result.append(ev)
                labels.append(doc["label"])
    # Prefer the more specific description, but retain noncurrent evidence for review.
    result.sort(key=lambda e: (e["start"], e["match_kind"] != "description", e["end"]))
    return result[:20], labels


def reference_matches(value: str, target: str) -> bool:
    """Code tokens/ranges only, not clinical interpretation of prose conditions."""
    target = compact_code(target)
    token = r"(?![A-Z]{3})[A-Z][A-Z0-9]{2}(?:\.[A-Z0-9]{0,4})?"
    pattern = rf"(?<![A-Za-z0-9])({token})(?:\s*-\s*({token}))?"
    for match in re.finditer(pattern, value):
        first, last = match.groups()
        first = compact_code(first)
        if last:
            last = compact_code(last)
            if first <= target[: len(first)] and target[: len(last)] <= last:
                return True
        elif target.startswith(first):
            return True
    return False
