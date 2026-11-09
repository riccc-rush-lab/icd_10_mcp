# ICD10 Reference MCP on Render Free

**A terminology-only demo was deployed with separate user approval on 2026-11-08.**
This targets the Python MCP test client, not a browser search page. No clinical
notes, OpenMed, patient data, institutional credentials or remote LLM. The local
stdio and loopback launcher's defaults are unchanged. Additional deployments,
paid resources and source publication still require approval.

## Public no-login release: activated 2026-11-08

The user approved implementation, tests, GitHub publication and redeployment of
the **existing Free service only**, without paid resources or billing changes.
Source now supports explicit `ICD10_PUBLIC_ACCESS=1`; absent/`0` retains the
token-protected default. Other values fail startup. Both full catalogs are still
required. No signup or identity-provider dependency was added.

Public admission is per process: 120 HTTP requests/60 seconds, four active requests,
8 KiB input, 256 KiB output and a 15-second cooperative body/application deadline.
Minimal GET health probes bypass admission. Response limits replace oversized
results, not truncate coding instructions. These are abuse controls, not distributed
quotas, strict CPU/socket guarantees or a hosting bill cap.

The operator reports **no payment method linked**. Under
[Render's documented Free policy](https://render.com/docs/free), Free quota exhaustion
then suspends services rather than charging overages. Keep the workspace/resources
Free, with no paid add-ons/APIs or linked payment method. A pipeline spend limit
does not cap every billable category. Shared allowances mean heavy public use can
also suspend other Free services. Provider terms can change; no perpetual $0 or
availability guarantee is claimed, and billing status was not independently audited.

After browser authorization, `ICD10_PUBLIC_ACCESS=1` was set on the existing service.
Deployment `dep-dbofn15g1s2s73f2a7cg`, application commit `9aed9d9`, became live at
22:47:07Z. Ten sequential anonymous public tool calls passed in 3.528 seconds across
official SDK HTTP, the CLI and local stdio bridge. Checks covered both releases,
independent CDC descriptions, selected-code validity, the `C78.31` release boundary,
invalid codes, nonassignable headers and readiness. Native client GUIs were not tested.
The Free/Oregon/one-instance/auto-deploy-off settings were rechecked afterward.
No billing, old-service or unrelated-service changes were made.

The subsequent repository hardening bounds response writes and remote-client
response reads; **it has not been deployed**. This change was approved for commit
and GitHub push only. See [the security policy](../SECURITY.md) and
[connection instructions](connect.md).

## Original branded replacement, 2026-11-08

The MCP identity is now **ICD10 Reference MCP**. Render's supported service-update
controls did not expose a URL/slug rename. The user separately approved creating
a replacement **Free** service named `icd10-reference-mcp`, verifying its actual
endpoint, and only then suspending the old demo for rollback. No deletion, paid
upgrade or unrelated-service change is authorized.

- **MCP endpoint:** `https://icd10-reference-mcp.onrender.com/mcp`.
- Free, Oregon; service `srv-dbocb63l550s739ah2vg`, deployment
  `dep-dbocb63l550s739ah3cg`, application commit `e1090e6`.
  The clean native build became live at 18:56:47Z. Automatic deploys are off.
- Both five-check official MCP client runs passed across the September/October
  release boundary. Live checks also passed branding, two note-free tools,
  anonymous/wrong-token rejection, exact-date minimization, new-code release
  selection, malformed-code validation and the stdin phrase client.
- The old `icd10-terminology-demo` service is **suspended, not deleted**, for rollback.
  The unrelated existing service's configuration matches the pre-cutover record.
  No paid resource or billing change was made.
- The replacement uses a **new, separate secret**. On the original development
  computer, `.scratch/reference-upgrade-20261108/replacement-path.txt` points to
  its private deployment directory. The `icd10-demo-token` file inside is mode
  `0600` in a mode-`0700` directory. These files are ignored, not published.
  Load the token privately into `ICD10_DEMO_TOKEN`; never paste it into chat,
  URLs, command arguments or logs.
- The token was absent from 197 captured provider log entries. Eleven provider
  memory samples had a maximum of 62,615,550 bytes (about 59.7 MiB).
  Samples are not peak RSS, complete file-cache accounting or a capacity guarantee.

For arbitrary public terminology, use `icd10_mcp.reference_client` as documented
in the [Python/terminal and Claude Desktop connection guide](connect.md).
The guide covers token-free public mode and optional private-token compatibility;
neither needs local catalogs or models.
It screens before network initialization, blocks suspicious inputs
without echoing them, and sends a public release anchor instead of the exact date.
The two hosted tools also screen their code/phrase inputs as defense in depth.
These checks are best effort, not PII certification; server checks happen after
receipt. Do not enter patient data, even through this client or a cloud MCP chat.
Core lookup stays independent of local OpenMed/models.

## Historical protected-mode load measurement

The following measurement predates public admission limits. It does not measure
the current anonymous deployment's throughput. Do not repeat this old benchmark
against the public endpoint or treat 120 HTTP requests/minute as 120 tool calls.

`icd10_mcp.load_check` runs fixed public exact-code, phrase, header and selected-code
workloads through the screened client across the two public release anchors.
It uses levels 1, 2, 4 and 8, at most 300 tool calls and 120 seconds, plus a
1,000-HTTP-request cap and a 20 MiB response-body stop threshold. Health probes
and MCP initialization count toward the HTTP budget. It checks readiness before
each level and stops on HTTP/tool errors, unhealthy state or a budget limit.

Run only against an explicitly authorized target, with the token securely set:

```sh
.venv/bin/python -m icd10_mcp.load_check \
  --url https://your-approved-host.example/mcp --authorized-target \
  --max-calls 300 --max-concurrency 8 --seconds 120
```

The JSON report measures successful calls/second and p50/p95/p99 client latency,
including local screening and per-call MCP initialization. The benchmark shares
an HTTP connection pool; it is not a fresh TLS handshake for every lookup.
A passed level is an observation,
not maximum server capacity, concurrent-user capacity, a sustained-load result
or an SLA. This short benchmark does not measure the 15-minute idle cold start.

### Measured result

One approved run used 75.94 seconds and 1,000 HTTP requests, with 1,465,957
response-body bytes. It completed 247 calls. It then stopped at its own HTTP cap;
four client operations were budget-interrupted, not demonstrated service failures.

| Concurrent client operations | Completed calls | Calls/second | Successful-call p95 |
| --- | --- | --- | --- |
| 1 | 75 | 1.972 | 635 ms |
| 2 | 75 | 3.648 | 729 ms |
| 4 | 75 | 5.829 | 959 ms |
| 8 | 22, incomplete | Not a completed-level result | Not established |

**Four concurrent operations are the highest fully completed level, not the
service's maximum.** The partial eight-operation level is inconclusive because
the HTTP budget ended. Post-test readiness remained healthy. No extra load run
was performed. Use conservative concurrency and measure a representative workload
before making availability, maximum-capacity or production claims.

## Original trial, 2026-11-08 (now suspended)

- MCP endpoint: `https://icd10-terminology-demo.onrender.com/mcp`.
  Anonymous `/healthz` and `/readyz` return minimal operational status.
- Render Free, Oregon; service `srv-dbobjpbm8hqs7383rea0`, deployment
  `dep-dbobjprm8hqs7383rf1g`, source commit `432fd2c`. Automatic deploys are off.
  The fresh native Linux build installed the hashed core dependencies, downloaded
  the pinned CDC archives and built both release catalogs successfully.
- CLI 2.36.0 used browser authorization. Its `--env-var` flag takes values in process
  arguments, so the shared demo token was instead generated locally in a private
  Git-ignored deployment directory and uploaded as the secret file
  `/etc/secrets/icd10-demo-token`. A short Python start-command bootstrap reads
  that file into `ICD10_DEMO_TOKEN` before invoking the unchanged demo launcher.
  The local token file is mode `0600`, inside a mode `0700` directory. Do not paste
  its contents into chat, command arguments, URLs, source or logs.
- The generated client token is retained locally at
  `.scratch/render-deploy-<run>/icd10-demo-token`. Set the client's environment
  privately from that file before using the existing `demo_client` command below.
  Token rotation must update the provider's secret file and the client copy, then
  restart the service. This is shared demo access, not per-user authentication.
- Both five-check official Python MCP client runs passed, for `2026-09-30` and
  `2026-10-01`. Further live checks covered note-free tool discovery, the new
  `C78.31` release boundary, malformed inputs, unavailable dates without fallback,
  authentication, Origin/media/body limits and four simultaneous lookups.
- Render reported eight memory samples between 18:06:50Z and 18:10:20Z; the largest
  was 60,805,120 bytes (58 MiB). This is a sampled provider metric, not process peak
  RSS or a capacity guarantee. Four simultaneous warm lookups completed in 0.318
  seconds in one small check, not a throughput or latency SLA.
- The secret was absent from the 199 captured provider log entries. Existing
  services and billing settings were not changed. This workspace already had a
  free service, so free usage allowances are shared, not reserved for this demo.

Idle suspension/resume, sustained load, longer-term memory and billing behavior,
token rotation and an independent security review of the demo remain untested.
These checks do not establish clinical or patient-data readiness.

## What is prepared

- `icd10_mcp.demo`: separate terminology-only Streamable HTTP launcher. Two tools:
  `phrase_search` and note-free `validate_selected_codes`.
- `icd10_mcp.demo_client`: official Python MCP client with five fixed terminology
  checks, an explicit service date and no note/file/query-input option.
- `icd10_mcp.demo_build`: clean-build artifact preparation. It creates both verified
  catalogs from the existing importer, without committing databases or archives.
- `deploy/render.example.yaml`: inactive native-Python service example using the
  hashed core dependency lock. It is **not** the auto-discovered `render.yaml`.

The example disables commit-triggered deploys, but **does not prevent the initial
deploy when a service is created**. Merely preparing the file created no service.
Its configuration follows the [Blueprint reference][blueprint] and passed Render's
Blueprint validation on 2026-11-08. The live CLI deployment above uses a secret-file
bootstrap instead of the example's provider-generated environment variable. The
example remains inactive and is not linked to the deployed service.

## Authentication and transport

The demo requires `ICD10_DEMO_TOKEN` and one exact hostname. On Render the hostname
comes from `RENDER_EXTERNAL_HOSTNAME`; local tests can set `ICD10_DEMO_HOSTNAME`.
The example asks Render to generate a 256-bit base64 secret, not a source-code value.
For manual local testing, use a cryptographically random secret of at least 32
characters, stored outside source control. Do not paste it into chat, URLs, command
arguments, shell history or logs. Set the environment securely before running.

Every non-probe request requires a single `Authorization: Bearer ...` header.
Query parameters and duplicate Authorization headers do not authenticate. Wrong
credentials return a generic 401. GET `/healthz` and `/readyz` are intentionally
anonymous, minimal operational probes, not clinical status endpoints.

Host validation allows only the configured hostname. Origin validation permits an
absent Origin (the Python client) or that hostname's HTTPS origin. MCP bodies retain
the 64 KiB cap. Access logs are disabled; invalid media-type errors do not echo/log
the supplied header. Do not add proxy or debug logging that captures requests or tokens.

**This is shared-secret demo access, not OAuth, Entra, per-user authorization,
token expiry or a PHI safeguard.** Rotate the environment secret and restart if it
is exposed. No CORS/browser UI, public signup or desktop OAuth interoperability is
claimed. Limit sharing and usage; institution-ready authentication remains separate.

## Local verification

Use the already installed catalogs on the development computer. Set a secure
`ICD10_DEMO_TOKEN` in the environment first, then run from the project directory:

```sh
ICD10_CATALOGS="$PWD/data/catalogs.json" ICD10_DEMO_HOSTNAME=127.0.0.1 \
  PORT=10000 .venv/bin/python -m icd10_mcp.demo
```

The launcher defaults to **127.0.0.1**. Do not pass `--public-bind` locally. In a
second terminal with the same secret securely set:

```sh
.venv/bin/python -m icd10_mcp.demo_client \
  --url http://127.0.0.1:10000/mcp --date 2026-10-01
```

The client checks tool discovery, E11.9, pneumonia/J18.9, the E11 nonassignable header
and selected-code validity. The JSON report contains no secret. A successful check
returns exit 0 and `status="passed"`; clinical/patient-data flags remain false.
Failure returns exit 2 with a generic report, not raw exceptions or credentials.

The CLI accepts plain HTTP **only for literal localhost/127.0.0.1**. Remote endpoints
must use HTTPS `/mcp`, without URL credentials, query strings or fragments. Proxy
environment settings are ignored. The pinned SDK applies its same-origin redirect
policy; no arbitrary cross-origin credential-forwarding behavior is promised.
Per-request timeout is 90 seconds, with a 180-second overall check timeout to allow
for a possible cold start, not to guarantee Render/client availability.

## Source-only build

The existing Dockerfile copies local databases and remains a separate, unverified
container contract. The proposed Render native build instead installs the hashed
core dependencies and explicitly downloads the four pinned complete CDC archives
**during build**, imports them, runs 28 smoke checks per catalog and removes database
write permissions. Runtime startup never downloads terminology or models.

`demo_build --download` accepts only the fixed official HTTPS CDC source paths.
Redirects stay on the publisher host, transfers have a socket timeout and a 64 MiB
per-archive limit, and exact SHA-256 archive pins are checked before import. The
ordinary importer separately enforces its seven member pins per release, XML/code/
order consistency and atomic no-overwrite database publication. These observed
checksums are not publisher signatures or independent authenticity certification.

To test without network access, select a **new, nonexistent output directory**:

```sh
.venv/bin/python -m icd10_mcp.demo_build \
  --april-downloads /absolute/path/to/april-2026-archives \
  --fy2027-downloads /absolute/path/to/fy2027-archives \
  --output /absolute/path/to/new-demo-artifacts
```

Never run the example's `--output data` against this computer's existing `data/`.
Existing output directories are refused, not deleted or overwritten. Failed builds
may leave partial artifacts in the newly created directory, but do not publish
`catalogs.json`. Retry into a new directory or use an explicitly approved clean build.

A fresh source checkout is required for the proposed Render build. Both catalogs
are build artifacts, about 319 MiB combined in the working installation, not a
separate hosted database. Free local filesystem changes do not survive lifecycle
events; rebuild artifacts rather than updating SQLite at runtime. [Free limits][free]

Tests use actual archive bytes and the real importer/SDK. Download-mode tests supply
those bytes through an external HTTP adapter and test failure/size limits; they do
**not by themselves** establish successful live CDC acquisition. The separately
verified deployed trial above supplies that operational evidence.

## Deployment and future-change gates

1. Obtain separate approval to publish source and create resources. The initial
   source push and free-service deployment received separate approval; that does
   not authorize a paid upgrade or additional deployment.
2. Confirm repository access, workspace free-plan eligibility, billing/usage limits
   and whether the exact Python/native build settings are supported.
3. Perform the fresh Linux build and real pinned CDC downloads. Confirm provenance,
   immutable artifacts, startup, health-check Host handling and exact HTTPS hostname.
4. Review secret access, rotation, TLS, proxy logging and host/origin behavior.
   Run the chosen Python client with absent/wrong/correct credentials.
5. Measure cold start, reconnect behavior, concurrent requests and **actual Linux/
   Render memory including file cache**, not just macOS Python RSS.
6. Recheck dependency/security findings and a rollback/rebuild procedure. No notes,
   patient data or patient-derived search terms, even if a token is present.

Render Free lists 512 MB RAM, idle suspension after 15 minutes, approximately
minute-long resume, 750 shared monthly instance hours, ephemeral files and additional
usage limits. It is not intended for production or guaranteed always-on/zero-cost
operation. Keep OpenMed local: the measured configuration exceeds that memory tier.
The initial preparation accessed no account or deployed service. The later
approved CLI deployment is recorded above; billing settings were not changed. [Limits][free]
[Pricing][pricing]

[blueprint]: https://render.com/docs/blueprint-spec
[free]: https://render.com/docs/free
[pricing]: https://render.com/pricing
