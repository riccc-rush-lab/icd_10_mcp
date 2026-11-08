# Clinical mapping: evidence audit and transferable engineering lessons

## Bottom line

The [John Snow Labs (JSL) article](https://www.johnsnowlabs.com/why-mapping-clinical-notes-to-icd-10-cpt-loinc-and-snomed-codes-takes-more-than-entity-recognition/) offers a useful architectural warning: recognizing a disease string, resolving terminology, and assigning a reportable code to the correct patient/encounter are different tasks. Its cited studies support contextual evaluation and domain-shift testing, **not** a universal ceiling for general-purpose LLMs, independently certified production readiness, or a measured end-to-end ICD-10-CM coding accuracy.

For this project, preserve deterministic, provenance-rich **code/phrase lookup** as the primary product. Treat synthetic-note assistance as a separate, explicitly limited candidate-generation experiment, not autonomous coding. None of the audited percentages validates this project's implementation.

Scope: bounded review of four decision-relevant primary papers, the first-party MiBA case study, and official coding rules. The parent session supplied the main article and project facts; source/tests were not re-examined. No deployment, implementation, patient data, credentials, or cloud accounts were used. Recommendations below are proposals, not descriptions of implemented behavior.

## 1. What the evidence actually measures

### Pandian et al.: strong domain-shift evidence, narrow CPT classification task

Source: [Generalizing machine learning models from clinical free text, Scientific Reports (2025)](https://www.nature.com/articles/s41598-025-17197-6), especially Methods, Results, Discussion, and competing interests.

- **Sample/task:** 1,607,393 anesthesiology procedures at 44 US institutions, January 2017–July 2019. The analysis retained **48 anesthesiology CPT codes shared by every institution**, excluding missing data and non-shared codes. Input was short procedural free text; TF-IDF features fed a deep neural network. This was single-label CPT classification, not full-note ICD-10-CM coding, and **LLMs were not evaluated**.
- **Results:** mean self-institution accuracy **92.5%** (SD 2.8 points), with a mean **22.4-percentage-point** drop on other institutions. The paper reports **17.1-point** external improvement from combined-institution approaches, with different F1 changes for its pooled and institution-holdout designs. Keep pooled 80:20 and leave-one-institution-out results distinct; they are not interchangeable demonstrations of unseen-site performance.
- **Important counterweight to the marketing narrative:** maximal spelling/acronym preprocessing improved accuracy only **0.51 points** on average. Normalizing vocabulary is not, by itself, evidence that clinical generalization has improved.
- **Limitations:** gold labels were institution-billed CPT charges, not independently adjudicated optimal codes. The authors cite earlier work finding about 5% billing-label error. Rare/non-shared codes were excluded. The study is retrospective and model-specific, not a prospective product safety assessment.
- **Independence:** peer-reviewed research outside JSL, but **not free of commercial interests**: disclosed billing-automation patent inventorship and Decimal Code equity. Do not describe it as entirely conflict-free.

**Transfer:** evaluate held-out documentation styles and eventually genuinely external sites; distinguish label validity from label correctness; do not assume a synonym/abbreviation expansion project solves domain shift.

### Mavridis et al.: the precision numbers are real, but not clinical-note coding accuracy

Source: [Large language models for intelligent RDF knowledge graph construction: results from medical ontology mapping, Frontiers in Artificial Intelligence (2025)](https://www.frontiersin.org/journals/artificial-intelligence/articles/10.3389/frai.2025.1546179/full), §§3–5 and Tables 1–2.

- **Sample/task:** **108 medical terms**, including demographics, measurements, diagnostic/procedural terms and treatments, drawn from a public-hospital use case. Experts established consensus SNOMED CT mappings and performed model-blinded validation. The task was term/structured-data ontology mapping for RDF construction, **not assigning billable diagnosis codes to patients from unrestricted notes**.
- **System:** the described framework includes preprocessing, BioBERT embeddings, ChromaDB retrieval and prompted LLMs without task-specific fine-tuning. The result should not be described as a bare general LLM's unassisted coding accuracy.
- **Reported results:** GPT-4o precision **93.75%**, recall **98.90%**, F1 **96.26%**; Llama 3.3 70B precision **19.19%**, recall **70.37%**, F1 **30.16%**. These are reported ontology-mapping metrics on this small task, not estimates for ICD-10-CM.
- **Reporting red flag:** Table 2 reports GPT-4o TP/FP/FN/TN = **90/6/1/11**, versus Llama **19/80/8/1**, each totaling 108. Thus the apparent positive-ground-truth denominator, TP+FN, changes from **91 to 27** on the same terms. The published precision arithmetic checks out, but these are not transparently comparable fixed-gold confusion matrices. Clarification of outcome definitions is needed before relying on the cross-model recall/F1 gap. No corrected performance estimate is asserted here.
- **Independence/limits:** peer-reviewed academic study, Aristotle University of Thessaloniki affiliations, EU project funding, and no declared commercial conflict. Small, constrained dataset; simplified temporal/hierarchical relationships; no prospective workflow or cross-hospital coding validation.

**Transfer:** build explicit gold candidate sets, fixed denominators and reproducible adjudication rules. Separate “identifier exists in this release” from “this is the right concept for this documented patient fact.” This study also contradicts a blanket claim that general-purpose LLMs can never be useful.

### Kocaman et al.: vendor-authored assertion benchmark, not a combined-pipeline coding score

Sources: [full text](https://arxiv.org/html/2503.17425v1), [PDF with affiliations](https://arxiv.org/pdf/2503.17425), and [arXiv record](https://arxiv.org/abs/2503.17425).

- **Status/independence:** all seven authors list **John Snow Labs**. The arXiv record says accepted at the Text2Story Workshop at ECIR 2025. Publication/workshop acceptance does not make this an independent evaluation of JSL.
- **Sample/task:** official **2010 i2b2 test split**, **12,592 assertion instances** across six labels. “Present” accounts for 8,622, versus 148 conditional and 131 associated-with-someone-else instances. The fine-tuned LLM and GPT-4o rows cover **12,444** instances without conditional cases. This evaluates assertion status for medical entities, not terminology resolution or code assignment.
- **Correct the headline:** **0.962 belongs to the fine-tuned Llama 3.1-8B assertion model**, versus GPT-4o **0.901**. **The combined pipeline is 0.941**, not 0.962. The abstract calls the aggregate “accuracy”; Table 2 labels it “weighted avg,” and the discussion also refers to F1. Preserve that metric-label ambiguity rather than relabeling it as clinical coding accuracy.
- **Do not blend model slices:** **0.599 conditional** is the AssertionDL row; **0.976 present** is the fine-tuned LLM row. They are not two categories measured in one all-label model. The fine-tuned LLM's conditional value is absent.
- **Comparison limitations:** cloud-service comparisons include only fully/partially overlapping extracted entities; supported label sets differ. The authors acknowledge selection bias. They report obfuscating i2b2 PHI and medical terms for GPT-4o evaluation. These conditions matter for reproducibility and fair system-to-system comparison.
- **Operational claims:** the paper reports approximately 3 CPU seconds for AssertionDL versus 294 GPU seconds for its fine-tuned LLM in its benchmark. This is not a portable latency/cost forecast for another workload, model, hardware configuration or service.

**Transfer:** examine class-level failures and unsupported labels, not only weighted aggregates. If learned components are considered later, benchmark small domain-adapted classifiers against rules and LLM alternatives; measure the local quality/latency/cost trade-off rather than inheriting vendor ratios.

### Ji et al.: 0.74 is a local sleep-corpus result, not an LLM ceiling

Sources: [PubMed PMID 40092287](https://pubmed.ncbi.nlm.nih.gov/40092287/), [full text in PMC](https://pmc.ncbi.nlm.nih.gov/articles/PMC11908446/), [DOI](https://doi.org/10.1109/ichi61247.2024.00039).

- According to PubMed, this is an **IEEE ICHI 2024 proceedings paper**, despite its 2025 PubMed identifier/indexing context. Authors have University of Pittsburgh affiliations; this is not a JSL product benchmark.
- **Sample/task:** assertion detection on i2b2 plus a local UPMC corpus of **456 keyword-sampled clinical notes about snoring/obstructive sleep apnea**, with healthcare-professional review/adjudication. The local labels include historical and family assertions; conditional was excluded from the i2b2 evaluation. Models were **Llama2-7B and ChatGPT 3.5 turbo**, with prompting strategies and LoRA fine-tuning.
- **Results:** the abstract reports **0.89 micro-averaged F1** on i2b2 (+0.11 over prior work), and **0.74 F1** on the local sleep dataset (+0.31). These are neither current-model performance ceilings nor an end-to-end joint score for all stages of clinical coding. Certainty, temporality and experiencer describe assertion dimensions; “0.74 across three axes” overstates what has been established.
- The authors explicitly acknowledge single-institution local data, constrained model size and rapidly evolving models. They describe LLM assertion detection as **viable**, not impossible.
- Retrieval limitation: the accessible article text did not expose complete dataset/result tables in the extracts used here. Exact per-label train/test counts and the detailed aggregation behind the local 0.74 were not independently reconstructed. The abstract-level values and 456-note sample are verified; do not invent missing denominators.

**Transfer:** test ambiguity and long-distance assertion cues, and report corpus-specific outcomes. Do not use this result to reject all future general models or claim one universal attainable F1.

## 2. First-party production stories versus independent evidence

The [JSL/MiBA oncology case study](https://www.johnsnowlabs.com/ai-enhanced-oncology-data-unlocking-insights-from-ehrs-with-nlp-and-llms-2/) reports **0.90 average relationship F1**, **0.81 trial-matching F1**, and **0.93 adverse-event relationship F1** (precision 0.91, recall 0.95), with integration and nightly refresh descriptions. These numbers were located in the original first-party article.

They are **vendor-reported task results**, not independent clinical coding validation. The page does not provide sufficient sample sizes, held-out split construction, label prevalence, adjudication protocol or uncertainty intervals to independently establish those performance claims. Drug–adverse-event relation extraction, trial eligibility matching and ICD-10-CM assignment have different endpoints. Neither the case study nor the main article alone establishes production certification, audited clinical safety, guaranteed compliance, or correct patient-level codes.

Other citations intentionally outside this bounded audit: [Kruse (2025)](https://aclanthology.org/2025.findings-emnlp.1128/) and [Chaturvedi (2025)](https://arxiv.org/pdf/2503.18085) were **not independently checked**; no numerical conclusions from them are adopted. The supplied “Andrew 2025” temporal reference lacked an identifiable linked citation and remains **unverified**.

## 3. Coding-rule guardrails: context is not a universal exclusion switch

Authoritative source: [CDC/NCHS, FY2026 ICD-10-CM Official Guidelines, updated April 1, 2026](https://ftp.cdc.gov/pub/Health_Statistics/NCHS/Publications/ICD10CM/2026-update/ICD-10-CM%20April%201%202026%20Guidelines%20Final.pdf), especially I.C.21.c.4, II.H, III.C and IV.H–J.

- **Uncertain diagnoses are setting-dependent.** For qualifying inpatient hospital admissions, uncertain diagnoses documented at discharge may be coded as established under II.H/III.C, subject to chapter-specific exceptions. Outpatient IV.H instead directs coding to the highest certainty for that encounter, such as documented signs/symptoms, not the uncertain disease. An isolated “possible” token cannot choose the coding policy.
- **History/family does not mean “no code.”** Personal-history and family-history Z codes may be appropriate. A historic/resolved disease must not automatically become an active disease code, and a relative's disease must not become the patient's active diagnosis. IV.J recognizes relevant history affecting current care.
- **Negated mentions do not establish that active diagnosis**, but do not prove the entire encounter has no reportable code; documented symptoms, history, screening or other encounter reasons may be relevant.
- **Co-occurrence is not causality.** For example, the guidelines say pneumonia plus ventilation does not by itself establish ventilator-associated pneumonia. Conversely, official coding conventions sometimes presume specified relationships (I.A.15, “With”); do not replace the classification with a universal “explicit causal phrase required” rule.
- Source-grounded coding requires the Index **and** Tabular instructions, documentation, encounter setting and date. A valid code/assignable leaf is not proof of a reportable diagnosis for this patient.

## 4. Conservative architecture for this project

Project facts here come from the supplied engineering context, not a fresh source-code audit.

1. **Preserve the primary lookup boundary.** Keep official MCP SDK 1.30 thin stdio adapters over deterministic SQLite FTS5 and the versioned CDC catalog. Ordinary code/phrase lookup should remain useful without note inference, LLMs, embeddings or external runtime calls. Ranking is lexical relevance, not calibrated clinical confidence.
2. **Separate note interpretation from catalog resolution.** A future note-assist layer should carry mention spans, original offsets, experiencer, assertion, temporality, section and unresolved context into candidate lookup. Any learned component would be optional, separately evaluated and explicitly approved—not a prerequisite implied by these papers.
3. **Make unsupported decisions visible.** Missing setting/date, conflicting laterality, cross-sentence ambiguity, longitudinal reconciliation and unproven relations should route to review/abstention, not silently default to “active patient diagnosis.” Do not silently discard appropriate history/encounter-code possibilities.
4. **Use the catalog as a constraint, not a truth oracle.** Check release applicability, assignability, hierarchy, Index paths and Tabular instructions independently of note interpretation. Preserve alternative candidates and why specificity is unsupported. Do not manufacture relationships or extra detail from a high retrieval score.
5. **Keep provenance and privacy together.** Retain official descriptions, archive/member hashes, source paths and lexical evidence offsets. If note assistance is later approved, distinguish source-text evidence from inferred assertions and record component/rule versions and reviewer decisions in an authorized workflow. Do not introduce raw-note logs, persistent excerpts or cloud transmission merely to obtain an audit trail.
6. **Do not broaden scope by analogy.** The current prototype supports April 1–September 30, 2026 only; out-of-range requests need an explicit unsupported-version response, not a fallback to that catalog. The complete FY2027 pipeline remains separate/pending. CPT, LOINC and SNOMED need separately sourced/versioned terminology and task validation; success in one does not validate another.

## 5. Gap list and benchmark design

### Current gaps that matter

- No demonstrated end-to-end, expert-adjudicated coding performance or calibrated confidence.
- Clause-regex negation, uncertainty, history, family and laterality are intentionally incomplete; no general relation extraction, longitudinal reconciliation or setting-aware coding.
- Lookup provenance and valid catalog membership do not resolve correct patient attribution, encounter relevance, sequencing or clinical specificity.
- Synthetic examples can test specified behavior and regressions but cannot establish real-site performance, population prevalence, clinical safety or production suitability.
- No PHI/authentication/runtime request logs in this prototype. Do not imply that an unapproved patient-data deployment is safe because the runtime is local or deterministic.

### Draft source-grounded synthetic benchmark categories

Maintain separate **lookup** and **note-assist** tracks. Freeze official release, source citations, expected candidates, prohibited assignments, ambiguity/review labels and lexical spans for every case.

| Category | Required contrast |
| --- | --- |
| Direct lookup | Exact code/official phrase versus abbreviation, synonym, typo and ambiguous acronym |
| Assertion scope | Present versus negated; coordinated lists, punctuation, double negation and distant cues |
| Setting/uncertainty | Same uncertain diagnosis under outpatient versus qualifying inpatient discharge; missing setting must not be guessed |
| Experiencer/history | Patient versus relative; resolved condition versus active chronic disease; appropriate history/encounter Z-code possibilities |
| Temporal/longitudinal | Current versus prior admission, planned versus performed, copied-forward text, contradictory updates |
| Specificity | Supported versus missing laterality/site/severity/encounter character; conflicting details must not force a specific leaf |
| Relationships | Co-occurrence versus supported relation; combination-code and official presumed-relationship conventions; unrelated conditions |
| Catalog/version | Valid assignable leaf versus category, invalid identifier, unsupported release and version mismatch |
| Evidence/robustness | Correct offsets/provenance, insufficient evidence, irrelevant text and held-out synthetic documentation styles/templates |

These are **draft categories, not validated test outcomes**. Require later qualified coding/clinical review, independent adjudication of disagreements and documented acceptance criteria. Select and validate the scoring method before reporting scores; no scoring or benchmarks were run for this report. Hold out source/templates and near-duplicate paraphrase families to reduce leakage. Eventually use appropriately governed external-site evaluation before claiming generalization; synthetic style holdouts are not a substitute.

### End-to-end metrics, not one blended F1

Proposed definitions to validate with experts before use:

- **Reviewed wrong-code rate:** adjudicated wrong patient/encounter/code assignments divided by reviewed proposed assignments; report the review sampling scheme and separate severe attribution errors. On a frozen fully reviewed test set, include all proposed assignments.
- **Top-1 correctness:** correct first candidate divided by cases with an adjudicated supported target; also publish all-case outcomes so abstentions are not hidden.
- **Recall@K:** supported gold targets recovered among top K divided by all supported gold targets, with K and acceptable-equivalence rules fixed beforehand. Separate multi-code target recall from single-target retrieval.
- **Coverage/abstention:** non-abstained cases divided by all eligible cases, plus wrong-code rate at each coverage level; distinguish justified abstention from missed answerable cases.
- **Slice failures:** numerators/denominators and uncertainty for setting, experiencer, history, rare assertion, laterality, relationship, version and held-out-style slices. Do not hide small hard slices inside weighted averages.
- **Additional checks:** invalid/out-of-release candidate rate, unsupported specificity, false-positive assignments on no-supported-code cases, evidence-offset/provenance correctness, reviewer correction burden, and local p50/p95 latency.

Report component metrics separately: mention extraction, assertion status, relation correctness, catalog validity, candidate retrieval and reviewed code assignment. Improvement in one stage is not proof of improvement downstream.

## Recommended next decision

Approve only the draft synthetic benchmark specification and expert-review workflow, if desired. Preserve deterministic lookup and the existing privacy boundary. Do not add an LLM, upgrade catalogs, claim production-grade note coding, or deploy patient-facing/PHI handling on the basis of this vendor article. Those require separate approval and validation.
