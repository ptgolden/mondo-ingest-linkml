"""Flatten a SourceRelease into ROBOT templates, for `robot template` to render as OWL.

Python only writes tables here; ROBOT owns the OWL. Output, in --out-dir:

  declarations.tsv     every term and relationship target (owl:Class), relationship
                       predicate (owl:ObjectProperty) and synonym type (an
                       owl:AnnotationProperty under oboInOwl:SynonymTypeProperty)
  terms.tsv            deprecation, definition, replaced_by, consider, subsets,
                       parents
  synonyms-<n>.tsv     one table per synonym scope
  relationships-<n>.tsv, mappings-<n>.tsv
                       one table per predicate, because ROBOT templates put the
                       predicate in the template string, not the cell
  prefixes.json        JSON-LD context for `robot --add-prefixes`
  templates.txt        the non-declaration tables, for the Makefile to pass to ROBOT
  annotate-args.txt    `robot annotate` arguments for the ontology header, from the
                       release metadata

declarations.tsv has to be rendered first and given to the others as input, so that
ROBOT can resolve the classes and properties they mention.

OWL properties all come from the schema: slot URIs, the synonym-scope enum's
meanings, and SSSOM's slot URIs for mapping annotations.
"""

import csv
import json
from pathlib import Path
from typing import Annotated

import curies
import typer
from linkml_runtime.linkml_model.meta import PermissibleValue
from linkml_runtime.utils.schemaview import SchemaView

from mondo_ingest_ordo.prefixes import load_converter
from mondo_ingest_ordo.yamlio import load_yaml

SPLIT = "|"


def schema_converter(sv: SchemaView) -> curies.Converter:
    return curies.Converter.from_prefix_map(dict(sv.namespaces().items()))


def slot_uri(sv: SchemaView, class_name: str, slot_name: str) -> str:
    """The slot's URI as a CURIE in the schema's own prefixes, for a template string."""
    uri = sv.get_uri(sv.induced_slot(slot_name, class_name), expand=True)
    return schema_converter(sv).compress(uri, passthrough=True)


class Table:
    def __init__(self, columns: list[tuple[str, str]]):
        self.headers = [h for h, _ in columns]
        self.templates = [t for _, t in columns]
        self.rows: list[list[str]] = []

    def add(self, *cells: str):
        self.rows.append(list(cells))

    def write(self, path: Path):
        with open(path, "w", newline="") as f:
            w = csv.writer(f, delimiter="\t", lineterminator="\n")
            w.writerow(self.headers)
            w.writerow(self.templates)
            w.writerows(self.rows)


def join(values: list[str]) -> str:
    """Join a multivalued slot into one cell, for a template column with SPLIT=|."""
    for v in values:
        if SPLIT in v:
            raise ValueError(f"value contains the split character {SPLIT!r}: {v!r}")
    return SPLIT.join(values)


def safe_name(curie_: str) -> str:
    return curie_.replace(":", "_")


