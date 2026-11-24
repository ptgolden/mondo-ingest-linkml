"""The mondo-source command: one subcommand per pipeline step."""

from pathlib import Path
from typing import Annotated

import pydantic
import typer

from mondo_source import rdfstore, render_owl, sssom
from mondo_source.prefixes import load_converter
from mondo_source.yamlio import dump_yaml

app = typer.Typer(no_args_is_help=True, add_completion=False)
app.command("sssom")(sssom.main)
app.command("render-owl")(render_owl.main)


@app.command("assemble")
def assemble(
    ontology: Annotated[Path, typer.Option(help="The source ontology (RDF/XML or Turtle, by extension)")],
    sparql: Annotated[
        list[Path], typer.Option(help="Directory of SPARQL updates (*.ru) and queries (*.rq); repeatable, later wins")
    ],
    prefixes: Annotated[Path, typer.Option(help="Extended prefix map (YAML) every identifier must use")],
    output: Annotated[Path, typer.Option()],
    metadata_output: Annotated[Path | None, typer.Option()] = None,
    extract_output: Annotated[Path | None, typer.Option(help="Where to leave the extract (JSON), to look at")] = None,
    set_: Annotated[list[str], typer.Option("--set", help="Extra metadata, KEY=VALUE")] = [],
):
    """Build a SourceRelease YAML from a source ontology."""
    # Imported here because they import datamodel.py, which make generates: `data-dir`
    # has to work before it exists.
    from mondo_source.extract import extract
    from mondo_source.finalize import finalize

    try:
        extracted = extract(ontology, sparql, load_converter(prefixes))
        if extract_output:
            extract_output.write_text(extracted.model_dump_json(exclude_none=True, indent=1))
        release = finalize(extracted, dict(s.split("=", 1) for s in set_))
    except (ValueError, pydantic.ValidationError) as e:
        raise SystemExit(f"assembly failed: {e}")
    data = release.model_dump(mode="json", exclude_none=True)
    dump_yaml(data, output)
    if metadata_output:
        dump_yaml(data["metadata"], metadata_output)


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
