# Technical verification

This records technical checks and deployment evidence, not clinical/privacy acceptance.
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
- Most recent full opt-in suite (2026-11-08): **249 passed in 190.87 seconds**;
  the focused hardening/licensing and earlier deployment evidence are recorded below.
- Earlier full opt-in suite (2026-11-07): **205 passed in 101.63 seconds**, including both fresh
  corpus imports, partial-XML rejection, actual local model weights and MCP transports.
  This run followed local-only Render preparation and its 19 demo/build checks.
  The previous 186-test run covered the local-trial command and its eight CLI checks.
  The previous 178-test run followed the NLP audit fixes and shared model-policy refactor.
  The earlier 172-test run followed the importer fix and Starlette upgrade to 1.10.0.
- Latest Ruff lint and formatting passed across all 50 files in `src`, `tests`, and `scripts`.
- The initial core dependency audit failed on Starlette advisories. The patched,
  regenerated `requirements/core.lock` audit then reported no known vulnerabilities.
  The separate OpenMed lock audit earlier in this build also reported no known
  vulnerabilities. These are historical build-time results, not fresh audits for
  the current hardening. Neither is a security certification.
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

## Source publication and Render trial, 2026-11-08

- Source commit `432fd2c` was pushed to public
  `riccc-rush-lab/icd_10_mcp/main` after Write access was granted. Catalogs, source
  archives, weights, environments, credentials and local reports remained excluded.
- After a separate hosting comparison, the user selected Render Free, approved
  CLI installation and completed browser authorization. CLI 2.36.0 selected the
  sole workspace; the inactive example passed Render's Blueprint validation.
- Created only `icd10-terminology-demo`, service `srv-dbobjpbm8hqs7383rea0`, on the
  Free plan in Oregon, with automatic deploys disabled and `/readyz` health checks.
  Initial deployment `dep-dbobjprm8hqs7383rf1g` built successfully on Linux and
  became live using the reviewed commit. Its clean build installed the hashed
  core lock, downloaded the pinned public CDC archives and built both catalogs.
- A generated token was stored in an ignored private local directory and uploaded
  as a Render secret file. The start-command bootstrap reads it into the demo's
  environment, avoiding a secret-valued CLI argument. Local loopback checks of
  this bootstrap passed for both releases; that local process was stopped.
- Live endpoint: `https://icd10-terminology-demo.onrender.com/mcp`. Both official
  client runs passed five checks each for `2026-09-30` and `2026-10-01`, including
  exact code, phrase, nonassignable header and selected-code validation.
- The final report passed 21 named verification gates (including grouped client
  checks), not 21 independently adjudicated clinical cases. Further controls
  confirmed exactly two note-free tools, correct `C78.31` release-boundary behavior,
  malformed-code rejection, `invalid_request` for malformed dates, and
  `release_unavailable` with no fallback for an unavailable date.
- Missing/wrong/query-only credentials returned 401; duplicate Authorization was
  rejected with 400 at the hosted boundary. Foreign Origin returned 403, non-JSON
  POST media returned 400 and a 65,537-byte body returned 413. Minimal anonymous
  health/readiness probes passed. Four simultaneous E11.9 lookups preserved their
  requested release identities and completed in 0.318 seconds in one warm check.
- Initial ad hoc verifier runs failed due to incorrect expectations: 415 instead
  of the established non-JSON 400 response, and empty candidate lists instead of
  date-error envelopes without candidate/release fields. The verifier was
  corrected against those existing contracts; no application code changed.
- Render's memory API returned eight samples between 18:06:50Z and 18:10:20Z,
  with a maximum observed 60,805,120 bytes (58 MiB). Sampling is not peak RSS,
  exhaustive file-cache accounting, sustained capacity or a production SLA.
  The shared token was absent from the 199 captured provider log entries.
- Detailed reports and the mode-0600 token remain under the ignored private
  `.scratch/render-deploy-20261108-yng6ia4g/` directory. No existing service or
  billing setting was modified. Another free service already existed; account
  usage allowances remain shared and are not a guarantee of a zero bill.
- This was an operational trial of unchanged application code. The full test
  suite and Ruff were not rerun. Idle suspension/resume, sustained concurrency,
  long-term memory/billing, token rotation and an independent demo security review
  remain unverified. OpenMed stayed local; clinical/patient-data readiness is false.
  Deployment documentation was updated locally, not committed or pushed again.

See `docs/render-demo.md` for the deployed configuration and remaining restrictions.

