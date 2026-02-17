
"""
Log preprocessing — strips CI-specific noise and splits logs into
step blocks.

Each CI provider gets its own preprocessor. Add new providers by
subclassing LogPreprocessor.
"""

import re
from dataclasses import dataclass


@dataclass
class StepBlock:
    """A single CI step's name and log output."""
    name: str
    text: str
    exit_code: int | None = None


class LogPreprocessor:
    """Base preprocessor. Override for provider-specific behavior."""

    def clean(self, raw: str) -> str:
        """Strip noise common to all providers."""
        # ANSI escape codes
        text = re.sub(r"\x1b\[[0-9;]*m", "", raw)
        return text

    def split_steps(self, raw: str) -> list[StepBlock]:
        """Split log into step blocks. Default: single block."""
        return [StepBlock(name="(full log)", text=self.clean(raw))]


class GitHubActionsPreprocessor(LogPreprocessor):
    """Preprocessor for GitHub Actions logs."""

    _TIMESTAMP = re.compile(r"^\d{4}-\d{2}-\d{2}T[\d:.]+Z\s*", re.M)
    _GROUP_START = re.compile(r"##\[group\](.*)")
    _GROUP_END = re.compile(r"##\[endgroup\]")
    _COMMAND = re.compile(r"^##\[command\].*$", re.M)

    def clean(self, raw: str) -> str:
        text = super().clean(raw)
        text = self._TIMESTAMP.sub("", text)
        text = self._COMMAND.sub("", text)
        return text

    def split_steps(self, raw: str) -> list[StepBlock]:
        cleaned = self.clean(raw)
        lines = cleaned.splitlines()

        blocks: list[StepBlock] = []
        current_name = "(preamble)"
        current_lines: list[str] = []

        for line in lines:
            gstart = self._GROUP_START.match(line)
            if gstart:
                # Save previous block if it has content
                if current_lines:
                    blocks.append(StepBlock(
                        name=current_name,
                        text="\n".join(current_lines),
                    ))
                current_name = gstart.group(1).strip()
                current_lines = []
                continue

            if self._GROUP_END.match(line):
                if current_lines:
                    blocks.append(StepBlock(
                        name=current_name,
                        text="\n".join(current_lines),
                    ))
                current_name = "(between steps)"
                current_lines = []
                continue

            current_lines.append(line)

        # Remaining lines
        if current_lines:
            blocks.append(StepBlock(
                name=current_name,
                text="\n".join(current_lines),
            ))

        # Filter out empty blocks
        return [b for b in blocks if b.text.strip()]

    def extract_exit_code(self, block: StepBlock) -> StepBlock:
        """Try to find exit code in a step block."""
        m = re.search(r"exit code (\d+)", block.text)
        if m:
            block.exit_code = int(m.group(1))
        return block


# Registry of preprocessors — extend as you add CI providers
PREPROCESSORS: dict[str, type[LogPreprocessor]] = {
    "github": GitHubActionsPreprocessor,
    # "gitlab": GitLabPreprocessor,
    # "jenkins": JenkinsPreprocessor,
}


def get_preprocessor(provider: str = "github") -> LogPreprocessor:
    cls = PREPROCESSORS.get(provider)
    if not cls:
        raise ValueError(
            f"Unknown CI provider '{provider}'. "
            f"Available: {', '.join(PREPROCESSORS)}"
        )
    return cls()