from mondo_source.finalize import Extract, finalize

PIPELINE = {
    "source_id": "example",
    "source_download_url": "https://example.org/example.owl",
    "schema_version": "0.0.0",
    "generated_at": "2026-01-01T00:00:00Z",
    "generated_by": "tests",
}


def extract(*terms: dict) -> Extract:
    return Extract.model_validate({"metadata": {"source_version": "1.0"}, "terms": list(terms)})


def test_release_has_the_sources_metadata_and_the_builds():
    release = finalize(extract({"id": "Orphanet:1", "label": "one"}), PIPELINE)

    assert release.metadata.source_version == "1.0"
    assert release.metadata.source_id == "example"
    assert [term.id for term in release.terms] == ["Orphanet:1"]
