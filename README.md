# Cifix

A CLI tool for fetching, analyzing, and classifying CI logs from GitHub Actions.

## Installation

```bash
git clone https://github.com/your-username/cifix.git
cd cifix
pip install -e .
```

## Authentication

Cifix requires a GitHub personal access token with `actions:read` scope.

Set it as an environment variable:

```bash
# Linux/macOS
export GITHUB_TOKEN=ghp_your_token_here

# PowerShell
$env:GITHUB_TOKEN = "ghp_your_token_here"
```

Or pass it directly with `--token`.

## Usage

### Fetch workflow run logs

```bash
cifix logs <run_id> --repo <owner/repo>
```

The run ID is the number in the GitHub Actions URL:
`github.com/owner/repo/actions/runs/12345678`

### Classify errors in a CI run

```bash
cifix classify <run_id> --repo <owner/repo>
```

Classifies errors as infrastructure (pipeline/environment) or code issues, with severity levels (fatal, error, warning).

### Examples

```bash
# Fetch raw logs
cifix logs 12345678 --repo octocat/hello-world

# Classify errors
cifix classify 12345678 --repo octocat/hello-world

# Classify with filters
cifix classify 12345678 --repo octocat/hello-world --category code --severity error

# JSON output
cifix classify 12345678 --repo octocat/hello-world --output json

# Pass token directly
cifix logs 12345678 --repo myorg/myrepo --token ghp_xxx
```

### Options

```
cifix --help              Show all commands
cifix logs --help         Show logs options
cifix classify --help     Show classify options
```

#### Classify options

| Option | Description |
|--------|-------------|
| `--repo`, `-r` | GitHub repo (owner/repo) — required |
| `--token`, `-t` | GitHub token (or set GITHUB_TOKEN env var) |
| `--provider`, `-p` | CI provider: github, gitlab, jenkins (default: github) |
| `--output`, `-o` | Output format: text, json (default: text) |
| `--category`, `-c` | Filter by category: all, infra, code (default: all) |
| `--severity`, `-s` | Minimum severity: all, fatal, error, warning (default: all) |

## Project Structure

```
cifix/
├── pyproject.toml
├── README.md
└── src/
    └── cifix/
        ├── __init__.py
        ├── cli.py            # Click CLI entry point
        ├── github.py         # GitHub API client
        ├── classifier.py     # Error classification engine
        ├── patterns.py       # Regex pattern registry
        ├── preprocessor.py   # Log cleaning and step splitting
        └── formatter.py      # Human-readable output formatting
```

## License

MIT