## Reference branding and privacy upgrade, 2026-11-08

- Public MCP identity: `ICD10 Reference MCP`. Existing tools, local lookup and the
  optional synthetic-only OpenMed workflow are retained.
- The new local reference client blocks the tested email/phone/SSN/DOB/MRN,
  name-shaped, address, URL, control-character and note-context examples before
  any HTTP request. All fixtures are synthetic. Ordinary/eponym phrases still
  reach the real application. Selected-code fields and numeric limits are checked
  before connection; errors do not echo the tested private markers.
- Exact service dates are mapped locally to public release anchors; the tested
  original date does not appear in recorded outbound traffic. Unsupported dates
  do not select a fallback. Static client identity avoids sending the hostname.
- Hosted note-free tools block suspected identifiers as defense in depth, **after
  receipt**. Best-effort rules have false positives/negatives; no general PII recall,
  arbitrary-client privacy, patient-data readiness or clinical validation is claimed.
- A stdin-only client command avoids query/token command arguments. Its malformed
  argument errors are sanitized. JSON note/extra fields are rejected locally.
- The fixed-public-workload benchmark rejects excessive budgets before network,
  exercises the real SDK/application, reports client latency and stops before
  raising concurrency when readiness fails. The bounded live result is recorded below.
- Observed failing/passing public-interface slices covered MCP branding, local
  identifier rejection, date minimization, code preflight, unsafe configuration,
  hosted screening, the stdin command, invalid limits and the bounded benchmark.
  Eponym coverage passed immediately and is a guard, not an invented red.
- No clinical or patient-data acceptance follows from a successful technical test
  or deployment.
- The initial upgrade passed **219 full opt-in tests in 149.16 seconds**.
  Independent review then found two gaps: framework errors could echo malformed
  tool arguments, and stalled readiness requests could exceed the load deadline.
  Both were reproduced with failing public tests and fixed. Raw hosted arguments
  are now screened before framework validation; schema errors remain generic MCP
  tool errors. Readiness waits now use the remaining absolute deadline.
- Standards review found no hard violations and one duplicated-parser heuristic;
  the shared sanitized CLI parser removes that duplication.
- After those fixes: **197 default tests passed, 24 explicitly skipped in 10.01
  seconds**. Ruff lint/format passed across 44 files. The final full opt-in rerun
  passed **221 tests in 155.73 seconds**, including both fresh CDC imports, actual
  local model weights and MCP transports. Reviews are not a security certification.

## Branded replacement, bounded load and cutover, 2026-11-08

- Reviewed application commit `e1090e6` was pushed and deployed as the replacement
  `icd10-reference-mcp`, service `srv-dbocb63l550s739ah2vg`, deployment
  `dep-dbocb63l550s739ah3cg`. The initial native build became live at 18:56:47Z.
  It uses the Free plan, Oregon, one instance, automatic deploys off and `/readyz`.
- Active endpoint: `https://icd10-reference-mcp.onrender.com/mcp`.
  A separate generated secret was uploaded as a secret file, not a secret-valued
  CLI argument. No database, archive, weights, secret or local report was published.
- Both five-check official-client runs passed for 2026-09-30 and 2026-10-01.
  Further live checks passed minimal probes, missing/wrong credentials, professional
  MCP identity, two note-free tool schemas, the screened client's date anchor,
  `C78.31` release selection, malformed-code validity and the stdin phrase command.
- One fixed-public-workload load run used **75.94 seconds, 1,000 HTTP requests and
  1,465,957 response-body bytes**. It completed 247 calls. Full levels 1/2/4 each
  completed 75 calls without errors, at 1.972/3.648/5.829 calls per second and
  p95 635/729/959 ms. These include screening and per-call MCP initialization,
  with a shared HTTP connection pool, not raw server throughput.
- The eight-operation level completed 22 calls before the HTTP cap interrupted
  four client operations. The result is `stopped` / `http_request_limit`, not a
  passed 300-call run or evidence of a service failure. Eight-operation capacity
  is inconclusive; four is the highest fully completed level, not a maximum/SLA.
  No extra load run was made. Post-load readiness returned 200 and `ready`.
- Eleven provider memory samples had maximum 62,615,550 bytes (about 59.7 MiB).
  An initial query using fractional/offset timestamps was rejected; UTC `Z`
  timestamps succeeded. This was a measurement-query correction, not an app change.
  Samples do not establish peak RSS, exhaustive cache use or sustained capacity.
