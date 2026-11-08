# OpenMed feasibility: extraction, terminology linking, and ICD-10-CM boundaries

## Bottom line

**Yes: a helpful extraction front-end, not independently verified end-to-end coding.** OpenMed can propose disease spans, add rule-based assertion context, generate bounded relation candidates, and resolve terminology against caller-supplied local vocabulary snapshots. It is therefore inaccurate to describe current OpenMed as “NER only” or as having no entity linking. It is equally inaccurate to treat its NER scores, linking scores, vocabulary version labels, or synthetic demonstrations as validated patient/encounter-specific ICD-10-CM assignment.

The inspected SDK is **Apache-2.0, not MIT**: both the actual [LICENSE at `v3.1.0`](https://github.com/maziyarpanahi/openmed/blob/v3.1.0/LICENSE) and [project metadata at that tag](https://github.com/maziyarpanahi/openmed/blob/v3.1.0/pyproject.toml) say so. Model weights, training datasets, terminology releases, and optional integrations have separate terms.

Scope: bounded, read-only primary-source review of `maziyarpanahi/openmed`, using named release `v3.1.0`, plus one revision-identified Hugging Face model. No packages installed, repository cloned, model weights downloaded, untrusted code executed, or patient data used. This is source verification, not a runtime benchmark or clinical validation. Hosting and the meaning of “OpenCode” are outside this report.

## 1. Capability answers

| Requested capability | Answer supported by inspected sources |
| --- | --- |
| Entity-span extraction | **Yes.** `analyze_text` orchestrates token classification and returns labels, surfaces, character offsets, and model scores. Actual labels depend on the selected checkpoint; a disease-only checkpoint does not also extract drugs simply because a generic example shows both. [Analyze API](https://github.com/maziyarpanahi/openmed/blob/v3.1.0/docs/analyze-text.md), [entity schema](https://github.com/maziyarpanahi/openmed/blob/v3.1.0/openmed/processing/outputs.py). |
| Negation, uncertainty, experiencer, temporality | **Yes, advisory/rule-based.** `assert_context` uses ConText-style scoped cues and optional section priors. `analyze_text(assert_context=True)` opts in; the default is off. This is not evidence that all complex assertion scopes are solved. [Context implementation](https://github.com/maziyarpanahi/openmed/blob/v3.1.0/openmed/clinical/context.py), [documented rules and limitations](https://github.com/maziyarpanahi/openmed/blob/v3.1.0/docs/clinical/context-and-extraction.md). |
| Relations | **Yes, bounded candidates.** `extract_relation_candidates` connects compatible existing spans using section/assertion constraints, distance windows, and limited explicit-connective cross-sentence handling. Its confidence is explicitly heuristic. A separate diagnosis-treatment helper requires explicit linking language and always requires review; neither establishes clinical causality. [Relation implementation](https://github.com/maziyarpanahi/openmed/blob/v3.1.0/openmed/clinical/relations_lite.py), [diagnosis-treatment contract](https://github.com/maziyarpanahi/openmed/blob/v3.1.0/docs/clinical/diagnosis-treatment-relations.md). |
| Abbreviation/synonym normalization | **Yes, limited and inventory-dependent.** The abbreviation resolver ranks a small synthetic starter inventory using section, nearby entity types, cue words, and priors. Unknown abbreviations return `None`; ties can be resolved by inventory order, so a returned winner is not proof of disambiguation. Vocabulary grounding indexes preferred terms and supplied synonyms/language aliases. [Abbreviation source](https://github.com/maziyarpanahi/openmed/blob/v3.1.0/openmed/clinical/abbreviation.py), [inventory/scoring documentation](https://github.com/maziyarpanahi/openmed/blob/v3.1.0/docs/clinical/abbreviation-disambiguation.md), [vocabulary schema](https://github.com/maziyarpanahi/openmed/blob/v3.1.0/openmed/clinical/grounding/vocab.py). |
| Concept → ICD-10-CM linking | **Yes, an implemented assistive path with supplied terminology.** `ground` runs local alias lookup/retrieval and ranking against supplied snapshots; it can return codes, alternatives, abstentions, and provenance. This is real resolution machinery, not solely a placeholder provider. It does not supply an authoritative clinical coding decision. [Grounding implementation](https://github.com/maziyarpanahi/openmed/blob/v3.1.0/openmed/clinical/grounding/api.py), [offline workbench](https://github.com/maziyarpanahi/openmed/blob/v3.1.0/docs/grounding.md). |
| Concept → UMLS/SNOMED CT linking | **Conditional.** Implemented local user-key-gated alias-table loaders and caller-owned out-of-process bridge hooks exist. Restricted vocabulary content is not bundled or automatically obtained. Do not describe these as unrestricted, turnkey terminology services. [Canonical grounding source](https://github.com/maziyarpanahi/openmed/blob/v3.1.0/openmed/clinical/grounding/api.py), [local restricted-loader documentation](https://github.com/maziyarpanahi/openmed/blob/v3.1.0/docs/clinical/concept-grounding.md). |
| Date/version-aware valid ICD-10-CM assignment | **Not established.** Snapshot version/checksum provenance exists, but the inspected `ground` signature has no encounter-date/release-selection contract; `VocabConcept` contains system/code/preferred term/aliases/source, not assignability, effective intervals, or Tabular/Index coding rules. Preserve our official catalog validation. This is a scoped finding about the inspected interfaces, not a claim that no other OpenMed module handles dates. [Grounding API](https://github.com/maziyarpanahi/openmed/blob/v3.1.0/openmed/clinical/grounding/api.py), [vocabulary fields](https://github.com/maziyarpanahi/openmed/blob/v3.1.0/openmed/clinical/grounding/vocab.py). |
| Free CPU/local inference | **Yes in supported configurations; not zero-resource or guaranteed free hosting.** The SDK supports CPU Transformers and local-artifact loading. The selected model below is public, ungated, and declared Apache-2.0. RAM, storage, package availability, latency, and deployment/privacy qualification remain our responsibility. [Loader guide](https://github.com/maziyarpanahi/openmed/blob/v3.1.0/docs/model-loader.md), [model metadata](https://huggingface.co/api/models/OpenMed/OpenMed-NER-DiseaseDetect-TinyMed-135M). |

## 2. Four relevant interfaces and their actual output contracts

### A. Extraction: `openmed.analyze_text(...)`

Inputs include `text`, registry alias/full model ID/local directory, aggregation and threshold settings, and optional `assert_context=True`. The typed `AnalyzeResult` has `text`, `entities`, `model`, `timestamp`, optional `processing_time`/`metadata`, and computed `text_length`. Its legacy `to_dict()` serializes **`model_name`**, not `model`, and does not serialize `text_length`. Each entity serializes:

```text
text: str
label: str
confidence: float
start: int | None
end: int | None
metadata: dict
```

Sources: [typed result implementation](https://github.com/maziyarpanahi/openmed/blob/v3.1.0/openmed/core/results.py), [entity formatter](https://github.com/maziyarpanahi/openmed/blob/v3.1.0/openmed/processing/outputs.py).

**`confidence` is an inference/entity-label score, not coding confidence.** Formatting/grouping can also combine scores and adjust spans. Our adapter must validate non-null half-open offsets against the exact submitted text, and preserve any text-normalization/chunk offset mapping. Long notes need explicit coverage/chunking tests; the helper documents truncation/max-length controls, not a universal guarantee that arbitrary-length notes are fully processed. [Extraction guide](https://github.com/maziyarpanahi/openmed/blob/v3.1.0/docs/analyze-text.md).

### B. Assertions: `openmed.clinical.assert_context(text, spans, ..., sections=...)`

Returns copied span mappings, not mutations, with `negation`, `uncertainty`, `experiencer`, and `temporality`, duplicated under `metadata["clinical_context"]`. Supplying sections adds per-axis `context_sources` and `metadata["clinical_context_sources"]`. The separate compact `ClinicalAssertion` schema uses **`certainty`**, not `uncertainty`; adapters must not silently conflate these field names or vocabularies.

Scoped local cues override section priors, which override defaults. Defaults such as affirmed/current/certain are mechanical fallbacks, **not positive clinical evidence**. Family-history and historical-section priors are available, but must be explicitly composed and tested. Sources: [implementation](https://github.com/maziyarpanahi/openmed/blob/v3.1.0/openmed/clinical/context.py), [documented precedence and schemas](https://github.com/maziyarpanahi/openmed/blob/v3.1.0/docs/clinical/context-and-extraction.md).

### C. Relations: `extract_relation_candidates(text, spans, sections=None, ...)`

Returns a deterministic tuple of `RelationCandidate` objects. Serialized fields are `head`, `tail`, `relation_type`, `confidence`, `distance`, `token_distance`, `sentence_distance`, and `explicit_connective`; each endpoint contains `start`, `end`, `label`, and `score`, without its source surface. Candidates depend on upstream spans and configured constraints. `asserted_only=True` filters explicitly marked negative/hypothetical endpoints; it is not a replacement for upstream assertion detection. Source: [actual implementation and schema](https://github.com/maziyarpanahi/openmed/blob/v3.1.0/openmed/clinical/relations_lite.py).

### D. Linking: `openmed.ground(text_or_entities, systems=..., snapshot=..., offline=True, ...)`

The canonical source accepts text or pre-extracted entities, `top_k`, local snapshot/loader, optional local dense encoder/ranking configuration, and restricted terminology resources. For raw text it performs a **deterministic vocabulary-backed alias scan**, not automatic disease-model inference. The ranking stage uses sparse retrieval and can add a supplied local dense encoder; the default does not magically include a downloaded SapBERT-class model. Sources: [facade](https://github.com/maziyarpanahi/openmed/blob/v3.1.0/openmed/clinical/grounding/api.py), [ranker](https://github.com/maziyarpanahi/openmed/blob/v3.1.0/openmed/clinical/grounding/ranker.py).

`GroundingResult` is sequence-compatible with `GroundedSpan` and also exposes `concepts: tuple[GroundedConcept, ...]`. A concept carries `span(start,end)`, `surface_text`, `system`, nullable `code`/`display`, `confidence`, ranked `candidates`, `provenance`, and optional `section_context`. `to_dict()` includes compatibility aliases such as `text`, `surface`, `score`, and `top_k`. Missing code means abstention. The facade and REST/CLI payloads have related but not identical envelopes; do not assume every `openmed.grounding.v1` payload has one interchangeable shape. Sources: [result types/serialization](https://github.com/maziyarpanahi/openmed/blob/v3.1.0/openmed/clinical/grounding/results.py), [span/candidate types](https://github.com/maziyarpanahi/openmed/blob/v3.1.0/openmed/clinical/grounding/types.py).

**Documentation mismatch to resolve before restricted terminology use:** the general [grounding guide](https://github.com/maziyarpanahi/openmed/blob/v3.1.0/docs/grounding.md) describes restricted systems as requiring out-of-process endpoints, while the [concept-grounding guide](https://github.com/maziyarpanahi/openmed/blob/v3.1.0/docs/clinical/concept-grounding.md) and [canonical source](https://github.com/maziyarpanahi/openmed/blob/v3.1.0/openmed/clinical/grounding/api.py) also expose explicit local `restricted_loaders`. The source supports both pathways. This review does not certify either licensing workflow.

## 3. One concrete CPU candidate, with revision and license evidence

Candidate for a **synthetic disease-span pilot**, not a selected production dependency:

| Field | Verified evidence |
| --- | --- |
| Repository | `OpenMed/OpenMed-NER-DiseaseDetect-TinyMed-135M` |
| Immutable model revision | `dcb346697f933cea9d9c9cb27b58a1faf8f08f5e`, reported by the first-party [Hub API](https://huggingface.co/api/models/OpenMed/OpenMed-NER-DiseaseDetect-TinyMed-135M). |
| Architecture/task | `DistilBertForTokenClassification`; six layers; 512 maximum positions; labels `O`, `B-DISEASE`, `I-DISEASE`. [Configuration inspected on `main`](https://huggingface.co/OpenMed/OpenMed-NER-DiseaseDetect-TinyMed-135M/resolve/main/config.json). The revision-specific config extraction failed, so configuration bytes have not been independently hash-verified here. |
| Size/artifact | API reports **134,736,387 BF16 parameters**, `model.safetensors`, and repository storage `269982200` bytes. Parameter storage is approximately 269 MB at BF16 or 539 MB if converted to FP32; these are arithmetic estimates, **not peak process RAM**. Torch, tokenizers, activations, batching, and concurrency add overhead. |
| Weights license | Publisher-declared **Apache-2.0**, confirmed in metadata and the [model card at the immutable revision](https://huggingface.co/OpenMed/OpenMed-NER-DiseaseDetect-TinyMed-135M/blob/dcb346697f933cea9d9c9cb27b58a1faf8f08f5e/README.md). The API file list did not show a standalone LICENSE file; the card links the Apache license. This is publisher evidence, not independent chain-of-title certification. |
| Evidence/limits | Card reports BC5CDR-Disease NER F1 `0.88`, precision `0.87`, recall `0.89`; these are author-reported literature-disease extraction metrics, **not clinical-note coding accuracy**. Despite broad use-case prose, the actual output taxonomy is disease-only. The multilingual base does not establish multilingual clinical validation; metadata declares English. |
| Dataset rights | Card identifies BC5CDR-Disease and a `distilbert-base-multilingual-cased` base. This bounded review did **not** independently clear dataset/base-model redistribution terms or all training provenance. Dataset acquisition/redistribution requires a separate terms review; SDK/weights declarations do not relicense datasets or terminology. |

The same card recommends CPU batches of 1–4. This supports a modest local pilot, not an unmeasured assertion that a small free-tier container will fit. A separate drug/anatomy model would increase memory and needs its own license and evaluation review.

## 4. Offline, package, and artifact-safety conditions

- At `v3.1.0`, core Python is `>=3.10`; our Python 3.11 baseline is within that declared range. Core dependencies include `pysbd`, `faker`, `jieba`, `pyyaml`, and `jsonschema`; core alone is not the Transformers inference stack. The `hf` extra adds Torch `>=2.13.0`, Transformers `>=4.50`, Hub `>=0.30`, Accelerate `>=0.29`, Tokenizers `>=0.15`, and additional support dependencies. These are source-declared requirements, not installation success verified on our platform. [Exact metadata](https://github.com/maziyarpanahi/openmed/blob/v3.1.0/pyproject.toml).
- Existing local model directories default to `local_files_only=True`; required tokenizer/config/weight files must already be present or loading fails locally. Use a controlled acquisition stage, then a local-only CPU runtime with outbound access denied. Downloads, remote adapters, configured telemetry exporters, and application integrations are separate network boundaries. [Loader documentation](https://github.com/maziyarpanahi/openmed/blob/v3.1.0/docs/model-loader.md), [loader implementation](https://github.com/maziyarpanahi/openmed/blob/v3.1.0/openmed/core/models.py), [repository boundary statement](https://github.com/maziyarpanahi/openmed).
- `ModelLoader.create_pipeline` accepts Hugging Face kwargs and forwards a `revision`; an alias or unpinned repository ID is not itself a reproducibility pin. Stage the exact model commit and record hashes of every tokenizer/config/weight artifact. A fresh loader bound to one immutable local directory avoids relying on mutable repository names or reused model caches. [Loader source](https://github.com/maziyarpanahi/openmed/blob/v3.1.0/openmed/core/models.py).
- The candidate provides safetensors and a standard DistilBERT architecture, so there is no apparent need for custom remote code. **Require** `trust_remote_code=False` and safetensors-only loading in the eventual wrapper, with tests that prove those options reach the selected loading path. Do not claim that all generic SDK paths enforce both settings merely because one specialized local sequence-classifier path explicitly disables remote code. No weight file was inspected or executed in this review. [Candidate metadata](https://huggingface.co/api/models/OpenMed/OpenMed-NER-DiseaseDetect-TinyMed-135M), [loader source](https://github.com/maziyarpanahi/openmed/blob/v3.1.0/openmed/core/models.py).
- The [v3.1.0 release notes](https://github.com/maziyarpanahi/openmed/releases/tag/v3.1.0) disclose optional dependency findings, including an NLTK exception expiring **3 November 2026** and an optional Accelerate finding. This source review does not establish that those findings are resolved. Before installation, resolve a fresh lockfile and scan the **selected minimal runtime closure**, rather than assuming release checks certify every optional integration.
- PII detection/de-identification does **not** make a public host safe for PHI and does not establish HIPAA compliance. For the proposed first experiment, accept synthetic notes only, avoid cloud agent prompts containing clinical records, and log neither notes nor entity surfaces. [Repository limitations and explicit HIPAA boundary](https://github.com/maziyarpanahi/openmed).

## 5. What the “clinical brief” demonstration proves

The actual [`examples/v30_clinical_brief.py`](https://github.com/maziyarpanahi/openmed/blob/v3.1.0/examples/v30_clinical_brief.py) declares itself an offline synthetic contract demonstration, uses fixture NER/NLI test doubles and a synthetic vocabulary, accepts no external note input, and emits `model_validation=False`. It can demonstrate API composition, citations, guarded review, and refusal contracts. It cannot establish trained-model extraction accuracy, NLI clinical validity, terminology coverage, or coding performance.

The [linking evaluation documentation](https://github.com/maziyarpanahi/openmed/blob/v3.1.0/docs/clinical/concept-grounding.md) likewise exposes a MedMentions evaluator requiring caller-provided licensed data/provider. Its `0.55` floor and `0.70` target are criteria, **not observed achieved accuracy**. No independently verified end-to-end ICD-10-CM clinical-note benchmark was established in this review.

## 6. Recommended integration seam — proposal only

Preserve the project architecture supplied by the parent session: authoritative deterministic ICD-10-CM lookup remains primary; optional note assistance is a separate, synthetic-only experiment. The downloaded FY2027 catalog is not imported merely because OpenMed is investigated.

```text
synthetic note + explicit catalog/date context
  → optional local OpenMed extraction adapter
  → source-aligned mentions + assertion/section evidence
  → reviewed normalization and candidate retrieval
  → our official version-specific ICD-10-CM lookup/validation
  → candidates with official descriptions/provenance, or explicit abstention
  → qualified human review
```

Recommended adapter record: source offsets/surface, entity label, `entity_score`, model ID/revision/artifact hashes, assertion values plus default/local/section provenance, normalization alternatives, optional relation evidence, and pipeline/config version. Treat note/mention records as sensitive even when the first fixtures are synthetic.

For a first specification:

1. Keep OpenMed optional and separately packaged; do not add Torch or a second terminology store to the lean lookup process by default.
2. Reuse our lookup for official descriptions, assignability, hierarchy, Index/Tabular evidence, catalog identity and source hashes. OpenMed's optional ICD-10-CM snapshot grounder is an alternative candidate generator to compare later, not an automatic replacement for that authority.
3. Keep `entity_score`, heuristic `relation_score`, terminology `link_score`, and our lexical retrieval rank distinct. None is clinical/coding confidence; do not expose a fabricated combined percentage.
4. Abstain on unknown/ambiguous abbreviation senses, conflicting context, insufficient evidence, unvalidated/mismatched catalog releases, missing required specificity, or failed artifact checks. No guessed code; never let a concept-string match silently materialize as an active patient diagnosis.
5. Before clinical claims, require an expert-reviewed benchmark with separate span/context/linking/code-validity/code-correctness results; held-out documentation styles; negation, family history, history versus active disease, uncertainty, abbreviation ambiguity, laterality, complication and long-note coverage cases; and measured CPU cold start, peak RSS, storage, latency and concurrency. Synthetic contract tests are the initial gate, not clinical validation.

**Decision:** technically feasible for a bounded, local synthetic extraction-and-candidate pilot. Not yet justified as an autonomous clinical-note-to-code product. Implementation, model acquisition, runtime qualification, dataset/terminology clearance, and clinical evaluation remain unapproved follow-ups.
