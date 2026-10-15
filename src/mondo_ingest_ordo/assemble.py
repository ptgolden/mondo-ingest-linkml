"""Build a SourceRelease YAML from a source ontology.

Oxigraph loads the ontology and runs the SPARQL directory: its updates (*.ru) in
name order, then its queries (*.rq), each of which fills one part of the release:

  metadata.rq   the release metadata (one row)
  terms.rq      one row per term: ?id and its single-valued slots
  <slot>.rq     the multivalued Term slot <slot>, one value per row, keyed by ?id;
                a row with columns besides ?id and ?<slot> is a nested object

Rows keep their query order (ORDER BY), so the output is stable. IRIs are
compressed to CURIEs and xsd:anyURI literals standardised by curies, using the
prefix map; other values are kept as their lexical form. Building the Pydantic
models generated from the schema (datamodel.py) does the rest: types, required
slots, CURIE patterns and unknown fields.
"""

from pathlib import Path
from typing import Annotated

import curies
import pydantic
import pyoxigraph as ox
import typer

from mondo_ingest_ordo.prefixes import load_converter
from mondo_ingest_ordo.yamlio import dump_yaml

ANY_URI = "http://www.w3.org/2001/XMLSchema#anyURI"


def run_queries(ontology: Path, sparql: Path, converter: curies.Converter) -> dict[str, list[dict]]:
    store = ox.Store()
    store.bulk_load(path=str(ontology), format=ox.RdfFormat.RDF_XML)
    for update in sorted(sparql.glob("*.ru")):
        store.update(update.read_text())
    results = {}
    for query in sorted(sparql.glob("*.rq")):
        solutions = store.query(query.read_text())
        assert isinstance(solutions, ox.QuerySolutions), f"{query.name} is not a SELECT query"
        results[query.stem] = [
            {v.value: as_value(s[v], converter) for v in solutions.variables if s[v] is not None}
            for s in solutions
        ]
    return results


def as_value(term, converter: curies.Converter) -> str:
    if isinstance(term, ox.NamedNode):
        value = converter.compress(term.value)
    elif isinstance(term, ox.Literal) and term.datatype.value == ANY_URI:
        value = converter.standardize_curie(term.value)
    elif isinstance(term, ox.Literal):
        return term.value
    else:
        raise ValueError(f"unexpected {type(term).__name__} in query results")
    if value is None:
        raise ValueError(f"no prefix in the prefix map for {term.value!r}")
    return value


def build(results: dict[str, list[dict]], extra_metadata: dict):
    from mondo_ingest_ordo.datamodel import ReleaseMetadata, SourceRelease, Term

    (metadata,) = results.pop("metadata")
    terms = {}
    for row in results.pop("terms"):
        # Two rows for one term means two values for a single-valued slot (e.g. two
        # labels); keeping either would silently drop the other.
        if row["id"] in terms:
            raise ValueError(f"{row['id']}: conflicting single-valued slots {terms[row['id']]} and {row}")
        terms[row["id"]] = row
    for slot, rows in results.items():
        for row in rows:
            term = terms[row.pop("id")]
            term.setdefault(slot, []).append(row[slot] if list(row) == [slot] else row)
    return SourceRelease(
        metadata=ReleaseMetadata(**metadata, **extra_metadata),
        terms=[Term(**term) for term in terms.values()],
    )


def main(
    ontology: Annotated[Path, typer.Option(help="The source ontology (RDF/XML)")],
    sparql: Annotated[Path, typer.Option(help="Directory of SPARQL updates (*.ru) and queries (*.rq)")],
    prefixes: Annotated[Path, typer.Option(help="Extended prefix map (YAML) every identifier must use")],
    output: Annotated[Path, typer.Option()],
    metadata_output: Annotated[Path | None, typer.Option()] = None,
    set_: Annotated[list[str], typer.Option("--set", help="Extra metadata, KEY=VALUE")] = [],
):
    """Build a SourceRelease YAML from a source ontology."""
    try:
        results = run_queries(ontology, sparql, load_converter(prefixes))
        release = build(results, dict(s.split("=", 1) for s in set_))
    except (ValueError, pydantic.ValidationError) as e:
        raise SystemExit(f"assembly failed: {e}")
    data = release.model_dump(mode="json", exclude_none=True)
    dump_yaml(data, output)
    if metadata_output:
        dump_yaml(data["metadata"], metadata_output)


if __name__ == "__main__":
    typer.run(main)
