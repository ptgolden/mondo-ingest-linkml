from pathlib import Path

import pytest

from mondo_source.extract import extract, gather

SHARED = Path(__file__).parent.parent / "src" / "mondo_source" / "sparql"

EX = "https://example.org/term/"

PREFIXES = """
@prefix ex: <https://example.org/term/> .
@prefix owl: <http://www.w3.org/2002/07/owl#> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
@prefix oio: <http://www.geneontology.org/formats/oboInOwl#> .
@prefix obo: <http://purl.obolibrary.org/obo/> .
@prefix ms: <https://w3id.org/monarch-initiative/mondo-source/> .
"""

METADATA_RQ = "SELECT ?source_version WHERE { ?o <http://www.w3.org/2002/07/owl#versionInfo> ?source_version }"
TERMS_RQ = "SELECT ?id ?label WHERE { ?id <http://www.w3.org/2000/01/rdf-schema#label> ?label }"
UPPERCASE_TERMS_RQ = (
    "SELECT ?id (UCASE(?l) AS ?label) WHERE { ?id <http://www.w3.org/2000/01/rdf-schema#label> ?l }"
)


def source(directory: Path, turtle: str) -> Path:
    path = directory / "source.ttl"
    path.write_text(PREFIXES + '<https://example.org/onto> a owl:Ontology ; owl:versionInfo "1.0" .' + turtle)
    return path


def queries(directory: Path, name: str, **files: str) -> Path:
    """A SPARQL directory. Keyword `terms_rq` is the file terms.rq."""
    path = directory / name
    path.mkdir()
    for file, text in files.items():
        (path / file.replace("_", ".")).write_text(text)
    return path


def test_gather_puts_each_querys_rows_on_their_term():
    extracted = gather(
        {
            "metadata": [{"source_version": "1.0"}],
            "terms": [{"id": "ex:1", "label": "one"}, {"id": "ex:2", "label": "two"}],
            "parents": [{"id": "ex:2", "parents": "ex:1"}, {"id": "ex:2", "parents": "ex:0"}],
            "synonyms": [{"id": "ex:1", "text": "uno", "scope": "EXACT"}],
        }
    )

    assert extracted.metadata == {"source_version": "1.0"}
    assert extracted.terms == [
        {"id": "ex:1", "label": "one", "synonyms": [{"text": "uno", "scope": "EXACT"}]},
        {"id": "ex:2", "label": "two", "parents": ["ex:1", "ex:0"]},
    ]


def test_two_rows_for_one_term_are_an_error():
    rows = {"metadata": [{}], "terms": [{"id": "ex:1", "label": "one"}, {"id": "ex:1", "label": "uno"}]}

    with pytest.raises(ValueError, match="terms.rq: conflicting single-valued slots for ex:1"):
        gather(rows)


def test_a_row_for_a_term_that_terms_rq_does_not_return_is_an_error():
    rows = {"metadata": [{}], "terms": [], "parents": [{"id": "ex:2", "parents": "ex:1"}]}

    with pytest.raises(ValueError, match="parents.rq: rows for ex:2"):
        gather(rows)


def test_updates_run_before_queries(tmp_path):
    sparql = queries(
        tmp_path,
        "sparql",
        metadata_rq=METADATA_RQ,
        terms_rq=TERMS_RQ,
        add_ru=f'INSERT DATA {{ <{EX}2> <http://www.w3.org/2000/01/rdf-schema#label> "two" }}',
    )

    extracted = extract(source(tmp_path, 'ex:1 rdfs:label "one" .'), [sparql])

    assert sorted(term["label"] for term in extracted.terms) == ["one", "two"]


def test_a_later_directorys_file_replaces_an_earlier_one_of_the_same_name(tmp_path):
    shared = queries(tmp_path, "shared", metadata_rq=METADATA_RQ, terms_rq=TERMS_RQ)
    own = queries(tmp_path, "own", terms_rq=UPPERCASE_TERMS_RQ)

    extracted = extract(source(tmp_path, 'ex:1 rdfs:label "one" .'), [shared, own])

    assert extracted.metadata == {"source_version": "1.0"}
    assert extracted.terms == [{"id": f"{EX}1", "label": "ONE"}]


def test_the_shared_queries_read_obo_in_owl_for_classes_marked_in_scope(tmp_path):
    turtle = """
        <https://example.org/onto> owl:versionIRI <https://example.org/onto/1.0> .

        ex:1 a owl:Class ; ms:in_scope true ;
            rdfs:label "one" , "one"@en ;
            obo:IAO_0000115 "The first." ;
            oio:hasExactSynonym "uno" ;
            oio:hasRelatedSynonym "first" .
        [] a owl:Axiom ;
            owl:annotatedSource ex:1 ; owl:annotatedProperty oio:hasExactSynonym ; owl:annotatedTarget "uno" ;
            oio:hasSynonymType ex:type .

        ex:2 a owl:Class ; ms:in_scope true ;
            rdfs:label "two" ;
            rdfs:subClassOf ex:1 , ex:9 ;
            owl:deprecated true ;
            obo:IAO_0100001 ex:1 ;
            oio:consider ex:1 .

        ex:3 a owl:Class ; ms:in_scope true ; owl:deprecated true .

        ex:9 a owl:Class ; rdfs:label "not marked in scope" .
    """

    extracted = extract(source(tmp_path, turtle), [SHARED])
    one, two, three = sorted(extracted.terms, key=lambda term: str(term["id"]))

    assert extracted.metadata == {"source_version": "1.0", "source_version_iri": "https://example.org/onto/1.0"}
    assert {**one, "synonyms": sorted(one["synonyms"], key=str)} == {
        "id": f"{EX}1",
        "label": "one",
        "definition": "The first.",
        "synonyms": [
            {"text": "first", "scope": "RELATED"},
            {"text": "uno", "scope": "EXACT", "synonym_type": f"{EX}type"},
        ],
    }
    assert two == {
        "id": f"{EX}2",
        "label": "two",
        "deprecated": "true",
        "replaced_by": f"{EX}1",
        "parents": [f"{EX}1"],
        "consider": [f"{EX}1"],
    }
    assert three == {"id": f"{EX}3", "deprecated": "true"}
