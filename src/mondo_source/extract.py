"""Extract what Mondo takes in from an RDF source, with SPARQL.

The ontology is loaded into an on-disk Oxigraph store (rdfstore.py), which runs the
SPARQL directories' updates (*.ru) in name order, then their queries (*.rq). A file in
a later directory replaces one of the same name in an earlier one, so a source can
override mondo-source's shared queries. Each query fills one part of the extract:

  metadata.rq   what the source says about itself (one row)
  terms.rq      one row per term: ?id and its single-valued slots
  <slot>.rq     the multivalued Term slot <slot>, one value per row, keyed by ?id;
                a row with columns besides ?id and ?<slot> is a nested object

Rows keep their query order (ORDER BY). An IRI is kept as the IRI and a literal as its
lexical form: finalize.py standardises the identifiers.
"""

from collections import defaultdict
from pathlib import Path

import pyoxigraph as ox
from pydantic import JsonValue

from mondo_source.finalize import Extract
from mondo_source.rdfstore import with_store

type Rows = list[dict[str, str]]


def run_queries(store: ox.Store, sparql: list[Path]) -> dict[str, Rows]:
    files = {f.name: f for d in sparql for f in sorted(d.iterdir()) if f.suffix in (".ru", ".rq")}
    for name in sorted(files):
        if name.endswith(".ru"):
            store.update(files[name].read_text())
    results = {}
    for query in (files[name] for name in sorted(files) if name.endswith(".rq")):
        solutions = store.query(query.read_text())
        assert isinstance(solutions, ox.QuerySolutions), f"{query.name} is not a SELECT query"
        results[query.stem] = [
            {v.value: as_text(s[v]) for v in solutions.variables if s[v] is not None}
            for s in solutions
        ]
    return results


def as_text(term: ox.NamedNode | ox.BlankNode | ox.Literal | ox.Triple) -> str:
    match term:
        case ox.NamedNode() | ox.Literal():
            return term.value
        case _:
            raise ValueError(f"unexpected {type(term).__name__} in query results")


def gather(results: dict[str, Rows]) -> Extract:
    """Group the queries' rows by term."""
    (metadata,) = results.pop("metadata")
    terms: dict[str, dict[str, JsonValue]] = {}
    for row in results.pop("terms"):
        # Two rows for one term means two values for a single-valued slot (e.g. two
        # labels); keeping either would silently drop the other.
        if row["id"] in terms:
            raise ValueError(f"{row['id']}: conflicting single-valued slots {terms[row['id']]} and {row}")
        terms[row["id"]] = {**row}
    for slot, rows in results.items():
        values: defaultdict[str, list[JsonValue]] = defaultdict(list)
        for row in rows:
            values[row.pop("id")].append(row[slot] if list(row) == [slot] else {**row})
        for term_id, of_term in values.items():
            terms[term_id][slot] = of_term
    return Extract(metadata=metadata, terms=list(terms.values()))


def extract(ontology: Path, sparql: list[Path]) -> Extract:
    return gather(with_store(ontology, lambda store: run_queries(store, sparql)))
