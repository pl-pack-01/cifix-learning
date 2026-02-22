"""Tests for Phase 3: RuffFixer."""

from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from cifix.fixer.ruff_fixer import (
    FileChange,
    FixResult,
    RuffFixer,
    VerifyResult,
    format_fix_results,
)


# -- FileChange -----------------------------------------------------------

class TestFileChange:
    def test_has_diff_true(self, tmp_path):
        fc = FileChange(path=tmp_path / "f.py", original="x = 1\n", fixed="x = 2\n")
        assert fc.has_diff is True

    def test_has_diff_false(self, tmp_path):
        fc = FileChange(path=tmp_path / "f.py", original="x = 1\n", fixed="x = 1\n")
        assert fc.has_diff is False

    def test_unified_diff_output(self, tmp_path):
        fc = FileChange(
            path=tmp_path / "f.py",
            original="import os\nimport sys\n",
            fixed="import sys\n",
        )
        diff = fc.unified_diff()
        assert "---" in diff
        assert "+++" in diff
        assert "-import os" in diff


# -- FixResult ------------------------------------------------------------

class TestFixResult:
    def test_files_changed_count(self, tmp_path):
        res = FixResult(
            tool="ruff format",
            changes=[
                FileChange(tmp_path / "a.py", "x=1\n", "x = 1\n"),
                FileChange(tmp_path / "b.py", "y=2\n", "y=2\n"),  # no change
            ],
        )
        assert res.files_changed == 1

    def test_ok_on_returncode_0(self):
        assert FixResult(tool="ruff format", returncode=0).ok is True

    def test_ok_on_returncode_1(self):
        assert FixResult(tool="ruff format", returncode=1).ok is True

    def test_not_ok_on_returncode_2(self):
        assert FixResult(tool="ruff format", returncode=2).ok is False


# -- VerifyResult ----------------------------------------------------------

class TestVerifyResult:
    def test_all_clean(self):
        v = VerifyResult(format_clean=True, check_clean=True)
        assert v.all_clean is True

    def test_not_clean(self):
        v = VerifyResult(format_clean=True, check_clean=False, remaining_issues="E501")
        assert v.all_clean is False


# -- RuffFixer (with real files, mocked subprocess) ------------------------

@pytest.fixture
def repo(tmp_path):
    """Create a minimal repo with a badly-formatted Python file."""
    src = tmp_path / "src"
    src.mkdir()
    bad_file = src / "app.py"
    bad_file.write_text("import os\nimport   sys\nx=1\n", encoding="utf-8")
    return tmp_path


