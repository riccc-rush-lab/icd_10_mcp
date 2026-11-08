"""Explicit public-weight acquisition only. No notes or inference, no remote code.

Run from the project root with PYTHONPATH=src and the isolated optional interpreter.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from pathlib import Path

from huggingface_hub import HfApi, hf_hub_download

from icd10_mcp.model_policy import (
    ALLOWED_MODEL_FILES,
    MODEL_LICENSE,
    MODEL_PINS,
    REQUIRED_MODEL_FILES,
)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    root = args.output.expanduser().resolve()
    for role, (repo, revision) in MODEL_PINS.items():
        destination = root / role
        if destination.exists():
            raise FileExistsError("Refusing to replace staged model artifacts")
        info = HfApi(token=False).model_info(repo, revision=revision, files_metadata=True)
        if info.sha != revision or info.card_data.get("license") != MODEL_LICENSE:
            raise ValueError("Model revision or publisher-declared license mismatch")
        files = [item for item in info.siblings if item.rfilename in ALLOWED_MODEL_FILES]
        names = {item.rfilename for item in files}
        if not REQUIRED_MODEL_FILES <= names:
            raise ValueError("Missing required safe model artifacts")
        destination.mkdir(parents=True)
        manifest = {
            "schema_version": 1,
            "role": role,
            "repo": repo,
            "revision": revision,
            "license": MODEL_LICENSE,
            "files": [],
            "usage": "Local synthetic research only; no dataset or model redistribution. "
            "Publisher weight license is recorded, not independent training-rights clearance.",
        }
        for item in files:
            source = Path(
                hf_hub_download(
                    repo,
                    item.rfilename,
                    revision=revision,
                    token=False,
                )
            )
            target = destination / item.rfilename
            shutil.copyfile(source, target)
            with target.open("rb") as stream:
                checksum = hashlib.file_digest(stream, "sha256").hexdigest()
            lfs = getattr(item, "lfs", None)
            if lfs is not None and checksum != lfs.sha256:
                raise ValueError("Model artifact disagrees with publisher LFS SHA-256")
            manifest["files"].append(
                {
                    "name": item.rfilename,
                    "bytes": target.stat().st_size,
                    "sha256": checksum,
                }
            )
        with (destination / "manifest.json").open("x") as stream:
            json.dump(manifest, stream, indent=2)
            stream.write("\n")
        print(json.dumps({"role": role, "revision": revision, "directory": str(destination)}))


if __name__ == "__main__":
    main()
