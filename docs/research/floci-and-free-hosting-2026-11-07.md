# Floci and free hosting

**Checked: 2026-11-07. Decision: local computer now; Render Free only a conditional future terminology demo. Nothing is deployed.**

## Can we use Floci for local testing?

**Yes for AWS integration tests, but it adds nothing to this application's current trial.** Floci is an MIT-licensed, local AWS-compatible emulator—not a provider of internet hosting. Its official README describes development/testing/CI without a cloud account or auth token, with AWS clients pointed at local port 4566. It lists native-binary support, so Docker is **not universally required**; Docker-backed execution such as Lambda, ECS and RDS does require Docker. These are upstream capabilities, not capabilities tested here. [1]

The supplied project status is ordinary Python, SQLite containing two frozen public CDC ICD-10-CM releases, and MCP over stdio or local-loopback HTTP; no AWS SDK or AWS service is required. Keep SQLite. Do not introduce DynamoDB or another AWS dependency merely to justify an emulator. Reconsider Floci only if an AWS architecture is actually adopted, then use isolated AWS integration tests.

**Security caution:** the README's generic Compose example publishes port 4566 without restricting the host interface. Its optional console uses a Docker socket and documents an all-interface publication default unless configured otherwise. These are development examples, not a secure public deployment design. Do not expose the emulator publicly or grant Docker-socket access casually. No commands, installation or daemon startup were performed. [1]

## Where can we host this for free?

| Scope | Recommendation |
| --- | --- |
| Full local trial | Use the current computer, with no additional hosting subscription. Keep optional OpenMed NER/PII experiments local and synthetic-only. This is not an internet deployment or an availability guarantee. |
| Future online terminology-only demo | **Render Free is a candidate, not an approved or verified deployment.** Exclude OpenMed and patient data. Complete the preparation and tests below first. |
| Always-on or clinical/PHI service | Not established by this research; do not represent the free demo as suitable. |

Render currently advertises a **$0/month Free web-service instance with 512 MB RAM**. Its free documentation explicitly says not to use free instances for production applications. [2][3]

Important limits:

- Sleeps after **15 minutes** without inbound traffic; waking takes **about one minute**. Services can also restart at any time. No always-on promise. [2]
- **750 instance hours per workspace per month**, shared by free web services; exhaustion suspends them until the next month. [2]
- Filesystem changes, including SQLite writes, disappear on restart, redeploy or sleep; free services cannot attach persistent disks. Frozen, read-only SQLite catalogs could instead be packaged into the deploy artifact and restored from it, subject to testing. Do not depend on runtime writes surviving. [2]
- Free web services **cannot receive private-network traffic**. This is not a private institutional hosting arrangement. [2]
- Bandwidth and build minutes have allowances. Overages can generate charges when a payment method is present, or suspension/build blocking otherwise; “free” does not mean unlimited or a blanket zero-charge guarantee. Hobby workspace pricing is separate from compute selection. [2][3]

The supplied local OpenMed measurement was approximately **722 MiB peak**, already above Render Free's advertised 512 MB. Do not put that measured configuration on this tier. The smaller terminology-only application's actual hosted memory fit remains unverified.

## Required before any online trial

1. Obtain separate approval to deploy and authorize private-repository access. The supplied status is a private, empty GitHub repository with local Git initialized, but no commit/push. GitHub source storage is not a running Python MCP web host.
2. Prepare a deployment-specific HTTP entry point: the current launcher hardcodes `127.0.0.1` and is unauthenticated, so **it must not be deployed unchanged**. Review authentication, host/origin validation, TLS/proxy behavior, request limits and logging before exposure.
3. Verify the intended remote MCP client/transport, cold-start/reconnect behavior, and memory under startup, catalog loading and concurrent requests. Bundle the frozen catalogs reproducibly and verify their availability after restart.
4. Keep the public demo limited to public terminology and synthetic queries: no patient narratives/PHI, local OpenMed service, or confidential logs. No HIPAA or clinical coding-correctness claim.

## Evidence boundaries

Fresh external research was limited to the official Floci repository and Render free/pricing pages. Project facts above are supplied session context, not newly rerun measurements: the local milestone passed 28 smoke/catalog checks plus 10 real stdio MCP checks without OpenMed. Floci was not executed; native-binary compatibility on this Mac, AWS fidelity, Render build/deploy feasibility, remote MCP compatibility and hosted memory were **not verified**. No accounts, installations, clones, deployment, uploads, exposed ports or Docker startup occurred.

## Primary sources

1. [Floci official repository / README](https://github.com/floci-io/floci) — local emulator purpose, licensing, native binary, Docker-backed services and Compose/console examples.
2. [Render: Deploy for Free](https://render.com/docs/free) — production warning, idle behavior, filesystem, hours, networking and usage limits.
3. [Render pricing](https://render.com/pricing) — Free web-service memory and price; workspace versus compute pricing.

All three retrieved on 2026-11-07; upstream terms and software can change.
