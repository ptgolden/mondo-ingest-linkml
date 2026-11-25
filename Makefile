# For work on the package itself. The rules a source builds with are in
# src/mondo_source/source.mk.

SCHEMA := src/mondo_source/schema/mondo_source.yaml
MODELS := src/mondo_source/datamodel.py

.PHONY: models

# The Pydantic models are generated from the schema and committed. Run this after
# changing the schema or upgrading linkml; a test fails while the two disagree.
models:
	mkdir -p tmp
	uv run python -m mondo_source.importmap > tmp/importmap.json
	uv run gen-pydantic --importmap tmp/importmap.json $(SCHEMA) > $(MODELS).part
	mv $(MODELS).part $(MODELS)
