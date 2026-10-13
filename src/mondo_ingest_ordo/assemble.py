"""Assemble ROBOT query results (CSV) into a SourceRelease YAML document.

Nothing in here knows about ORDO or about RDF. ROBOT runs the source-specific
SPARQL; each query's columns are named after schema slots. This module only
reshapes those rows, using the schema to decide what is multivalued, inlined,
boolean or a CURIE, and fails on anything it cannot place unambiguously.
"""

import argparse
import csv
import json
import re
import sys
from pathlib import Path

import yaml
from linkml_runtime.utils.schemaview import SchemaView

csv.field_size_limit(sys.maxsize)


class AssemblyError(Exception):
    pass


def read_rows(path: Path) -> list[dict[str, str]]:
    with open(path, newline="") as f:
        # Unbound SPARQL variables come back as empty strings.
        return [{k: v for k, v in row.items() if v != ""} for row in csv.DictReader(f)]


class Assembler:
    def __init__(self, schema_path: Path, prefixes: dict[str, str]):
        self.sv = SchemaView(str(schema_path))
        self.prefixes = prefixes

    def slot(self, class_name: str, slot_name: str):
        if slot_name not in self.sv.class_slots(class_name):
            raise AssemblyError(f"{class_name} has no slot {slot_name!r}")
        return self.sv.induced_slot(slot_name, class_name)

    def coerce(self, class_name: str, slot_name: str, value: str):
        slot = self.slot(class_name, slot_name)
        if slot.range == "boolean":
            if value not in ("true", "false"):
                raise AssemblyError(f"{class_name}.{slot_name}: not a boolean: {value!r}")
            return value == "true"
        if slot.range == "uriorcurie":
            prefix = value.split(":", 1)[0]
            if prefix not in self.prefixes:
                raise AssemblyError(f"{class_name}.{slot_name}: undeclared prefix in {value!r}")
        return value

    def build_object(self, class_name: str, row: dict[str, str]) -> dict:
        obj = {}
        for name, value in row.items():
            value = self.coerce(class_name, name, value)
            obj[name] = [value] if self.slot(class_name, name).multivalued else value
        return obj

    def set_slot(self, obj: dict, class_name: str, slot_name: str, row: dict[str, str], where: str):
        """Add one row's worth of `slot_name` to `obj`, merging with what is already there."""
        slot = self.slot(class_name, slot_name)
        if slot.range in self.sv.all_classes():
            value = self.build_object(slot.range, row)
        else:
            if list(row) != [slot_name]:
                raise AssemblyError(f"{where}: expected one column {slot_name!r}, got {list(row)}")
            value = self.coerce(class_name, slot_name, row[slot_name])

        if slot.multivalued:
            values = obj.setdefault(slot_name, [])
            if value not in values:
                values.append(value)
        elif slot_name not in obj:
            obj[slot_name] = value
        elif isinstance(value, dict):
            merge_object(obj[slot_name], value, f"{where}.{slot_name}")
        elif obj[slot_name] != value:
            raise AssemblyError(
                f"{where}.{slot_name}: single-valued but got {obj[slot_name]!r} and {value!r}"
            )

    def assemble(self, config: dict, root: Path, metadata_extra: dict[str, str]) -> dict:
        metadata_rows = read_rows(root / config["metadata"])
        if len(metadata_rows) != 1:
            raise AssemblyError(f"metadata query returned {len(metadata_rows)} rows, expected 1")
        metadata = {}
        for name, value in {**metadata_rows[0], **metadata_extra}.items():
            self.set_slot(metadata, "ReleaseMetadata", name, {name: value}, "metadata")

        terms: dict[str, dict] = {}
        for row in read_rows(root / config["terms"]):
            term_id = row.pop("id")
            term = terms.setdefault(term_id, {"id": self.coerce("Term", "id", term_id)})
            for name, value in row.items():
                self.set_slot(term, "Term", name, {name: value}, term_id)

        for slot_name, path in config.get("term_slots", {}).items():
            for row in read_rows(root / path):
                term_id = row.pop("id")
                if term_id not in terms:
                    raise AssemblyError(f"{path}: row for unknown term {term_id}")
                self.set_slot(terms[term_id], "Term", slot_name, row, term_id)

        release = {
            "metadata": metadata,
            "terms": [canonical(terms[k]) for k in sorted(terms, key=natural_key)],
        }
        if "mappings" in config:
            mappings = [self.build_object("Mapping", row) for row in read_rows(root / config["mappings"])]
            release["mappings"] = sorted(
                mappings, key=lambda m: (natural_key(m["subject_id"]), m["object_id"], m["predicate_id"])
            )
        return release


