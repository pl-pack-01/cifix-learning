"""Phase 3: Automated ruff fix application with diff generation and verification."""

from __future__ import annotations

import difflib
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal


@dataclass
class FileChange:
    """A single file's before/after state."""
    path: Path
    original: str
    fixed: str

    @property
    def has_diff(self) -> bool:
        return self.original != self.fixed

    def unified_diff(self, context_lines: int = 3) -> str:
        return "".join(difflib.unified_diff(
            self.original.splitlines(keepends=True),
            self.fixed.splitlines(keepends=True),
            fromfile=f"a/{self.path}",
            tofile=f"b/{self.path}",
            n=context_lines,
        ))


@dataclass
class FixResult:
    """Outcome of a ruff fix pass."""
    tool: Literal["ruff format", "ruff check --fix"]
    changes: list[FileChange] = field(default_factory=list)
    returncode: int = 0
    stderr: str = ""

    @property
    def files_changed(self) -> int:
        return sum(1 for c in self.changes if c.has_diff)

    @property
    def ok(self) -> bool:
        return self.returncode in (0, 1)  # ruff exits 1 when it finds fixable issues


@dataclass
class VerifyResult:
    """Outcome of the post-fix verification pass."""
    format_clean: bool = False
    check_clean: bool = False
    remaining_issues: str = ""

    @property
    def all_clean(self) -> bool:
        return self.format_clean and self.check_clean


class RuffFixer:
    """Applies ruff format and ruff check --fix to a local repo."""

    def __init__(self, repo_path: str | Path, dry_run: bool = False):
        self.repo_path = Path(repo_path).resolve()
        self.dry_run = dry_run
        self._validate()

    def _validate(self) -> None:
        if not self.repo_path.is_dir():
            raise FileNotFoundError(f"Repo path not found: {self.repo_path}")
        if not shutil.which("ruff"):
            raise EnvironmentError(
                "ruff not found on PATH. Install with: pip install ruff"
            )

    # -- Snapshot helpers --------------------------------------------------

    def _collect_py_files(self, targets: list[str] | None = None) -> list[Path]:
        """Gather Python files, optionally scoped to specific paths."""
        if targets:
            files = []
            for t in targets:
                p = self.repo_path / t
                if p.is_file() and p.suffix == ".py":
                    files.append(p)
                elif p.is_dir():
                    files.extend(p.rglob("*.py"))
            return sorted(set(files))
        return sorted(self.repo_path.rglob("*.py"))

    def _snapshot(self, files: list[Path]) -> dict[Path, str]:
        """Read current contents of all target files."""
        snap = {}
        for f in files:
            try:
                snap[f] = f.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                continue
        return snap

    @staticmethod
    def _diff_snapshots(
        before: dict[Path, str], after: dict[Path, str]
    ) -> list[FileChange]:
        changes = []
        for p in before:
            changes.append(FileChange(
                path=p,
                original=before[p],
                fixed=after.get(p, before[p]),
            ))
        return changes

    def _restore(self, snapshot: dict[Path, str]) -> None:
        """Restore files to their snapshotted state (for dry-run rollback)."""
        for p, content in snapshot.items():
            p.write_text(content, encoding="utf-8")

    # -- Core fix methods --------------------------------------------------

    def _run_ruff(self, args: list[str]) -> subprocess.CompletedProcess:
        return subprocess.run(
            ["ruff", *args],
            cwd=self.repo_path,
            capture_output=True,
            text=True,
        )

    def fix_format(self, targets: list[str] | None = None) -> FixResult:
        """Run `ruff format` on the repo."""
        files = self._collect_py_files(targets)
        before = self._snapshot(files)

        cmd_args = ["format", *(str(f.relative_to(self.repo_path)) for f in files)]
        proc = self._run_ruff(cmd_args)

        after = self._snapshot(files)
        changes = self._diff_snapshots(before, after)

        if self.dry_run:
            self._restore(before)

        return FixResult(
            tool="ruff format",
            changes=changes,
            returncode=proc.returncode,
            stderr=proc.stderr.strip(),
        )

    def fix_check(self, targets: list[str] | None = None) -> FixResult:
        """Run `ruff check --fix` on the repo."""
        files = self._collect_py_files(targets)
        before = self._snapshot(files)

        cmd_args = [
            "check", "--fix",
            *(str(f.relative_to(self.repo_path)) for f in files),
        ]
        proc = self._run_ruff(cmd_args)

        after = self._snapshot(files)
        changes = self._diff_snapshots(before, after)

        if self.dry_run:
            self._restore(before)

        return FixResult(
            tool="ruff check --fix",
            changes=changes,
            returncode=proc.returncode,
            stderr=proc.stderr.strip(),
        )

    def fix_all(self, targets: list[str] | None = None) -> list[FixResult]:
        """Run both format and check --fix in sequence."""
        return [
            self.fix_format(targets),
            self.fix_check(targets),
        ]

    # -- Verification ------------------------------------------------------

    def verify(self, targets: list[str] | None = None) -> VerifyResult:
        """Re-run ruff in check-only mode to confirm fixes took effect."""
        scope = []
        if targets:
            scope = [str(self.repo_path / t) for t in targets]

        fmt_proc = self._run_ruff(["format", "--check", *scope])
        chk_proc = self._run_ruff(["check", *scope])

        remaining = ""
        if chk_proc.stdout.strip():
            remaining = chk_proc.stdout.strip()

        return VerifyResult(
            format_clean=fmt_proc.returncode == 0,
            check_clean=chk_proc.returncode == 0,
            remaining_issues=remaining,
        )


# -- Output formatting -----------------------------------------------------

def format_fix_results(
    results: list[FixResult],
    verify: VerifyResult | None = None,
    show_diff: bool = True,
    dry_run: bool = False,
) -> str:
    """Render fix results as human-readable output."""
    lines: list[str] = []
    mode = "DRY RUN" if dry_run else "APPLIED"
    lines.append(f"── cifix ruff fixer ({mode}) ──\n")

    total_changed = 0
    for res in results:
        changed = res.files_changed
        total_changed += changed
        status = "✓" if res.ok else "✗"
        lines.append(f"  {status} {res.tool}: {changed} file(s) modified")
        if res.stderr:
            for l in res.stderr.splitlines()[:5]:
                lines.append(f"    {l}")

        if show_diff:
            for c in res.changes:
                diff = c.unified_diff()
                if diff:
                    lines.append("")
                    lines.append(diff.rstrip())

    lines.append(f"\n  Total files changed: {total_changed}")

    if verify:
        lines.append("\n── Verification ──")
        fmt_icon = "✓" if verify.format_clean else "✗"
        chk_icon = "✓" if verify.check_clean else "✗"
        lines.append(f"  {fmt_icon} ruff format --check")
        lines.append(f"  {chk_icon} ruff check")
        if verify.remaining_issues:
            lines.append(f"\n  Remaining issues:\n{verify.remaining_issues}")

    lines.append("")
    return "\n".join(lines)