"""Project a SourceRelease's mappings to an SSSOM TSV.

The SSSOM file is derived, never edited: every row comes from the release's
`mappings`, and set-level metadata comes from the release's `metadata`.
"""

import argparse
import csv
import sys
from pathlib import Path

import yaml

COLUMNS = [
    "subject_id",
    "subject_label",
    "predicate_id",
    "object_id",
    "mapping_justification",
    "source_mapping_qualifier",
]

EXTENSIONS = [
    {
        "slot_name": "source_mapping_qualifier",
        "property": "https://w3id.org/monarch-initiative/mondo-source/source_mapping_qualifier",
        "type_hint": "http://www.w3.org/2001/XMLSchema#string",
    }
]


def project(release: dict, prefixes: dict[str, str], mapping_set_id: str) -> tuple[dict, list[dict]]:
    labels = {term["id"]: term["label"] for term in release["terms"]}
    rows = []
    for mapping in release.get("mappings", []):
        row = {**mapping, "subject_label": labels.get(mapping["subject_id"], "")}
        # SSSOM/TSV cells cannot contain newlines.
        if "source_mapping_qualifier" in row:
            row["source_mapping_qualifier"] = " ".join(row["source_mapping_qualifier"].split("\n"))
        rows.append(row)

    used = {
        row[col].split(":", 1)[0]
        for row in rows
        for col in ("subject_id", "predicate_id", "object_id", "mapping_justification")
    }
    meta = release["metadata"]
    header = {
        "curie_map": {p: prefixes[p] for p in sorted(used)},
        "mapping_set_id": mapping_set_id,
        "mapping_set_version": meta["source_version"],
        "license": meta["source_license"],
        "publication_date": meta["generated_at"][:10],
        "mapping_tool": meta["generated_by"],
        "extension_definitions": EXTENSIONS,
    }
    return header, rows


def write(header: dict, rows: list[dict], out):
    for line in yaml.safe_dump(header, sort_keys=False, allow_unicode=True).splitlines():
        out.write(f"#{line}\n")
    writer = csv.DictWriter(out, COLUMNS, delimiter="\t", lineterminator="\n", extrasaction="raise")
    writer.writeheader()
    writer.writerows(rows)


def main():
    parser = argparse.ArgumentParser(description="Project a SourceRelease's mappings to SSSOM TSV.")
    parser.add_argument("release", type=Path)
    parser.add_argument("--prefixes", type=Path, required=True)
    parser.add_argument("--mapping-set-id", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    loader = getattr(yaml, "CSafeLoader", yaml.SafeLoader)
    release = yaml.load(args.release.read_text(), Loader=loader)
    prefixes = yaml.safe_load(args.prefixes.read_text())
    try:
        header, rows = project(release, prefixes, args.mapping_set_id)
    except KeyError as e:
        sys.exit(f"sssom projection failed: missing {e}")
    with open(args.output, "w", newline="") as f:
        write(header, rows, f)


if __name__ == "__main__":
    main()
