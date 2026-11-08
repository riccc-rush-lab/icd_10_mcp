"""Argument errors shared by public-terminology client commands."""

import argparse
import json
import sys


class SafeArgumentParser(argparse.ArgumentParser):
    def error(self, message):
        print(
            json.dumps(
                {"status": "invalid_request", "message": "Invalid command arguments; use --help."}
            ),
            file=sys.stderr,
        )
        raise SystemExit(2)
