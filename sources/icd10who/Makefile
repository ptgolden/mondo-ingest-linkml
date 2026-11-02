# ICD-10 (WHO) for Mondo. See mondo-source's source.mk for the targets.

SOURCE := icd10who
# WHO publishes ICD-10 only through its API. mondo-ingest-icd10who walks the API and
# publishes the result as Turtle (icd10who.raw.ttl); that is the source here, not the
# icd10who.owl it renders. Pinned to a release: the Turtle states only the ICD-10
# edition (2019), not which API walk it came from.
SOURCE_URL := https://github.com/monarch-initiative/mondo-ingest-icd10who/releases/download/v2026-10-12/icd10who.raw.ttl
SOURCE_FILE := tmp/icd10who.ttl
SSSOM_METADATA := icd10who.metadata.sssom.yml

MONDO_SOURCE := $(shell uv run mondo-source data-dir)
include $(MONDO_SOURCE)/source.mk
