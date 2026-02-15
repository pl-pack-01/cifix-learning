import io
import zipfile
import requests


GITHUB_API = "https://api.github.com"


def get_headers(token):
    return {
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {token}",
        "X-GitHub-Api-Version": "2022-11-28",
    }


def fetch_run_logs(repo, run_id, token):
    """Download and extract workflow run logs from GitHub Actions.

    Args:
        repo: "owner/repo" string
        run_id: Workflow run ID
        token: GitHub personal access token

    Returns:
        List of (filename, content) tuples for each log file.
    """
    url = f"{GITHUB_API}/repos/{repo}/actions/runs/{run_id}/logs"
    resp = requests.get(url, headers=get_headers(token), allow_redirects=True)

    if resp.status_code == 404:
        raise click.ClickException(
            f"Run {run_id} not found in {repo}. "
            "Check the repo name and run ID, or ensure logs haven't expired."
        )
    resp.raise_for_status()

    logs = []
    with zipfile.ZipFile(io.BytesIO(resp.content)) as zf:
        for name in sorted(zf.namelist()):
            if name.endswith(".txt"):
                content = zf.read(name).decode("utf-8", errors="replace")
                logs.append((name, content))
    return logs