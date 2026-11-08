"""Isolated optional runtime. JSON stdin/stdout, no note logging or downloads."""

import json
import math
import resource
import sys
import time
from contextlib import redirect_stdout
from importlib.metadata import version


def run(request):
    started = time.perf_counter()
    original = request["text"]
    text = original.strip()
    offset = len(original) - len(original.lstrip())
    if version("openmed") != "3.1.0":
        return {"status": "runtime_version_mismatch"}
    from openmed import ModelLoader, OpenMedConfig, analyze_text
    from openmed.core.offline import network_blocked_if_offline
    from openmed.core.safety_sweep import SAFETY_SWEEP_SOURCE, safety_sweep

    config = OpenMedConfig(device="cpu", local_only=True)
    loader = ModelLoader(config)
    output = {}
    flags = {"local_files_only": True, "trust_remote_code": False, "use_safetensors": True}
    with network_blocked_if_offline(config, local_only=True):
        for role in ["ner", "pii"]:
            model = loader.load_model(request[role], **flags)
            tokens = model["tokenizer"](text, truncation=False)["input_ids"]
            if len(tokens) > model["model"].config.max_position_embeddings:
                return {"status": "token_limit_exceeded"}
            result = analyze_text(
                text,
                model_id=request[role],
                loader=loader,
                config=config,
                sentence_detection=False,
                assert_context=role == "ner",
                # Preflight above rejects overlength input; this SDK setting avoids
                # its zero-length tokenizer sentinel without discarding any tokens.
                truncation=True,
                max_length=model["model"].config.max_position_embeddings,
                cache_results=False,
                local_files_only=True,
                trust_remote_code=False,
                model_kwargs={"use_safetensors": True},
            )
            entities = []
            predicted = list(result.entities)
            if role == "pii":
                # Keep full rule matches even when an ML span covers only a fragment.
                predicted.extend(safety_sweep(text, []))
            for item in predicted:
                start, end = item.start, item.end
                if (
                    type(start) is not int
                    or type(end) is not int
                    or not 0 <= start < end <= len(text)
                    or item.text.casefold() != text[start:end].casefold()
                    or not math.isfinite(item.confidence)
                    or not 0 <= item.confidence <= 1
                ):
                    return {"status": "invalid_model_spans"}
                metadata = item.metadata or {}
                rule = metadata.get("source") == SAFETY_SWEEP_SOURCE
                entities.append(
                    {
                        "text": original[start + offset : end + offset],
                        "label": item.label,
                        "start": start + offset,
                        "end": end + offset,
                        "entity_score": None if rule else float(item.confidence),
                        "detector": "deterministic_pattern" if rule else "model",
                        "context": metadata.get("clinical_context", {}),
                    }
                )
            output[role] = entities
    rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return {
        **output,
        "status": "review_required",
        "runtime": {
            "openmed": version("openmed"),
            "torch": version("torch"),
            "transformers": version("transformers"),
            "offline_requested": True,
            "seconds": time.perf_counter() - started,
            "peak_rss_bytes": rss if sys.platform == "darwin" else rss * 1024,
        },
    }


def main():
    try:
        request = json.loads(sys.stdin.read(100_000))
        with redirect_stdout(sys.stderr):
            output = run(request)
    except Exception:
        # Third-party exceptions can contain input text. Never serialize them.
        output = {"status": "inference_failed"}
    print(json.dumps(output))


if __name__ == "__main__":
    main()
