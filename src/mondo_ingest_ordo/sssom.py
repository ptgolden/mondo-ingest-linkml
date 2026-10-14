"""Project a SourceRelease's mappings to an SSSOM TSV.

The SSSOM file is derived, never edited: every row is a mapping inlined on one
of the release's terms, and set-level metadata comes from the release's `metadata`.
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
    "comment",
]


def project(release: dict, prefixes: dict[str, str], mapping_set_id: str) -> tuple[dict, list[dict]]:
    rows = []
    for term in release["terms"]:
        for mapping in term.get("mappings", []):
            # Inline mappings omit their subject: it is the term they sit under.
            rows.append({"subject_id": term["id"], "subject_label": term["label"], **mapping})

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
