# Local build verification

This records technical checks, not clinical/privacy acceptance or deployment.
Approved scope and six public TDD seams:
`.scratch/health-system-build/spec.md`.
Historical non-Git comparison baseline:
`.scratch/health-system-build/before-ci0owdn0`.

## Verified

- Both complete CDC releases imported separately. April remains unchanged.
  All 28 smoke checks pass for each working catalog.
- April: 74,719 assignable codes, 23,467 headers, 47,200 hierarchy nodes.
  FY2027: 74,879 assignable codes, 23,524 headers, 47,344 hierarchy nodes.
- Core environment has no installed `openmed` package. Public lookup succeeds for
  April `E11.9` and FY2027-only `C78.31`; the new code is not returned for April.
- Most recent full opt-in suite (2026-11-07): **205 passed in 101.63 seconds**, including both fresh
  corpus imports, partial-XML rejection, actual local model weights and MCP transports.
  This run followed local-only Render preparation and its 19 demo/build checks.
  The previous 186-test run covered the local-trial command and its eight CLI checks.
  The previous 178-test run followed the NLP audit fixes and shared model-policy refactor.
  The earlier 172-test run followed the importer fix and Starlette upgrade to 1.10.0.
- Ruff lint and formatting passed across all 38 files in `src`, `tests`, and `scripts`.
- The initial core dependency audit failed on Starlette advisories. The patched,
  regenerated `requirements/core.lock` audit now reports no known vulnerabilities.
  The separate OpenMed lock audit earlier in this build also reported no known
  vulnerabilities. Neither is a security certification.
- Official MCP stdio and in-memory HTTP client calls, a real loopback launcher,
  startup artifact admission, host/origin checks, 64 KiB body limits, missing-catalog
  readiness and an invalid-input payload-log regression pass.
- Real-weight checks cover NER-to-catalog candidates, four context contrasts,
  source offsets including leading whitespace, complete synthetic email masking
  after an observed fragment failure, token-limit rejection and model provenance.
- Optional candidates now carry original-note evidence offsets, including Unicode
  prefixes, and retain distinct evidence from repeated mentions of a deduplicated code.
  Each candidate receives an independent documentation/specificity assessment;
  alternative candidates are not validated together as coexisting selected diagnoses.
- Staging and runtime admission share a dependency-free model policy. Offline public
  guards verify the documented staging invocation, no-overwrite behavior and rejection
  of an unmanifested model artifact while core lookup remains available.
- At completion of the NLP audit fixes, comparison against the audit hashes found
  all 32 recorded existing files outside those fixes unchanged, including release
  import, service/rules, locks and container files.

## Local-trial handoff, 2026-11-07

- New public command:
  `icd10-catalog trial-check --catalog-config data/catalogs.json`.
  The working installation returned `ready_for_local_trial` after 28 smoke checks
  per catalog and ten checks through a fresh official-client stdio MCP session.
- A fresh-corpus CLI test also passed outside the repository working directory,
  with deliberately invalid inherited transport/port/catalog settings. The child
  uses explicit stdio/catalog settings; catalogs remained unchanged.
- Missing/malformed configuration, an incomplete release map, synthetic catalogs
  and swapped full catalogs return `not_ready` with exit 2. Configuration failures
  do not echo a private filename marker or create the missing file.
- The unavailable-command/configuration case and then the complete real-catalog/MCP
  case were observed red-to-green. Six additional admission guards passed immediately
  and are hardening, not additional observed reds.
- OpenMed is not required or checked. Both clinical and patient-data readiness flags
  remain false even when technical checks pass. Actual end-user MCP app integration
  still needs its app/version selected and tested.
- The original repository target was authenticated as private and empty. Local
  Git was initialized against that target; no commit or push was performed then.
  Ignore checks cover catalogs, archives/models/environments, `.scratch/`, local
  secrets and note directories. A limited token/private-key pattern scan found no
  matches in eligible files; that is not comprehensive secret or security clearance.
- Portable setup, lookup controls and the human-review handoff are documented in
  `docs/local-trial.md`. No hosting service or emulator was installed or deployed.

## Render preparation only, 2026-11-07

The user selected **prepare locally, do not push**, then selected the Python MCP
test client. No files were staged, committed or pushed; no service/account was
created, no public port was opened and no cloud deployment was performed.

- A separate `python -m icd10_mcp.demo` launcher requires a bearer secret, exact
  hostname and both full catalogs. Binding defaults to loopback; `--public-bind`
  is an explicit future TLS-hosting opt-in. Ordinary local launchers are unchanged.