- The replacement token was absent from 197 captured provider log entries.
  After successful functional verification and healthy post-load checks, the
  approved suspension returned 202; the old service then reported `suspended`.
  Nothing was deleted. Its original configuration/secret remain for rollback.
  The unrelated service's configuration matched the pre-cutover record.
- Detailed reports and token remain in the ignored private deployment directory
  referenced by `.scratch/reference-upgrade-20261108/replacement-path.txt`.
  Paid plans and billing settings were not changed. Shared free allowances,
  idle resume, sustained load, rotation, institutional auth and an independent
  security/clinical review remain outside this technical acceptance.

## Connection handoff and continued functional checks, 2026-11-08

- [Connection guide](connect.md) covers hosted access, Python/terminal and manual
  Claude Desktop configuration. Public source does not grant hosted access; the
  shared-secret service remains an operator-approved trusted-pilot demo.
- A local stdio bridge uses the existing screened remote client, without local
  catalogs or models. Its checked-in macOS configuration arguments were exercised
  through a real subprocess and the official MCP SDK from an unrelated directory.
  Identity, exactly two note-free tools, local blocking with zero HTTP requests,
  release-anchor date handling, public lookup and selected-code validation pass.
- Private-file credentials are bounded to 4 KiB. Public CLI guards cover an
  absolute regular file, POSIX permissions, a symlink, oversized content, relative/
  missing/directory paths and no secret/path-marker echo. Owner checks are
  implemented, but a different-owner runtime case was not independently exercised.
  Windows ACLs are not validated and Windows runtime acceptance remains untested.
- File-based CLI admission and the bridge workflow were observed failing then
  passing. A further real-stdio test reproduced malformed-argument identifier echo
  from framework validation. Hosted and bridge transports now share the existing
  raw-argument guard before coercion; wrong types and extra/note fields return
  generic errors without echo or outbound requests. Startup and configuration
  template guards that passed immediately are hardening, not extra observed reds.
- Final full opt-in suite: **226 passed in 194.03 seconds**, with both fresh CDC
  imports, actual optional model weights and transports. Default suite:
  **202 passed, 24 skipped in 22.83 seconds**. Ruff lint/format pass across 48 files.
- One additional **sequential functional check**, not another load benchmark,
  completed **50 tool calls in 50.503 seconds**, concurrency one, within its
  50-call/120-second bound. Forty cases checked 20 public assignable codes across
  September 30 and October 1 against descriptions read independently from the
  pinned CDC code text, not the service/database being tested.
- That check also verified release IDs, hierarchy/provenance presence, poisoning
  instructions, nonassignable `E11`, malformed `A00..1`, selected-code validity,
  the `C78.31` release boundary, and two actual hosted calls through the stdio
  bridge. Its stderr did not contain the token. Inputs were public terminology only.
  Private evidence is in `.scratch/reference-upgrade-20261108/connection-*` and
  `real-code-expected.json`; credentials and local reports are not published.
- The hosted application remains deployment `dep-dbocb63l550s739ah3cg`, commit
  `e1090e6`; automatic deploys are off. This handoff does not redeploy, change auth,
  create resources, repeat load testing or change billing.
- Fresh independent Standards and Spec reviews of the staged connection changes
  against `7c9bccc` each returned zero actionable findings. These are focused
  implementation reviews, not security or clinical certification.
- Actual Claude Desktop UI/version acceptance remains a manual gate. Local bridge
  screening cannot undo text already processed by a chat provider. No patient-data,
  clinical, institutional-auth or broader security acceptance is implied.

## Public access implementation, 2026-11-08

- Approved scope: implement/test/push/redeploy only the existing Free MCP, no
  billing or paid-resource changes. Operator confirms no payment method linked.
  The zero-spend condition depends on provider billing configuration and accepting
  quota shutdown, not a promise that rate limits prevent bills.
- Public mode is opt-in (`ICD10_PUBLIC_ACCESS=1`); protected mode remains default.
  Same two read-only note-free tools and raw argument privacy guard; local core
  remains independent of hosted authentication and optional NLP.
- Local public HTTP cases pass: real official-SDK anonymous lookup/validation,
  malformed-argument no-echo, shared request quota/reset with live health probes,
  declared/chunked body limits, oversized response replacement without partial
  output, in-flight rejection/release, and stalled-body deadline/release.
  The first SDK test initially used an official description against a declared
  synthetic fixture; its literal expectation was corrected to the fixture source.
  This was a test-fixture correction, not a clinical-label adjudication.
