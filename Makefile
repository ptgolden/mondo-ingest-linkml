# ORDO source pipeline (experiment).
#
#   make            download (if needed), extract, assemble, project SSSOM
#   make validate   validate the release against the schema, and the SSSOM file
#   make refresh    re-download the latest ORDO release, then build
#
# ROBOT does all RDF work. Python only reshapes ROBOT's query results.

# ORDO has no stable "latest" URL: the old orphadata.org path is frozen at 4.7,
# the current filename embeds the version, and the last_version/ directory
# listing is 403. So we read the link off the ORDO landing page.
ORDO_PAGE := https://www.orphadata.com/ordo/
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
	url=$$(curl -sSfL $(ORDO_PAGE) | grep -o 'https://[^"]*/ORDO_en_[0-9.]*\.owl' | sort -uV | tail -1) && \
	test -n "$$url" && \
	curl -sSfL -o $@.part "$$url" && \
	mv $@.part $@ && \
	echo "$$url" > $(TMP)/source-url.txt

refresh:
	rm -f $(TMP)/ordo.owl $(TMP)/source-url.txt
	$(MAKE) all

# One ROBOT invocation loads ORDO once and runs every query.
$(TMP)/query/.done: $(TMP)/ordo.owl $(QUERIES)
	mkdir -p $(TMP)/query
	robot query -i $< --format csv \
		$(foreach q,$(QUERIES),--query $(q) $(TMP)/query/$(basename $(notdir $(q))).csv)
	touch $@

$(RELEASE)/ordo.yaml $(RELEASE)/ordo.metadata.yaml &: $(TMP)/query/.done $(SCHEMA) config/assembly.yaml config/prefixes.yaml $(PYTHON_SRC)
	mkdir -p $(RELEASE)
	uv run python -m mondo_ingest_ordo.assemble \
		--schema $(SCHEMA) \
		--prefixes config/prefixes.yaml \
		--config config/assembly.yaml \
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

validate: all
	uv run linkml-validate -s $(SCHEMA) -C SourceRelease $(RELEASE)/ordo.yaml
	uv run sssom validate $(RELEASE)/ordo.sssom.tsv

clean:
	rm -rf $(TMP)/query $(RELEASE)
