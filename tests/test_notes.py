import pytest

DAY = "2026-04-01"


@pytest.mark.parametrize(
    "note,context",
    [
        ("No pneumonia.", "negated"),
        ("Denies pneumonia.", "negated"),
        ("Pneumonia ruled out.", "negated"),
        ("Resolved pneumonia.", "historical"),
        ("History of pneumonia.", "historical"),
        ("Past medical history: pneumonia.", "historical"),
        ("PMH: pneumonia.", "historical"),
        ("Family history of pneumonia.", "family_history"),
        ("Possible pneumonia.", "uncertain"),
        ("Cannot exclude pneumonia.", "uncertain"),
        ("Pneumonia?", "uncertain"),
    ],
)
def test_noncurrent_mentions_excluded(service, note, context):
    result = service.suggest(note, DAY)
    assert result["status"] == "abstain"
    assert not result["candidates"]
    assert result["excluded_mentions"][0]["context"] == context
    span = result["excluded_mentions"][0]
    assert note[span["start"] : span["end"]] == span["text"]


def test_negation_does_not_cross_clause_boundary(service):
    note = "No pneumonia, but Test infection."
    result = service.suggest(note, DAY)
    assert [candidate["code"] for candidate in result["candidates"]] == ["A00.1"]
    assert result["excluded_mentions"]


def test_note_candidates_need_review_and_preserve_offsets(service):
    note = "Synthetic demo: Pneumonia."
    result = service.suggest(note, DAY)
    assert result["status"] == "needs_clarification"
    item = result["candidates"][0]
    assert item["code"] == "J18.9"
    assert item["assessments"]["documentation_support"] == "partial"
    assert item["missing_details"]
    for span in item["evidence_spans"]:
        assert note[span["start"] : span["end"]] == span["text"]


def test_no_specificity_inference(service):
    result = service.suggest("Test injury.", DAY)
    assert result["candidates"][0]["assessments"]["code_validity"] == "header_not_assignable"
    assert all(not item["is_assignable"] for item in result["candidates"])


def test_table_cell_intent_not_inferred(service):
    assert not service.suggest("Test drug.", DAY)["candidates"]


def test_laterality_conflict_not_suggested(service):
    assert not service.suggest("Left wrist syndrome.", DAY)["candidates"]


def test_unknown_note_abstains_and_is_not_stored(service, catalog_path):
    before = catalog_path.read_bytes()
    assert service.suggest("Nothing matches zzzzz.", DAY)["status"] == "abstain"
    assert catalog_path.read_bytes() == before


def test_note_limits(service):
    assert service.suggest("", DAY)["status"] == "invalid_request"
    assert service.suggest("x" * 20001, DAY)["status"] == "invalid_request"
