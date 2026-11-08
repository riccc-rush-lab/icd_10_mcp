import pytest

DAY = "2026-04-01"


@pytest.mark.parametrize("code", ["a00.1", "A001", " A00.1 "])
def test_exact_lookup(service, code):
    candidate = service.search(code, DAY)["candidates"][0]
    assert candidate["code"] == "A00.1"
    assert candidate["description"] == "Synthetic infection"
    assert candidate["is_assignable"]
    assert candidate["assessments"]["documentation_support"] == "not_assessed"
    assert candidate["catalog_provenance"]["codes_line"] is not None
    assert candidate["release"]["id"] == "icd10cm-2026-04-01"


def test_header_is_not_assignable(service):
    item = service.search("A00", DAY)["candidates"][0]
    assert not item["is_assignable"]
    assert item["assessments"]["code_validity"] == "header_not_assignable"
    assert item["child_examples"][0]["code"] == "A001"
    assert item["missing_details"]


def test_phrase_index_to_tabular_and_evidence(service):
    result = service.search("Pneumonia", DAY)
    assert result["candidates"][0]["code"] == "J18.9"
    candidate = result["candidates"][0]
    assert candidate["index_path"][0]["references"][0]["value"] == "J18.9"
    span = candidate["evidence_spans"][0]
    assert "Pneumonia"[span["start"] : span["end"]] == span["text"]


def test_nested_index_and_see_reference(service):
    candidate = service.search("Diabetes type 2", DAY)["candidates"][0]
    assert candidate["code"] == "E11.9"
    assert " > " in candidate["index_path"][0]["path"]
    alias = service.search("Infection alias", DAY)["candidates"][0]
    assert alias["code"] == "A00.1"
    assert len(alias["index_path"]) == 2


def test_index_cycle_and_missing_reference_abstain(service):
    for phrase in ["Loop one", "Missing alias"]:
        result = service.search(phrase, DAY)
        assert not result["candidates"]
        assert result["status"] == "needs_clarification"
        assert result["index_matches"]


def test_index_prefix_is_header_not_guessed_extension(service):
    result = service.search("Test injury", DAY)
    candidate = result["candidates"][0]
    assert candidate["code"] == "T36.0"
    assert not candidate["is_assignable"]


def test_table_columns_and_references_preserved(service):
    candidate = service.search("Test drug", DAY)["candidates"][0]
    ref = candidate["index_path"][0]["references"][0]
    assert ref == {"kind": "cell", "value": "T36.0", "column_label": "Accidental poisoning"}


def test_inherited_instructions_and_hierarchy(service):
    candidate = service.search("A00.1", DAY)["candidates"][0]
    assert [node["kind"] for node in candidate["tabular_hierarchy"]] == [
        "chapter",
        "section",
        "diag",
        "diag",
    ]
    assert any(i["kind"] == "notes" and i["inherited"] for i in candidate["instructions"])
    assert any(i["kind"] == "includes" and i["inherited"] for i in candidate["instructions"])
    assert any(i["kind"] == "excludes1" and i["origin"] == "A00" for i in candidate["instructions"])
    assert any(
        i["kind"] == "inclusionTerm" and not i["inherited"] for i in candidate["instructions"]
    )


@pytest.mark.parametrize("day", ["2026-04-01", "2026-09-30"])
def test_effective_boundaries_available(service, day):
    assert service.search("A00.1", day)["status"] == "candidates"


@pytest.mark.parametrize("day", ["2026-03-31", "2026-10-01", "2027-01-01", "2025-10-01"])
def test_dates_outside_release_fail_all_workflows(service, day):
    for result in [
        service.search("A00.1", day),
        service.suggest("Pneumonia", day),
        service.validate(["A00.1"], day),
    ]:
        assert result["status"] == "release_unavailable"


@pytest.mark.parametrize("day", ["2026-02-30", "April 1 2026", "20260401", ""])
def test_bad_dates(service, day):
    assert service.search("A00.1", day)["status"] == "invalid_request"


def test_abstention_and_input_bounds(service):
    assert service.search("zzzzzzzz", DAY)["status"] == "abstain"
    for query, limit in [("", 10), ("x" * 501, 10), ("pneumonia", 26), ("pneumonia", 0)]:
        assert service.search(query, DAY, limit)["status"] == "invalid_request"


def test_unknown_code_is_not_autocorrected(service):
    result = service.search("A00.2", DAY)
    assert result["status"] == "abstain"
    assert result["code_validity"]["status"] == "invalid_code"
    assert not result["candidates"]


def test_alphanumeric_category_supported(service):
    assert service.search("QA0.0101", DAY)["candidates"][0]["is_assignable"]


def test_deterministic(service):
    assert service.search("Pneumonia", DAY) == service.search("Pneumonia", DAY)


@pytest.mark.parametrize(
    "query", ["A00..1", "E11..9", "A0.01", "A.001", "E11/9", "A00-1", "C7..A012", "T36..0XXA"]
)
def test_malformed_code_requests_clarification_without_diagnosis_candidates(service, query):
    result = service.search(query, DAY, limit=1)
    assert result["status"] == "needs_clarification"
    assert result["candidates"] == []
    assert result["code_validity"]["status"] == "invalid_format"


