"""Project a SourceRelease's mappings to an SSSOM TSV.

The SSSOM file is derived, never edited: every row is a mapping inlined on one of
the release's terms. Set-level metadata comes from a metadata file (for ORDO,
mondo-ingest's own ordo.metadata.sssom.yml, so the file matches what mondo-ingest
publishes) plus the release's metadata.
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

# Set-level slots whose values are entity references. mondo-ingest's metadata gives
# creator_id as a scalar full ORCID IRI, which makes its own ordo.sssom.tsv fail
# `sssom validate`; SSSOM wants a list of CURIEs.
ID_SLOTS = ("creator_id", "author_id", "reviewer_id")


def contract(iri: str, prefixes: dict[str, str]) -> str:
    for prefix, ns in sorted(prefixes.items(), key=lambda kv: -len(kv[1])):
        if iri.startswith(ns):
            return f"{prefix}:{iri[len(ns):]}"
    return iri


def project(release: dict, prefixes: dict[str, str], metadata: dict) -> tuple[dict, list[dict]]:
    rows = []
    for term in release["terms"]:
        for mapping in term.get("mappings", []):
            # Inline mappings omit their subject: it is the term they sit under.
            rows.append({"subject_id": term["id"], "subject_label": term["label"], **mapping})

    header = dict(metadata)
    for slot in ID_SLOTS:
        if slot in header:
            values = header[slot] if isinstance(header[slot], list) else [header[slot]]
            header[slot] = [contract(v, prefixes) for v in values]

    used = {
        value.split(":", 1)[0]
        for row in rows
        for value in (row["subject_id"], row["predicate_id"], row["object_id"], row["mapping_justification"])
    } | {v.split(":", 1)[0] for slot in ID_SLOTS for v in header.get(slot, [])}
    header["curie_map"] = {p: prefixes[p] for p in sorted(used)}

    meta = release["metadata"]
    header["mapping_set_version"] = meta["source_version"]
    header.setdefault("license", meta.get("source_license"))
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
    parser.add_argument("--metadata", type=Path, required=True, help="SSSOM mapping set metadata (YAML)")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    loader = getattr(yaml, "CSafeLoader", yaml.SafeLoader)
    release = yaml.load(args.release.read_text(), Loader=loader)
    prefixes = yaml.safe_load(args.prefixes.read_text())
    metadata = yaml.safe_load(args.metadata.read_text())
    try:
        header, rows = project(release, prefixes, metadata)
    except KeyError as e:
        sys.exit(f"sssom projection failed: undeclared prefix or missing field {e}")
    with open(args.output, "w", newline="") as f:
        write(header, rows, f)


if __name__ == "__main__":
    main()
