"""Assemble a SourceRelease YAML from SPARQL query results, via the schema's Pydantic models.

Each result file fills one part of the release, by its name:

  metadata.srx   the release metadata (one row)
  terms.srx      ?id plus single-valued Term slots, one term per row
  <slot>.srx     Term.<slot>, one value per row, keyed by ?id

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
import xml.etree.ElementTree as ET
from collections import defaultdict
from collections.abc import Iterator
from pathlib import Path
from typing import Annotated, Any

import curies
import pydantic
import typer

from mondo_ingest_ordo.prefixes import load_converter
from mondo_ingest_ordo.yamlio import dump_yaml

RESULTS = "{http://www.w3.org/2005/sparql-results#}"
XSD = "http://www.w3.org/2001/XMLSchema#"


class AssemblyError(Exception):
    pass


def read_results(path: Path, converter: curies.Converter) -> Iterator[dict[str, Any]]:
    """Rows of a SPARQL XML results file, identifiers normalised, booleans and integers typed."""
    for _, el in ET.iterparse(path):
        if el.tag != RESULTS + "result":
            continue
        row = {}
        for binding in el.iter(RESULTS + "binding"):
            name, value = binding.get("name"), binding[0]
            kind, text, datatype = value.tag.removeprefix(RESULTS), value.text or "", value.get("datatype")
            if kind == "uri":
                normalised = converter.compress(text)
            elif kind == "literal" and datatype == XSD + "anyURI":
                normalised = converter.standardize_curie(text)
            elif kind == "literal":
                if datatype == XSD + "boolean":
                    row[name] = text == "true"
                elif datatype == XSD + "integer":
                    row[name] = int(text)
                else:
                    row[name] = text
                continue
            else:
                raise AssemblyError(f"{path.name}: unexpected {kind} for ?{name}")
            if normalised is None:
                raise AssemblyError(f"{path.name}: ?{name} {text!r} has no prefix in the prefix map")
            row[name] = normalised
        el.clear()
        yield row


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


def assemble(results: Path, models: types.ModuleType, converter: curies.Converter, extra_metadata: dict):
    metadata_rows = list(read_results(results / "metadata.srx", converter))
    if len(metadata_rows) != 1:
        raise AssemblyError(f"metadata.srx has {len(metadata_rows)} rows, expected 1")

    terms: dict[str, dict[str, list]] = {}
    for row in read_results(results / "terms.srx", converter):
        term = terms.setdefault(row["id"], defaultdict(list))
        for k, v in row.items():
            term[k].append(v)

    for path in sorted(results.glob("*.srx")):
        if path.stem in ("metadata", "terms"):
            continue
        if path.stem not in models.Term.model_fields:
            raise AssemblyError(f"{path.name}: Term has no slot {path.stem!r}")
        _, nested = field_shape(models.Term.model_fields[path.stem])
        for row in read_results(path, converter):
            tid = row.pop("id")
            if tid not in terms:
                raise AssemblyError(f"{path.name}: row for unknown term {tid}")
            terms[tid][path.stem].append(row if nested else row[path.stem])

    return models.SourceRelease(
        metadata={**metadata_rows[0], **extra_metadata},
        terms=[gather(models.Term, terms[k], k) for k in sorted(terms, key=id_key)],
    )


def id_key(curie: str):
    prefix, _, local = curie.partition(":")
    return (prefix, int(local)) if local.isdigit() else (prefix, float("inf"), local)


def main(
    results: Annotated[Path, typer.Option(help="Directory of SPARQL XML result files")],
    models: Annotated[Path, typer.Option(help="Pydantic models generated from the schema (gen-pydantic)")],
    prefixes: Annotated[Path, typer.Option(help="Extended prefix map (YAML) every identifier must use")],
    output: Annotated[Path, typer.Option()],
    metadata_output: Annotated[Path | None, typer.Option()] = None,
    set_: Annotated[list[str], typer.Option("--set", help="Extra metadata, KEY=VALUE")] = [],
):
    """Assemble a SourceRelease YAML from SPARQL query results."""
    try:
        release = assemble(results, load_models(models), load_converter(prefixes), dict(s.split("=", 1) for s in set_))
    except (AssemblyError, pydantic.ValidationError) as e:
        raise SystemExit(f"assembly failed: {e}")
    data = release.model_dump(mode="json", exclude_none=True)
    dump_yaml(data, output)
    if metadata_output:
        dump_yaml(data["metadata"], metadata_output)


if __name__ == "__main__":
    typer.run(main)
