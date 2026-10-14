"""Flatten a SourceRelease into ROBOT templates, for `robot template` to render as OWL.

Python only writes tables here; ROBOT owns the OWL. Output, in --out-dir:

  declarations.tsv     every term (owl:Class) and relationship predicate (owl:ObjectProperty)
  terms.tsv            single-valued term annotations, definitions, obsoletion, parents
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

OWL properties come from the schema where it says (slot_uri, enum meanings, SSSOM's
slot URIs); the few choices it doesn't make are named below.
"""

import argparse
import csv
import json
import sys
from pathlib import Path

import yaml
from linkml_runtime.utils.schemaview import SchemaView

# Choices the schema does not make.
DEFINITION = "IAO:0000115"
DEFINITION_CITATION = "dcterms:source"
OBSOLETION_REASON = "rdfs:comment"
# OBO synonym properties all carry a scope; skos:altLabel is the scope-less one.
UNSCOPED_SYNONYM = "skos:altLabel"

SPLIT = "|"


def curie(sv: SchemaView, uri: str) -> str:
    """Contract an expanded slot/enum URI with the schema's own prefixes."""
    for prefix, ns in sorted(sv.namespaces().items(), key=lambda kv: -len(kv[1])):
        if uri.startswith(ns):
            return f"{prefix}:{uri[len(ns):]}"
    return uri


def slot_uri(sv: SchemaView, class_name: str, slot_name: str) -> str:
    return curie(sv, sv.get_uri(sv.induced_slot(slot_name, class_name), expand=True))


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

    decl = Table([("ID", "ID"), ("TYPE", "TYPE"), ("LABEL", "LABEL")])
    terms = Table([
        ("ID", "ID"),
        ("deprecated", f"AT {slot_uri(sv, 'Term', 'deprecated')}^^xsd:boolean"),
        ("obsoletion_reason", f"A {OBSOLETION_REASON}"),
        ("definition", f"A {DEFINITION}"),
        ("citations", f">A {DEFINITION_CITATION} SPLIT={SPLIT}"),
        ("replaced_by", f"AI {slot_uri(sv, 'Term', 'replaced_by')}"),
        ("consider", f"AI {slot_uri(sv, 'Term', 'consider')} SPLIT={SPLIT}"),
        ("parents", f"SC % SPLIT={SPLIT}"),
    ])
    tables["terms"] = terms

    scope_property = {
        name: curie(sv, pv.meaning)
        for name, pv in sv.get_enum("SynonymScope").permissible_values.items()
    }
    synonyms: dict[str, Table] = {}
    relationships: dict[str, Table] = {}
    mappings: dict[str, Table] = {}

    predicates = set()

    for term in release["terms"]:
        tid = term["id"]
        decl.add(tid, "owl:Class", term["label"])

        definition = term.get("definition", {})
        terms.add(
            tid,
            "true" if term.get("deprecated") else "",
            term.get("obsoletion_reason", ""),
            definition.get("text", ""),
            join(definition.get("citations", [])),
            term.get("replaced_by", ""),
            join(term.get("consider", [])),
            join(term.get("parents", [])),
        )

        for syn in term.get("synonyms", []):
            prop = scope_property[syn["scope"]] if "scope" in syn else UNSCOPED_SYNONYM
            table = synonyms.setdefault(prop, Table([
                ("ID", "ID"),
                ("text", f"A {prop}"),
                ("synonym_type", f">AI {slot_uri(sv, 'Synonym', 'synonym_type')}"),
            ]))
            table.add(tid, syn["text"], syn.get("synonym_type", ""))

        for rel in term.get("relationships", []):
            predicates.add(rel["predicate"])
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

    for p in sorted(predicates):
        decl.add(p, "owl:ObjectProperty", "")

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


def main():
    parser = argparse.ArgumentParser(description="Flatten a SourceRelease into ROBOT templates.")
    parser.add_argument("release", type=Path)
    parser.add_argument("--schema", type=Path, required=True)
    parser.add_argument("--importmap", type=Path)
    parser.add_argument("--prefixes", type=Path, required=True)
    parser.add_argument("--out-dir", type=Path, required=True)
    args = parser.parse_args()

    importmap = json.loads(args.importmap.read_text()) if args.importmap else None
    sv = SchemaView(str(args.schema), importmap=importmap)
    loader = getattr(yaml, "CSafeLoader", yaml.SafeLoader)
    release = yaml.load(args.release.read_text(), Loader=loader)

    try:
        tables = flatten(release, sv)
    except ValueError as e:
        sys.exit(f"template flattening failed: {e}")

    args.out_dir.mkdir(parents=True, exist_ok=True)
    for old in args.out_dir.glob("*.tsv"):
        old.unlink()
    for name, table in tables.items():
        table.write(args.out_dir / f"{name}.tsv")
    (args.out_dir / "templates.txt").write_text(
        "".join(f"{args.out_dir / name}.tsv\n" for name in tables if name != "declarations")
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
            sys.exit(f"header value contains whitespace: {value!r}")
    (args.out_dir / "annotate-args.txt").write_text(
        " ".join(f"{flag} {prop} {value}" for flag, prop, value in header if value) + "\n"
    )

    # Release prefixes plus the vocabulary prefixes the templates use.
    context = dict(yaml.safe_load(args.prefixes.read_text()))
    for prefix, ns in sv.namespaces().items():
        context.setdefault(prefix, ns)
    context.setdefault("xsd", "http://www.w3.org/2001/XMLSchema#")
    (args.out_dir / "prefixes.json").write_text(json.dumps({"@context": context}, indent=2))


if __name__ == "__main__":
    main()
