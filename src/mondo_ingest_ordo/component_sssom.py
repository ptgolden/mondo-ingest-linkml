"""Write the component's ordo.sssom.tsv from a ROBOT query of the component.

The input is component/sparql/component-mappings.sparql's CSV, with full IRIs.
IRIs are contracted with the curie_map from mondo-ingest's SSSOM metadata for the
source, and the header is that metadata, so the file matches what mondo-ingest
publishes as mappings/<source>.sssom.tsv. Any IRI the curie_map cannot contract
is an error.
"""

import argparse
import csv
import sys
from pathlib import Path

import yaml

from mondo_ingest_ordo.sssom import write

# Multivalued SSSOM set slots that mondo-ingest's metadata files give as scalars
# (sssom-py's parse wraps them into lists; so do we).
MULTIVALUED = ("creator_id", "creator_label", "author_id", "author_label", "reviewer_id", "reviewer_label", "see_also")

# Vocabulary the rows use but mondo-ingest's per-source metadata does not declare.
VOCABULARY = {
    "skos": "http://www.w3.org/2004/02/skos/core#",
    "semapv": "https://w3id.org/semapv/vocab/",
    "orcid": "https://orcid.org/",
}

# Set-level slots whose values are entity references. mondo-ingest's metadata gives
# creator_id as a full ORCID IRI, which makes its own ordo.sssom.tsv fail
# `sssom validate`; contracting it fixes that.
ID_SLOTS = ("creator_id", "author_id", "reviewer_id")


def contract(iri: str, curie_map: dict[str, str]) -> tuple[str, str]:
    best = max((p for p, ns in curie_map.items() if iri.startswith(ns)), key=lambda p: len(curie_map[p]), default=None)
    if best is None:
        raise ValueError(f"no prefix for {iri}")
    return best, f"{best}:{iri[len(curie_map[best]):]}"


def main():
    parser = argparse.ArgumentParser(description="Write a component's SSSOM file from a ROBOT query result.")
    parser.add_argument("mappings_csv", type=Path)
    parser.add_argument("--metadata", type=Path, required=True, help="mondo-ingest's <source>.metadata.sssom.yml")
    parser.add_argument("--extra-prefixes", type=Path, help="Prefixes to add to the metadata's curie_map")
    parser.add_argument("--set", action="append", default=[], metavar="KEY=VALUE", help="Extra header fields")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    header = yaml.safe_load(args.metadata.read_text())
    for slot in MULTIVALUED:
        if isinstance(header.get(slot), str):
            header[slot] = [header[slot]]
    extra = yaml.safe_load(args.extra_prefixes.read_text()) if args.extra_prefixes else {}
    curie_map = {**VOCABULARY, **extra, **header["curie_map"]}

    used = set()
    for slot in ID_SLOTS:
        if slot in header:
            contracted = []
            for v in header[slot]:
                try:
                    prefix, v = contract(v, curie_map)
                    used.add(prefix)
                except ValueError:
                    pass  # already a CURIE
                contracted.append(v)
            header[slot] = contracted

    rows = []
    csv.field_size_limit(sys.maxsize)
    try:
        with open(args.mappings_csv, newline="") as f:
            for r in csv.DictReader(f):
                row = {k: v for k, v in r.items() if v != ""}
                for col in ("subject_id", "predicate_id", "object_id", "mapping_justification"):
                    if col in row:
                        prefix, row[col] = contract(row[col], curie_map)
                        used.add(prefix)
                rows.append(row)
    except ValueError as e:
        sys.exit(f"component sssom failed: {e}")
    rows.sort(key=lambda r: (r["subject_id"], r["predicate_id"], r["object_id"]))

    header["curie_map"] = {p: curie_map[p] for p in sorted(used)}
    header.update(dict(item.split("=", 1) for item in args.set))
    with open(args.output, "w", newline="") as f:
        write(header, rows, f)


if __name__ == "__main__":
    main()