- Official-client ASGI tests verify the hosted hostname, two note-free tools and
  authenticated lookup. Guards reject missing/wrong/query-only/duplicate credentials,
  untrusted hosts/origins and bodies over 64 KiB. Health probes intentionally remain
  anonymous. Media-type errors do not log the supplied marker; mixed-case JSON
  media types are normalized before SDK handling.
- The chosen Python check client uses fixed terminology queries and an explicit
  service date. It accepts remote HTTPS or literal loopback HTTP only, gets its
  secret from the environment and sanitizes failures. It is not an OAuth client.
- A fresh full-corpus artifact build also started the actual demo process on
  loopback, rejected unauthenticated access and passed the Python client CLI.
  Database files were prepared read-only. No OpenMed was required.
- The source-only builder verifies four pinned archive hashes, uses the ordinary
  member-pinned importer and runs 28 smoke checks per release. Existing output is
  refused; source changes/download failures/oversized responses do not publish a
  ready configuration. Download-mode tests use actual archives through a controlled
  **external HTTP** adapter, not mocked owned import/catalog modules.
- Observed red-to-green slices covered demo authentication/interface, hosted MCP
  host handling, fail-closed startup, Python checks, artifact preparation, download
  failure handling and media-type behavior. Additional guards that passed immediately
  are coverage hardening, not invented reds.
- HTTPX is now declared directly because the check client imports it. Offline lock
  regeneration/export changed dependency attribution only: all package versions,
  locked requirements and artifact hashes stayed identical. The rerun core audit
  reports no known vulnerabilities; the unchanged optional lock was not re-audited.
- `deploy/render.example.yaml` passed local YAML parsing and checks for free plan,
  auto-deploys off and a generated, nonembedded secret. This is **not** Render schema
  or runtime validation. The filename is inactive; initial service creation could
  still trigger a deploy after later approval.

See `docs/render-demo.md`. Live CDC acquisition, Linux/Render build compatibility,
TLS/proxy/health-host behavior, real Render service/client connections, cold starts,
concurrency and memory including file cache remain unverified. The previous
independent reviews covered earlier audit fixes, not a security audit of this new
demo. Shared-secret access is not institutional auth, clinical or PHI readiness.

## Working-catalog local trial, 2026-11-08

- Reran `trial-check` against the working catalogs: both 28-check smoke suites and
  all ten stdio MCP checks passed.
- Started the separate authenticated demo on loopback with a short-lived,
  in-memory random secret. The Python client CLI passed all five checks for both
  2026-09-30 (April release) and 2026-10-01 (FY2027).
- All **23 runtime checks** passed: health/readiness, absent/wrong-token rejection,
  client results and safety flags, note-free tool discovery, C78.31 across the
  release boundary, malformed code/date handling and unavailable-release behavior.
  These are technical controls, not adjudicated clinical-performance cases.
- Both working catalog SHA-256 hashes were unchanged after the trial. The secret
  was absent from captured client/server logs and was not written to the report.
  The demo process was stopped after the checks.
- Local report: `.scratch/local-trials/trial-2026-11-08-ra8wla9q.json`, confirmed
  ignored by Git. Nothing was staged, committed, pushed or deployed.
- No application code was edited for this execution-only trial. The full test
  suite and Ruff were not rerun; the targeted working-installation checks above
  are the new validation. OpenMed was not required. Clinical and patient-data
  readiness remain false; Render and independent human-review gates remain open.

## Public source handoff preparation, 2026-11-08

- The user explicitly approved committing and pushing source to the public target
  `riccc-rush-lab/icd_10_mcp`, replacing the earlier private target. This permission
  does not authorize a hosting deployment.
- Machine-specific example paths were replaced with portable placeholders.
  Catalogs, archives, weights/environments, local reports and credentials remain
  excluded from the source handoff. Only synthetic benchmark/example text is included.
- The public/default check run passed **181 tests**, with **24 explicit skips**
  for opt-in corpus/model checks. Ruff lint and formatting passed across 38 files.
  The earlier 205-test opted-in run and working-catalog trial remain recorded above;
  default-test success does not replace those integration checks.

## Observed red-to-green slices

