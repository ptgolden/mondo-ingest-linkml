import curies

from mondo_source.sssom import project, write

CONVERTER = curies.Converter.from_prefix_map(
    {
        "EX": "https://example.org/term/",
        "MONDO": "http://purl.obolibrary.org/obo/MONDO_",
        "UNUSED": "https://example.org/unused/",
        "skos": "http://www.w3.org/2004/02/skos/core#",
        "semapv": "https://w3id.org/semapv/vocab/",
        "orcid": "https://orcid.org/",
    }
)

MAPPING = {
    "predicate_id": "skos:exactMatch",
    "object_id": "MONDO:0000001",
    "mapping_justification": "semapv:ManualMappingCuration",
}

RELEASE = {
    "metadata": {"source_version": "1.0", "source_license": "https://example.org/licence"},
    "terms": [
        {"id": "EX:1", "label": "one", "mappings": [MAPPING, {**MAPPING, "comment": "Specific code"}]},
        {"id": "EX:2", "label": "two"},
        {"id": "EX:3", "deprecated": True, "mappings": [MAPPING]},
    ],
}


def test_each_inline_mapping_is_a_row_with_its_term_as_the_subject():
    _, rows = project(RELEASE, CONVERTER, {})

    assert [(row["subject_id"], row["subject_label"], row.get("comment")) for row in rows] == [
        ("EX:1", "one", None),
        ("EX:1", "one", "Specific code"),
        ("EX:3", "", None),
    ]
    assert rows[0]["object_id"] == "MONDO:0000001"


def test_the_header_has_the_releases_version_and_only_the_prefixes_used():
    header, _ = project(RELEASE, CONVERTER, {"mapping_set_id": "https://example.org/example.sssom.tsv"})

    assert header["mapping_set_id"] == "https://example.org/example.sssom.tsv"
    assert header["mapping_set_version"] == "1.0"
    assert list(header["curie_map"]) == ["EX", "MONDO", "semapv", "skos"]


def test_the_license_is_the_sources_unless_the_metadata_gives_one():
    from_source, _ = project(RELEASE, CONVERTER, {})
    from_metadata, _ = project(RELEASE, CONVERTER, {"license": "https://example.org/other"})

    assert from_source["license"] == "https://example.org/licence"
    assert from_metadata["license"] == "https://example.org/other"


def test_a_creator_given_as_one_iri_becomes_a_list_of_curies():
    header, _ = project(RELEASE, CONVERTER, {"creator_id": "https://orcid.org/0000-0000-0000-0001"})

    assert header["creator_id"] == ["orcid:0000-0000-0000-0001"]
    assert "orcid" in header["curie_map"]


def test_the_file_is_the_header_as_comments_then_the_rows(tmp_path):
    path = tmp_path / "example.sssom.tsv"

    write(*project(RELEASE, CONVERTER, {}), path)

    lines = path.read_text().splitlines()
    assert lines[0] == "#curie_map:"
    assert "#mapping_set_version: '1.0'" in lines
    table = [line.split("\t") for line in lines if not line.startswith("#")]
    assert table[0] == ["subject_id", "subject_label", "predicate_id", "object_id", "mapping_justification", "comment"]
    assert table[1] == ["EX:1", "one", "skos:exactMatch", "MONDO:0000001", "semapv:ManualMappingCuration", ""]
