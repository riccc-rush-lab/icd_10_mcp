"""Build-time public CDC acquisition/import, never a runtime request path."""

from __future__ import annotations

import argparse
import hashlib
import json
from contextlib import nullcontext
from pathlib import Path
from tempfile import TemporaryDirectory
from urllib.error import URLError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request, build_opener

from .catalog import Catalog
from .importer import import_corpus
from .releases import APRIL_ID, FY2027_ID, get_profile
from .smoke import smoke_check

# Observed official archive bytes, not CDC-published signatures. Member pins and
# full import checks remain independently enforced by the ordinary importer.
ARCHIVES = {
    APRIL_ID: (
        "2026-update",
        (
            "4036ae3696e069cb402b89e163dfabe6c85acd2e2174ff0433b760a8befc47a1",
            "0b50672322cd53b222d007fe703e2708dfa3b34f296eb2016bb3cf2109f0fd64",
        ),
    ),
    FY2027_ID: (
        "2027",
        (
            "93e3ad6004badf470c55bfe679b748ae88fd9b2b421851e409eec382c7713b9a",
            "99b5c2be16ff53eab861cc0be4b1dacba27f687b8ff4bc700679944355037ee0",
        ),
    ),
}


class _PublisherRedirects(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        target = urlsplit(newurl)
        if (
            target.scheme != "https"
            or target.hostname != "ftp.cdc.gov"
            or target.username is not None
            or target.port not in {None, 443}
        ):
            raise URLError("Unsupported publisher redirect")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def _download_archives(release_id: str, directory: Path):
    directory.mkdir()
    profile = get_profile(release_id)
    opener = build_opener(ProxyHandler({}), _PublisherRedirects())
    for archive in [profile["text_archive"], profile["xml_archive"]]:
        url = (
            "https://ftp.cdc.gov/pub/Health_Statistics/NCHS/Publications/ICD10CM/"
            f"{ARCHIVES[release_id][0]}/{archive}"
        )
        request = Request(url, headers={"User-Agent": "icd10-local-mcp-build/0.1"})
        with opener.open(request, timeout=60) as response, (directory / archive).open("xb") as out:
            if response.status != 200:
                raise URLError("Publisher download unavailable")
            size = 0
            while chunk := response.read(1_048_576):
                size += len(chunk)
                if size > 64 * 1_048_576:
                    raise ValueError("Publisher archive exceeded the build limit")
                out.write(chunk)


def build_demo_catalogs(
    output: Path,
    *,
    april_downloads: Path | None = None,
    fy2027_downloads: Path | None = None,
    download: bool = False,
) -> dict:
    """Prepare a new source-only build's immutable artifacts, never overwrite."""
    if download:
        if april_downloads is not None or fy2027_downloads is not None:
            raise ValueError("Choose local sources or explicit download, not both")
    elif april_downloads is None or fy2027_downloads is None:
        raise ValueError("Both local source directories are required")
    output.mkdir(parents=True, exist_ok=False)
    paths = {
        APRIL_ID: "catalog.sqlite3",
        FY2027_ID: "releases/2027/catalog.sqlite3",
    }
    checks = []
    temporary = (
        TemporaryDirectory(prefix="icd10-public-sources-") if download else nullcontext(None)
    )
    with temporary as root:
        for release_id, downloads in [
            (APRIL_ID, april_downloads),
            (FY2027_ID, fy2027_downloads),
        ]:
            if download:
                downloads = Path(root) / release_id
                _download_archives(release_id, downloads)
            profile = get_profile(release_id)
            for archive, expected in zip(
                [profile["text_archive"], profile["xml_archive"]],
                ARCHIVES[release_id][1],
                strict=True,
            ):
                with (downloads / archive).open("rb") as source:
                    if hashlib.file_digest(source, "sha256").hexdigest() != expected:
                        raise ValueError("Source archive checksum mismatch")
            database = output / paths[release_id]
            import_corpus(downloads, database, release_id=release_id)
            checks.append(smoke_check(Catalog(database, release_id=release_id)))
            database.chmod(database.stat().st_mode & ~0o222)
    with (output / "catalogs.json").open("x") as config:
        json.dump(paths, config, indent=2)
        config.write("\n")
    return {"status": "prepared", "network_downloads": download, "catalogs": checks}


def main():
    parser = argparse.ArgumentParser(description="Prepare public terminology build artifacts only.")
    parser.add_argument(
        "--output", type=Path, required=True, help="New, nonexistent output directory"
    )
    parser.add_argument("--april-downloads", type=Path)
    parser.add_argument("--fy2027-downloads", type=Path)
    parser.add_argument(
        "--download", action="store_true", help="Explicitly fetch the four pinned official archives"
    )
    args = parser.parse_args()
    try:
        result = build_demo_catalogs(
            args.output,
            april_downloads=args.april_downloads,
            fy2027_downloads=args.fy2027_downloads,
            download=args.download,
        )
    except Exception:
        print(json.dumps({"status": "failed", "reason": "catalog_build_failed"}))
        raise SystemExit(2) from None
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