def flatten(release: dict, sv: SchemaView) -> dict[str, Table]:
    tables: dict[str, Table] = {}

    decl = Table([("ID", "ID"), ("TYPE", "TYPE"), ("LABEL", "LABEL"), ("PARENT_PROPERTY", "SP %")])
    terms = Table([
        ("ID", "ID"),
        ("deprecated", f"AT {slot_uri(sv, 'Term', 'deprecated')}^^xsd:boolean"),
        ("definition", f"A {slot_uri(sv, 'Term', 'definition')}"),
        ("replaced_by", f"AI {slot_uri(sv, 'Term', 'replaced_by')}"),
        ("consider", f"AI {slot_uri(sv, 'Term', 'consider')} SPLIT={SPLIT}"),
        ("subsets", f"AI {slot_uri(sv, 'Term', 'subsets')} SPLIT={SPLIT}"),
        ("parents", f"SC % SPLIT={SPLIT}"),
    ])
    tables["terms"] = terms

    scope_enum = sv.get_enum("SynonymScope")
    assert scope_enum is not None and isinstance(scope_enum.permissible_values, dict)
    scope_property = {
        str(name): str(pv.meaning)
        for name, pv in scope_enum.permissible_values.items()
        if isinstance(pv, PermissibleValue)
    }
    synonyms: dict[str, Table] = {}
    relationships: dict[str, Table] = {}
    mappings: dict[str, Table] = {}

    predicates: set[str] = set()
    targets: set[str] = set()
    synonym_types: set[str] = set()
    term_ids = {t["id"] for t in release["terms"]}

    for term in release["terms"]:
        tid = term["id"]
        decl.add(tid, "owl:Class", term["label"], "")

        terms.add(
            tid,
            "true" if term.get("deprecated") else "",
            term.get("definition", ""),
            term.get("replaced_by", ""),
            join(term.get("consider", [])),
            join(term.get("subsets", [])),
            join(term.get("parents", [])),
        )

        for syn in term.get("synonyms", []):
            prop = scope_property[syn["scope"]]
            table = synonyms.setdefault(prop, Table([
                ("ID", "ID"),
                ("text", f"A {prop}"),
                ("synonym_type", f">AI {slot_uri(sv, 'Synonym', 'synonym_type')}"),
            ]))
            table.add(tid, syn["text"], syn.get("synonym_type", ""))
            if "synonym_type" in syn:
                synonym_types.add(syn["synonym_type"])

        for rel in term.get("relationships", []):
            predicates.add(rel["predicate"])
            targets.add(rel["target"])
            table = relationships.setdefault(rel["predicate"], Table([
                ("ID", "ID"),
                ("target", f"SC {rel['predicate']} some %"),
            ]))
            table.add(tid, rel["target"])

        for m in term.get("mappings", []):
            extra = sorted(set(m) - {"predicate_id", "object_id"} - set(MAPPING_ANNOTATION_COLUMNS))
            if extra:
                raise ValueError(f"{tid}: mapping uses slots this renderer does not handle yet: {extra}")
            pred = m["predicate_id"]
            if pred not in mappings:
                # The other mapping slots become axiom annotations on the mapping,
                # using SSSOM's own slot URIs.
                mappings[pred] = Table([("ID", "ID"), ("object_id", f"AI {pred}")] + [
                    (s, f">{annotation_kind(sv, s)} {slot_uri(sv, 'TermMapping', s)}")
                    for s in MAPPING_ANNOTATION_COLUMNS
                ])
            mappings[pred].add(tid, m["object_id"], *(str(m.get(s, "")) for s in MAPPING_ANNOTATION_COLUMNS))

    # Relationship targets outside the release (e.g. HGNC genes) still need declaring.
    for t in sorted(targets - term_ids):
        decl.add(t, "owl:Class", "", "")
    for p in sorted(predicates):
        decl.add(p, "owl:ObjectProperty", "", "")
    if synonym_types:
        decl.add("oboInOwl:SynonymTypeProperty", "owl:AnnotationProperty", "", "")
        for st in sorted(synonym_types):
            decl.add(st, "owl:AnnotationProperty", "", "oboInOwl:SynonymTypeProperty")

    tables["declarations"] = decl
    for prefix, group in (("synonyms", synonyms), ("relationships", relationships), ("mappings", mappings)):
        for pred, table in group.items():
            tables[f"{prefix}-{safe_name(pred)}"] = table
    return tables


def annotation_kind(sv: SchemaView, slot_name: str) -> str:
    """AI for IRI-valued slots, A for literals."""
    rng = sv.induced_slot(slot_name, "TermMapping").range
    types = sv.all_types()
    if rng in types and "uriorcurie" in sv.type_ancestors(rng):
        return "AI"
    return "A"


# Mapping slots rendered as axiom annotations. Only these are populated by any
# current source; flatten() refuses mappings that use others.
MAPPING_ANNOTATION_COLUMNS = ["mapping_justification", "comment"]


def main(
    release_path: Annotated[Path, typer.Argument(metavar="RELEASE")],
    schema: Annotated[Path, typer.Option()],
    prefixes: Annotated[Path, typer.Option(help="Extended prefix map (YAML) the release's CURIEs use")],
    out_dir: Annotated[Path, typer.Option()],
    importmap: Annotated[Path | None, typer.Option(help="LinkML importmap (JSON)")] = None,
):
    """Flatten a SourceRelease into ROBOT templates."""
    sv = SchemaView(str(schema), importmap=json.loads(importmap.read_text()) if importmap else None)
    release = load_yaml(release_path)
    try:
        tables = flatten(release, sv)
    except ValueError as e:
        raise SystemExit(f"template flattening failed: {e}")

    out_dir.mkdir(parents=True, exist_ok=True)
    for old in out_dir.glob("*.tsv"):
        old.unlink()
    for name, table in tables.items():
        table.write(out_dir / f"{name}.tsv")
    (out_dir / "templates.txt").write_text(
        "".join(f"{out_dir / name}.tsv\n" for name in tables if name != "declarations")
    )

    meta = release["metadata"]
    header = [
        ("--annotation", "owl:versionInfo", meta["source_version"]),
        ("--link-annotation", "oboInOwl:source", meta.get("source_version_iri") or meta["source_download_url"]),
        ("--link-annotation", "dcterms:license", meta.get("source_license")),
        ("--annotation", "dcterms:modified", meta.get("source_date")),
        ("--annotation", "pav:createdOn", meta["generated_at"]),
    ]
    for _, _, value in header:
        if value and any(c.isspace() for c in str(value)):
            raise SystemExit(f"header value contains whitespace: {value!r}")
    (out_dir / "annotate-args.txt").write_text(
        " ".join(f"{flag} {prop} {value}" for flag, prop, value in header if value) + "\n"
    )

    # Release prefixes plus the vocabulary prefixes the templates use.
    context = dict(load_converter(prefixes).prefix_map)
    for prefix, ns in sv.namespaces().items():
        context.setdefault(prefix, ns)
    context.setdefault("xsd", "http://www.w3.org/2001/XMLSchema#")
    (out_dir / "prefixes.json").write_text(json.dumps({"@context": context}, indent=2))


if __name__ == "__main__":
    typer.run(main)
