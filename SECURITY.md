# Security policy

This is a research prototype for public/synthetic terminology, not a
production, patient-data, de-identification or clinical-certification system.
The supported maintenance target is the latest repository revision; a hosted
deployment may run an older commit. No security response SLA is promised.

## Reporting

Use this repository's GitHub private vulnerability reporting **if available**.
If it is unavailable, open an issue requesting a private contact channel,
without exploit details, credentials, real patient information or private logs.
Provide only synthetic/public reproductions through the agreed private channel.
Do not probe other users' information or run load/abuse tests against the demo.

## Operating safely

- Core lookup is independent of optional OpenMed. Keep note/model workflows
  local and synthetic. Native cloud clients transmit arguments before hosted
  screening; screening never proves PII absence.
- Local HTTP binds to loopback. Use the explicit hosted launcher, an exact
  hostname and TLS termination for public hosting. Protected mode is the
  default; `ICD10_PUBLIC_ACCESS=1` intentionally permits anonymous access.
  A shared bearer token is not per-user OAuth or institutional authorization.
- Hosted tools are read-only and note-free. Never add note tools, filesystem
  commands or model runtimes to the anonymous deployment.
- Public admission defaults are per-process: 120 HTTP requests per fixed
  60-second window, four active requests, 8 KiB input and 256 KiB output.
  Health/readiness GETs bypass admission so hosting probes remain available.
- In the hardened repository code, the 15-second cooperative exchange deadline
  covers input, application work and response writes. A timeout before headers
  can attempt a generic 504 for at most one additional second. Rejection writes
  are bounded; a response already started is not restarted.
- The screened client requests identity encoding, rejects compressed or
  oversized remote responses, and caps streamed input at 256 KiB before SDK
  parsing. It rejects HTTP redirects before SDK processing, including same-origin
  path redirects; `follow_redirects=False` alone does not constrain the SDK.
  Its exchange has a 90-second cooperative deadline. Do not treat
  this as an OS sandbox or hard CPU/memory bound.
- Keep catalog imports pinned and verified. Do not bypass lockfile hashes,
  expose secrets in committed configurations, enable debug/access logs or
  assume upstream MCP validation errors are safe to disclose.

These controls are not DDoS protection, a distributed/monthly quota, a provider
billing cap or a complete security audit. Free hosting has shared allowances
and may suspend. Never add payment details, paid resources or upstream paid
APIs on the assumption that application rate limits guarantee zero charges.

## Deployment status

After separate operator approval, reviewed hardening commit `def06ee` became
live at `2026-11-09T02:13:41Z` (UTC). Nine public acceptance calls passed through
SDK HTTP, the CLI and local stdio bridge. The existing service remains Free,
Oregon, one instance, with automatic deployments disabled. No billing or resource
settings changed. This is technical acceptance, not a security certification.
See [deployment evidence](docs/verification.md#hardening-rollout).
