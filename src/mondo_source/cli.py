"""The mondo-source command: one subcommand per pipeline step."""

from pathlib import Path
from typing import Annotated

import typer

from mondo_source import assemble, rdfstore, render_owl, sssom

app = typer.Typer(no_args_is_help=True, add_completion=False)
app.command("assemble")(assemble.main)
app.command("sssom")(sssom.main)
app.command("render-owl")(render_owl.main)


@app.command("select")
def select(
    source: Annotated[Path, typer.Argument(help="RDF/XML (.owl) or Turtle")],
    query: Annotated[Path, typer.Option(help="A SPARQL SELECT")],
    output: Annotated[Path, typer.Option(help="SPARQL TSV, rows sorted")],
):
    """Run a SELECT over a source, writing sorted SPARQL TSV."""
    rdfstore.select_tsv(source, query, output)


@app.command("rdfxml")
def rdfxml(
    source: Annotated[Path, typer.Argument(help="Any RDF format Oxigraph reads, by extension")],
    output: Annotated[Path, typer.Option()],
):
    """Convert a source to RDF/XML, streaming."""
    rdfstore.to_rdfxml(source, output)


@app.command("data-dir")
def data_dir():
    """Print the directory of the package's shared files (schema, SPARQL, source.mk)."""
    print(Path(__file__).parent)
