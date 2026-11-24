"""Extract what Mondo takes in from an RDF source, with SPARQL.

The ontology is loaded into an on-disk Oxigraph store (rdfstore.py), which runs the
SPARQL directories' updates (*.ru) in name order, then their queries (*.rq). A file in
a later directory replaces one of the same name in an earlier one, so a source can
override mondo-source's shared queries. Each query fills one part of the extract:

  metadata.rq   what the source says about itself (one row)
  terms.rq      one row per term: ?id and its single-valued slots
  <slot>.rq     the multivalued Term slot <slot>, one value per row, keyed by ?id;
                a row with columns besides ?id and ?<slot> is a nested object

Rows keep their query order (ORDER BY). IRIs are compressed to CURIEs and xsd:anyURI
literals standardised by curies, using the prefix map; other values are kept as their
lexical form.
"""

from pathlib import Path

import curies
import pyoxigraph as ox

from mondo_source.finalize import Extract
from mondo_source.rdfstore import with_store

ANY_URI = "http://www.w3.org/2001/XMLSchema#anyURI"

type Rows = list[dict[str, str]]


def run_queries(store: ox.Store, sparql: list[Path], converter: curies.Converter) -> dict[str, Rows]:
    files = {f.name: f for d in sparql for f in sorted(d.iterdir()) if f.suffix in (".ru", ".rq")}
    for name in sorted(files):
        if name.endswith(".ru"):
            store.update(files[name].read_text())
    results = {}
    for query in (files[name] for name in sorted(files) if name.endswith(".rq")):
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


def gather(results: dict[str, Rows]) -> Extract:
    """Group the queries' rows by term."""
    (metadata,) = results.pop("metadata")
    terms: dict[str, dict] = {}
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
    return Extract.model_validate({"metadata": metadata, "terms": list(terms.values())})


def extract(ontology: Path, sparql: list[Path], converter: curies.Converter) -> Extract:
    return gather(with_store(ontology, lambda store: run_queries(store, sparql, converter)))
