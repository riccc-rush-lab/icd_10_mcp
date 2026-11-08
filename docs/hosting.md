# Local first; hosting later

No cloud deployment, account access, public port, tunnel, PHI use or institutional
readiness is part of this build.

## Local MCP

Stdio is the default. Set absolute `ICD10_CATALOGS` to a release/path JSON map;
relative database paths resolve beside that file. Without it, `ICD10_CATALOG`
selects the existing April-only database. Startup rejects missing/mismatched catalogs
without creating a database or printing local artifact paths.

```sh
# From the checked-out project directory:
ICD10_CATALOGS="$PWD/data/catalogs.json" ICD10_TRANSPORT=streamable-http \
  ICD10_PORT=8000 .venv/bin/icd10-mcp
```

This launcher hardcodes `127.0.0.1`, not `0.0.0.0`. `/mcp` uses stateless Streamable
HTTP and JSON responses. Host/origin protection is enabled and HTTP bodies are capped
at 64 KiB. `/healthz` reports liveness; `/readyz` returns 503 if any configured catalog
fails read-only schema, provenance, identity or FTS readiness checks.
Readiness is artifact admission, not clinical approval or full rehashing on each probe.

HTTP exposes only `phrase_search` and note-free `validate_selected_codes`.
No OpenMed process or model is loaded. Stdio retains the three legacy deterministic
tools for compatibility; its synthetic-note tools are not OpenMed.
Access logging is disabled by the HTTP launcher. Do not enable debug/payload logging
or add proxies that capture arguments/results. Local loopback has no authentication:
other local users/processes may reach it. DNS protections are not authorization.

The official MCP client is tested in memory and the launcher is tested over loopback.
Institutional OAuth, actual end-user clients and private network routes are not tested.

## Portable core image, not a deployed service

`Dockerfile` includes only source, hashed core dependencies and both verified public
terminology databases. A context allowlist excludes archives, models, notes, virtual
environments and credentials. Builds run both release smoke checks and use UID/GID
10001 with read-only application files. The default is stdio, with no published port.

After Docker Desktop/another approved daemon is running, the unverified local checks are:

```sh
docker build -t icd10-local:trial .
docker run --rm -i --read-only --tmpfs /tmp:rw,noexec,nosuid,size=16m \
  --cap-drop=ALL --security-opt=no-new-privileges icd10-local:trial
```

Connect a local stdio MCP client to the second command for protocol tests. No `-p`
is needed. Recheck immutable-catalog behavior, non-root UID, dependency/image scans,
memory and client initialization. The base image tag must be pinned to an approved
digest before institutional distribution. The current image is **not build/runtime
verified** because the local Docker daemon was unavailable. Static files are not proof.

## Optional later Render Free terminology demo

Local-only preparation now includes a separate bearer-authenticated launcher,
Python MCP check client, source-only catalog builder and inactive native-Python
service example. See [Render demo preparation](render-demo.md). Nothing is deployed;
the existing local defaults and Docker contract are unchanged.

Do not deploy it now. Current researched constraints: 512 MB RAM, idle suspension
after 15 minutes, approximately minute-long cold starts, shared monthly runtime limits
and ephemeral storage. Usage overages may incur cost. A later demo would require
measured core-only memory/cold-start behavior, baked immutable catalogs, authentication,
appropriate host/origin and ingress configuration, approved actual-client testing and
separate permission. The default loopback-only launcher is deliberately not an
Internet-facing production entrypoint. The separate demo launcher uses shared-secret
access, not institutional OAuth or production readiness. OpenMed's measured memory
exceeds that tier.

Do not assume free Hugging Face CPU hardware means free creation of Docker Spaces.
See the dated [free-first research](research/free-first-local-openmed-hosting.md).

## Later private Azure migration gates

1. Choose approved tenant, region, contracts, identity/client and private networking.
2. Package the same verified stateless core catalog/runtime, without local note data.
3. Use a Container Apps **internal environment**, with app ingress enabled externally
   to that environment so approved VNet clients can reach it. App-internal ingress
   means something different and can block ordinary VNet clients.
4. Provide private DNS and VPN/ExpressRoute routes for the actual MCP client. A cloud
   assistant does not inherit the user's computer's VPN.
5. Configure Entra authorization, audience/scopes, issuer/tenant validation, expiration
   and credential handling; test the selected client's complete MCP OAuth workflow.
   Easy Auth alone does not prove MCP client compatibility.
6. Verify TLS, least privilege, request limits, no payload logs, monitoring, rollback,
   load/resource bounds, vulnerability scans and recovery with approved teams.
7. Obtain security/privacy, operations and clinician/coder sign-off before any PHI use.

No tenant-specific OAuth code or live Azure configuration is implied by this runbook.
Source details: [hosting/FY2027 research](research/hosting-and-fy2027-2026-11-07.md).
