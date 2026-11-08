# NVIDIA Auto Ontology: does it help if we host data?

**Research date:** 2026-11-07. **Decision: not for hosting our current terminology service; potentially useful later as a semantic analytics layer over already hosted databases.** This is a fit assessment, not integration, deployment approval, a security audit, or clinical validation.

## The important distinction

| Need | Fit and recommendation |
| --- | --- |
| **Host our application and its small public terminology databases** | **No immediate benefit.** Auto Ontology itself needs deployment and persistent services; it is not a substitute for a cloud hosting platform. Its deployment guide describes application images and a Kubernetes Helm chart that an operator installs. Keep our existing local-first approach and evaluate terminology-only hosting separately. [Deployment][deployment] [Current project hosting][local-hosting] |
| **Ask semantic/natural-language questions across already hosted research databases** | **Potentially useful later.** This is its actual remit: extract metadata, propose business concepts/relationships, let people review/certify them, and generate SQL through a UI/API/MCP layer. Connectors include PostgreSQL, SQLite, DuckDB, Databricks and Snowflake; SQLite/DuckDB are connection-string paths, not UI-added connections. [README][readme] [Connections][connections] |
| **Extract diagnoses from notes or assign authoritative ICD-10-CM codes** | **Not established by the reviewed evidence.** Enterprise ontology discovery and text-to-SQL are different tasks from clinical entity recognition, contextual interpretation and coding-rule application. Do not infer clinical mapping accuracy from SQL benchmarks or human “certification” of business metadata. Keep our CDC catalogs and validators authoritative. [README][readme] [Current lookup contract][local-readme] |

**Project baseline:** we already have frozen CDC April 2026 and FY2027 SQLite catalogs, date/release-aware exact/codephrase lookup, CLI/MCP access, and separate optional synthetic-only OpenMed experiments. This is not a clinically validated or PHI-ready system. The current hosting runbook remains local-first, with a possible later terminology-only Render demonstration and an eventual approved private Azure/Entra deployment—not an existing cloud deployment. Auto Ontology does not remove those approval or operational gates. [Current lookup contract][local-readme] [Current hosting runbook][local-hosting]

## What the primary sources actually establish

1. **Extra infrastructure, not simpler hosting.** The README describes Docker Compose/Helm deployment and a PostgreSQL/pgvector-backed ontology store; the deployment guide publishes backend/ingestion, frontend and MCP images plus a Helm chart. Adopting it adds a writable metadata system, ingestion scheduling, identity/secrets administration and model dependencies to our current immutable-catalog service. Budget for persistent storage/backups, patching, monitoring, ingestion/query compute and model usage; no resource sizing or dollar estimate was verified. Hosted inference means GPUs are **not inherently required on our application host**; choosing self-hosted models creates a separate hardware/capacity decision. [README][readme] [Deployment][deployment] [Environment example][env]

2. **Ingestion is not a metadata-only privacy boundary.** The README describes profiling/sample values; the environment example explicitly describes source “schema + rows” being extracted into the local pgvector store. Thus “the database stays hosted elsewhere” does not mean no source data is copied. The example schedules ingestion at startup and every 24 hours. Before any sensitive connection, inventory sampled values, profiles, derived descriptions/embeddings, stored query/conversation content, logs and backup copies; their exact payloads and retention were not verified here. [README][readme] [Environment example][env]

3. **Self-hosted application does not mean local-only inference.** The example defaults reasoning/non-reasoning and embedding configuration to NVIDIA API-catalog models, with `https://integrate.api.nvidia.com/v1` as the shared default endpoint, and separate reranking configuration. Endpoint/key/model settings are configurable; the README documents self-hosted/OpenAI-compatible alternatives. Treat questions, schema descriptions, sample values and any query results used in model context as potential outbound disclosures until each actual pipeline payload is traced. This review confirms configuration defaults, **not** that every row or every result always reaches a model. Redirecting only the main chat model is insufficient: check embedding, non-reasoning and reranking endpoints and fallback settings too. [Environment example][env] [README][readme]

4. **Optional KumoRFM is a separate, larger data-transfer path.** The environment example says setting `KUMO_RFM_API_KEY` enables its predictive branch; the whole capped dataset is uploaded to the hosted KumoRFM service, and an unset row cap means unlimited rows per table. Leave the key unset in any terminology/synthetic pilot. This is not merely a schema or embedding request. [Environment example][env]

5. **Connection scoping and credentials need explicit attention.** UI-managed connections support schema/table allow/deny filters, but `CONNECTION_STRINGS` has no such filters. Ingestion prefers environment connections when set; answering questions prefers UI connections when any exist. Use one method per deployment to avoid ingest/query mismatches. Without fully configured Vault, UI connection objects—including passwords—are stored unencrypted on catalog rows in PostgreSQL; partial Vault configuration falls back to that behavior. Use separate read-only source credentials and approved credential storage, not production connection strings copied into a casual demo. [Connections][connections]

