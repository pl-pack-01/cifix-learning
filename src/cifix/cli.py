import click


@click.group()
@click.version_option()
@click.option("--verbose", "-v", is_flag=True, help="Enable verbose output.")
@click.pass_context
def cli(ctx, verbose):
    """Cifix — a tool that supports reviewing CI logs and suggesting fixes."""
    ctx.ensure_object(dict)
    ctx.obj["VERBOSE"] = verbose


@cli.command()
@click.argument("name")
@click.option("--greeting", "-g", default="Hello", help="Custom greeting.")
def hello(name, greeting):
    """Greet someone by NAME."""
    click.echo(f"{greeting}, {name}!")


@cli.command()
@click.option("--count", "-c", default=1, type=int, help="Number of items.")
@click.option("--output", "-o", type=click.Path(), help="Output file path.")
@click.pass_context
def generate(ctx, count, output):
    """Generate some items."""
    verbose = ctx.obj["VERBOSE"]
    items = [f"item-{i}" for i in range(1, count + 1)]

    if verbose:
        click.echo(f"Generating {count} item(s)...")

    result = "\n".join(items)

    if output:
        with open(output, "w") as f:
            f.write(result)
        click.echo(f"Written to {output}")
    else:
        click.echo(result)


@cli.command()
@click.confirmation_option(prompt="Are you sure you want to reset?")
def reset():
    """Reset configuration (with confirmation)."""
    click.echo("Configuration reset.")


if __name__ == "__main__":
    cli()