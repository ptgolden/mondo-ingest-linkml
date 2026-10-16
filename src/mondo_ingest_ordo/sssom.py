"""Project a SourceRelease's mappings to an SSSOM TSV.

The SSSOM file is derived, never edited: every row is a mapping inlined on one of
the release's terms. Set-level metadata comes from a metadata file (for ORDO,
mondo-ingest's own ordo.metadata.sssom.yml, so the file matches what mondo-ingest
publishes) plus the release's metadata.
"""

import csv
from pathlib import Path
from typing import Annotated

import curies
import typer
import yaml

from mondo_ingest_ordo.prefixes import load_converter
from mondo_ingest_ordo.yamlio import load_yaml

COLUMNS = ["subject_id", "subject_label", "predicate_id", "object_id", "mapping_justification", "comment"]

# Set-level slots whose values are entity references. mondo-ingest's metadata gives
# creator_id as a scalar full ORCID IRI, which makes its own ordo.sssom.tsv fail
# `sssom validate`; SSSOM wants a list of CURIEs.
ID_SLOTS = ("creator_id", "author_id", "reviewer_id")


def project(release: dict, converter: curies.Converter, metadata: dict) -> tuple[dict, list[dict]]:
    rows = [
        # Inline mappings omit their subject: it is the term they sit under.
        {"subject_id": term["id"], "subject_label": term["label"], **mapping}
        for term in release["terms"]
        for mapping in term.get("mappings", [])
    ]

    header = dict(metadata)
    for slot in ID_SLOTS:
        if slot in header:
            values = header[slot] if isinstance(header[slot], list) else [header[slot]]
            header[slot] = [converter.compress(v, passthrough=True) for v in values]

    used = {
        converter.parse_curie(value, strict=True).prefix
        for row in rows
        for value in (row["subject_id"], row["predicate_id"], row["object_id"], row["mapping_justification"])
    } | {converter.parse_curie(v, strict=True).prefix for slot in ID_SLOTS for v in header.get(slot, [])}
    header["curie_map"] = {p: converter.bimap[p] for p in sorted(used)}

    meta = release["metadata"]
    header["mapping_set_version"] = meta["source_version"]
    header.setdefault("license", meta.get("source_license"))
    return header, rows


def write(header: dict, rows: list[dict], path: Path):
    with open(path, "w", newline="") as out:
        for line in yaml.safe_dump(header, sort_keys=False, allow_unicode=True).splitlines():
            out.write(f"#{line}\n")
        writer = csv.DictWriter(out, COLUMNS, delimiter="\t", lineterminator="\n", extrasaction="raise")
        writer.writeheader()
        writer.writerows(rows)


def main(
    release: Annotated[Path, typer.Argument()],
    prefixes: Annotated[Path, typer.Option(help="Extended prefix map (YAML)")],
    metadata: Annotated[Path, typer.Option(help="SSSOM mapping set metadata (YAML)")],
    output: Annotated[Path, typer.Option()],
):
    """Project a SourceRelease's mappings to SSSOM TSV."""
    converter = load_converter(prefixes)
    header, rows = project(load_yaml(release), converter, yaml.safe_load(metadata.read_text()))
    write(header, rows, output)


if __name__ == "__main__":
    typer.run(main)
