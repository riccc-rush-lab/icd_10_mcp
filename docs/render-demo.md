# Render Free demo preparation

**Prepared locally, not deployed. Do not create a service or publish source without
separate approval.** This targets the Python MCP test client and public terminology
only. No clinical notes, OpenMed, patient data, institutional credentials or remote LLM.
The local stdio and loopback launcher's defaults are unchanged.

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
Its configuration follows the [Blueprint reference][blueprint]; the actual Render
schema, Linux runtime and deployment have not been exercised.

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
**not** establish successful live CDC acquisition from Render.

## Gates before any deployment

1. Obtain separate approval to publish the reviewed source and create the free service.
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
No account, billing settings or deployed service were accessed. [Limits][free]
[Pricing][pricing]

[blueprint]: https://render.com/docs/blueprint-spec
[free]: https://render.com/docs/free
[pricing]: https://render.com/pricing
