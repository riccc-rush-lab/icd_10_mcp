"""Optional local synthetic-note assistance; never a PHI clearance decision."""

import hashlib
import json
import os
import re
import subprocess
from pathlib import Path

from .model_policy import ALLOWED_MODEL_FILES, MODEL_LICENSE, MODEL_PINS, REQUIRED_MODEL_FILES


def _verified_model(directory, role):
    manifest = json.loads((directory / "manifest.json").read_text())
    if (
        manifest["schema_version"] != 1
        or manifest["role"] != role
        or (manifest["repo"], manifest["revision"]) != MODEL_PINS[role]
        or manifest["license"] != MODEL_LICENSE
    ):
        raise ValueError("Unapproved model identity")
    names = set()
    for item in manifest["files"]:
        name = item["name"]
        if name not in ALLOWED_MODEL_FILES or name in names:
            raise ValueError("Unexpected model artifact")
        names.add(name)
        path = directory / name
        if path.is_symlink() or path.stat().st_size != item["bytes"]:
            raise ValueError("Invalid model artifact")
        with path.open("rb") as stream:
            checksum = hashlib.file_digest(stream, "sha256").hexdigest()
        if not re.fullmatch("[0-9a-f]{64}", item["sha256"]) or checksum != item["sha256"]:
            raise ValueError("Model integrity mismatch")
    if not REQUIRED_MODEL_FILES <= names:
        raise ValueError("Incomplete model")
    if {path.name for path in directory.iterdir()} != names | {"manifest.json"}:
        raise ValueError("Unmanifested model artifacts")
    for name in ["config.json", "tokenizer_config.json"]:
        config = json.loads((directory / name).read_text())
        if not isinstance(config, dict) or "auto_map" in config:
            raise ValueError("Invalid config or forbidden custom model code")
    config = json.loads((directory / "config.json").read_text())
    if config.get("model_type") not in {"bert", "distilbert"}:
        raise ValueError("Unsupported local architecture")
    return manifest


class LocalNLP:
    def __init__(self, *, python, ner_dir, pii_dir):
        self.python = str(Path(python).expanduser().absolute())
        self.ner_dir = Path(ner_dir).resolve()
        self.pii_dir = Path(pii_dir).resolve()

    def analyze(self, text, service, service_date, *, synthetic=False):
        unavailable = {
            "status": "nlp_unavailable",
            "reason": "models_not_verified",
            "pii_scan_completed": False,
            "safe_to_upload": False,
            "candidates": [],
        }
        if synthetic is not True or not isinstance(text, str) or not 1 <= len(text) <= 20_000:
            return {**unavailable, "status": "invalid_request", "reason": "synthetic_text_required"}
        _, metadata, error = service.begin(service_date)
        if error:
            return {**unavailable, **error}
        try:
            manifests = {
                "ner": _verified_model(self.ner_dir, "ner"),
                "pii": _verified_model(self.pii_dir, "pii"),
            }
        except (OSError, ValueError, TypeError, KeyError):
            return unavailable
        env = {
            "PATH": os.defpath,
            "PYTHONPATH": str(Path(__file__).resolve().parents[1]),
            "PYTHONDONTWRITEBYTECODE": "1",
            "OPENMED_OFFLINE": "1",
            "HF_HUB_OFFLINE": "1",
            "TRANSFORMERS_OFFLINE": "1",
            "HF_HUB_DISABLE_TELEMETRY": "1",
            "HF_HUB_DISABLE_PROGRESS_BARS": "1",
            "TOKENIZERS_PARALLELISM": "false",
            "OMP_NUM_THREADS": "2",
            "OTEL_SDK_DISABLED": "true",
            "DO_NOT_TRACK": "1",
        }
        try:
            process = subprocess.run(
                [self.python, "-m", "icd10_mcp.nlp_worker"],
                input=json.dumps(
                    {"text": text, "ner": str(self.ner_dir), "pii": str(self.pii_dir)}
                ),
                capture_output=True,
                text=True,
                timeout=180,
                env=env,
            )
            if process.returncode != 0:
                return {**unavailable, "reason": "inference_failed"}
            output = json.loads(process.stdout)
            if output["status"] != "review_required":
                return {**unavailable, "reason": output["status"]}
        except (OSError, ValueError, KeyError, subprocess.TimeoutExpired):
            return {**unavailable, "reason": "inference_failed"}
        pii = output["pii"]
        spans = []
        for item in sorted(pii, key=lambda value: value["start"]):
            if spans and item["start"] <= spans[-1][1]:
                spans[-1][1] = max(spans[-1][1], item["end"])
            else:
                spans.append([item["start"], item["end"]])
        preview = text
        for start, end in reversed(spans):
            preview = preview[:start] + "[PII]" + preview[end:]
        candidates, mentions = {}, output["ner"]
        for mention in mentions:
            context = mention["context"]
            active = (
                context.get("negation") == "affirmed"
                and context.get("uncertainty") == "certain"
                and context.get("experiencer") == "patient"
                and context.get("temporality") == "recent"
            )
            overlap = any(mention["start"] < end and mention["end"] > start for start, end in spans)
            mention["context_is_advisory"] = True
            mention["lookup_status"] = "context_review_required"
            if active and not overlap:
                lookup = service.search(mention["text"], service_date, limit=5)
                mention["lookup_status"] = lookup["status"]
                mention["candidate_codes"] = [item["code"] for item in lookup.get("candidates", [])]
                for item in lookup.get("candidates", []):
                    if item["code"] not in candidates and len(candidates) >= 25:
                        continue
                    item["evidence_spans"] = [
                        {
                            **span,
                            "start": span["start"] + mention["start"],
                            "end": span["end"] + mention["start"],
                        }
                        for span in item["evidence_spans"]
                    ]
                    existing = candidates.get(item["code"])
                    if existing is None:
                        candidates[item["code"]] = item
                    else:
                        existing["evidence_spans"].extend(
                            span
                            for span in item["evidence_spans"]
                            if span not in existing["evidence_spans"]
                        )
        for candidate in candidates.values():
            validation = service.validate([candidate["code"]], service_date, note=text)
            if "results" not in validation:
                return {
                    **unavailable,
                    **validation,
                    "reason": "documentation_review_failed",
                    "pii_scan_completed": True,
                }
            review = validation["results"][0]
            candidate["assessments"] = {
                "code_validity": review["code_validity"]["status"],
                "documentation_support": review["documentation_support"]["status"],
                "completeness": review["completeness"]["status"],
            }
            candidate["missing_details"] = review["missing_details"]
            candidate["findings"] = review["findings"]
        return {
            "status": "review_required",
            "release": metadata["release"],
            "is_final_assignment": False,
            "safe_to_upload": False,
            "pii_scan_completed": True,
            "offset_basis": "original_input",
            "redacted_preview": preview,
            "pii_findings": [
                {key: value for key, value in item.items() if key not in {"text", "context"}}
                for item in pii
            ],
            "mentions": mentions,
            "candidates": list(candidates.values()),
            "models": manifests,
            "runtime": output["runtime"],
            "warning": "Synthetic-only research. PII detection is incomplete; do not upload "
            "notes or derived concepts. Entity scores and context defaults are not coding "
            "confidence. History/family coding and clinical relations require human review.",
        }
