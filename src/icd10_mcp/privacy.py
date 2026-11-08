"""Lightweight best-effort input screening, not a de-identification guarantee."""

from __future__ import annotations

import re
import unicodedata

from .catalog import CODE_PATTERN, looks_like_code

PRIVACY_NOTICE = {
    "screening": "best_effort",
    "pii_absence_guaranteed": False,
    "patient_data_allowed": False,
}

_IDENTIFIERS = [
    re.compile(pattern, re.IGNORECASE)
    for pattern in (
        r"[^\s@]+@[^\s@]+\.[^\s@]+",
        r"\[(?:at|dot)\]|\((?:at|dot)\)",
        r"\b\d{3}[- ]\d{2}[- ]\d{4}\b",
        r"(?<!\w)(?:\+?\d[\d ().-]{7,}\d)(?!\w)",
        r"\b\d{7,}\b",
        r"\b(?:name|dob|mrn|ssn|address|email|phone|contact|patient)\s*[:=#]",
        r"\b(?:ssn|mrn|dob|date of birth|medical record|chart number)\b",
        r"https?://|www\.|\b(?:\d{1,3}\.){3}\d{1,3}\b",
        r"\b\d{1,6}\s+(?:[a-z][a-z'’-]*\s+){1,4}"
        r"(?:street|st|avenue|ave|road|rd|lane|ln|drive|dr|boulevard|blvd|court|ct)\b",
        r"\b(?:patient|he|she)\s+(?:has|is|was|reports|presents|states)\b",
    )
]
_NAME_RUN = re.compile(r"\b[A-Z][\w'’-]+(?:[ -]+[A-Z][\w'’-]+)+\b")
_CLINICAL_STARTS = set(
    "acute chronic congestive type diabetes pneumonia pain right left bilateral "
    "malignant benign essential primary secondary generalized bipolar major "
    "unspecified other fracture encounter history family personal injury "
    "deficiency disorder abscess postprocedural postpartum infection "
    "cellulitis bacterial viral cardiac renal hepatic neoplasm".split()
)
_EPONYM_ENDINGS = set(
    "disease syndrome lymphoma anemia anaemia tumor tumour sarcoma fracture "
    "palsy arteritis thyroiditis dementia neuropathy leukemia leukaemia cyst "
    "fever angina encephalitis cancer dystrophy chorea murmur".split()
)
_ACRONYMS = set("HIV AIDS HTN COPD CHF CKD DM AF ARDS MI CAD TBI PTSD UTI DVT PE GERD IBS".split())


def blocked_phrase(query: str) -> bool:
    if not isinstance(query, str) or len(query) > 500 or len(query.split()) > 25:
        return True
    if any(unicodedata.category(char) in {"Cc", "Cf", "Cs"} for char in query):
        return True
    normalized = unicodedata.normalize("NFKC", query)
    if any(pattern.search(normalized) for pattern in _IDENTIFIERS):
        return True
    # Conservative name-shaped runs can be false positives; eponyms are common
    # in terminology. Neither these exceptions nor the patterns prove PII absence.
    for match in _NAME_RUN.finditer(normalized):
        words = match.group().split()
        following = normalized[match.end() :].strip().split(maxsplit=1)
        if (
            words[0].casefold() in _CLINICAL_STARTS
            or words[-1].casefold() in _EPONYM_ENDINGS
            or (following and following[0].casefold() in _EPONYM_ENDINGS)
            or all(word in _ACRONYMS for word in words)
        ):
            continue
        return True
    return False


def blocked_response() -> dict:
    return {
        "status": "privacy_blocked",
        "message": "Use public terminology only. Suspected identifiers or notes are blocked.",
        "privacy": dict(PRIVACY_NOTICE),
    }


def blocked_codes(codes: list[str]) -> bool:
    return (
        not isinstance(codes, list)
        or not 1 <= len(codes) <= 25
        or any(
            not isinstance(code, str)
            or len(code) > 12
            or blocked_phrase(code)
            or not (CODE_PATTERN.fullmatch(code.strip().upper()) or looks_like_code(code))
            for code in codes
        )
    )
