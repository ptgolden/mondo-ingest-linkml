import json
from pathlib import Path

import pytest
import yaml
from typer.testing import CliRunner

from mondo_source.cli import app

PACKAGE = Path(__file__).parent.parent / "src" / "mondo_source"

PREFIXES = """
- {prefix: EX, uri_prefix: "https://example.org/term/"}
- {prefix: mondo_vocab, uri_prefix: "http://purl.obolibrary.org/obo/mondo#"}
"""

TURTLE = """
@prefix ex: <https://example.org/term/> .
@prefix owl: <http://www.w3.org/2002/07/owl#> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .

<https://example.org/onto> a owl:Ontology ; owl:versionInfo "1.0" .
ex:1 a owl:Class ; rdfs:label "one" .
ex:2 a owl:Class ; rdfs:label "two (2)" ; rdfs:subClassOf ex:1 .
"""

MARK_IN_SCOPE = """
INSERT { ?term <https://w3id.org/monarch-initiative/mondo-source/in_scope> true }
WHERE { ?term a <http://www.w3.org/2002/07/owl#Class> }
"""


@pytest.fixture
def release_options(tmp_path, schema_file, importmap_file) -> list[str]:
    """The options `assemble` and `finalize` share, writing into tmp_path."""
    (tmp_path / "prefixes.yaml").write_text(PREFIXES)
    return [
        *("--prefixes", str(tmp_path / "prefixes.yaml")),
        *("--schema", str(schema_file)),
        *("--importmap", str(importmap_file)),
        *("--output", str(tmp_path / "example.yaml")),
        *("--metadata-output", str(tmp_path / "example.metadata.yaml")),
        *("--set", "source_id=example"),
        *("--source-download-url", "https://example.org/onto.ttl"),
        *("--source-download-url", "https://example.org/versions.json"),
        *("--set", "generated_at=2026-01-01T00:00:00Z"),
        *("--set", "generated_by=tests"),
    ]


def run(*arguments: str):
    return CliRunner().invoke(app, list(arguments))


def test_finalize_writes_the_release_and_its_metadata(tmp_path, release_options):
    extract = tmp_path / "example.extract.json"
    extract.write_text(
        json.dumps({"metadata": {"source_version": "1.0"}, "terms": [{"id": "https://example.org/term/1", "label": "one"}]})
    )

    result = run("finalize", str(extract), *release_options)

    assert result.exit_code == 0, result.output
    release = yaml.safe_load((tmp_path / "example.yaml").read_text())
    assert release["terms"] == [
        {"id": "EX:1", "label": "one", "synonyms": [{"text": "one", "scope": "EXACT", "synonym_type": "mondo_vocab:GENERATED_FROM_LABEL"}]}
    ]
    assert yaml.safe_load((tmp_path / "example.metadata.yaml").read_text()) == release["metadata"]
    assert release["metadata"]["source_id"] == "example"
    assert release["metadata"]["source_download_urls"] == [
        "https://example.org/onto.ttl",
        "https://example.org/versions.json",
    ]


def test_finalize_prints_the_problems_and_writes_nothing(tmp_path, release_options):
    extract = tmp_path / "example.extract.json"
    extract.write_text(json.dumps({"metadata": {"source_version": "1.0"}, "terms": [{"id": "No:1"}, {"id": "EX:2"}]}))

    result = run("finalize", str(extract), *release_options)

    assert result.exit_code == 1
    assert "No:1  id     No:1       no prefix in the prefix map" in result.output
    assert "EX:2  label  (missing)  required unless the term is deprecated" in result.output
    assert not (tmp_path / "example.yaml").exists()


def test_assemble_builds_the_release_from_rdf_and_leaves_the_extract(tmp_path, release_options):
    (tmp_path / "source.ttl").write_text(TURTLE)
    (tmp_path / "sparql").mkdir()
    (tmp_path / "sparql" / "01-mark-in-scope.ru").write_text(MARK_IN_SCOPE)

    result = run(
        "assemble",
        *("--ontology", str(tmp_path / "source.ttl")),
        *("--sparql", str(PACKAGE / "sparql")),
        *("--sparql", str(tmp_path / "sparql")),
        *("--extract-output", str(tmp_path / "example.extract.json")),
        "--strip-brackets",
        *release_options,
    )

    assert result.exit_code == 0, result.output
    one, two = yaml.safe_load((tmp_path / "example.yaml").read_text())["terms"]
    assert (one["id"], two["id"], two["parents"]) == ("EX:1", "EX:2", ["EX:1"])
    assert [s["text"] for s in two["synonyms"]] == ["two", "two (2)"]
    stated = json.loads((tmp_path / "example.extract.json").read_text())
    assert sorted(term["id"] for term in stated["terms"]) == ["https://example.org/term/1", "https://example.org/term/2"]


def test_data_dir_is_where_the_shared_files_are():
    result = run("data-dir")

    assert (Path(result.output.strip()) / "source.mk").exists()
