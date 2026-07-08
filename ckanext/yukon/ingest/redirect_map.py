from __future__ import annotations

from pathlib import Path
from urllib.parse import quote, urlparse

from typing_extensions import override


class RedirectMap:
    """Accumulates old -> new URL mappings and can emit a Nginx map file."""

    def __init__(self) -> None:
        self._pairs: list[tuple[str, str]] = []

    def add(self, old_url: str, new_url: str) -> None:
        old = _normalise(old_url)
        new = _normalise(new_url)
        if old and new:
            self._pairs.append((old, new))

    def write(self, path: str | Path) -> None:
        with Path(path).open("w", encoding="utf-8") as fp:
            for src, dst in self._pairs:
                fp.write(f"{src} {dst};\n")

    @override
    def __repr__(self) -> str:
        return f"RedirectMap of {len(self._pairs)} pairs."


def _normalise(url: str) -> str:
    """Return path+query only, URL‑encoded, starting with a slash."""
    if not url:
        return ""
    parsed = urlparse(url)
    return quote(parsed.path)