Release-aware import/workflows/CLI, evaluator/CLI, scoring status, missing-model
isolation, actual SDK compatibility, full-email preview masking, original whitespace
offsets, optional note CLI, public HTTP/client parity, missing-catalog startup,
loopback launcher, malformed benchmark-label admission, explicit unsafe-code reporting,
optional model evaluation/CLI and malformed model-config failure handling.
The final spec review reproduced admission of a well-formed empty index and a removed
Tabular diagnosis, then both public-import cases went red-to-green after full-corpus
publication was tied to the seven pinned member hashes per release. Canonical imports
for both releases still pass. Explicit synthetic fixtures remain labeled synthetic.
The subsequent optional NLP audit reproduced four more failing public real-weight
cases: literal ASCII and Unicode-prefixed evidence offsets, repeated-mention evidence,
and missing specificity review for valid unspecified J18.9. Each went red-to-green.
The two new staging/admission guards passed before and after policy consolidation;
they are coverage hardening, not additional observed reds.
Existing-behavior guards that passed immediately are coverage hardening, not claimed
as observed reds. No tests mock owned collaborators or use SQL to bypass public seams.

## Exploratory evaluation

Both drafts were rerun after the optional NLP fixes. The metrics below were unchanged;
both reports retain `review_required`, `ready_for_clinical_use=false`, zero reviewed
cases and zero runtime errors. Reports:
`.scratch/health-system-build/matt-fixed-core-evaluation.json` and
`.scratch/health-system-build/matt-fixed-openmed-evaluation.json`.

Core draft, 20 synthetic cases, **zero reviewed labels**:
top-1 9/12, recall-at-10 10/12, abstention 10/20, wrong-code 0/7 returned codes
in exhaustive-label cases only, and zero explicitly forbidden outputs.
These are not clinical accuracy estimates. The draft HTN expansion is unsupported
by this lexical engine, pneumothorax is not top-ranked, and the new-code pre-release
case's desired status differs from the engine's `abstain`. Human adjudication is needed;
labels are not silently rewritten to match the engine.

Optional real-model draft, nine synthetic cases, **zero reviewed labels**:
top-1 4/5, recall-at-10 5/5, abstention 4/9, wrong-code 0/4 returned codes in exhaustive
cases only, zero explicitly forbidden outputs, and zero runtime errors.
The mixed diabetes case returned `E23.2` before expected `E11.9`, plus other alternatives.
That case is nonexhaustively labeled, so its extra outputs are excluded from the
wrong-code rate. Thus 100% recall and a zero reported wrong-code rate emphatically
do not mean correct or safe note coding. Preserve this gap for expert review rather
than interpreting draft retrieval metrics as validation.

The coding evaluator does not measure PII recall. The real PII model initially masked
only the local part of one synthetic email. Full-identifier matching fixes that example; general
PII misses and harmful redactions remain unmeasured.

Initial short-note worker: about 5.6 seconds and 684 MiB peak RSS, not a capacity SLA.
That memory alone exceeds Render Free's researched 512 MB tier.
The nine-case run measured approximately 4.5–8.5 worker seconds and up to 722 MiB
peak RSS. These fresh-process observations are not production load/cold-start guarantees.

## Independent review axes

- **Initial build review:** one P2 completeness-admission finding, fixed with observed failing/passing
  import tests for truncated Index and Tabular members and canonical-import regressions.
- **Subsequent current-code audit:** two P2 optional NLP findings (evidence offsets
  and omitted specificity review) and one P3 duplicated model-policy heuristic.
  All three were fixed after the user's approval.
- **Fresh focused follow-up, Standards and Spec reviewed independently:** no actionable
  findings in the fixes. This is not a broader security or clinical certification.
- External human, rights, image/runtime and cloud gates remain explicit, not self-certified.

## Final reproduction commands

```sh
# From the checked-out project directory:
uv run pytest -q tests --cdc-downloads /absolute/path/to/april-2026-archives \
  --fy2027-downloads data/releases/2027/sources \
  --openmed-models data/models/openmed-pilot \
  --openmed-python data/openmed-venv/bin/python
uv run ruff check src tests scripts
uv run ruff format --check src tests scripts
uvx pip-audit --disable-pip --no-deps -r requirements/core.lock
```

The documented `match-note` CLI example also passed end-to-end against real weights:
FY2027 `J18.9`, completed scan, full synthetic email/name preview masking and
`safe_to_upload=false`. No source note was edited.

## Unverified / external gates

- Docker daemon unavailable: no image build, non-root runtime, Linux install,
  image scan, container MCP or memory/load result is claimed.
- Container base tag is not digest-pinned; institutional distribution is gated.
- Model/dataset inherited terms are not independently cleared. No datasets downloaded.
- No clinician/coder gold-label approval, held-out clinical/PII validation or scoring
  method selection. Scoring remains disabled.
- No cloud accounts, deployment, public port/tunnel, Entra/OAuth tenant/client
  integration, private Azure routes/DNS, production acceptance or patient-data use.
