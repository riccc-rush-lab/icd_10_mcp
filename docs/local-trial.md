# Local trial

**Goal:** repeatable local terminology lookup with both supported CDC releases.
No cloud service, OpenMed environment, Docker, patient data or remote model is
required. Passing these checks is technical readiness for a local trial, not clinical,
privacy or production approval.

## 1. Install the core

Run from the project directory. Python 3.13 is the verified runtime; SQLite must
include FTS5. Install [uv](https://docs.astral.sh/uv/) separately if needed.

```sh
uv sync --frozen --extra dev --python 3.13
```

Installation accesses package registries. The checks and lookup then use local files
and a local subprocess, without a hosted model. Do not install the optional OpenMed
environment just to use terminology lookup.

## 2. Prepare the catalogs once

**On the original development computer, both catalogs already exist. Skip imports.**
A new checkout contains neither source archives nor generated databases.

Obtain the complete official archives listed in the [README](../README.md#what-is-imported),
not just addenda. Use separate April and FY2027 source directories. Never put notes or
credentials in those directories. Import only when the destination does not exist:

```sh
uv run --frozen icd10-catalog import \
  --downloads /absolute/path/to/april-2026-archives \
  --database data/catalog.sqlite3

uv run --frozen icd10-catalog import --release icd10cm-2026-10-01 \
  --downloads /absolute/path/to/fy2027-archives \
  --database data/releases/2027/catalog.sqlite3
```

The importer refuses overwrite. If rebuilding, choose a new destination and verify
it before changing configuration; do not delete the old database to force an import.

Create `data/catalogs.json` only if it is absent. The versioned template already uses
the default local database layout:

```sh
mkdir -p data
test -e data/catalogs.json || cp deploy/catalogs.json data/catalogs.json
```

Database paths resolve relative to this JSON file, not the shell working directory.
Existing custom configuration is left alone.

## 3. Run the local readiness check

```sh
uv run --frozen icd10-catalog trial-check --catalog-config data/catalogs.json
```

This command:

- Requires both April 2026 and FY2027 catalogs; missing releases never fall back.
- Runs the existing 28 full-corpus smoke checks for each release, including integrity,
  counts, provenance, hierarchy, indexes, instructions and lookup behavior.
- Starts a fresh local stdio server with the same Python interpreter and an explicit
  catalog configuration. It does not change your MCP app's settings or open a port.
- Uses the official MCP client for initialization, tool discovery and ten checks:
  release-boundary lookup, phrase search, nonassignable headers, the FY2027-only code,
  malformed input, an unavailable release and selected-code validity.
- Does not require or check OpenMed. Full-corpus smoke checks include fixed synthetic
  context controls through the legacy deterministic workflow, not model inference.
- Leaves catalog files read-only and closes the test server when done.

Success returns JSON with `status="ready_for_local_trial"` and exit code **0**.
`ready_for_clinical_use` and `ready_for_patient_data` remain **false**;
`optional_nlp="not_checked"` is expected, not a failure.

Failure returns `status="not_ready"`, a sanitized reason and exit code **2**.
Reasons distinguish unavailable configuration, missing releases, full-catalog failure
and MCP failure. Completed catalog checks remain visible. The MCP exchange has a
45-second timeout; total runtime also includes the catalog checks.

This checks installed artifacts and behavior, not full source reauthentication,
all possible coding rules, clinical accuracy, OS network isolation or your chosen
end-user app. Do not treat a successful check as permission to enter patient data.

## 4. Try ordinary lookup

```sh
uv run --frozen icd10-catalog lookup E11.9 \
  --date 2026-10-01 --catalog-config data/catalogs.json
uv run --frozen icd10-catalog lookup pneumonia \
  --date 2026-10-01 --catalog-config data/catalogs.json --limit 5
uv run --frozen icd10-catalog lookup E11 \
  --date 2026-10-01 --catalog-config data/catalogs.json
uv run --frozen icd10-catalog lookup C78.31 \
  --date 2026-09-30 --catalog-config data/catalogs.json
```

Expected controls: E11.9 is assignable; pneumonia includes J18.9; E11 is a
nonassignable header; C78.31 is absent from April and must not be silently supplied
from FY2027. Every request needs its actual intended service date.

## 5. Connect your chosen MCP app

The readiness command verifies the SDK/client exchange, **not an end-user app**.
Configure your app separately using absolute paths. Generic stdio configuration:

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

Settings locations and formats vary by app; this is not an automatic configuration
change. Use the actual checkout path, even if its folder has a different name.
Verify tool discovery and the same lookup controls in that app. Record its name,
version and the outcome before calling that integration tested.

Stdio exposes three tools for compatibility. `suggest_candidates` is deterministic,
not OpenMed. Use `phrase_search` for the primary trial. Never send real notes: the
host or its model may store or transmit arguments even though this server is local.

## 6. Record the trial and stop at the remaining gates

Record the date, Python/app versions, readiness outcome, release IDs and any surprising
lookup results. Keep local reports under ignored `.scratch/`, without patient data.
Do not turn observations into reviewed benchmark labels automatically.

Use the [human-review checklist](evaluation.md#cliniciancoder-review-checklist) to
adjudicate the separate synthetic benchmark before making performance claims.
The known optional mixed-diabetes ranking problem remains open; this trial does not
fix or validate note coding or PII recall.

The repository is source-only. `.gitignore` excludes catalogs, source archives,
models/environments, `.scratch/`, common local secrets and note directories. Exclusions
are a guard, not a secret detector: inspect the exact proposed files and diff before
any commit/push. Do not upload local reports, model weights or patient-derived material.

Docker verification is a separate portable-handoff milestone. Cloud deployment,
identity/network integration, rights clearance and clinical/privacy approval remain
external gates. See [verification](verification.md) and [hosting](hosting.md).