- Anonymous library calls preserve local screening/date anchors and send no
  Authorization header. Explicit anonymous CLI ignores inherited credentials.
  The checked-in token-free desktop arguments pass actual stdio exchanges against
  both anonymous and protected loopback servers; blocked input produces zero HTTP.
- Fresh verified real-catalog builds launch in both protected and public mode.
  The public subprocess starts without any token and the actual anonymous CLI
  returns FY2027 `C78.31`. Both launcher cases passed in 33.87 seconds.
  Public admission, client, CLI, bridge and launcher additions were each observed
  failing then passing at the public seams; no owned mocks or SQL test side channels.
- Initial full corpus/model suite: **236 passed in 186.82 seconds**.
  Standards review found zero hard violations or actionable smells. Independent
  Spec review found SDK-generated HTTP protocol errors could still echo malformed
  envelope/header values. A new public HTTP regression reproduced that leak;
  public HTTP error bodies are now replaced with generic responses before release.
  The test also verifies no marker echo in captured application logs.
  The focused Spec re-review verified the actual malformed envelope/header cases
  and successful initialization, marked the issue resolved, and found no remaining
  high-confidence issues. This is not a broader security certification.
- After the fix, default suite: **212 passed, 25 opt-in skips in 21.38 seconds**.
  Final full corpus/model rerun: **237 passed in 211.38 seconds**, including fresh
  imports and actual local model weights. Private log:
  `.scratch/public-access-20261108/final-full-tests.log`.
  Ruff lint/format pass across 50 files. No dependency or model changes.
- Public limits: 120 HTTP requests/60-second fixed window, four active requests,
  8 KiB input, 256 KiB output, 15-second cooperative input/application deadline.
  Health probes are exempt; state resets on restart. This is not a distributed
  quota, hard CPU bound, socket-write deadline, monthly budget or provider bill cap.
- At that implementation stage, deployment awaited Render authorization and the
  previous protected build was still live. Subsequent activation is recorded below.
  No extra load test or actual Claude UI/Windows runtime acceptance was claimed.

## Public activation, 2026-11-08

- After separate browser authorization, the existing Free service received
  `ICD10_PUBLIC_ACCESS=1`. Deployment `dep-dbofn15g1s2s73f2a7cg` made the tested
  commit `9aed9d95177602ec9d29e21b67108d6191e98a94` live at 22:47:07Z.
- One reserved acceptance run passed ten sequential anonymous public tool calls
  in 3.528 seconds through official SDK HTTP, the project CLI and local stdio bridge.
  Independent CDC descriptions matched for `E11.9` and `J18.9` across both release
  dates. Selected-code checks verified the `C78.31` release boundary, malformed
  code handling and nonassignable headers. Readiness returned 200/ready, exactly
  two read-only note-free tools were discovered, and direct SDK traffic sent no
  Authorization header. CLI ignored an invalid inherited token; the bridge ran
  without a token file. Private evidence:
  `.scratch/public-access-20261108/activation-acceptance-report.json`.
- Free/Oregon/one instance/automatic deploys off were rechecked after deployment.
  No paid resource, billing, old-service or unrelated-service change was made.
  No load test or native client GUI acceptance followed from these checks.

## Focused MCP hardening and licensing, 2026-11-08

- User chose Apache-2.0, copyright/attribution **JC Rojas**, focused MCP work on
  main, and commit/push only. This is not a whole-repository security audit.
- The admitted request deadline now covers response writes as well as body/app
  work. Stalled header/body transports release capacity, never start a second
  response, and temporary rejection writes have a bounded budget. A pre-header
  timeout can attempt a generic 504 for at most one additional second.
- The screened client's upstream response stream is capped at 256 KiB before SDK
  parsing. Oversized/malformed declared lengths and compressed responses are
  rejected before body reads; it requests identity encoding and closes rejected
  streams. Supervision aborts rejected exchanges even when the SDK swallows a
  parser exception; the whole exchange has a 90-second cooperative deadline.
- External ASGI/HTTP adapters reproduced the stalled-write and oversized-response
  gaps before the corresponding fixes. The first oversized-response fixture was
  invalid JSON and stalled SDK initialization, so it was corrected to a valid,
  oversized MCP initialization response before observing the intended overread.
  Four stalled-send cases and four upstream-budget cases now pass. No owned mocks,
  private-helper assertions, database side channels or patient inputs were used.
