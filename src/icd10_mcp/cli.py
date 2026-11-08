"""Local command-line lookup and catalog maintenance."""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from pathlib import Path
from zipfile import BadZipFile

from .capabilities import scoring_status
from .catalog import Catalog, configured_catalog
from .evaluation import evaluate
from .importer import import_corpus
from .releases import APRIL_ID, PROFILES
from .service import ICDService
from .smoke import smoke_check


def main():
    parser = argparse.ArgumentParser(description="Local ICD-10-CM lookup, synthetic use only.")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("scoring-status", help="Explain why score calculation is disabled.")
    trial = commands.add_parser(
        "trial-check", help="Check local catalogs and MCP; never certify clinical readiness."
    )
    trial.add_argument("--catalog-config", type=Path, required=True)
    importer = commands.add_parser("import", help="Build a complete release catalog, no overwrite.")
    importer.add_argument("--downloads", type=Path, default=Path.home() / "Downloads")
    importer.add_argument("--database", type=Path, default=Path("data/catalog.sqlite3"))
    smoke = commands.add_parser("smoke", help="Check the full imported corpus.")
    smoke.add_argument("--database", type=Path, default=Path("data/catalog.sqlite3"))
    for command in [importer, smoke]:
        command.add_argument("--release", choices=list(PROFILES), default=APRIL_ID)
    lookup = commands.add_parser("lookup", help="Look up a code or phrase.")
    lookup.add_argument("query")
    lookup.add_argument("--date", required=True, help="YYYY-MM-DD service date")
    lookup.add_argument("--database", type=Path, default=Path("data/catalog.sqlite3"))
    lookup.add_argument("--limit", type=int, default=10)
    lookup.add_argument("--catalog-config", type=Path, help="JSON release-to-catalog path map")
    evaluation = commands.add_parser(
        "evaluate", help="Evaluate synthetic cases, never certify coding."
    )
    evaluation.add_argument("benchmark", type=Path)
    evaluation.add_argument("--database", type=Path, default=Path("data/catalog.sqlite3"))
    evaluation.add_argument("--catalog-config", type=Path)
    evaluation.add_argument("--limit", type=int, default=10)
    evaluation.add_argument(
        "--models", type=Path, help="Explicit optional local OpenMed model root"
    )
    evaluation.add_argument("--nlp-python", type=Path)
    note = commands.add_parser("match-note", help="OPTIONAL local OpenMed, synthetic notes only.")
    note.add_argument("--file", type=Path, required=True)
    note.add_argument("--synthetic", action="store_true", required=True)
    note.add_argument("--date", required=True)
    note.add_argument("--database", type=Path, default=Path("data/catalog.sqlite3"))
    note.add_argument("--catalog-config", type=Path)
    note.add_argument("--models", type=Path, default=Path("data/models/openmed-pilot"))
    note.add_argument("--nlp-python", type=Path, default=Path("data/openmed-venv/bin/python"))
    args = parser.parse_args()
    try:
        if args.command == "scoring-status":
            result = scoring_status()
        elif args.command == "trial-check":
            from .trial import check_local_trial

            result = check_local_trial(args.catalog_config)
        elif args.command == "match-note":
            from .nlp import LocalNLP

            if args.file.stat().st_size > 100_000:
                raise ValueError("Synthetic note file is too large")
            result = LocalNLP(
                python=args.nlp_python,
                ner_dir=args.models / "ner",
                pii_dir=args.models / "pii",
            ).analyze(
                args.file.read_text(),
                ICDService(
                    configured_catalog(
                        args.database,
                        args.catalog_config,
                    )
                ),
                args.date,
                synthetic=args.synthetic,
            )
        elif args.command == "import":
            result = import_corpus(args.downloads, args.database, release_id=args.release)
        elif args.command == "smoke":
            result = smoke_check(Catalog(args.database, release_id=args.release))
        elif args.command == "evaluate":
            nlp = None
            if bool(args.models) != bool(args.nlp_python):
                raise ValueError("OpenMed evaluation requires both --models and --nlp-python")
            if args.models is not None:
                from .nlp import LocalNLP

                nlp = LocalNLP(
                    python=args.nlp_python,
                    ner_dir=args.models / "ner",
                    pii_dir=args.models / "pii",
                )
            result = evaluate(
                ICDService(configured_catalog(args.database, args.catalog_config)),
                json.loads(args.benchmark.read_text()),
                limit=args.limit,
                nlp=nlp,
            )
        else:
            result = ICDService(configured_catalog(args.database, args.catalog_config)).search(
                args.query, args.date, args.limit
            )
    except (OSError, ValueError, KeyError, sqlite3.Error, BadZipFile) as exc:
        # Import/maintenance errors contain no user note text.
        message = (
            "Local note input or configuration unavailable"
            if args.command == "match-note"
            else str(exc)
        )
        print(json.dumps({"status": "error", "message": message}), file=sys.stderr)
        raise SystemExit(1) from None
    print(json.dumps(result, indent=2, ensure_ascii=False))
    if result.get("status") in {
        "release_unavailable",
        "catalog_unavailable",
        "invalid_request",
        "nlp_unavailable",
        "not_ready",
    }:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
