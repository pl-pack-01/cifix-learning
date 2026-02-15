import os
import click
from cifix.github import fetch_run_logs


@click.group()
@click.version_option()
@click.pass_context
def cli(ctx):
    """Cifix — CI log analysis tool."""
    ctx.ensure_object(dict)


@cli.command("fetch-logs")
@click.argument("repo")
@click.argument("run_id", type=int)
@click.option(
    "--token",
    envvar="GITHUB_TOKEN",
    help="GitHub PAT. Falls back to $GITHUB_TOKEN env var.",
)
def fetch_logs(repo, run_id, token):
    """Fetch GitHub Actions logs for a workflow run.

    REPO is the "owner/repo" string (e.g. octocat/hello-world).
    RUN_ID is the numeric workflow run ID.

    \b
    Examples:
        cifix fetch-logs octocat/hello-world 12345678
        cifix fetch-logs myorg/myrepo 99999999 --token ghp_xxx
    """
    if not token:
        raise click.ClickException(
            "GitHub token required. Set $GITHUB_TOKEN or pass --token."
        )

    if "/" not in repo:
        raise click.ClickException(
            f"Invalid repo format '{repo}'. Use 'owner/repo'."
        )

    click.echo(f"Fetching logs for {repo} run #{run_id}...")

    try:
        logs = fetch_run_logs(repo, run_id, token)
    except Exception as e:
        raise click.ClickException(str(e))

    if not logs:
        click.echo("No log files found in this run.")
        return

    for filename, content in logs:
        click.secho(f"\n{'='*60}", fg="cyan")
        click.secho(f" {filename}", fg="cyan", bold=True)
        click.secho(f"{'='*60}", fg="cyan")
        click.echo(content)

    click.echo(f"\n({len(logs)} log file(s) printed)")


if __name__ == "__main__":
    cli()