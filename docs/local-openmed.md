# Optional local OpenMed workflow

**Core ICD-10-CM lookup does not require any of this setup.** OpenMed is an optional,
isolated local research add-on. No real patient data, cloud note submission, or claim
of complete de-identification is authorized.

## Setup only if not already staged

The tested optional environment uses Python 3.13. These are explicit public package
and weight downloads, not runtime inference downloads. Skip existing environments
and models; staging refuses to overwrite artifacts.

```sh
# From the checked-out project directory:
uv venv --python 3.13 data/openmed-venv
uv pip sync --python data/openmed-venv/bin/python \
  --require-hashes requirements/openmed.lock
PYTHONPATH=src data/openmed-venv/bin/python scripts/stage_openmed.py \
  --output data/models/openmed-pilot
```

The main `uv sync` never installs OpenMed, Torch or Transformers. The optional lock
pins OpenMed 3.1.0, Torch 2.15.0 and Transformers 5.22.2. CPU inference is tested on
this Mac, not certified across operating systems.

Staging and runtime admission use the same dependency-free model policy.
`PYTHONPATH=src` lets the isolated staging interpreter import that local policy;
it does not install OpenMed into the core environment.

| Role | Publisher model | Exact revision |
| --- | --- | --- |
| Disease NER | `OpenMed/OpenMed-NER-DiseaseDetect-TinyMed-135M` | `dcb346697f933cea9d9c9cb27b58a1faf8f08f5e` |
| PII | `OpenMed/OpenMed-PII-ClinicalE5-Small-33M-v1` | `2ea947130eb28d610ceb96472af0b694fce9c344` |

The SDK and publisher-declared model licenses are Apache-2.0, **not MIT**. This is
not independent clearance of upstream training rights. In particular, BC5CDR
dataset terms remain unresolved; the PII card's Nemotron-PII attribution/license
also needs institutional review. No dataset is downloaded or model redistributed.
See [feasibility research](research/openmed-feasibility.md).

## Run synthetic notes locally

```sh
uv run icd10-catalog match-note --file examples/synthetic-note.md --synthetic \
  --date 2026-10-01 --catalog-config data/catalogs.json
```

`--synthetic` is an explicit user attestation, not a detector that can verify a note
is synthetic. Inputs are bounded to 20,000 characters and the models' token limits;
overlength notes fail rather than silently truncate. Notes are not chunked.
The worker has a 180-second deadline and runs in a separate process.

The parent verifies pinned identity, an allowlisted safetensors/config/tokenizer
manifest, every file's size/hash and absence of extra/custom-code artifacts.
The worker uses local-only loading, `trust_remote_code=False`, offline flags and
OpenMed's network-blocking guard during loading/inference. It receives a sanitized
environment without inherited cloud credentials or remote-provider settings.
This is not an OS-level sandbox or protection against a compromised local machine.

Output includes:

- Original-input, zero-based, end-exclusive Unicode offsets, extracted disease
  mentions, advisory context and source-grounded lookup candidates.
- Candidate evidence uses original-note coordinates too. Repeated mentions retain
  their distinct evidence spans when a code is deduplicated.
- Each candidate is reviewed independently against the original note using the
  existing code-validation workflow. Documentation status, missing specificity and
  conditional instruction findings are review prompts, not proof of a diagnosis.
  Alternatives are not treated as a selected set of coexisting diagnoses.
- Entity-model scores, distinct from retrieval scores and clinical confidence.
  Deterministic PII pattern matches are separately identified and have no model score.
- Exact model manifests, runtime versions, worker elapsed time and peak RSS.
- A redaction **preview only**, never an edited input file. Source context remains
  available locally for human review. Mentions can contain sensitive source text.

Only affirmed, certain, patient, recent-context mentions without a detected PII
overlap go to the authoritative date-selected CDC lookup. OpenMed context defaults
are not positive clinical evidence. Negation, uncertainty, history and family
mentions remain visible for review, not silently transformed into active diseases.
History/family Z codes and setting-specific coding rules require human adjudication.
No causal relationships, combination codes or final diagnosis assignments are inferred.

## PII limits and failure behavior

An initial real-model check detected only `avery` inside a synthetic email,
leaving `@example.invalid`. The wrapper now unions full OpenMed deterministic
identifier-pattern matches with model spans before preview masking. A regression
test checks the complete email suffix, not merely disappearance of the full string.
That fixes this observed example, **not general PII recall**.

`safe_to_upload` is always `false`, including after a completed scan. A missed
identifier, alias, date, address, MRN or other PII remains possible. The current
tiny synthetic checks are not an exhaustive privacy benchmark.
Missing/tampered artifacts, absent dependencies, failed inference or token limits
produce `nlp_unavailable`, `pii_scan_completed=false`, and no candidates.
Core lookup remains usable.

Do not put notes, extracted concepts, CLI output or previews into cloud-connected
chat/MCP hosts. Local inference does not prevent host retention or onward transmission.

## Real-weight checks

```sh
uv run pytest -q tests/test_nlp.py \
  --openmed-models data/models/openmed-pilot \
  --openmed-python data/openmed-venv/bin/python
```

Without both explicit paths, real-weight tests skip, never substitute a fake model.
The initial short-note worker measured about 5.6 seconds and 684 MiB peak RSS,
excluding a production service's full overhead. This exceeds Render Free's 512 MB
memory allowance. Keep NLP on the computer; do not package weights in the core image.
