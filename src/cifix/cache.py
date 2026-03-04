"""Local disk cache for GitHub Actions log downloads."""

from __future__ import annotations

import json
import os
import re
from pathlib import Path


def get_cache_dir() -> Path:
    """Return the platform-specific cache directory, creating it if needed."""
    if os.name == "nt":
        base = os.environ.get("LOCALAPPDATA") or Path.home() / ".cache"
    else:
        base = os.environ.get("XDG_CACHE_HOME") or Path.home() / ".cache"

    cache_dir = Path(base) / "cifix" / "logs"
    cache_dir.mkdir(parents=True, exist_ok=True)
    return cache_dir


def _cache_key(repo: str, run_id: str) -> str:
    """Produce a safe filename from repo and run_id."""
    safe_repo = re.sub(r"[^\w\-]", "_", repo)
    return f"{safe_repo}_{run_id}.json"


def get(repo: str, run_id: str) -> list[tuple[str, str]] | None:
    """Return cached logs for the given run, or None on miss."""
    path = get_cache_dir() / _cache_key(repo, run_id)
    if not path.exists():
        return None

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return [tuple(entry) for entry in data["logs"]]
    except (json.JSONDecodeError, KeyError, TypeError):
        path.unlink(missing_ok=True)
        return None


def put(repo: str, run_id: str, logs: list[tuple[str, str]]) -> None:
    """Write logs to the cache."""
    path = get_cache_dir() / _cache_key(repo, run_id)
    data = {"repo": repo, "run_id": str(run_id), "logs": logs}
    path.write_text(json.dumps(data), encoding="utf-8")


def clear(repo: str | None = None, run_id: str | None = None) -> int:
    """Delete cached entries. Returns the number of files removed.

    If both repo and run_id are given, deletes that specific entry.
    If only repo is given, deletes all entries for that repo.
    If neither is given, deletes everything.
    """
    cache_dir = get_cache_dir()
    removed = 0

    if repo and run_id:
        path = cache_dir / _cache_key(repo, run_id)
        if path.exists():
            path.unlink()
            removed = 1
    else:
        prefix = re.sub(r"[^\w\-]", "_", repo) + "_" if repo else ""
        for path in cache_dir.glob(f"{prefix}*.json"):
            path.unlink()
            removed += 1

    return removed
