import curies
import pytest

from mondo_source.identifiers import Identifiers, UnknownPrefix, identifier_slots

CONVERTER = curies.Converter.from_extended_prefix_map(
    [{"prefix": "EX", "uri_prefix": "https://example.org/term/", "prefix_synonyms": ["Example"]}]
)


def test_identifier_slots_are_references_and_uriorcuries_at_any_depth(schema):
    slots = set(identifier_slots(schema, "Term"))

    assert slots >= {
        ("id",),
        ("parents",),
        ("replaced_by",),
        ("subsets",),
        ("synonyms", "synonym_type"),
        ("relationships", "target"),
        ("mappings", "object_id"),
        ("mappings", "mapping_justification"),
    }
    assert not slots & {
        ("label",),
        ("deprecated",),
        ("synonyms",),
        ("synonyms", "text"),
        ("synonyms", "scope"),
        ("mappings", "comment"),
        ("mappings", "license"),
    }


def test_to_curies_converts_identifiers_and_nothing_else():
    identifiers = Identifiers(frozenset({("id",), ("parents",), ("mappings", "object_id")}), CONVERTER)
    stated = {
        "id": "https://example.org/term/1",
        "label": "Example:1",
        "deprecated": True,
        "parents": ["Example:2", "EX:3"],
        "mappings": [{"object_id": "https://example.org/term/4", "comment": "Example:4"}],
    }

    assert identifiers.to_curies(stated) == {
        "id": "EX:1",
        "label": "Example:1",
        "deprecated": True,
        "parents": ["EX:2", "EX:3"],
        "mappings": [{"object_id": "EX:4", "comment": "Example:4"}],
    }
    assert stated["id"] == "https://example.org/term/1"


def test_identifiers_with_no_prefix_in_the_map_are_found_and_left_as_they_are():
    identifiers = Identifiers(frozenset({("parents",), ("mappings", "object_id")}), CONVERTER)
    stated = {"parents": ["EX:1", "No:2"], "mappings": [{"object_id": "https://elsewhere.org/3"}]}

    assert identifiers.unknown_in(stated) == [
        (("parents",), "No:2"),
        (("mappings", "object_id"), "https://elsewhere.org/3"),
    ]
    assert identifiers.to_curies(stated) == stated


def test_curie_is_for_an_identifier_that_must_have_one():
    identifiers = Identifiers(frozenset(), CONVERTER)

    assert identifiers.curie("https://example.org/term/1", ("id",)) == "EX:1"
    with pytest.raises(UnknownPrefix) as raised:
        identifiers.curie("No:1", ("id",))
    assert (raised.value.slot, raised.value.identifier) == (("id",), "No:1")
