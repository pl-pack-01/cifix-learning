
"""
Add this command to your existing Click CLI.

Assumes Phase 1 gave you something like:
    from cifix.github import fetch_run_logs
that returns raw log text for a given run ID.
"""

import json
import click

# -- Paste/merge into your existing cli.py --

# from cifix.github import fetch_run_logs      # your Phase 1 function
# from cifix.classifier import classify
# from cifix.formatter import format_analysis   # see below


@click.command()
@click.argument("run_id")
@click.option(
    "--provider", "-p",
    default="github",
    help="CI provider (github, gitlab, jenkins).",
)
@click.option(
    "--output", "-o",
    type=click.Choice(["text", "json"]),
    default="text",
    help="Output format.",
)
@click.option(
    "--category", "-c",
    type=click.Choice(["all", "infra", "code"]),
    default="all",
    help="Filter by error category.",
)
@click.option(
    "--severity", "-s",
    type=click.Choice(["all", "fatal", "error", "warning"]),
    default="all",
    help="Minimum severity to show.",
)
def classify_cmd(run_id, provider, output, category, severity):
    """Classify errors in a CI run's logs."""
    from cifix.classifier import classify, AnalysisResult
    from cifix.formatter import format_analysis
    from cifix.github import fetch_run_logs
    from cifix.patterns import ErrorCategory, ErrorSeverity

    click.echo(f"Fetching logs for run {run_id}...")
    raw_log = fetch_run_logs(run_id)

    click.echo("Classifying errors...")
    result = classify(raw_log, provider=provider)

    # Apply filters
    if category != "all":
        cat_filter = ErrorCategory.INFRASTRUCTURE if category == "infra" else ErrorCategory.CODE
        result.errors = [e for e in result.errors if e.category == cat_filter]

    if severity != "all":
        sev_map = {"fatal": 0, "error": 1, "warning": 2}
        min_sev = sev_map[severity]
        sev_rank = {ErrorSeverity.FATAL: 0, ErrorSeverity.ERROR: 1, ErrorSeverity.WARNING: 2}
        result.errors = [e for e in result.errors if sev_rank[e.severity] <= min_sev]

    # Output
    if output == "json":
        click.echo(json.dumps(result.to_dict(), indent=2))
    else:
        click.echo(format_analysis(result))


# Register with your existing CLI group:
# cli.add_command(classify_cmd, "classify")