def merge_object(existing: dict, new: dict, where: str):
    for key, value in new.items():
        if key not in existing:
            existing[key] = value
        elif isinstance(value, list):
            existing[key].extend(v for v in value if v not in existing[key])
        elif existing[key] != value:
            raise AssemblyError(f"{where}.{key}: conflicting values {existing[key]!r} and {value!r}")


def natural_key(curie: str):
    prefix, _, local = curie.partition(":")
    return (prefix, int(local)) if local.isdigit() else (prefix, float("inf"), local)


def canonical(obj):
    """Sort list values so output is stable across runs."""
    if isinstance(obj, dict):
        return {k: canonical(v) for k, v in obj.items()}
    if isinstance(obj, list):
        items = [canonical(v) for v in obj]
        return sorted(items, key=lambda v: json.dumps(v, sort_keys=True))
    return obj


# PyYAML emits YAML 1.1, where e.g. "2E4" is a string and is written unquoted.
# YAML 1.2 parsers (ruamel, most non-Python tools) read that as the float 20000.0.
# Quote any string a YAML 1.2 core-schema parser would resolve to a non-string.
YAML_12_NON_STRING = re.compile(
    r"""^(?:~|null|Null|NULL|true|True|TRUE|false|False|FALSE
    |[-+]?[0-9]+|0o[0-7]+|0x[0-9a-fA-F]+
    |[-+]?(?:\.[0-9]+|[0-9]+(?:\.[0-9]*)?)(?:[eE][-+]?[0-9]+)?
    |[-+]?\.(?:inf|Inf|INF)|\.(?:nan|NaN|NAN))$""",
    re.VERBOSE,
)


class ReleaseDumper(getattr(yaml, "CSafeDumper", yaml.SafeDumper)):
    pass


def represent_str(dumper, value: str):
    style = "'" if YAML_12_NON_STRING.match(value) else None
    return dumper.represent_scalar("tag:yaml.org,2002:str", value, style=style)


ReleaseDumper.add_representer(str, represent_str)


def main():
    parser = argparse.ArgumentParser(description="Assemble ROBOT query results into a SourceRelease YAML.")
    parser.add_argument("--schema", type=Path, required=True)
    parser.add_argument("--prefixes", type=Path, required=True)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--set", action="append", default=[], metavar="KEY=VALUE",
                        help="Extra metadata not available from the source (e.g. generated_at)")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--metadata-output", type=Path)
    args = parser.parse_args()

    prefixes = yaml.safe_load(args.prefixes.read_text())
    config = yaml.safe_load(args.config.read_text())
    extra = dict(item.split("=", 1) for item in args.set)

    try:
        release = Assembler(args.schema, prefixes).assemble(config, Path("."), extra)
    except AssemblyError as e:
        sys.exit(f"assembly failed: {e}")

    dumper = ReleaseDumper
    with open(args.output, "w") as f:
        yaml.dump(release, f, Dumper=dumper, sort_keys=False, allow_unicode=True, width=1000)
    if args.metadata_output:
        with open(args.metadata_output, "w") as f:
            yaml.dump(release["metadata"], f, Dumper=dumper, sort_keys=False, allow_unicode=True)


if __name__ == "__main__":
    main()
