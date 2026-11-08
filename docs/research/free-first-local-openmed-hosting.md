# Free-first hosting with local OpenMed NLP and PII

Research date: 2026-11-07. Scope: design recommendation, not a deployment.

## Recommendation

**Run the complete first trial on the user's computer.** It avoids a hosting bill,
keeps note extraction and PII detection out of external services, and preserves the
existing ordinary Python/SQLite MCP design. Begin with wholly synthetic input only.
The current application and a new NLP adapter are not clinically or PHI validated.

Proposed local flow:

```text
Synthetic note in a local CLI
  -> local OpenMed clinical extraction and context candidates
  -> local OpenMed PII findings / redaction preview
  -> local CDC-backed, service-date-specific ICD-10-CM lookup
  -> code validation, source evidence, review or abstention
```

PII scanning and extraction can inspect the same original text locally; keep source
offsets meaningful and do not assume redacting dates first preserves clinical context.
Do not send notes, redacted notes or patient-derived concepts to an external demo.
Local model execution alone does not make a cloud-connected MCP client/model private.

OpenMed implements NER/PII, limited deterministic context, relation candidates and
terminology grounding against supplied resources. Its current SDK is Apache-2.0,
not MIT; model and dataset terms require separate review. This supports an optional
extraction module, not replacing the authoritative ICD-10-CM catalog or certifying
correct patient-level assignments. See [OpenMed source][openmed] and the more detailed
`openmed-feasibility.md` in this directory.

## A genuinely free external terminology demo

**Render Free is the preferred candidate for a later, small synthetic-data
terminology-only demo**, subject to actual memory, startup and MCP-client tests.
This is a fit recommendation, not a successful deployment claim.

Verified from first-party docs:

- Free web services are available. Render explicitly says not to use them for
  production applications. They have **512 MB RAM**; pricing lists custom Docker
  container support. Do not assume this can host the NLP stack. [Free][render-free]
  [Pricing][render-pricing]
- They suspend after **15 minutes** without inbound traffic and take approximately
  **one minute** to resume. That can interrupt an MCP client's first connection;
  measure and document the real behavior. Do not promise always-on availability.
  [Free][render-free]
- Local filesystem changes disappear on restart, redeploy or idle suspension. Free
  services cannot attach persistent disks. Package verified catalogs as immutable
  image/build artifacts instead of importing or modifying them at runtime.
  [Free][render-free]
- A workspace receives **750 free instance hours per month**, shared across its free
  web services. Bandwidth and build limits also apply. With a payment method,
  supplementary usage can incur charges; without one, applicable services/builds
  are suspended or disabled when limits are reached. Review account settings rather
  than promising unlimited zero-cost use. [Free][render-free]
- Free web services cannot receive private-network traffic, so this is not a
  private institutional deployment substitute. Application authentication, a no-PHI
  policy and separate approval for Internet exposure are still needed.
  [Free][render-free]

No Render account was accessed or created; no service was published. Do not select
a paid upgrade or submit content to a hosting provider without user authorization.

## Why not assume Hugging Face Docker Spaces is free?

The current official overview distinguishes free **CPU Basic hourly compute** from
permission to create a compute Space. It says creating **Gradio or Docker Spaces
requires a paid plan** (PRO for a personal account, Team/Enterprise for organizations).
It also describes a limited exception allowing eligible free personal accounts up
to two **Gradio ZeroGPU** Spaces. That is not the same as a free portable Docker MCP
server. Static Spaces are free but do not run this Python/SQLite server.
[Spaces overview][hf-spaces]

This was checked in the full official overview, including its hardware and creation
sections, not inferred from a search snippet saying CPU Basic is free. Terms may
change; recheck before deployment.

## Migration sequence

1. Approve the revised local trial and public test seams.
2. Verify model/dataset terms and dependency compatibility in an isolated optional
   NLP environment. Pin artifacts and enforce offline inference; measure performance
   on synthetic inputs before making resource or accuracy claims.
3. Complete the versioned catalog and evaluation work, keeping drafted labels
   explicitly unreviewed and scoring disabled.
4. If external sharing is wanted, separately approve and test a **terminology-only**
   container demo on Render Free. Keep NLP/PII local and use synthetic traffic only.
5. Move the same terminology module/container contract to institution-approved Azure
   Container Apps with private access and tested Entra authorization. Decide whether
   NLP stays local or moves into approved infrastructure only after privacy/security
   review. See `hosting-and-fy2027-2026-11-07.md`.

Research created no source/test changes and ran no model inference.

[openmed]: https://github.com/maziyarpanahi/openmed/tree/v3.1.0
[render-free]: https://render.com/docs/free
[render-pricing]: https://render.com/pricing
[hf-spaces]: https://huggingface.co/docs/hub/spaces-overview