- Initial default suite: **220 passed, 25 opt-in skips in 22.27 seconds**.
  Ruff lint and formatting pass across 50 files. The offline uv lock check passes;
  runtime dependency versions/hashes and optional model assets are unchanged.
- The initial full corpus/model rerun passed **245 tests in 207.21 seconds**.
  Independent Standards review found no actionable violations or smells. Spec
  review then reproduced a pre-existing redirect-policy gap: MCP 1.30 follows
  same-origin redirects independently of HTTPX's `follow_redirects=False`.
  Four external-HTTP regressions failed before the fix, confirming redirected
  paths were contacted. The client now rejects 3xx responses in its response
  guard, before SDK redirect handling; the 51 targeted MCP/client tests pass.
- After the redirect fix, the default suite passes **224 tests with 25 opt-in
  skips in 27.70 seconds**; Ruff lint/format and the offline lock check pass.
  Final full corpus/model rerun: **249 passed in 190.87 seconds**. Standards
  re-review found zero actionable breaches/smells; Spec re-review confirmed the
  redirect finding resolved with no remaining focused-review issue.
- LICENSE, NOTICE, third-party scope notices, citation metadata and Python package
  metadata credit JC Rojas. Original code is Apache-2.0; third-party data,
  dependencies and model assets retain separate terms. No worldwide corpus or
  training-data rights clearance, mandatory academic citation or endorsement is
  asserted. [SECURITY.md](../SECURITY.md) records safe reporting and residual limits.
- Offline wheel/sdist builds passed. Both artifacts carry `Author: JC Rojas`,
  `License-Expression: Apache-2.0` and the three exact license/notice files.
  The 34-file wheel and 86-file sdist exclude ignored data/model/secret paths.
  Canonical license words match the standard Apache text; citation YAML parses,
  and 30 relative documentation links resolve. This is not a complete third-party
  rights or secret-disclosure audit.
- At initial source publication, no new deployment was authorized and the live
  application remained `9aed9d9`. The subsequent authorized rollout is below.

## Hardening rollout

- The user subsequently requested deployment and repository fixes. Existing
  service `srv-dbocb63l550s739ah2vg` received reviewed commit
  `def06eefb9ce298fdcdf42bfb1c057bfdc17053d`, deployment
  `dep-dboinu8u01pc73fd5big`, live at `2026-11-09T02:13:41Z` (UTC).
- One separately reserved public-only acceptance run passed all **nine tool
  calls in 4.161 seconds** through SDK HTTP, the anonymous CLI and local stdio
  bridge. Readiness was 200/ready; the expected identity and exactly two read-only,
  note-free tools were discovered. Independent CDC descriptions matched for
  `E11.9` across both releases and `J18.9` for FY2027; selected-code validation
  verified the `C78.31` release boundary. Nonassignable headers and malformed codes
  behaved correctly. CLI/bridge date-minimization flags passed; the CLI ignored
  an invalid inherited token. The direct SDK counter recorded 11 HTTP requests
  and zero Authorization headers; it does not count subprocess HTTP traffic.
- Private report:
  `.scratch/rollout-dep-dboinu8u01pc73fd5big/acceptance-report.json`.
  No extra load test, patient input, native client GUI check or clinical
  acceptance was performed. Source commit `def06ee` already passed 249 full
  corpus/model tests; those were not rerun for this documentation-only follow-up.
- Repository docs now distinguish current anonymous hosting from the protected
  default, document the correct 8 KiB/64 KiB request limits and remove stale
  not-deployed claims. Apache-2.0/JC Rojas attribution remains unchanged.
- Post-rollout provider reads confirmed Free/Oregon/one instance, `/readyz`,
  automatic deploys off and `ICD10_PUBLIC_ACCESS=1`. No service configuration,
  billing, old-service or unrelated-resource write was made. Documentation checks
  passed for 29 relative links and four rollout anchors.

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

- Docker daemon unavailable: no image build, non-root runtime, Docker-specific Linux install,
  image scan, container MCP or memory/load result is claimed.
- Container base tag is not digest-pinned; institutional distribution is gated.
- Model/dataset inherited terms are not independently cleared. No datasets downloaded.
- No clinician/coder gold-label approval, held-out clinical/PII validation or scoring
  method selection. Scoring remains disabled.
- No Entra/OAuth tenant/client integration, private Azure routes/DNS, production
  acceptance or patient-data use. The separately authorized public Render trial is
  recorded above; it does not resolve these institutional gates.
