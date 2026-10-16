"""The mondo-source command: one subcommand per pipeline step."""

from pathlib import Path

import typer

from mondo_source import assemble, render_owl, sssom

app = typer.Typer(no_args_is_help=True, add_completion=False)
app.command("assemble")(assemble.main)
app.command("sssom")(sssom.main)
app.command("render-owl")(render_owl.main)


@app.command("data-dir")
def data_dir():
    """Print the directory of the package's shared files (schema, SPARQL, source.mk)."""
    print(Path(__file__).parent)