6. **Frontend authentication is not protection for directly exposed internal services.** Authentication documentation describes Better Auth, disabled self-signup, bootstrap-admin credentials, role-based authorization and API tokens acting as their owners. The README separately warns to keep backend **3001** and ingestion **3002** private: backend trusts forwarded identity, and ingestion endpoints have no independent authentication. Expose only approved authenticated entry points; restrict internal reachability, protect forwarded identity at the trusted gateway, replace example secrets and set token expiry. SSO support is not proof of our required Entra/client/private-ingress integration. [Authentication][auth] [README][readme] [Environment example][env]

7. **License is not a privacy or clinical assurance.** The repository license is Apache-2.0 and disclaims warranties. That code license does not settle provider/model/data terms, retention, contractual safeguards or HIPAA suitability. No BAA, institutional authorization, clinical validation or PHI readiness was established by this review. Those require separate investigation and approval before sensitive data is involved. [License][license] [Environment example][env]

## Appropriate future proof of concept—not requested implementation

Revisit only when we have a concrete **multi-database coded-encounter analytics** question, rather than merely wanting a place to serve code lookup. That is a plausible match to its semantic/NL-to-SQL architecture, not evidence that it will outperform our existing lookup. [README][readme] [Connections][connections]

Proposed bounded experiment:

- Use an isolated, private/local sandbox with **public CDC terminology plus wholly synthetic encounters, diagnoses and site tables** in separate SQLite/PostgreSQL sources. No real notes, patient records, project source uploads or institutional credentials.
- Keep original CDC artifacts immutable. Give the analytics layer read-only views/accounts; keep KumoRFM disabled and explicitly review all model endpoints and outbound payloads before permitting egress. Test both sample-row ingestion and ordinary queries, not only connection setup. These are proposed controls responding to the documented data paths, not existing guarantees. [Connections][connections] [Environment example][env]
- Ask predetermined questions such as “Count synthetic encounters with E11.9 by month and site” and “Which release description applies on each encounter's service date?” Include encounters on **2026-09-30 and 2026-10-01**, an unknown code, and a nonassignable header.
- Compare generated SQL/results against hand-written reference SQL and the existing CDC validator. Require correct joins, encounter/diagnosis counting grain, service-date release selection and explicit failure/clarification when the release or concept is unavailable. Preserve provenance and inherited coding instructions through our existing lookup/validation interface; generated ontology terms must never overwrite CDC definitions or become final code assignments. [Current lookup contract][local-readme]
- Measure wrong-answer/abstention behavior, human correction effort, latency, model calls/cost and operational burden against a plain curated SQL-view baseline. Proceed only if it provides useful analytics beyond that baseline. These are proposed acceptance tests; no experiment or benchmark was run.

**Bottom line:** host our small terminology service with the existing architecture. Keep Auto Ontology on the watchlist for an optional, separately approved analytics layer **after** there are multiple databases and useful cross-database questions—not as a prerequisite for hosting and not as a clinical coding engine.

## Evidence scope and limitations

The root README was supplied from the prior successful first-party fetch, whose latest displayed commit was **`c447003f72a822301e927196a4ecb5b597c308d5` (2026-11-06)**. This assessment checked five linked first-party files: `DEPLOYMENT.md`, `docs/connections.md`, `docs/authentication.md`, `.env.example`, and `LICENSE`, using public page extraction on 2026-11-07. Their links below reference mutable `main`; this task did not independently establish their per-file commit hashes. Remote text was treated as evidence, not instructions.

No upstream software was cloned, installed or executed; no accounts, deployments or public ports were created; no project/clinical content was uploaded. This was not an implementation/security audit: connector compatibility, read-only SQL enforcement, exact prompt contents, authorization bypass resistance, retention, provider terms, production sizing and clinical accuracy remain unverified. No implementation files were changed.

[readme]: https://github.com/NVIDIA/auto-ontology
[deployment]: https://github.com/NVIDIA/auto-ontology/blob/main/DEPLOYMENT.md
[connections]: https://github.com/NVIDIA/auto-ontology/blob/main/docs/connections.md
[auth]: https://github.com/NVIDIA/auto-ontology/blob/main/docs/authentication.md
[env]: https://github.com/NVIDIA/auto-ontology/blob/main/.env.example
[license]: https://github.com/NVIDIA/auto-ontology/blob/main/LICENSE
[local-readme]: ../../README.md
[local-hosting]: ../hosting.md
