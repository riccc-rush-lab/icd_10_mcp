"""Explicitly unavailable scoring, not an unvalidated calculation placeholder."""


def scoring_status() -> dict:
    return {
        "status": "not_configured",
        "calculation_enabled": False,
        "available_methods": [],
        "required_evidence": [
            "method_version",
            "required_inputs",
            "mapping_source_and_license",
            "supported_terminology_releases",
            "independent_worked_examples",
            "expert_review",
        ],
        "message": "No scoring method has been selected or validated. APACHE requires "
        "physiological and clinical inputs, not ICD codes alone.",
    }
