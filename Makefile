# ORDO source pipeline (experiment).
#
#   make            download (if needed), extract, assemble, project SSSOM
#   make validate   validate the release against the schema, and the SSSOM file
#   make refresh    re-download the latest ORDO release, then build
#
# ROBOT does all RDF work. Python only reshapes ROBOT's query results.

# Stable URL for the current English ORDO. (The orphadata.org URL mondo-ingest
# uses is frozen at 4.7.) The exact version is recorded from the file's own
# owl:versionIRI in the release metadata.
ORDO_URL := https://www.orphadata.com/data/ontologies/ordo/last_version/ordo_orphanet.owl
MAPPING_SET_ID := https://w3id.org/monarch-initiative/mondo-ingest/sources/ordo/ordo.sssom.tsv

SCHEMA := schema/mondo_source.yaml
SCHEMA_VERSION := $(shell sed -n 's/^version: *//p' $(SCHEMA))
QUERIES := $(wildcard sparql/*.rq)
PYTHON_SRC := $(wildcard src/mondo_ingest_ordo/*.py)

TMP := tmp
RELEASE := release

GENERATED_BY = $(shell git remote get-url origin 2>/dev/null || echo $(CURDIR))@$(shell git rev-parse --short HEAD)$(shell git diff --quiet HEAD -- || echo -dirty)

.PHONY: all validate refresh clean
all: $(RELEASE)/ordo.yaml $(RELEASE)/ordo.metadata.yaml $(RELEASE)/ordo.sssom.tsv

$(TMP)/ordo.owl:
	mkdir -p $(TMP)
	curl -sSfL -o $@.part $(ORDO_URL)
	mv $@.part $@
	echo $(ORDO_URL) > $(TMP)/source-url.txt

refresh:
	rm -f $(TMP)/ordo.owl $(TMP)/source-url.txt
	$(MAKE) all

# Resolve the schema's sssom_schema: import to the installed sssom-schema package
# (pinned in pyproject.toml to the same version as the URL in the schema).
$(TMP)/importmap.json: pyproject.toml uv.lock
	mkdir -p $(TMP)
	uv run python -c 'import json, pathlib, sssom_schema; \
		print(json.dumps({"sssom_schema:": str(pathlib.Path(sssom_schema.__file__).parent / "schema") + "/"}))' > $@

# One ROBOT invocation loads ORDO once and runs every query.
$(TMP)/query/.done: $(TMP)/ordo.owl $(QUERIES)
	mkdir -p $(TMP)/query
	robot query -i $< --format csv \
		$(foreach q,$(QUERIES),--query $(q) $(TMP)/query/$(basename $(notdir $(q))).csv)
	touch $@

$(RELEASE)/ordo.yaml $(RELEASE)/ordo.metadata.yaml &: $(TMP)/query/.done $(TMP)/importmap.json $(SCHEMA) config/assembly.yaml config/prefixes.yaml $(PYTHON_SRC)
	mkdir -p $(RELEASE)
	uv run python -m mondo_ingest_ordo.assemble \
		--schema $(SCHEMA) \
		--prefixes config/prefixes.yaml \
		--config config/assembly.yaml \
		--importmap $(TMP)/importmap.json \
		--query-dir $(TMP)/query \
		--set source_id=ordo \
		--set source_download_url=$$(cat $(TMP)/source-url.txt) \
		--set schema_version=$(SCHEMA_VERSION) \
		--set generated_at=$$(date -u +%Y-%m-%dT%H:%M:%SZ) \
		--set generated_by=$(GENERATED_BY) \
		--output $(RELEASE)/ordo.yaml \
		--metadata-output $(RELEASE)/ordo.metadata.yaml

$(RELEASE)/ordo.sssom.tsv: $(RELEASE)/ordo.yaml config/prefixes.yaml $(PYTHON_SRC)
	uv run python -m mondo_ingest_ordo.sssom $< \
		--prefixes config/prefixes.yaml \
		--mapping-set-id $(MAPPING_SET_ID) \
		--output $@

# linkml-validate has no importmap option, so it fetches the SSSOM schema from the
# pinned URL in the schema's prefixes (network required).
validate: all
	uv run linkml-validate -s $(SCHEMA) -C SourceRelease $(RELEASE)/ordo.yaml
	uv run sssom validate $(RELEASE)/ordo.sssom.tsv

clean:
	rm -rf $(TMP)/query $(RELEASE)
