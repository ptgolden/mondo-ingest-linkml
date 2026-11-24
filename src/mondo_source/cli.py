"""The mondo-source command: one subcommand per pipeline step."""

import json
from pathlib import Path
from typing import TYPE_CHECKING, Annotated

import pydantic
import typer
from linkml_runtime.utils.schemaview import SchemaView

from mondo_source import rdfstore, render_owl, sssom
from mondo_source.prefixes import load_converter
from mondo_source.yamlio import dump_yaml

if TYPE_CHECKING:
    from mondo_source.finalize import Extract

app = typer.Typer(no_args_is_help=True, add_completion=False)
app.command("sssom")(sssom.main)
app.command("render-owl")(render_owl.main)

# `assemble` and `finalize` import extract.py and finalize.py when they run, not here:
# those import datamodel.py, which make generates, and `data-dir` has to work before
# it exists.

Prefixes = Annotated[Path, typer.Option(help="Extended prefix map (YAML) every identifier must use")]
Schema = Annotated[Path, typer.Option()]
Importmap = Annotated[Path | None, typer.Option(help="LinkML importmap (JSON)")]
Output = Annotated[Path, typer.Option()]
MetadataOutput = Annotated[Path | None, typer.Option()]
StripBrackets = Annotated[
    bool, typer.Option("--strip-brackets", help="Add each label and exact synonym without its final bracketed part")
]
Set = Annotated[list[str], typer.Option("--set", help="Extra metadata, KEY=VALUE")]


def write_release(
    extract: "Extract",
    prefixes: Path,
    schema: Path,
    importmap: Path | None,
    output: Path,
    metadata_output: Path | None,
    strip_brackets: bool,
    set_: list[str],
):
    from mondo_source.finalize import finalize
    from mondo_source.problems import Problems

    schema_view = SchemaView(str(schema), importmap=json.loads(importmap.read_text()) if importmap else None)
    metadata = dict(s.split("=", 1) for s in set_)
    try:
        release = finalize(extract, load_converter(prefixes), schema_view, metadata, strip_brackets)
    except Problems as e:
        raise SystemExit(f"{e}; nothing written")
    data = release.model_dump(mode="json", exclude_none=True)
    dump_yaml(data, output)
    if metadata_output:
        dump_yaml(data["metadata"], metadata_output)


@app.command("assemble")
def assemble(
    ontology: Annotated[Path, typer.Option(help="The source ontology (RDF/XML or Turtle, by extension)")],
    sparql: Annotated[
        list[Path], typer.Option(help="Directory of SPARQL updates (*.ru) and queries (*.rq); repeatable, later wins")
    ],
    prefixes: Prefixes,
    schema: Schema,
    output: Output,
    importmap: Importmap = None,
    metadata_output: MetadataOutput = None,
    extract_output: Annotated[Path | None, typer.Option(help="Where to leave the extract (JSON), to look at")] = None,
    strip_brackets: StripBrackets = False,
    set_: Set = [],
):
    """Build a SourceRelease YAML from an RDF source: extract it with SPARQL, then finalize."""
    from mondo_source.extract import extract

    try:
        extracted = extract(ontology, sparql)
    except ValueError as e:
        raise SystemExit(f"no extract: {e}")
    if extract_output:
        extract_output.write_text(extracted.model_dump_json(indent=1))
    write_release(extracted, prefixes, schema, importmap, output, metadata_output, strip_brackets, set_)


@app.command("finalize")
def finalize(
    extract: Annotated[Path, typer.Argument(help="An extract (JSON), as a source's own code wrote it")],
    prefixes: Prefixes,
    schema: Schema,
    output: Output,
    importmap: Importmap = None,
    metadata_output: MetadataOutput = None,
    strip_brackets: StripBrackets = False,
    set_: Set = [],
):
    """Build a SourceRelease YAML from an extract: for a source that isn't RDF."""
    from mondo_source.finalize import Extract

    try:
        stated = Extract.model_validate_json(extract.read_text())
    except pydantic.ValidationError as e:
        raise SystemExit(f"{extract} is not an extract: {e}")
    write_release(stated, prefixes, schema, importmap, output, metadata_output, strip_brackets, set_)


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
