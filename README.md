# Cifix

A CLI tool for fetching and analyzing CI logs from GitHub Actions.

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
cifix fetch-logs <owner/repo> <run_id>
```

The run ID is the number in the GitHub Actions URL:
`github.com/owner/repo/actions/runs/12345678`

### Examples

```bash
# Using $GITHUB_TOKEN env var
cifix fetch-logs octocat/hello-world 12345678

# Passing token directly
cifix fetch-logs myorg/myrepo 99999999 --token ghp_xxx
```

### Options

```
cifix --help             Show all commands
cifix --version          Show version
cifix fetch-logs --help  Show fetch-logs options
```

## Project Structure

```
cifix/
├── pyproject.toml
├── README.md
└── src/
    └── cifix/
        ├── __init__.py
        ├── cli.py          # Click CLI entry point
        └── github.py       # GitHub API client
```

## License

MIT