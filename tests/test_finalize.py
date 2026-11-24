import curies
import pytest

from mondo_source.finalize import Extract, finalize
from mondo_source.problems import Problem, Problems

PIPELINE = {
    "source_id": "example",
    "source_download_urls": ["https://example.org/example.owl"],
    "generated_at": "2026-01-01T00:00:00Z",
    "generated_by": "tests",
}

CONVERTER = curies.Converter.from_extended_prefix_map(
    [
        {"prefix": "EX", "uri_prefix": "https://example.org/term/", "prefix_synonyms": ["Example"]},
        {"prefix": "skos", "uri_prefix": "http://www.w3.org/2004/02/skos/core#"},
        {"prefix": "semapv", "uri_prefix": "https://w3id.org/semapv/vocab/"},
        {"prefix": "mondo_vocab", "uri_prefix": "http://purl.obolibrary.org/obo/mondo#"},
    ]
)

JUSTIFICATION = "semapv:ManualMappingCuration"
FROM_LABEL, GENERATED = "mondo_vocab:GENERATED_FROM_LABEL", "mondo_vocab:GENERATED"


def extract(*terms: dict) -> Extract:
    return Extract.model_validate({"metadata": {"source_version": "1.0"}, "terms": list(terms)})


def test_release_has_the_sources_metadata_and_the_builds(schema):
    release = finalize(extract({"id": "EX:1", "label": "one"}), CONVERTER, schema, PIPELINE)

    assert release.metadata.source_version == "1.0"
    assert release.metadata.source_id == "example"
    assert release.metadata.schema_version == schema.schema.version
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


def problems(schema, *terms: dict, pipeline: dict = PIPELINE) -> list[Problem]:
    with pytest.raises(Problems) as raised:
        finalize(extract(*terms), CONVERTER, schema, pipeline)
    return raised.value.problems


def test_an_unknown_prefix_is_a_problem_naming_the_term_and_the_slot(schema):
    mapping = {"predicate_id": "skos:exactMatch", "object_id": "No:2", "mapping_justification": JUSTIFICATION}
    stated = {"id": "Example:1", "label": "one", "mappings": [mapping]}

    assert problems(schema, stated) == [Problem("Example:1", "mappings.object_id", "No:2", "no prefix in the prefix map")]


def test_every_unknown_prefix_in_a_term_is_a_problem_and_so_is_what_the_model_rejects(schema):
    stated = {"id": "EX:1", "label": "one", "parents": ["No:2", "Nor:3"], "colour": "red"}

    assert [(p.slot, p.value) for p in problems(schema, stated)] == [
        ("colour", "red"),
        ("parents", "No:2"),
        ("parents", "Nor:3"),
    ]


def test_what_the_model_rejects_is_a_problem_for_each_slot(schema):
    stated = {"id": "EX:1", "synonyms": [{"text": "one", "scope": "SIMILAR"}], "colour": "red"}

    assert [(p.term, p.slot, p.value) for p in problems(schema, stated)] == [
        ("EX:1", "colour", "red"),
        ("EX:1", "synonyms.scope", "SIMILAR"),
    ]


def test_a_term_without_a_label_is_a_problem_unless_it_is_deprecated(schema):
    retired = {"id": "EX:1", "deprecated": True, "replaced_by": "EX:2"}
    current = {"id": "EX:2"}

    assert problems(schema, retired, current) == [
        Problem("EX:2", "label", "(missing)", "required unless the term is deprecated")
    ]
    (term, _) = finalize(extract(retired, {**current, "label": "two"}), CONVERTER, schema, PIPELINE).terms
    assert (term.label, term.synonyms, term.replaced_by) == (None, None, "EX:2")


def test_problems_in_every_term_and_in_the_metadata_are_reported_together(schema):
    found = problems(
        schema,
        {"id": "EX:1", "label": "one", "parents": ["No:2"]},
        {"id": "EX:2", "label": "two"},
        {"id": "EX:3"},
        pipeline={**PIPELINE, "generated_at": "yesterday"},
    )

    assert [(p.term, p.slot) for p in found] == [("(metadata)", "generated_at"), ("EX:1", "parents"), ("EX:3", "label")]


def test_terms_and_their_values_come_out_sorted(schema):
    stated = extract(
        {
            "id": "EX:2",
            "label": "two",
            "parents": ["EX:3", "EX:1"],
            "synonyms": [
                {"text": "b", "scope": "EXACT"},
                {"text": "a", "scope": "RELATED"},
                {"text": "a", "scope": "EXACT", "synonym_type": "EX:type"},
                {"text": "a", "scope": "EXACT"},
            ],
            "mappings": [
                {"predicate_id": "skos:narrowMatch", "object_id": "EX:8", "mapping_justification": JUSTIFICATION},
                {"predicate_id": "skos:exactMatch", "object_id": "EX:9", "mapping_justification": JUSTIFICATION},
                {"predicate_id": "skos:exactMatch", "object_id": "EX:8", "mapping_justification": JUSTIFICATION},
            ],
        },
        {"id": "EX:1", "label": "one"},
        {"id": "EX:3", "label": "three"},
    )

    one, two, three = finalize(stated, CONVERTER, schema, PIPELINE).terms

    assert (one.id, two.id, three.id) == ("EX:1", "EX:2", "EX:3")
    assert two.parents == ["EX:1", "EX:3"]
    assert [(s.text, s.scope, s.synonym_type) for s in two.synonyms or []] == [
        ("a", "EXACT", None),
        ("a", "EXACT", "EX:type"),
        ("a", "RELATED", None),
        ("b", "EXACT", None),
        ("two", "EXACT", FROM_LABEL),
    ]
    assert [(m.object_id, m.predicate_id) for m in two.mappings or []] == [
        ("EX:8", "skos:exactMatch"),
        ("EX:8", "skos:narrowMatch"),
        ("EX:9", "skos:exactMatch"),
    ]


def test_mondos_synonyms_are_added_to_the_sources(schema):
    stated = extract({"id": "EX:1", "label": "Leprosy [Hansen disease]", "synonyms": [{"text": "Lepra", "scope": "EXACT"}]})

    (term,) = finalize(stated, CONVERTER, schema, PIPELINE, strip_brackets=True).terms

    assert [(s.text, s.synonym_type) for s in term.synonyms or []] == [
        ("Lepra", None),
        ("Leprosy [Hansen disease]", FROM_LABEL),
        ("leprosy", GENERATED),
    ]


def test_two_terms_with_one_id_are_a_problem(schema):
    found = problems(schema, {"id": "EX:1", "label": "one"}, {"id": "Example:1", "label": "uno"})

    assert found == [Problem("EX:1", "id", "EX:1", "the id of 2 terms")]


def test_a_parent_that_is_not_a_term_of_the_release_is_a_problem(schema):
    found = problems(schema, {"id": "EX:1", "label": "one", "parents": ["EX:2"]})

    assert found == [Problem("EX:1", "parents", "EX:2", "not a term of the release")]
