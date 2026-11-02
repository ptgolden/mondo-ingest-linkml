"""A source loaded into a temporary on-disk Oxigraph store.

On disk, so memory stays bounded however big the source is: all of NCIT (10.8M
triples) loads with a 2.2 GB peak and queries in about 0.5 GB. For a small source it
costs time instead (ORDO: about 19 s rather than 5 s in memory).
"""

import tempfile
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

import pyoxigraph as ox


def rdf_format(path: Path) -> ox.RdfFormat:
    extension = path.suffix.removeprefix(".")
    rdf_format = ox.RdfFormat.RDF_XML if extension == "owl" else ox.RdfFormat.from_extension(extension)
    if rdf_format is None:
        raise ValueError(f"unknown RDF format for {path}")
    return rdf_format


@contextmanager
def loaded(source: Path) -> Iterator[ox.Store]:
    """The source in a fresh store, deleted afterwards. The directory honours TMPDIR."""
    with tempfile.TemporaryDirectory(prefix="mondo-source-store-") as directory:
        store = ox.Store(directory)
        store.bulk_load(path=str(source), format=rdf_format(source))
        yield store


def select_tsv(source: Path, query: Path, output: Path):
    """A SELECT over the source, as SPARQL TSV with its rows sorted (mondo-ingest's
    signature reports; formerly `robot query`)."""
    with loaded(source) as store:
        solutions = store.query(query.read_text())
        assert isinstance(solutions, ox.QuerySolutions), f"{query} is not a SELECT query"
        tsv = solutions.serialize(format=ox.QueryResultsFormat.TSV)
    assert tsv is not None
    header, *rows = tsv.decode().splitlines()
    output.write_text("\n".join([header, *sorted(rows)]) + "\n")


def to_rdfxml(source: Path, output: Path):
    """The source as RDF/XML, streamed triple by triple, so any size fits in memory."""
    ox.serialize(ox.parse(path=str(source), format=rdf_format(source)), output=str(output), format=ox.RdfFormat.RDF_XML)
