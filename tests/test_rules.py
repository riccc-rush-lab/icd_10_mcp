import pytest

from icd10_mcp.matching import reference_matches

DAY = "2026-04-01"


def test_separate_assessments(service):
    result = service.validate(["A00.1"], DAY, "No Test infection.")["results"][0]
    assert result["code_validity"]["status"] == "valid"
    assert result["documentation_support"]["status"] == "negated_or_noncurrent"
    assert result["completeness"]["status"] == "needs_clarification"


def test_documentation_optional_not_assessed(service):
    result = service.validate(["A00.1"], DAY)["results"][0]
    assert result["documentation_support"]["status"] == "not_assessed"


def test_exact_description_is_lexical_support_not_completeness(service):
    item = service.validate(["A00.1"], DAY, "Synthetic infection.")["results"][0]
    assert item["documentation_support"]["status"] == "lexical_support"
    assert item["completeness"]["status"] != "complete"


def test_code_without_documentation_match_not_disease_inference(service):
    item = service.validate(["A00.1"], DAY, "Synthetic unrelated phrase.")["results"][0]
    assert item["documentation_support"]["status"] == "not_found"


def test_laterality_contradiction(service):
    item = service.validate(["M00.1"], DAY, "Left wrist syndrome.")["results"][0]
    assert item["code_validity"]["status"] == "valid"
    assert item["documentation_support"]["status"] == "conflicting_details"


@pytest.mark.parametrize("code", ["T36.0X1A", "T360X1D", "T36.0X1S"])
def test_valid_seventh_characters(service, code):
    item = service.validate([code], DAY)["results"][0]
    assert item["code_validity"]["status"] == "valid"
    assert any(i["kind"] == "sevenChrDef" for i in item["instructions"])


@pytest.mark.parametrize("code", ["T36.01A", "T36.0X1Q", "T36.0X1"])
def test_missing_placeholder_or_extension_invalid(service, code):
    validity = service.validate([code], DAY)["results"][0]["code_validity"]
    assert validity["status"] == "invalid_code"
    assert validity["reason"] == "seventh_character_or_placeholder_invalid"
    assert validity["required_length"] == 7
    assert set(validity["allowed_seventh_characters"]) == {"A", "D", "S"}


def test_header_and_bad_format_are_distinct(service):
    results = service.validate(["A00", "garbage", "A00..1"], DAY)["results"]
    assert [r["code_validity"]["status"] for r in results] == [
        "header_not_assignable",
        "invalid_format",
        "invalid_format",
    ]


def test_exclusions_are_review_not_code_invalidity(service):
    results = service.validate(["A00.1", "Z00.1", "Z00.2"], DAY)["results"]
    findings = results[0]["findings"]
    assert any(f["status"] == "potential_excludes1_conflict" for f in findings)
    assert any(f["status"] == "coexistence_permitted" for f in findings)
    assert all(r["code_validity"]["status"] == "valid" for r in results)


def test_code_first_and_additional_sequencing(service):
    wrong = service.validate(["G00.1", "B00.1"], DAY)["results"]
    assert any(f["status"] == "sequencing_review" for r in wrong for f in r["findings"])
    right = service.validate(["B00.1", "G00.1"], DAY)["results"]
    assert not any(f["status"] == "sequencing_review" for r in right for f in r["findings"])
    assert any(f["status"] == "referenced_code_present" for r in right for f in r["findings"])


def test_missing_underlying_and_additional_codes(service):
    first = service.validate(["G00.1"], DAY)["results"][0]
    assert any(f["status"] == "underlying_code_review" for f in first["findings"])
    additional = service.validate(["B00.1"], DAY)["results"][0]
    assert any(f["status"] == "additional_code_review" for f in additional["findings"])


def test_code_also_does_not_impose_sequence(service):
    result = service.validate(["G00.1", "Z00.1"], DAY)["results"][0]
    rule = next(f for f in result["findings"] if f["kind"] == "codeAlso")
    assert rule["status"] == "code_also_review"


@pytest.mark.parametrize(
    "text,code,expected",
    [
        ("condition (A00.-)", "A001", True),
        ("condition (A00-A09)", "A051", True),
        ("condition (A00-A09)", "B001", False),
        ("condition (Z00.1)", "Z002", False),
        ("condition (QA0.-)", "QA00101", True),
        ("No interpretable reference", "A001", False),
    ],
)
def test_reference_tokens_and_ranges(text, code, expected):
    assert reference_matches(text, code) is expected


def test_bounds_and_duplicate_selection(service):
    assert service.validate([], DAY)["status"] == "invalid_request"
    assert service.validate(["A001"] * 51, DAY)["status"] == "invalid_request"
    assert service.validate(["A001"], DAY, "x" * 20001)["status"] == "invalid_request"
    item = service.validate(["A001", "A00.1"], DAY)["results"][0]
    assert any(f["status"] == "duplicate_selected_code" for f in item["findings"])
