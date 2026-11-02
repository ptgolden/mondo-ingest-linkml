"""A source loaded into a temporary on-disk Oxigraph store.

On disk, so memory stays bounded however big the source is: all of NCIT (10.8M
triples) loads with a 2.2 GB peak and queries in about 0.5 GB. For a small source it
costs time instead (ORDO: about 19 s rather than 5 s in memory).
"""

import tempfile
from collections.abc import Callable
from pathlib import Path

import pyoxigraph as ox


def rdf_format(path: Path) -> ox.RdfFormat:
    extension = path.suffix.removeprefix(".")
    rdf_format = ox.RdfFormat.RDF_XML if extension == "owl" else ox.RdfFormat.from_extension(extension)
    if rdf_format is None:
        raise ValueError(f"unknown RDF format for {path}")
    return rdf_format


def with_store[T](source: Path, use: Callable[[ox.Store], T]) -> T:
    """use(store) on the source in a fresh store, which is deleted afterwards (the
    directory honours TMPDIR). use must not keep the store: RocksDB stays open, its
    background threads writing files, until the last reference to the store is gone,
    and the directory can only be deleted after that."""
    with tempfile.TemporaryDirectory(prefix="mondo-source-store-") as directory:
        store = ox.Store(directory)
        store.bulk_load(path=str(source), format=rdf_format(source))
        result = use(store)
        del store
    return result


def select_tsv(source: Path, query: Path, output: Path):
    """A SELECT over the source, as SPARQL TSV with its rows sorted (mondo-ingest's
    signature reports; formerly `robot query`)."""
    def select(store: ox.Store) -> bytes | None:
        solutions = store.query(query.read_text())
        assert isinstance(solutions, ox.QuerySolutions), f"{query} is not a SELECT query"
        return solutions.serialize(format=ox.QueryResultsFormat.TSV)

    tsv = with_store(source, select)
    assert tsv is not None
    header, *rows = tsv.decode().splitlines()
    output.write_text("\n".join([header, *sorted(rows)]) + "\n")


def to_rdfxml(source: Path, output: Path):
    """The source as RDF/XML, streamed triple by triple, so any size fits in memory."""
    ox.serialize(ox.parse(path=str(source), format=rdf_format(source)), output=str(output), format=ox.RdfFormat.RDF_XML)
