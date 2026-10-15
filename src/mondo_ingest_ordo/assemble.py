"""Assemble a SourceRelease YAML from SPARQL query results.

Each result file fills one part of the release, by its name:

  metadata.srx   the release metadata (one row)
  terms.srx      one Term per row, ?id plus single-valued slots
  <slot>.srx     Term.<slot>, one value per row, keyed by ?id

The schema decides everything else. If a slot's range is a class, each row is one
object, built from the row's other columns; otherwise the row's <slot> column is
the value. Multivalued slots collect each distinct value; single-valued slots must
get exactly one. IRIs in CURIE-typed slots are compressed with the prefix map;
CURIE strings are checked against it. Lists are sorted by the fields named in the
slot's `sort_by` annotation, then by full content, so output is stable.
"""

import json
import xml.etree.ElementTree as ET
from collections.abc import Iterator
from pathlib import Path
from typing import Annotated, Any

import curies
import typer
import yaml
from linkml_runtime.utils.schemaview import SchemaView

from mondo_ingest_ordo.yamlio import dump_yaml

RESULTS = "{http://www.w3.org/2005/sparql-results#}"
XSD = "http://www.w3.org/2001/XMLSchema#"


class IRI(str):
    """A SPARQL result value that was an IRI, not a literal."""


class AssemblyError(Exception):
    pass


def read_results(path: Path) -> Iterator[dict[str, Any]]:
    """Rows of a SPARQL XML results file, with IRIs, booleans and integers typed."""
    for _, el in ET.iterparse(path):
        if el.tag != RESULTS + "result":
            continue
        row = {}
        for binding in el.iter(RESULTS + "binding"):
            name, value = binding.get("name"), binding[0]
            kind = value.tag.removeprefix(RESULTS)
            if kind == "uri":
                row[name] = IRI(value.text)
            elif kind == "literal":
                datatype, text = value.get("datatype"), value.text or ""
                if datatype == XSD + "boolean":
                    row[name] = text == "true"
                elif datatype == XSD + "integer":
                    row[name] = int(text)
                else:
                    row[name] = text
            else:
                raise AssemblyError(f"{path.name}: unexpected {kind} for ?{name}")
        el.clear()
        yield row


class Assembler:
    def __init__(self, sv: SchemaView, converter: curies.Converter):
        self.sv = sv
        self.converter = converter
        self.classes = set(sv.all_classes())
        self.types = sv.all_types()

    def slot(self, class_name: str, slot_name: str):
        if slot_name not in self.sv.class_slots(class_name):
            raise AssemblyError(f"{class_name} has no slot {slot_name!r}")
        return self.sv.induced_slot(slot_name, class_name)

    def is_curie_slot(self, slot) -> bool:
        return slot.range in self.types and "uriorcurie" in self.sv.type_ancestors(slot.range)

    def value(self, class_name: str, slot_name: str, value: Any) -> Any:
        slot = self.slot(class_name, slot_name)
        if self.is_curie_slot(slot):
            if isinstance(value, IRI):
                try:
                    return self.converter.compress_strict(value)
                except curies.CompressionError:
                    raise AssemblyError(f"{class_name}.{slot_name}: no prefix for {value}") from None
            # curies accepts an empty or whitespace-containing local part; ORDO has both.
            _, _, local = str(value).partition(":")
            if not self.converter.is_curie(value) or not local or any(c.isspace() for c in local):
                raise AssemblyError(f"{class_name}.{slot_name}: not a CURIE in the prefix map: {value!r}")
        return str(value) if isinstance(value, IRI) else value

    def add(self, target: dict, class_name: str, slot_name: str, value: Any, where: str):
        if self.slot(class_name, slot_name).multivalued:
            values = target.setdefault(slot_name, [])
            if value not in values:
                values.append(value)
        elif target.setdefault(slot_name, value) != value:
            raise AssemblyError(f"{where}.{slot_name}: single-valued but got {target[slot_name]!r} and {value!r}")

    def assemble(self, results: Path, extra_metadata: dict[str, str]) -> dict:
        metadata_rows = list(read_results(results / "metadata.srx"))
        if len(metadata_rows) != 1:
            raise AssemblyError(f"metadata.srx has {len(metadata_rows)} rows, expected 1")
        metadata = {}
        for k, v in {**metadata_rows[0], **extra_metadata}.items():
            self.add(metadata, "ReleaseMetadata", k, self.value("ReleaseMetadata", k, v), "metadata")

        terms: dict[str, dict] = {}
        for row in read_results(results / "terms.srx"):
            tid = self.value("Term", "id", row.pop("id"))
            term = terms.setdefault(tid, {"id": tid})
            for k, v in row.items():
                self.add(term, "Term", k, self.value("Term", k, v), tid)

        for path in sorted(results.glob("*.srx")):
            if path.stem in ("metadata", "terms"):
                continue
            slot_name = path.stem
            slot = self.slot("Term", slot_name)
            for row in read_results(path):
                tid = self.value("Term", "id", row.pop("id"))
                if tid not in terms:
                    raise AssemblyError(f"{path.name}: row for unknown term {tid}")
                if slot.range in self.classes:
                    value = {k: self.value(slot.range, k, v) for k, v in row.items()}
                else:
                    value = self.value("Term", slot_name, row[slot_name])
                self.add(terms[tid], "Term", slot_name, value, tid)

        return {"metadata": metadata, "terms": [self.sorted(terms[k]) for k in sorted(terms, key=id_key)]}

    def sorted(self, term: dict) -> dict:
        """Keys in schema slot order; lists sorted so output is stable across runs."""
        out = {}
        for k in sorted(term, key=self.sv.class_slots("Term").index):
            v = term[k]
            if isinstance(v, list):
                annotation = getattr(self.slot("Term", k).annotations, "sort_by", None)
                fields = annotation.value.split() if annotation else []
                v = sorted(v, key=lambda x: ([str(x.get(f, "")) for f in fields] if isinstance(x, dict) else [],
                                             json.dumps(x, sort_keys=True)))
            out[k] = v
        return out


def id_key(curie: str):
    prefix, _, local = curie.partition(":")
    return (prefix, int(local)) if local.isdigit() else (prefix, float("inf"), local)


def main(
    results: Annotated[Path, typer.Option(help="Directory of SPARQL XML result files")],
    schema: Annotated[Path, typer.Option()],
    prefixes: Annotated[Path, typer.Option(help="Prefix map (YAML) every CURIE must use")],
    output: Annotated[Path, typer.Option()],
    metadata_output: Annotated[Path | None, typer.Option()] = None,
    importmap: Annotated[Path | None, typer.Option(help="LinkML importmap (JSON)")] = None,
    set_: Annotated[list[str], typer.Option("--set", help="Extra metadata, KEY=VALUE")] = [],
):
    """Assemble a SourceRelease YAML from SPARQL query results."""
    sv = SchemaView(str(schema), importmap=json.loads(importmap.read_text()) if importmap else None)
    converter = curies.Converter.from_prefix_map(yaml.safe_load(prefixes.read_text()))
    try:
        release = Assembler(sv, converter).assemble(results, dict(s.split("=", 1) for s in set_))
    except AssemblyError as e:
        raise SystemExit(f"assembly failed: {e}")
    dump_yaml(release, output)
    if metadata_output:
        dump_yaml(release["metadata"], metadata_output)


if __name__ == "__main__":
    typer.run(main)
