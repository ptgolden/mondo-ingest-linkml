import curies
import pytest

from mondo_source.finalize import Extract, finalize

PIPELINE = {
    "source_id": "example",
    "source_download_url": "https://example.org/example.owl",
    "schema_version": "0.0.0",
    "generated_at": "2026-01-01T00:00:00Z",
    "generated_by": "tests",
}

CONVERTER = curies.Converter.from_extended_prefix_map(
    [
        {"prefix": "EX", "uri_prefix": "https://example.org/term/", "prefix_synonyms": ["Example"]},
        {"prefix": "skos", "uri_prefix": "http://www.w3.org/2004/02/skos/core#"},
        {"prefix": "semapv", "uri_prefix": "https://w3id.org/semapv/vocab/"},
    ]
)


def extract(*terms: dict) -> Extract:
    return Extract.model_validate({"metadata": {"source_version": "1.0"}, "terms": list(terms)})


def test_release_has_the_sources_metadata_and_the_builds(schema):
    release = finalize(extract({"id": "EX:1", "label": "one"}), CONVERTER, schema, PIPELINE)

    assert release.metadata.source_version == "1.0"
    assert release.metadata.source_id == "example"
    assert [term.id for term in release.terms] == ["EX:1"]


def test_identifiers_become_canonical_curies(schema):
    stated = extract(
        {"id": "https://example.org/term/1", "label": "one"},
        {
            "id": "Example:2",
            "label": "two",
            "parents": ["https://example.org/term/1"],
            "mappings": [
                {
                    "predicate_id": "http://www.w3.org/2004/02/skos/core#exactMatch",
                    "object_id": "Example:3",
                    "mapping_justification": "https://w3id.org/semapv/vocab/ManualMappingCuration",
                }
            ],
        },
    )

    one, two = finalize(stated, CONVERTER, schema, PIPELINE).terms

    assert (one.id, two.id, two.parents) == ("EX:1", "EX:2", ["EX:1"])
    assert two.mappings is not None
    assert (two.mappings[0].predicate_id, two.mappings[0].object_id) == ("skos:exactMatch", "EX:3")
    assert stated.terms[1]["id"] == "Example:2"


def test_text_that_looks_like_an_identifier_is_left_alone(schema):
    (term,) = finalize(extract({"id": "EX:1", "label": "Example:2"}), CONVERTER, schema, PIPELINE).terms

    assert term.label == "Example:2"


def test_an_unknown_prefix_fails_naming_the_term_and_the_slot(schema):
    stated = extract({"id": "EX:1", "label": "one", "parents": ["Unknown:2"]})

    with pytest.raises(ValueError, match=r"EX:1: parents: .*'Unknown:2'"):
        finalize(stated, CONVERTER, schema, PIPELINE)
