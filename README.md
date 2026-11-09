# ICD10 Reference MCP

By **JC Rojas**. Original project code is licensed under [Apache-2.0](LICENSE);
see [NOTICE](NOTICE), [third-party materials](THIRD_PARTY_NOTICES.md) and
[citation metadata](CITATION.cff). Commercial reuse is permitted under the
license; preserve applicable notices. Scholarly citation is appreciated, not
an additional license condition.

Local-first ICD-10-CM reference lookup for healthcare teams and researchers.
This is a descriptive working name, not trademark clearance or clinical approval.

**Primary use: look up an ICD-10-CM code or diagnosis phrase.** Returns the official
description, assignable-code vs header status, hierarchy, Alphabetic Index references,
and applicable inherited Tabular instructions.

Two separate workflows:

1. **Core: code/phrase lookup.** Works independently, without OpenMed or model weights.
2. **Optional: local OpenMed note matching and PII preview.** Separate Python environment
   and explicit CLI invocation, synthetic notes only. Missing models never disable core lookup.

See [optional OpenMed setup](docs/local-openmed.md),
[evaluation and human review](docs/evaluation.md), and
[local execution / later hosting](docs/hosting.md).
Technical check results and remaining gates: [verification](docs/verification.md).
Step-by-step setup and acceptance: [local trial guide](docs/local-trial.md).
Terminology-only hosting trial: [Render demo](docs/render-demo.md).
**Connecting as a user?** Follow [Python/terminal and Claude Desktop setup](docs/connect.md).
The hosted path needs no local catalogs or models. Public no-login access and
the reviewed hardening are live at commit `def06ee`. Nine public acceptance calls
passed across SDK HTTP, the CLI and local bridge; see the
[deployment evidence](docs/verification.md#hardening-rollout) and
[security policy](SECURITY.md).
For remote lookup, use the [screened local client](#screened-remote-reference-client),
not a patient note in a cloud chat.

**Research prototype. Not production- or PHI-ready. Results are coder-review
candidates, never final assignments. Do not enter patient data.** No diagnosis
inference, claim submission or application-side LLM calls. Cloud MCP hosts can
process conversations before a tool runs. Core lookup runs locally or in the
explicitly configured hosting demo; optional OpenMed stays local.

## Quick start

Python 3.11+ with SQLite FTS5 and [uv](https://docs.astral.sh/uv/) are required.
Dependencies install from the package registry; lookup/import run offline afterward.
The official MCP Python SDK is the `mcp` package, not a third-party MCP server framework.

For a new checkout:

```sh
git clone https://github.com/riccc-rush-lab/icd_10_mcp.git
cd icd_10_mcp
```

```sh
# From the checked-out project directory:
uv sync --frozen --extra dev --python 3.13
uv run icd10-catalog import \
  --downloads /absolute/path/to/april-2026-archives \
  --database data/catalog.sqlite3
uv run icd10-catalog smoke
```

If the catalog already exists, **skip import**. The importer deliberately refuses to
overwrite it. A completed local catalog is generated during initial implementation.

### Look up a code

```sh
uv run icd10-catalog lookup E11.9 --date 2026-04-01
```

### Look up a phrase

```sh
uv run icd10-catalog lookup "pneumonia" --date 2026-04-01 --limit 5
uv run icd10-catalog lookup "Abdominalgia" --date 2026-04-01
uv run icd10-catalog lookup "Abnormity" --date 2026-04-01
uv run icd10-catalog lookup E11 --date 2026-04-01
```

Output is JSON. A header such as `E11` is **not assignable**; its response includes
descendant examples for refinement. Dotted and undotted codes are accepted. Unknown
codes are not autocorrected. Phrase results include matched index paths and references.
Ranking is deterministic lexical retrieval, not a probability or clinical confidence.
Malformed code-like input such as `A00..1` returns `needs_clarification` with
`code_validity.status="invalid_format"` and no candidates. It is not converted into
an unrelated diagnosis search. Numbered phrases such as `CMML-1` and `B12-deficiency`
still use phrase lookup.

**A service date is required.** Two separately imported releases are supported:

| Release ID | Effective service dates | Assignable codes / headers |
| --- | --- | --- |
| `icd10cm-2026-04-01` | 2026-04-01 through 2026-09-30 | 74,719 / 23,467 |
| `icd10cm-2026-10-01` (FY2027) | 2026-10-01 through 2027-09-30 | 74,879 / 23,524 |

The default single database remains April 2026 for compatibility. To use both, create
`data/catalogs.json` (paths are relative to this configuration file):

```json
{
  "icd10cm-2026-04-01": "catalog.sqlite3",
  "icd10cm-2026-10-01": "releases/2027/catalog.sqlite3"
}
```

```sh
uv run icd10-catalog lookup E11.9 --date 2026-10-01 --catalog-config data/catalogs.json
```

With both full catalogs installed, check local trial readiness in one command:

```sh
uv run --frozen icd10-catalog trial-check --catalog-config data/catalogs.json
```

It runs both full-corpus smoke checks and a fresh official-client stdio MCP exchange.
Exit `0` means `ready_for_local_trial`, never clinical or patient-data readiness.
Exit `2` means `not_ready`; OpenMed is optional and not checked by this command.

Absent, mismatched or out-of-range releases fail explicitly, never fall back to April.
No current-date default or anticipated future release is used.
CLI exit codes: `0` for successful workflows (including abstention), `1` for maintenance
errors, `2` for invalid requests or unavailable catalog/release.

## MCP host configuration

Use a host that supports local stdio servers. Example server definition:

```json
{
  "mcpServers": {
    "icd10-local": {
      "command": "/absolute/path/to/icd_10_mcp/.venv/bin/icd10-mcp",
      "env": {
        "ICD10_CATALOGS": "/absolute/path/to/icd_10_mcp/data/catalogs.json",
        "ICD10_TRANSPORT": "stdio"
      }
    }
  }
}
```

This is an example only. No host settings are changed automatically. The server exposes
three read-only, structured-output tools in compatibility stdio mode. These legacy
synthetic-note helpers are deterministic and **do not use OpenMed**. The optional
OpenMed workflow runs separately through `match-note`, not through a cloud MCP chat:

| Tool | Arguments | Purpose |
| --- | --- | --- |
| `phrase_search` | `query`, `service_date`, optional `limit` (1–25) | Primary code/phrase lookup |
| `suggest_candidates` | `note`, `service_date`, optional `limit` | Conservative lexical review candidates, synthetic text only |
| `validate_selected_codes` | `codes`, `service_date`, optional `note` | Structural validity, documentation support, selected-set rules |

Examples of tool arguments:

```json
{"query": "E11.9", "service_date": "2026-04-01"}
```

```json
{"note": "No pneumonia. History of cholera.", "service_date": "2026-04-01"}
```

```json
{"codes": ["T36.0X1A"], "service_date": "2026-04-01"}
```

Python callers can use `ICDService(Catalog(path)).search(...)`, `.suggest(...)`, and
`.validate(...)` directly, without MCP.

## Screened remote reference client

The optional client screens short public code/phrase inputs **before any connection**,
without OpenMed or model weights. Suspected identifiers or note-like inputs return
`privacy_blocked`, without echoing the blocked input. It rejects rather than silently
redacting clinical meaning. Codes, ordinary terminology and common eponyms remain supported.

**Best effort, not a PII-absence guarantee.** Names and identifiers can be missed,
and legitimate terminology can be blocked. Never use patient-derived queries.
Hosted screening happens after receipt. Arbitrary MCP clients, cloud chats,
platform/proxy logs and a caller's debug logging are outside this client's control.
The application cannot promise that PII is never transmitted.

Public mode needs no token. Use `--anonymous` to avoid forwarding an inherited
credential. Protected deployments retain private token-file/environment support.
See the [connection guide](docs/connect.md) for activation status, direct URL setup,
local screening, and shared Free quotas. Endpoint:
`https://icd10-reference-mcp.onrender.com/mcp`.

```sh
.venv/bin/python -m icd10_mcp.reference_client \
  --url https://icd10-reference-mcp.onrender.com/mcp \
  --anonymous --public-terminology <<'JSON'
{"operation":"lookup","query":"pneumonia","service_date":"2026-10-01","limit":5}
JSON
```

For selected-code validation, use
`{"operation":"validate","codes":["E11.9"],"service_date":"2026-10-01"}` on stdin.
No note field is accepted. Python callers can use `ReferenceClient.lookup(...)`
and `.validate(...)` from `icd10_mcp.reference_client`.

The exact service date is checked locally and replaced on the wire by the chosen
release's public start date. The result restores the requested date locally.
Unsupported dates fail locally, without fallback or a connection. This reduces
date disclosure; it does not make a patient-related query safe to upload.
The client uses HTTPS (literal loopback HTTP only), ignores proxy environment
settings, uses a constant MCP client identity and sanitizes failures.

## What is imported

For April 2026, these exact archives and members from `~/Downloads`:

* `icd10cm-table-and-index-April-1-2026.zip`
  * complete `icd10cm-codes-April-1-2026.txt`
  * complete `icd10cm-order-April-1-2026.txt`
* `icd10cm-April-1-2026-XML.zip`
  * `icd10c-tabular-April-1-2026.xml` (CDC's actual filename)
  * `icd10cm-index-April-1-2026-XML.xml`
  * `icd10cm-eindex-April-1-2026-XML.xml`
  * `icd10cm-drug-April-1-2026-XML.xml`
  * `icd10cm-neoplasm-April-1-2026-XML.xml`

The code-description ZIP containing PDFs is not a complete code corpus and is not
needed. PDF renderings and XSDs are not ingested. The `2027-icd-10-cm-addendum.zip`
and all other addenda are ignored, even if present in the same directory.

The importer checks **74,719 assignable codes and 23,467 headers**, agreement between
the complete code and order descriptions, XML root/version, and Tabular ancestry for
every order entry. It stores chapter/section/diagnosis hierarchy, all four index trees,
nonessential modifiers, cross-references, manifestation/category references, and table
column labels. Codes expanded by seventh character in order text link to their nearest
Tabular XML ancestor.

Instructions include Includes, inclusion terms, Excludes1/2, Code First, Code Also,
Use Additional Code, seventh-character definitions/notes, general notes, and visual
impairment tables. Original instruction XML and grouping paths are retained.
Introduction conventions, effective period, archive/member SHA-256 hashes, source
member names, order/code line numbers, and XML paths are preserved in SQLite.

Import uses safe XML parsing, a temporary database, consistency/integrity checks, and
atomic no-overwrite publication. It never extracts archives over arbitrary paths.
Hashes provide reproducible provenance, **not independent proof of CDC authenticity**.
Full-corpus publication also requires the seven exact verified member hashes pinned
in the release profile. A well-formed empty index or removed Tabular diagnosis cannot
be relabeled a complete release merely because code counts and XML versions match.
Changed publisher bytes require a separately verified profile update, not a manifest edit.
No source archives or generated catalog are committed; `.gitignore` excludes both.
The database contains public terminology only, never tool requests or notes.

### FY2027 complete import

The original April catalog is retained. Complete official archives, not addenda,
belong in a separate source directory:

- `icd10cm-code-descriptions-2027.zip`, containing nested
  `icd10cm-code-descriptions-2027/icd10cm-{codes,order}-2027.txt`.
- `icd10cm-table-and-index-2027.zip`, containing nested
  `icd10cm-table-and-index-2027/icd10cm-tabular_-2027.xml` (actual underscore),
  plus `icd10cm-{index,eindex,drug,neoplasm}-2027.xml` in that directory.

```sh
# Skip import when this separately verified catalog already exists.
uv run icd10-catalog import --release icd10cm-2026-10-01 \
  --downloads data/releases/2027/sources --database data/releases/2027/catalog.sqlite3
uv run icd10-catalog smoke --release icd10cm-2026-10-01 \
  --database data/releases/2027/catalog.sqlite3
```

Official source directory: <https://ftp.cdc.gov/pub/Health_Statistics/NCHS/Publications/ICD10CM/2027/>.
Archive/member hashes and local acquisition provenance are recorded beside sources.
Counts are observed and reconciled import counts, not a claim of publisher certification.

## Interpreting results

* **Code validity** means exact assignable membership in the selected release. Headers,
  invalid formats, unknown codes, and missing/invalid seventh characters or placeholders
  are distinct. No encounter character or placeholder is guessed.
* **Documentation support** is assessed separately, only when synthetic text is supplied.
  `lexical_support` means an affirmative description/inclusion match, not clinical proof.
  Index defaults alone are `partial`; noncurrent mentions and explicit laterality
  conflicts are flagged. Evidence spans use zero-based Python Unicode character offsets,
  end-exclusive, into the submitted text.
* **Completeness** is never certified. Missing specificity and unresolved instructions
  prompt review. No whole-note, encounter, principal-diagnosis, or claim-completeness claim.
* Index `see`/`seeAlso` traversal is bounded and cycle-safe. Unresolved references and code
  stems remain visible for clarification, not silently converted to specific descendants.
  Supplied heading alternatives are resolved within the same index hierarchy, with
  exact headings preferred. Ambiguous aliases, cycles, and depth limits are reported
  explicitly instead of selecting an arbitrary target. Top-level `reference_issues`
  retains traversal warnings even when `limit=1` truncates the detailed index matches.
* Excludes1 pair matches are **potential conflicts for review**, allowing for clinical
  exceptions. Excludes2 does not prohibit coexistence. Code First/Use Additional Code
  checks use proposed list order; Code Also does not set order. Conditional instructions
  and prose without parseable code references always require human interpretation.
* `abstain`, `needs_clarification`, `release_unavailable`, and `catalog_unavailable` are
  explicit statuses. Lookup does not assess documentation that was not supplied.
  Catalog admission checks required schema columns, read-only FTS readiness,
  manifest/scope structure, and supplied member/archive provenance fields.
  Missing or malformed catalog metadata returns `catalog_unavailable`.

## Limitations and safety

This is a terminology lookup aid, not a clinical coding system. It is ICD-10-**CM**
(US diagnosis terminology), not ICD-10-PCS, WHO ICD-10, or a billing service.

Core matching is lexical, with no embeddings, medical synonym expansion beyond CDC index
entries, abbreviation inference, or clinical reasoning. Bounded retrieval can miss
relevant candidates. Note handling is intentionally conservative and incomplete:
simple clause-scoped negation, uncertainty, history, resolution, and family-history
patterns do not handle every chart format, experiencer, double negation, or copied-forward
statement. Do not use it to infer an active diagnosis or absence of disease.
Drug/neoplasm table cells are exposed in lookup, not automatically turned into note
suggestions without intent/behavior selection.

Rules surface Tabular instructions; they do not implement all Official Guidelines,
setting-specific uncertain-diagnosis rules, causal relationships, guideline exceptions,
combination-code logic, payer edits, sequencing across an entire encounter, or all
special tabular tables. Preserved XML remains available for human review.

The application opens the catalog read-only, does not persist requests, does not
configure telemetry, and defaults to stdio. Optional HTTP is loopback-only and excludes
note inputs. **An MCP host or its model may store or
transmit tool arguments and outputs. Local server operation is not a privacy guarantee.**
The default local launcher has no authentication. The separate prepared demo uses
a shared bearer secret, not institutional OAuth or validated PHI safeguards.
There is no security certification, institutional audit control or production
acceptance. Use only synthetic text. Do not connect this to patient records.

## Development checks

```sh
uv run pytest -q
uv run ruff check src tests scripts
uv run ruff format --check src tests scripts
uv run icd10-catalog smoke --database data/catalog.sqlite3
```

Enable the fresh-import integration checks against the supplied complete archives:

```sh
uv run pytest -q tests --cdc-downloads /absolute/path/to/april-2026-archives \
  --fy2027-downloads data/releases/2027/sources
```

Without `--cdc-downloads`, corpus import tests are explicitly skipped. An explicitly
requested directory missing required archives fails the check. These tests build a
new catalog in a temporary directory, verify public lookup and an independently
recorded member checksum, and reject a wrong XML release without publishing a catalog.
They do not replace the working catalog or commit/copy source data into the project.

Unit tests build small synthetic catalogs in temporary directories. They do not need
CDC files, do not use patient data, and include a real stdio MCP handshake/tool-call test.
The smoke command requires the full local CDC catalog and checks counts, all-code
ancestry, provenance, four indexes, instructions, lookup/cross-references, seventh
characters/placeholders, noncurrent-note abstention, and release boundaries.

## Updating safely

1. Obtain complete code/order, Tabular XML, and all index XML files for a new release
   from CDC/NCHS. Independently verify source authenticity, dates, counts, and changes.
   An addendum alone is **insufficient**.
2. Build a release-specific import profile and separately verified catalog. Do not
   relabel this release, extend its date interval, change filenames to trick this importer,
   or append FY2027 addenda to April 2026 data.
3. Define nonoverlapping effective intervals and explicit date selection before adding
   new release support. The current profiles accept April 2026 and FY2027 separately;
   the tool cannot anticipate an intervening future midyear update.
4. Add release-specific regression fixtures, count checks, source hashes, import smoke
   checks, and boundary tests. Review changed instructions and seventh-character behavior.
5. To rebuild April 2026, import to a **new path**, run tests and smoke there, then point
   `ICD10_CATALOG` at it. Keep the previous catalog until verification is complete.

Do not commit CDC source archives, generated databases, notes, or patient fixtures.
