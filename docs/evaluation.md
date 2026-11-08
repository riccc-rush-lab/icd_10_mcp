# Synthetic evaluation and human-review packet

Nothing here is a clinically approved gold standard. All 20 core/baseline cases
and nine optional OpenMed cases begin **unreviewed**. They are entirely synthetic.

## Reproduce

```sh
# From the checked-out project directory:
uv run icd10-catalog evaluate benchmarks/lookup-draft.json \
  --catalog-config data/catalogs.json --limit 10

# Optional, only after the separately staged local OpenMed setup:
uv run icd10-catalog evaluate benchmarks/openmed-draft.json \
  --catalog-config data/catalogs.json --limit 10 \
  --models data/models/openmed-pilot --nlp-python data/openmed-venv/bin/python
```

The core draft includes exact codes, headers, boundaries and a genuinely new FY2027
code (`C78.31`, absent from April), CDC heading aliases, draft abbreviation/ambiguity,
laterality, near matches, malformed inputs, abstention and legacy synthetic-note context.
Source members/anchors accompany every terminology proposal.
The OpenMed draft is separate: affirmed, negated, uncertain, historical, family, mixed
assertions and synthetic identifier context. It records model pins and worker resource
measurements; no fake model is used as evidence for its performance.

The evaluator rejects duplicate IDs, malformed label types, missing source references
and unsupported workflows. Labels are not generated from retrieval results.
`forbidden_codes` reports explicitly unsafe outputs even for nonexhaustive labels.
Do not tune the engine to these tiny draft examples and report them as a held-out test.

## Metric meanings

- **Top-1 match**: first returned code in the expected set, divided by cases with at
  least one expected code.
- **Recall-at-k**: expected codes retrieved, divided by all expected codes in those
  positive cases. `k` is bounded to 1–25.
- **Wrong-code rate**: unexpected returned codes divided by returned codes, **only
  in cases explicitly labeled exhaustive**. It says nothing about unlabelled outputs.
- **Unsafe-code count**: outputs explicitly named in `forbidden_codes`. This is a
  count over supplied controls, not a population safety rate.
- **Abstention**: a successful empty candidate result, divided by all cases. Unavailable
  catalogs/models and invalid inputs are errors, not successful abstentions.
- **Coverage**: cases returning any candidates divided by all cases. Higher is not
  necessarily safer or better. Errors are counted separately.

Every report includes denominators, per-case status/status-match, source/release,
slices and a canonical benchmark hash. Draft statistics are exploratory.
Reviewed-case metrics remain `null` until human review metadata is supplied.
Even then, `ready_for_clinical_use=false`; reviewer metadata is an attestation,
not verification of credentials or institutional acceptance.

OpenMed candidate order is a source-span-order union of bounded lexical results,
not a learned code-confidence ranking. The coding evaluator does **not** measure PII
recall, false-positive redactions, clinical relation accuracy or complete note coding.
The email regression demonstrates one observed partial-mask failure and its fix;
broader privacy evaluation remains a gate.

## Clinician/coder review checklist

Review each case, without consulting engine output first:

1. Confirm the exact release, service dates, authoritative member/path and anchor.
2. State the case objective and care setting. Separate terminology membership from
   clinical diagnosis, documentation support, sequencing and whole-encounter coding.
3. Adjudicate every expected code, allowed alternative, forbidden code and status.
   Mark `exhaustive=true` only if the expected set is complete **for this objective**.
4. Review abbreviations (especially HTN/MS), unspecified defaults, laterality,
   near-match alternatives, release changes and inherited instructions.
5. For history/family/uncertainty, do not mistake active-disease suppression for a
   universal clinical coding rule. Consider Z codes and setting-specific guidelines.
6. Independently author challenging held-out cases. Use two reviewers and a documented
   disagreement/adjudication process before performance claims.
7. Record `review.status="reviewed"`, `reviewer`, `reviewed_at` and `evidence` in a
   separately versioned human-adjudicated benchmark. Preserve the unreviewed original.
8. Define prospective acceptance thresholds and denominators with the institution.
   A passing software test or a zero wrong-code count in a tiny slice is insufficient.

For PII, independently label complete identifiers/spans and measure misses and harmful
redactions across realistic synthetic formats before considering any approved local
patient-data evaluation. Never automatically turn a preview into upload permission.

## Scoring is gated, not implemented

```sh
uv run icd10-catalog scoring-status
```

This read-only administrative interface reports `disabled`, no methods and no score.
A later method needs its exact name/version, licensed release-specific mappings,
required clinical inputs, deterministic specification, independent worked examples
and expert review. Diagnosis codes cannot supply APACHE physiological measurements.
