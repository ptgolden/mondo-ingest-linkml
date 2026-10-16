# ORDO (Orphanet Rare Disease Ontology) for Mondo. See mondo-source's source.mk for
# the targets.

SOURCE := ordo
# Stable URL for the current English ORDO (the same one mondo-ingest uses). The
# exact version is recorded from the file's own owl:versionIRI.
SOURCE_URL := https://www.orphadata.com/data/ontologies/ordo/last_version/ordo_orphanet.owl
SOURCE_FILE := tmp/ordo.owl
# mondo-ingest's own src/ontology/metadata/ordo.metadata.sssom.yml.
SSSOM_METADATA := ordo.metadata.sssom.yml

MONDO_SOURCE := $(shell uv run mondo-source data-dir)
include $(MONDO_SOURCE)/source.mk
