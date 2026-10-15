"""Build a SourceRelease YAML from a source ontology, via SPARQL and the schema's Pydantic models.

The ontology is loaded into an in-memory Oxigraph store. The SPARQL directory's
updates (*.ru) run first, in name order; then each query (*.rq) fills one part of
the release, by its name:

  metadata.rq    the release metadata (one row)
  terms.rq       ?id plus single-valued Term slots, one term per row
  <slot>.rq      Term.<slot>, one value per row, keyed by ?id

Identifiers are normalised with the prefix map as they are read: IRIs are
compressed to CURIEs, and literals typed xsd:anyURI (identifiers a source gives as
strings, like ORDO's "ICD-10:Q87.4" xrefs) are standardised, so prefix synonyms
become the canonical prefix. An identifier the map can't handle is an error.

Everything else is up to the models generated from the schema (gen-pydantic): a
field's type says whether a slot is a list and whether its values are nested
objects, and building the models validates types, required slots, patterns and
unknown fields. Lists are sorted by the fields in the slot's `sort_by` annotation,
then by content, so output is stable.
"""

import importlib.util
import json
import types
import typing
from collections import defaultdict
from pathlib import Path
from typing import Annotated, Any

import curies
import pydantic
import pyoxigraph as ox
import typer

from mondo_ingest_ordo.prefixes import load_converter
from mondo_ingest_ordo.yamlio import dump_yaml

XSD = "http://www.w3.org/2001/XMLSchema#"


class AssemblyError(Exception):
    pass


def run_queries(ontology: Path, sparql: Path, converter: curies.Converter) -> dict[str, list[dict[str, Any]]]:
    """Load the ontology, run the updates, then return each query's rows by query name."""
    store = ox.Store()
    store.bulk_load(path=str(ontology), format=ox.RdfFormat.RDF_XML)
    for update in sorted(sparql.glob("*.ru")):
        store.update(update.read_text())
    results = {}
    for query in sorted(sparql.glob("*.rq")):
        solutions = store.query(query.read_text())
        results[query.stem] = [
            {var.value: value(solution[var], converter, query.name, var.value)
             for var in solutions.variables if solution[var] is not None}
            for solution in solutions
        ]
    return results


def value(term, converter: curies.Converter, query: str, var: str) -> Any:
    """A query result term as release data: identifiers normalised, booleans and integers typed."""
    if isinstance(term, ox.NamedNode):
        normalised = converter.compress(term.value)
    elif isinstance(term, ox.Literal) and term.datatype.value == XSD + "anyURI":
        normalised = converter.standardize_curie(term.value)
    elif isinstance(term, ox.Literal):
        if term.datatype.value == XSD + "boolean":
            return term.value == "true"
        if term.datatype.value == XSD + "integer":
            return int(term.value)
        return term.value
    else:
        raise AssemblyError(f"{query}: unexpected {type(term).__name__} for ?{var}")
    if normalised is None:
        raise AssemblyError(f"{query}: ?{var} {term.value!r} has no prefix in the prefix map")
    return normalised


def load_models(path: Path) -> types.ModuleType:
    spec = importlib.util.spec_from_file_location("datamodel", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def field_shape(field) -> tuple[bool, bool]:
    """(is it a list, are its values nested objects) for a model field."""
    tp = field.annotation
    if typing.get_origin(tp) in (typing.Union, types.UnionType):  # Optional[X]
        tp = next(a for a in typing.get_args(tp) if a is not type(None))
    is_list = typing.get_origin(tp) is list
    if is_list:
        tp = typing.get_args(tp)[0]
    return is_list, isinstance(tp, type) and issubclass(tp, pydantic.BaseModel)


def sort_fields(field) -> list[str]:
    meta = (field.json_schema_extra or {}).get("linkml_meta", {})
    return meta.get("annotations", {}).get("sort_by", {}).get("value", "").split()


def gather(model: type[pydantic.BaseModel], values: dict[str, list], where: str) -> dict:
    """Turn {slot: [collected values]} into constructor arguments for `model`."""
    unknown = set(values) - set(model.model_fields)
    if unknown:
        raise AssemblyError(f"{where}: {model.__name__} has no slots {sorted(unknown)}")
    out = {}
    for name, field in model.model_fields.items():
        if name not in values:
            continue
        distinct = []
        for v in values[name]:
            if v not in distinct:
                distinct.append(v)
        if field_shape(field)[0]:
            keys = sort_fields(field)
            out[name] = sorted(distinct, key=lambda x: ([str(x.get(k, "")) for k in keys] if isinstance(x, dict) else [],
                                                        json.dumps(x, sort_keys=True)))
        elif len(distinct) == 1:
            out[name] = distinct[0]
        else:
            raise AssemblyError(f"{where}.{name}: single-valued but got {distinct}")
    return out


def assemble(results: dict[str, list[dict]], models: types.ModuleType, extra_metadata: dict):
    metadata_rows = results.pop("metadata")
    if len(metadata_rows) != 1:
        raise AssemblyError(f"metadata.rq returned {len(metadata_rows)} rows, expected 1")

    terms: dict[str, dict[str, list]] = {}
    for row in results.pop("terms"):
        term = terms.setdefault(row["id"], defaultdict(list))
        for k, v in row.items():
            term[k].append(v)

    for slot, rows in results.items():
        if slot not in models.Term.model_fields:
            raise AssemblyError(f"{slot}.rq: Term has no slot {slot!r}")
        _, nested = field_shape(models.Term.model_fields[slot])
        for row in rows:
            tid = row.pop("id")
            if tid not in terms:
                raise AssemblyError(f"{slot}.rq: row for unknown term {tid}")
            terms[tid][slot].append(row if nested else row[slot])

    return models.SourceRelease(
        metadata={**metadata_rows[0], **extra_metadata},
        terms=[gather(models.Term, terms[k], k) for k in sorted(terms, key=id_key)],
    )


def id_key(curie: str):
    prefix, _, local = curie.partition(":")
    return (prefix, int(local)) if local.isdigit() else (prefix, float("inf"), local)


def main(
    ontology: Annotated[Path, typer.Option(help="The source ontology (RDF/XML)")],
    sparql: Annotated[Path, typer.Option(help="Directory of SPARQL updates (*.ru) and queries (*.rq)")],
    models: Annotated[Path, typer.Option(help="Pydantic models generated from the schema (gen-pydantic)")],
    prefixes: Annotated[Path, typer.Option(help="Extended prefix map (YAML) every identifier must use")],
    output: Annotated[Path, typer.Option()],
    metadata_output: Annotated[Path | None, typer.Option()] = None,
    set_: Annotated[list[str], typer.Option("--set", help="Extra metadata, KEY=VALUE")] = [],
):
    """Build a SourceRelease YAML from a source ontology."""
    try:
        results = run_queries(ontology, sparql, load_converter(prefixes))
        release = assemble(results, load_models(models), dict(s.split("=", 1) for s in set_))
    except (AssemblyError, pydantic.ValidationError) as e:
        raise SystemExit(f"assembly failed: {e}")
    data = release.model_dump(mode="json", exclude_none=True)
    dump_yaml(data, output)
    if metadata_output:
        dump_yaml(data["metadata"], metadata_output)


if __name__ == "__main__":
    typer.run(main)
