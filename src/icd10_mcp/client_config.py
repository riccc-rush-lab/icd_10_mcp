"""Local credential-file configuration for public-terminology clients."""

import os
import stat
from pathlib import Path


def load_token_file(path: str) -> str:
    """Read at most 4 KiB; never expose the path or contents in an error."""
    try:
        target = Path(path)
        if not target.is_absolute() or target.is_symlink():
            raise ValueError
        flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0)
        with os.fdopen(os.open(target, flags), "rb") as source:
            metadata = os.fstat(source.fileno())
            if not stat.S_ISREG(metadata.st_mode):
                raise ValueError
            if os.name == "posix" and (
                metadata.st_uid != os.geteuid() or stat.S_IMODE(metadata.st_mode) & 0o077
            ):
                raise ValueError
            raw = source.read(4097)
        if len(raw) > 4096:
            raise ValueError
        return raw.decode("ascii").strip()
    except (OSError, ValueError, TypeError):
        raise ValueError("Invalid private token file.") from None
