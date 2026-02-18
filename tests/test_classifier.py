
"""
Tests for Phase 2 classification.
Run with: pytest tests/test_classifier.py -v
"""

import pytest
from cifix.classifier import classify
from cifix.patterns import ErrorCategory, ErrorSeverity


# -- Fixtures: sample logs --

INFRA_LOG = """
2024-01-15T10:30:06Z ##[group]Install dependencies
2024-01-15T10:30:45Z ERROR: Could not find a version that satisfies the requirement torch==2.5.0
2024-01-15T10:30:45Z ERROR: No matching distribution found for torch==2.5.0
2024-01-15T10:30:46Z ##[endgroup]
2024-01-15T10:31:00Z ##[error]Process completed with exit code 1.
"""

CODE_LOG = """
2024-01-15T10:32:00Z ##[group]Run ruff check
2024-01-15T10:32:01Z src/app.py:42:5: E302 expected 2 blank lines, got 1
2024-01-15T10:32:01Z src/app.py:87:1: F401 'os' imported but unused
2024-01-15T10:32:02Z ##[endgroup]
2024-01-15T10:32:03Z ##[group]Run pytest
2024-01-15T10:32:10Z FAILED tests/test_api.py::test_login - AssertionError: assert 401 == 200
2024-01-15T10:32:11Z === 1 failed, 15 passed in 4.32s ===
2024-01-15T10:32:12Z ##[endgroup]
"""

MIXED_LOG = """
2024-01-15T10:33:00Z ##[group]Build Docker image
2024-01-15T10:33:30Z failed to fetch https://ghcr.io/v2/myorg/base:latest
2024-01-15T10:33:30Z Error: connection timed out
2024-01-15T10:33:31Z ##[endgroup]
2024-01-15T10:33:32Z ##[group]Run tests
2024-01-15T10:33:40Z Traceback (most recent call last):
2024-01-15T10:33:40Z   File "src/main.py", line 12, in <module>
2024-01-15T10:33:40Z     from config import Settings
2024-01-15T10:33:40Z ModuleNotFoundError: No module named 'config'
2024-01-15T10:33:41Z ##[endgroup]
"""

CLEAN_LOG = """
2024-01-15T10:34:00Z ##[group]Run tests
2024-01-15T10:34:05Z ====== 42 passed in 3.21s ======
2024-01-15T10:34:06Z ##[endgroup]
"""

PERMISSIONS_LOG = """
2024-01-15T10:35:00Z ##[group]Deploy
2024-01-15T10:35:05Z Error: Resource not accessible by integration
2024-01-15T10:35:06Z ##[endgroup]
"""

OOM_LOG = """
2024-01-15T10:36:00Z ##[group]Build
2024-01-15T10:36:30Z Cannot allocate memory
2024-01-15T10:36:31Z ##[endgroup]
"""

SECRET_LOG = """
2024-01-15T10:37:00Z ##[group]Setup
2024-01-15T10:37:01Z secret AWS_ACCESS_KEY_ID not found
2024-01-15T10:37:02Z ##[endgroup]
"""


# -- Tests --

class TestVerdict:
    def test_infra_only(self):
        result = classify(INFRA_LOG)
        assert result.verdict == "infrastructure"
        assert result.infra_count > 0
        assert result.code_count == 0

    def test_code_only(self):
        result = classify(CODE_LOG)
        assert result.verdict == "code"
        assert result.code_count > 0
        assert result.infra_count == 0

    def test_mixed(self):
        result = classify(MIXED_LOG)
        assert result.verdict == "both"
        assert result.infra_count > 0
        assert result.code_count > 0

    def test_clean(self):
        result = classify(CLEAN_LOG)
        assert result.verdict == "clean"
        assert not result.has_errors


class TestInfraPatterns:
    def test_dependency_resolution(self):
        result = classify(INFRA_LOG)
        types = {e.error_type for e in result.errors}
        assert "dependency_resolution" in types

    def test_permissions(self):
        result = classify(PERMISSIONS_LOG)
        types = {e.error_type for e in result.errors}
        assert "permissions" in types

    def test_out_of_memory(self):
        result = classify(OOM_LOG)
        fatal = [e for e in result.errors if e.severity == ErrorSeverity.FATAL]
        assert any(e.error_type == "out_of_memory" for e in fatal)

    def test_missing_secret(self):
        result = classify(SECRET_LOG)
        types = {e.error_type for e in result.errors}
        assert "missing_secret" in types


class TestCodePatterns:
    def test_lint_violation(self):
        result = classify(CODE_LOG)
        types = {e.error_type for e in result.errors}
        assert "lint_violation" in types

    def test_test_failure(self):
        result = classify(CODE_LOG)
        types = {e.error_type for e in result.errors}
        assert "test_failure" in types

    def test_import_error(self):
        result = classify(MIXED_LOG)
        code_errors = [e for e in result.errors if e.category == ErrorCategory.CODE]
        types = {e.error_type for e in code_errors}
        assert "import_error" in types


class TestStructure:
    def test_errors_sorted_infra_first(self):
        result = classify(MIXED_LOG)
        categories = [e.category for e in result.errors]
        infra_idx = [i for i, c in enumerate(categories) if c == ErrorCategory.INFRASTRUCTURE]
        code_idx = [i for i, c in enumerate(categories) if c == ErrorCategory.CODE]
        if infra_idx and code_idx:
            assert max(infra_idx) < min(code_idx)

    def test_to_dict_roundtrip(self):
        result = classify(MIXED_LOG)
        d = result.to_dict()
        assert "verdict" in d
        assert "errors" in d
        assert isinstance(d["errors"], list)
        for err in d["errors"]:
            assert "category" in err
            assert "error_type" in err

    def test_step_names_captured(self):
        result = classify(CODE_LOG)
        steps = {e.step_name for e in result.errors}
        assert any("ruff" in s.lower() or "pytest" in s.lower() for s in steps)

    def test_context_lines_present(self):
        result = classify(MIXED_LOG)
        for e in result.errors:
            assert len(e.source_lines) > 0