def test_numeric_diagnosis_phrase_still_uses_phrase_lookup(service):
    result = service.search("type 2 diabetes", DAY, limit=1)
    assert [candidate["code"] for candidate in result["candidates"]] == ["E11.9"]


def test_cross_reference_resolves_supplied_heading_alias(service_with_index):
    service = service_with_index("""
        <mainTerm><title>Abnormity</title><see>Anomaly</see></mainTerm>
        <mainTerm><title>Anomaly, anomalous</title><code>A00.1</code></mainTerm>
    """)
    result = service.search("Abnormity", DAY, limit=1)
    assert [item["code"] for item in result["candidates"]] == ["A00.1"]
    path = result["candidates"][0]["index_path"]
    assert [entry["label"] for entry in path] == ["Abnormity", "Anomaly, anomalous"]
    assert all(entry["source_path"] for entry in path)


def test_cross_reference_resolves_aliases_at_each_index_level(service_with_index):
    service = service_with_index("""
        <mainTerm><title>Referral</title><see>Inflammation, acute</see></mainTerm>
        <mainTerm><title>Inflammation, inflammatory</title>
          <term level="1"><title>acute, subacute</title><code>A00.1</code></term>
        </mainTerm>
    """)
    result = service.search("Referral", DAY, limit=1)
    assert [item["code"] for item in result["candidates"]] == ["A00.1"]
    assert result["candidates"][0]["index_path"][-1]["path"] == (
        "Inflammation, inflammatory > acute, subacute"
    )


def test_exact_reference_heading_wins_over_competing_alias(service_with_index):
    service = service_with_index("""
        <mainTerm><title>Referral</title><see>Anomaly</see></mainTerm>
        <mainTerm><title>Anomaly, anomalous</title><code>B00.1</code></mainTerm>
        <mainTerm><title>Anomaly</title><code>A00.1</code></mainTerm>
    """)
    result = service.search("Referral", DAY, limit=1)
    assert [item["code"] for item in result["candidates"]] == ["A00.1"]


def test_ambiguous_reference_alias_requires_review_not_arbitrary_code(service_with_index):
    service = service_with_index("""
        <mainTerm><title>Referral</title><see>Anomaly</see></mainTerm>
        <mainTerm><title>Anomaly, anomalous</title><code>A00.1</code></mainTerm>
        <mainTerm><title>Anomaly, other</title><code>B00.1</code></mainTerm>
    """)
    result = service.search("Referral", DAY)
    assert result["status"] == "needs_clarification"
    assert result["candidates"] == []
    assert result["index_matches"][0]["cross_reference_results"][0]["status"] == (
        "ambiguous_review_required"
    )


def test_index_cycle_is_reported_explicitly(service):
    result = service.search("Loop one", DAY)
    assert result["candidates"] == []
    assert any(
        reference["status"] == "cycle_review_required"
        for entry in result["index_matches"]
        for reference in entry.get("cross_reference_results", [])
    )


@pytest.mark.parametrize("limit", [1, 10])
def test_reference_depth_limit_requires_explicit_review(service_with_index, limit):
    service = service_with_index(
        "".join(
            f"<mainTerm><title>Referral {n}</title><see>Referral {n + 1}</see></mainTerm>"
            for n in range(6)
        )
        + "<mainTerm><title>Referral 6</title><code>A00.1</code></mainTerm>"
    )
    result = service.search("Referral 0", DAY, limit=limit)
    assert result["candidates"] == []
    assert any(
        issue["status"] == "depth_limit_review_required" for issue in result["reference_issues"]
    )


def test_exact_phrase_beats_related_competing_candidate(service_with_index):
    service = service_with_index("""
        <mainTerm><title>Acute cough</title><code>B00.1</code></mainTerm>
        <mainTerm><title>Cough</title><code>A00.1</code></mainTerm>
    """)
    result = service.search("Cough", DAY, limit=1)
    assert [item["code"] for item in result["candidates"]] == ["A00.1"]


def test_numbered_acronym_remains_a_phrase_not_a_malformed_code(service_with_index):
    service = service_with_index("""
        <mainTerm><title>CMML-1</title><code>B00.1</code></mainTerm>
    """)
    result = service.search("CMML-1", DAY, limit=1)
    assert [item["code"] for item in result["candidates"]] == ["B00.1"]


@pytest.mark.parametrize("query", ["B12-deficiency", "B12-low", "B12deficiency"])
def test_numbered_diagnosis_word_is_not_misclassified_as_a_code(service_with_index, query):
    service = service_with_index(f"<mainTerm><title>{query}</title><code>A00.1</code></mainTerm>")
    result = service.search(query, DAY, limit=1)
    assert [item["code"] for item in result["candidates"]] == ["A00.1"]


def test_small_candidate_limit_does_not_hide_reference_cycle(service):
    result = service.search("Loop one", DAY, limit=1)
    assert result["candidates"] == []
    assert any(
        issue["status"] == "cycle_review_required" for issue in result.get("reference_issues", [])
    )
