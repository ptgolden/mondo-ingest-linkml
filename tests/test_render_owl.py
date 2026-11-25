import pyoxigraph as ox
import pytest
import yaml

from mondo_source import render_owl

EX = "https://example.org/term/"
OIO = "http://www.geneontology.org/formats/oboInOwl#"
OWL = "http://www.w3.org/2002/07/owl#"
RDF = "http://www.w3.org/1999/02/22-rdf-syntax-ns#"
RDFS = "http://www.w3.org/2000/01/rdf-schema#"
SKOS = "http://www.w3.org/2004/02/skos/core#"

PREFIXES = [
    {"prefix": "EX", "uri_prefix": EX},
    {"prefix": "mondo_vocab", "uri_prefix": "http://purl.obolibrary.org/obo/mondo#"},
    {"prefix": "skos", "uri_prefix": SKOS},
    {"prefix": "oboInOwl", "uri_prefix": OIO},
    {"prefix": "semapv", "uri_prefix": "https://w3id.org/semapv/vocab/"},
]

METADATA = {
    "source_id": "example",
    "source_version": "1.0",
    "schema_version": "0.0.0",
    "generated_at": "2026-01-01T00:00:00Z",
    "generated_by": "tests",
}

JUSTIFICATION = "semapv:ManualMappingCuration"

TERMS = [
    {
        "id": "EX:1",
        "label": "one",
        "synonyms": [{"text": 'the "first", a\\b', "scope": "EXACT", "synonym_type": "mondo_vocab:GENERATED"}],
        "mappings": [
            {
                "predicate_id": "skos:exactMatch",
                "object_id": "EX:9",
                "mapping_justification": JUSTIFICATION,
                "comment": 'a "specific" code',
            },
            {"predicate_id": "oboInOwl:hasDbXref", "object_id": "EX:8", "mapping_justification": JUSTIFICATION},
        ],
    },
    {"id": "EX:2", "deprecated": True, "replaced_by": "EX:1"},
]


@pytest.fixture
def rendered(tmp_path, schema_file, importmap_file) -> ox.Store:
    """TERMS, rendered as OWL and loaded as a graph."""
    (tmp_path / "prefixes.yaml").write_text(yaml.safe_dump(PREFIXES))
    (tmp_path / "example.yaml").write_text(yaml.safe_dump({"metadata": METADATA, "terms": TERMS}))
    (tmp_path / "example.metadata.yaml").write_text(yaml.safe_dump(METADATA))
    render_owl.main(
        release=tmp_path / "example.yaml",
        schema=schema_file,
        prefixes=tmp_path / "prefixes.yaml",
        output=tmp_path / "example.owl",
        metadata=tmp_path / "example.metadata.yaml",
        ontology_iri="https://example.org/example.owl",
        version_iri="https://example.org/2026-01-01/example.owl",
        importmap=importmap_file,
    )
    store = ox.Store()
    store.load(path=str(tmp_path / "example.owl"), format=ox.RdfFormat.RDF_XML)
    return store


def objects(store: ox.Store, subject: str, predicate: str) -> list[ox.NamedNode | ox.BlankNode | ox.Literal | ox.Triple]:
    quads = store.quads_for_pattern(ox.NamedNode(subject), ox.NamedNode(predicate), None)
    return [quad.object for quad in quads]


def test_a_term_is_a_class_with_its_slots_as_axioms(rendered):
    assert objects(rendered, EX + "1", RDF + "type") == [ox.NamedNode(OWL + "Class")]
    assert [label.value for label in objects(rendered, EX + "1", RDFS + "label")] == ["one"]
    assert objects(rendered, EX + "2", "http://purl.obolibrary.org/obo/IAO_0100001") == [ox.NamedNode(EX + "1")]
    assert objects(rendered, EX + "2", RDFS + "label") == []


def test_quotes_and_backslashes_in_text_come_through(rendered):
    (synonym,) = objects(rendered, EX + "1", OIO + "hasExactSynonym")
    comments = rendered.query(f'SELECT ?c WHERE {{ ?axiom <{OWL}annotatedProperty> <{SKOS}exactMatch> ; <{RDFS}comment> ?c }}')

    assert synonym.value == 'the "first", a\\b'
    assert [row["c"].value for row in comments] == ['a "specific" code']


def test_a_mappings_object_is_an_iri(rendered):
    assert objects(rendered, EX + "1", SKOS + "exactMatch") == [ox.NamedNode(EX + "9")]


def test_an_xrefs_object_is_the_curie_as_text(rendered):
    justified = rendered.query(
        f'SELECT ?target WHERE {{ ?axiom <{OWL}annotatedProperty> <{OIO}hasDbXref> ; <{OWL}annotatedTarget> ?target ;'
        f" <https://w3id.org/sssom/mapping_justification> ?justification }}"
    )

    assert objects(rendered, EX + "1", OIO + "hasDbXref") == [ox.Literal("EX:8")]
    assert [row["target"] for row in justified] == [ox.Literal("EX:8")]


def test_the_header_and_the_annotation_properties_are_written(rendered):
    ontology = "https://example.org/example.owl"

    assert [version.value for version in objects(rendered, ontology, OWL + "versionInfo")] == ["1.0"]
    assert objects(rendered, OIO + "hasExactSynonym", RDF + "type") == [ox.NamedNode(OWL + "AnnotationProperty")]
