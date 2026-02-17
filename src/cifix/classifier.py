
"""
Core classification engine.

Takes raw CI logs → preprocesses → matches patterns → returns
structured ClassifiedError results with infra-vs-code triage.
"""

from dataclasses import dataclass, field

from cifix.patterns import (
    ErrorCategory,
    ErrorSeverity,
    get_code_patterns,
    get_infra_patterns,
)
from cifix.preprocessor import StepBlock, get_preprocessor


@dataclass
class ClassifiedError:
    category: ErrorCategory
    error_type: str
    summary: str
    severity: ErrorSeverity = ErrorSeverity.ERROR
    source_lines: list[str] = field(default_factory=list)
    step_name: str = ""
    suggestion: str = ""
    match_text: str = ""  # raw matched text for downstream phases

    def to_dict(self) -> dict:
        return {
            "category": self.category.value,
            "error_type": self.error_type,
            "summary": self.summary,
            "severity": self.severity.value,
            "source_lines": self.source_lines,
            "step_name": self.step_name,
            "suggestion": self.suggestion,
            "match_text": self.match_text,
        }


@dataclass
class AnalysisResult:
    """Full analysis of a CI run."""
    errors: list[ClassifiedError]
    verdict: str  # "infrastructure", "code", "both", "clean"
    infra_count: int = 0
    code_count: int = 0

    @property
    def has_errors(self) -> bool:
        return len(self.errors) > 0

    def to_dict(self) -> dict:
        return {
            "verdict": self.verdict,
            "infra_count": self.infra_count,
            "code_count": self.code_count,
            "errors": [e.to_dict() for e in self.errors],
        }


def _context_window(lines: list[str], idx: int, window: int = 2) -> list[str]:
    start = max(0, idx - window)
    end = min(len(lines), idx + window + 1)
    return lines[start:end]


def _classify_block(
    block: StepBlock,
) -> list[ClassifiedError]:
    """Classify errors in a single step block."""
    infra_patterns = get_infra_patterns()
    code_patterns = get_code_patterns()
    errors: list[ClassifiedError] = []
    seen: set[tuple[str, str]] = set()
    lines = block.text.splitlines()

    for i, line in enumerate(lines):
        matched = False

        # Infrastructure patterns first — they take priority
        for pattern, err_type, severity, suggestion in infra_patterns:
            m = pattern.search(line)
            if m:
                summary = m.group(0).strip()[:200]
                key = (err_type, summary)
                if key not in seen:
                    seen.add(key)
                    errors.append(ClassifiedError(
                        category=ErrorCategory.INFRASTRUCTURE,
                        error_type=err_type,
                        summary=summary,
                        severity=severity,
                        source_lines=_context_window(lines, i),
                        step_name=block.name,
                        suggestion=suggestion,
                        match_text=m.group(0),
                    ))
                matched = True
                break

        if matched:
            continue

        # Code patterns
        for pattern, err_type, severity, suggestion in code_patterns:
            m = pattern.search(line)
            if m:
                summary = m.group(0).strip()[:200]
                key = (err_type, summary)
                if key not in seen:
                    seen.add(key)
                    errors.append(ClassifiedError(
                        category=ErrorCategory.CODE,
                        error_type=err_type,
                        summary=summary,
                        severity=severity,
                        source_lines=_context_window(lines, i),
                        step_name=block.name,
                        suggestion=suggestion,
                        match_text=m.group(0),
                    ))
                break

    return errors


def classify(raw_log: str, provider: str = "github") -> AnalysisResult:
    """
    Classify all errors in a CI log.

    Args:
        raw_log: Raw log text from CI provider.
        provider: CI provider name ("github", "gitlab", etc.)

    Returns:
        AnalysisResult with classified errors and a verdict.
    """
    preprocessor = get_preprocessor(provider)
    blocks = preprocessor.split_steps(raw_log)

    all_errors: list[ClassifiedError] = []
    for block in blocks:
        all_errors.extend(_classify_block(block))

    # Sort: infra first, then by severity
    sev_rank = {ErrorSeverity.FATAL: 0, ErrorSeverity.ERROR: 1, ErrorSeverity.WARNING: 2}
    cat_rank = {ErrorCategory.INFRASTRUCTURE: 0, ErrorCategory.CODE: 1, ErrorCategory.UNKNOWN: 2}
    all_errors.sort(key=lambda e: (cat_rank[e.category], sev_rank[e.severity]))

    infra = sum(1 for e in all_errors if e.category == ErrorCategory.INFRASTRUCTURE)
    code = sum(1 for e in all_errors if e.category == ErrorCategory.CODE)

    if infra and code:
        verdict = "both"
    elif infra:
        verdict = "infrastructure"
    elif code:
        verdict = "code"
    else:
        verdict = "clean"

    return AnalysisResult(
        errors=all_errors,
        verdict=verdict,
        infra_count=infra,
        code_count=code,
    )