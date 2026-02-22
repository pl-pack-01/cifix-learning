"""Tests for cifix logs and classify CLI commands."""

from __future__ import annotations

import json
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from click.testing import CliRunner

from cifix.cli import cli
from cifix.patterns import ErrorCategory, ErrorSeverity


@pytest.fixture
def runner():
    return CliRunner()


@pytest.fixture
def mock_log_files():
    return [
        ("job1/step1.txt", "Step 1 output\nAll good"),
        ("job1/step2.txt", "Error: something failed\nexit code 1"),
    ]


@pytest.fixture
def mock_classify_result():
    """Minimal classification result with one error."""
    err = SimpleNamespace(
        pattern_name="pytest_failure",
        category=ErrorCategory.CODE,
        severity=ErrorSeverity.ERROR,
        tool="pytest",
        file_path="tests/test_foo.py",
        line="FAILED tests/test_foo.py::test_bar",
        matched_text="FAILED tests/test_foo.py::test_bar",
    )
    return SimpleNamespace(
        errors=[err],
        to_dict=lambda: {
            "errors": [{"pattern": "pytest_failure", "file": "tests/test_foo.py"}],
        },
    )


# -- cifix logs ------------------------------------------------------------

class TestLogsCommand:
    @patch("cifix.github.fetch_run_logs")
    def test_fetches_and_displays_logs(self, mock_fetch, runner, mock_log_files):
        mock_fetch.return_value = mock_log_files
        result = runner.invoke(cli, [
            "logs", "12345", "-r", "owner/repo", "-t", "fake-token",
        ])
        assert result.exit_code == 0
        assert "job1/step1.txt" in result.output
        assert "job1/step2.txt" in result.output
        assert "Step 1 output" in result.output
        assert "something failed" in result.output
        mock_fetch.assert_called_once_with("owner/repo", "12345", "fake-token")

    def test_missing_repo_flag(self, runner):
        result = runner.invoke(cli, ["logs", "12345", "-t", "fake-token"])
        assert result.exit_code != 0
        assert "Missing option" in result.output or "required" in result.output.lower()

    def test_missing_token(self, runner):
        """No token passed and no env var should error."""
        result = runner.invoke(cli, ["logs", "12345", "-r", "owner/repo"], env={"GITHUB_TOKEN": ""})
        assert result.exit_code != 0
        assert "token required" in result.output.lower() or "GITHUB_TOKEN" in result.output

    @patch("cifix.github.fetch_run_logs")
    def test_token_from_env(self, mock_fetch, runner, mock_log_files):
        mock_fetch.return_value = mock_log_files
        result = runner.invoke(
            cli,
            ["logs", "12345", "-r", "owner/repo"],
            env={"GITHUB_TOKEN": "ghp_env_token"},
        )
        assert result.exit_code == 0
        mock_fetch.assert_called_once_with("owner/repo", "12345", "ghp_env_token")


# -- cifix classify --------------------------------------------------------

class TestClassifyCommand:
    @patch("cifix.formatter.format_analysis", return_value="Formatted analysis output")
    @patch("cifix.classifier.classify")
    @patch("cifix.github.fetch_run_logs")
    def test_basic_classify(self, mock_fetch, mock_cls, mock_fmt, runner, mock_log_files, mock_classify_result):
        mock_fetch.return_value = mock_log_files
        mock_cls.return_value = mock_classify_result
        result = runner.invoke(cli, [
            "classify", "12345", "-r", "owner/repo", "-t", "fake-token",
        ])
        assert result.exit_code == 0
        assert "Formatted analysis output" in result.output
        mock_cls.assert_called_once()

    @patch("cifix.formatter.format_analysis", return_value="")
    @patch("cifix.classifier.classify")
    @patch("cifix.github.fetch_run_logs")
    def test_json_output(self, mock_fetch, mock_cls, _fmt, runner, mock_log_files, mock_classify_result):
        mock_fetch.return_value = mock_log_files
        mock_cls.return_value = mock_classify_result
        result = runner.invoke(cli, [
            "classify", "12345", "-r", "owner/repo", "-t", "fake-token", "-o", "json",
        ])
        assert result.exit_code == 0
        payload = json.loads(result.output.split("Classifying errors...")[-1].strip())
        assert "errors" in payload

    @patch("cifix.formatter.format_analysis", return_value="Filtered output")
    @patch("cifix.classifier.classify")
    @patch("cifix.github.fetch_run_logs")
    def test_category_filter(self, mock_fetch, mock_cls, _fmt, runner, mock_log_files, mock_classify_result):
        mock_fetch.return_value = mock_log_files
        mock_cls.return_value = mock_classify_result
        result = runner.invoke(cli, [
            "classify", "12345", "-r", "owner/repo", "-t", "fake-token", "-c", "infra",
        ])
        assert result.exit_code == 0

    @patch("cifix.formatter.format_analysis", return_value="Filtered output")
    @patch("cifix.classifier.classify")
    @patch("cifix.github.fetch_run_logs")
    def test_severity_filter(self, mock_fetch, mock_cls, _fmt, runner, mock_log_files, mock_classify_result):
        mock_fetch.return_value = mock_log_files
        mock_cls.return_value = mock_classify_result
        result = runner.invoke(cli, [
            "classify", "12345", "-r", "owner/repo", "-t", "fake-token", "-s", "fatal",
        ])
        assert result.exit_code == 0

    def test_missing_repo_flag(self, runner):
        result = runner.invoke(cli, ["classify", "12345", "-t", "fake-token"])
        assert result.exit_code != 0

    def test_invalid_output_format(self, runner):
        result = runner.invoke(cli, [
            "classify", "12345", "-r", "owner/repo", "-t", "fake-token", "-o", "xml",
        ])
        assert result.exit_code != 0


# -- cifix --help ----------------------------------------------------------

class TestHelpOutput:
    def test_main_help(self, runner):
        result = runner.invoke(cli, ["--help"])
        assert result.exit_code == 0
        assert "logs" in result.output
        assert "classify" in result.output
        assert "fix" in result.output
        assert "diagnose" in result.output

    def test_logs_help(self, runner):
        result = runner.invoke(cli, ["logs", "--help"])
        assert result.exit_code == 0
        assert "--repo" in result.output

    def test_classify_help(self, runner):
        result = runner.invoke(cli, ["classify", "--help"])
        assert result.exit_code == 0
        assert "--category" in result.output
        assert "--severity" in result.output

    def test_fix_help(self, runner):
        result = runner.invoke(cli, ["fix", "--help"])
        assert result.exit_code == 0
        assert "--dry-run" in result.output

    def test_diagnose_help(self, runner):
        result = runner.invoke(cli, ["diagnose", "--help"])
        assert result.exit_code == 0
        assert "--no-fix" in result.output