class TestRuffFixerInit:
    def test_missing_repo_path(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            RuffFixer(tmp_path / "nonexistent")

    @patch("shutil.which", return_value=None)
    def test_missing_ruff(self, _mock, tmp_path):
        with pytest.raises(EnvironmentError, match="ruff not found"):
            RuffFixer(tmp_path)


class TestRuffFixerCollect:
    @patch("shutil.which", return_value="/usr/bin/ruff")
    def test_collects_py_files(self, _mock, repo):
        fixer = RuffFixer(repo)
        files = fixer._collect_py_files()
        assert len(files) == 1
        assert files[0].name == "app.py"

    @patch("shutil.which", return_value="/usr/bin/ruff")
    def test_collects_scoped_targets(self, _mock, repo):
        fixer = RuffFixer(repo)
        files = fixer._collect_py_files(targets=["src/app.py"])
        assert len(files) == 1

    @patch("shutil.which", return_value="/usr/bin/ruff")
    def test_collects_directory_target(self, _mock, repo):
        fixer = RuffFixer(repo)
        files = fixer._collect_py_files(targets=["src"])
        assert len(files) == 1


class TestRuffFixerDryRun:
    @patch("shutil.which", return_value="/usr/bin/ruff")
    @patch("subprocess.run")
    def test_dry_run_restores_files(self, mock_run, _which, repo):
        """Dry run should leave files unchanged even if ruff modifies them."""
        original_content = (repo / "src" / "app.py").read_text()

        def fake_ruff(args, **kwargs):
            # Simulate ruff modifying the file
            if "format" in args:
                (repo / "src" / "app.py").write_text("import os\nimport sys\n\nx = 1\n")
            return subprocess.CompletedProcess(args, 0, "", "")

        mock_run.side_effect = fake_ruff

        fixer = RuffFixer(repo, dry_run=True)
        result = fixer.fix_format()

        # File should be restored
        assert (repo / "src" / "app.py").read_text() == original_content
        # But diff should still be captured
        assert result.files_changed == 1


class TestRuffFixerApply:
    @patch("shutil.which", return_value="/usr/bin/ruff")
    @patch("subprocess.run")
    def test_apply_keeps_changes(self, mock_run, _which, repo):
        """Non-dry-run should leave ruff's changes in place."""
        fixed_content = "import os\nimport sys\n\nx = 1\n"

        def fake_ruff(args, **kwargs):
            if "format" in args:
                (repo / "src" / "app.py").write_text(fixed_content)
            return subprocess.CompletedProcess(args, 0, "", "")

        mock_run.side_effect = fake_ruff

        fixer = RuffFixer(repo, dry_run=False)
        fixer.fix_format()

        assert (repo / "src" / "app.py").read_text() == fixed_content

    @patch("shutil.which", return_value="/usr/bin/ruff")
    @patch("subprocess.run")
    def test_fix_all_runs_both(self, mock_run, _which, repo):
        mock_run.return_value = subprocess.CompletedProcess([], 0, "", "")
        fixer = RuffFixer(repo)
        results = fixer.fix_all()
        assert len(results) == 2
        assert results[0].tool == "ruff format"
        assert results[1].tool == "ruff check --fix"


class TestRuffFixerVerify:
    @patch("shutil.which", return_value="/usr/bin/ruff")
    @patch("subprocess.run")
    def test_verify_clean(self, mock_run, _which, repo):
        mock_run.return_value = subprocess.CompletedProcess([], 0, "", "")
        fixer = RuffFixer(repo)
        v = fixer.verify()
        assert v.all_clean is True

    @patch("shutil.which", return_value="/usr/bin/ruff")
    @patch("subprocess.run")
    def test_verify_with_remaining(self, mock_run, _which, repo):
        def side_effect(args, **kwargs):
            if "--check" in args:
                return subprocess.CompletedProcess(args, 0, "", "")
            # ruff check (no --check) returns issues
            return subprocess.CompletedProcess(args, 1, "src/app.py:1:1: E501", "")

        mock_run.side_effect = side_effect
        fixer = RuffFixer(repo)
        v = fixer.verify()
        assert v.format_clean is True
        assert v.check_clean is False


# -- Output formatting ----------------------------------------------------

class TestFormatFixResults:
    def test_dry_run_label(self):
        out = format_fix_results([], dry_run=True)
        assert "DRY RUN" in out

    def test_applied_label(self):
        out = format_fix_results([], dry_run=False)
        assert "APPLIED" in out

    def test_verification_section(self):
        v = VerifyResult(format_clean=True, check_clean=False, remaining_issues="E501")
        out = format_fix_results([], verify=v)
        assert "Verification" in out
        assert "E501" in out

    def test_includes_diff(self, tmp_path):
        change = FileChange(tmp_path / "f.py", "x=1\n", "x = 1\n")
        res = FixResult(tool="ruff format", changes=[change])
        out = format_fix_results([res], show_diff=True)
        assert "---" in out

    def test_suppresses_diff(self, tmp_path):
        change = FileChange(tmp_path / "f.py", "x=1\n", "x = 1\n")
        res = FixResult(tool="ruff format", changes=[change])
        out = format_fix_results([res], show_diff=False)
        assert "---" not in out