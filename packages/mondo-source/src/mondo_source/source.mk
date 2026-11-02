# Build rules shared by every source, included by the source's own Makefile:
#
#   make            <source>.yaml (what Mondo takes in from the source) and what is
#                   rendered from it: <source>.sssom.tsv, <source>.owl, component
#                   signature. Needs only uv.
#   make bundle     everything mondo-ingest downloads for the source; adds the mirror,
#                   its signature, and the semsql db and metrics, which need Docker
#   make validate   validate <source>.yaml against the schema and <source>.sssom.tsv as SSSOM
#   make refresh    re-download the source, then build
#
# The source's Makefile sets, before including this file:
#
#   SOURCE          short id, e.g. ordo; names every output
#   SOURCE_URL      where to download the source (RDF/XML or Turtle)
#   SOURCE_FILE     where to keep the download; its extension gives its RDF format
#   SSSOM_METADATA  mapping set metadata for <source>.sssom.tsv
#   MONDO_SOURCE    this package's data directory (`mondo-source data-dir`)
#
# <source>.yaml is built in-process: the source is loaded into Oxigraph and queried with
# the SPARQL in mondo-source's sparql/ and the source's own sparql/, whose files
# replace ones of the same name. linkml-owl renders <source>.owl from it. Oxigraph's
# store is on disk, so even NCIT fits in a couple of GB. ROBOT is used only inside the
# ODK image, for the metrics.

COMPONENT_IRI := http://purl.obolibrary.org/obo/mondo/sources/$(SOURCE).owl

SCHEMA := $(MONDO_SOURCE)/schema/mondo_source.yaml
SCHEMA_VERSION := $(shell sed -n 's/^version: *//p' $(SCHEMA))
PREFIXES := $(MONDO_SOURCE)/prefixes.yaml
SPARQL := $(MONDO_SOURCE)/sparql sparql
SPARQL_FILES = $(wildcard $(addsuffix /*.ru,$(SPARQL)) $(addsuffix /*.rq,$(SPARQL)))
MODELS := $(MONDO_SOURCE)/datamodel.py
PYTHON_SRC := $(filter-out $(MODELS),$(wildcard $(MONDO_SOURCE)/*.py))
COMPAT := $(MONDO_SOURCE)/mondo-ingest

TMP := tmp
RELEASE := release
TODAY := $(shell date +%Y-%m-%d)

GENERATED_BY = $(shell git remote get-url origin 2>/dev/null || echo $(CURDIR))@$(shell git rev-parse --short HEAD)$(shell git diff --quiet HEAD -- || echo -dirty)

# Named as mondo-ingest's targets expect (cf. ICD10WHO_DOWNLOADS in mondo-ingest.Makefile).
CORE := $(RELEASE)/$(SOURCE).yaml $(RELEASE)/$(SOURCE).metadata.yaml $(RELEASE)/$(SOURCE).sssom.tsv \
	$(RELEASE)/$(SOURCE).owl $(RELEASE)/component_signature-$(SOURCE).tsv
BUNDLE := $(CORE) $(RELEASE)/mirror-$(SOURCE).owl $(RELEASE)/mirror_signature-$(SOURCE).tsv \
	$(RELEASE)/$(SOURCE).db $(RELEASE)/$(SOURCE)-metrics.json

.PHONY: all bundle validate refresh clean
all: $(CORE)
bundle: $(BUNDLE)

$(SOURCE_FILE):
	mkdir -p $(dir $@) $(TMP)
	curl -sSfL -o $@.part $(SOURCE_URL)
	mv $@.part $@
	echo $(SOURCE_URL) > $(TMP)/source-url.txt

refresh:
	rm -f $(SOURCE_FILE) $(TMP)/source-url.txt
	$(MAKE) all

# ── <source>.yaml ─────────────────────────────────────────────────────────────
# Resolve the schema's sssom_schema: import to the installed sssom-schema package
# (pinned in mondo-source's pyproject.toml to the same version as the URL in the schema).
$(TMP)/importmap.json:
	mkdir -p $(TMP)
	uv run python -c 'import json, pathlib, sssom_schema; \
		print(json.dumps({"sssom_schema:": str(pathlib.Path(sssom_schema.__file__).parent / "schema") + "/"}))' > $@

# Pydantic models generated from the schema, into the package; not committed.
$(MODELS): $(SCHEMA) $(TMP)/importmap.json
	uv run gen-pydantic --importmap $(TMP)/importmap.json $(SCHEMA) > $@.part
	mv $@.part $@

$(RELEASE)/$(SOURCE).yaml $(RELEASE)/$(SOURCE).metadata.yaml &: $(SOURCE_FILE) $(SPARQL_FILES) $(MODELS) $(PREFIXES) $(PYTHON_SRC)
	mkdir -p $(RELEASE)
	uv run mondo-source assemble \
		--ontology $(SOURCE_FILE) \
		$(addprefix --sparql ,$(SPARQL)) \
		--prefixes $(PREFIXES) \
		--set source_id=$(SOURCE) \
		--set source_download_url=$$(cat $(TMP)/source-url.txt) \
		--set schema_version=$(SCHEMA_VERSION) \
		--set generated_at=$$(date -u +%Y-%m-%dT%H:%M:%SZ) \
		--set generated_by=$(GENERATED_BY) \
		--output $(RELEASE)/$(SOURCE).yaml \
		--metadata-output $(RELEASE)/$(SOURCE).metadata.yaml

# ── Renderings of <source>.yaml ───────────────────────────────────────────────
$(RELEASE)/$(SOURCE).sssom.tsv: $(RELEASE)/$(SOURCE).yaml $(PREFIXES) $(SSSOM_METADATA) $(PYTHON_SRC)
	uv run mondo-source sssom $< \
		--prefixes $(PREFIXES) \
		--metadata $(SSSOM_METADATA) \
		--output $@

# <source>.owl: linkml-owl renders <source>.yaml from the schema's `owl` annotations,
# with an ontology header from the release metadata.
$(RELEASE)/$(SOURCE).owl: $(RELEASE)/$(SOURCE).yaml $(RELEASE)/$(SOURCE).metadata.yaml $(TMP)/importmap.json $(SCHEMA) $(PREFIXES) $(PYTHON_SRC)
	uv run mondo-source render-owl $< \
		--schema $(SCHEMA) --importmap $(TMP)/importmap.json --prefixes $(PREFIXES) \
		--metadata $(RELEASE)/$(SOURCE).metadata.yaml \
		--ontology-iri $(COMPONENT_IRI) \
		--version-iri http://purl.obolibrary.org/obo/mondo/sources/$(TODAY)/$(SOURCE).owl \
		--output $@

# mondo-ingest's signature reports: classes.sparql, rows sorted by code point (so the
# order no longer depends on the machine's locale, as with `sort`).
$(RELEASE)/component_signature-$(SOURCE).tsv: $(RELEASE)/$(SOURCE).owl $(COMPAT)/classes.sparql
	uv run mondo-source select $< --query $(COMPAT)/classes.sparql --output $@

# The mirror is the source as downloaded, as RDF/XML. mondo-ingest made it with
# `robot merge` + `odk:normalize --add-source true`, which loads the whole source into
# the OWL API (more memory than NCIT allows on a laptop) to add one ontology annotation
# nothing in mondo-ingest reads; its readers use owl:versionIRI/versionInfo, which the
# download has.
$(RELEASE)/mirror-$(SOURCE).owl: $(SOURCE_FILE)
	mkdir -p $(RELEASE)
ifeq ($(suffix $(SOURCE_FILE)),.owl)
	cp $< $@
else
	uv run mondo-source rdfxml $< --output $@
endif

$(RELEASE)/mirror_signature-$(SOURCE).tsv: $(RELEASE)/mirror-$(SOURCE).owl $(COMPAT)/classes.sparql
	uv run mondo-source select $< --query $(COMPAT)/classes.sparql --output $@

# ── Files that need the ODK image ──────────────────────────────────────────────
# Paths are mounted at the same absolute location so TMP/RELEASE overrides work.
ODK_IMAGE := obolibrary/odkfull:v1.6
ODK = docker run --rm -u $$(id -u):$$(id -g) -e ROBOT_PLUGINS_DIRECTORY=/tools/robot-plugins \
	$(foreach d,$(sort $(CURDIR) $(abspath $(TMP)) $(abspath $(RELEASE)) $(MONDO_SOURCE)),-v $(d):$(d)) \
	-w $(CURDIR) $(ODK_IMAGE)

# mondo-ingest's metrics rule, on the component. ROBOT's "extended" metrics
# (expressivity, OWL 2 profiles) need the OWL API, so this stays ROBOT, in the image.
$(RELEASE)/$(SOURCE)-metrics.json: $(RELEASE)/$(SOURCE).owl
	$(ODK) robot measure --prefix 'OMIM: http://omim.org/entry/' \
		--prefix 'CHR: http://purl.obolibrary.org/obo/CHR_' \
		--prefix 'UMLS: http://linkedlifedata.com/resource/umls/id/' \
		--prefix 'HGNC: https://www.genenames.org/data/gene-symbol-report/\#!/hgnc_id/' \
		--prefix 'biolink: https://w3id.org/biolink/vocab/' \
		-i $(abspath $<) --format json --metrics extended --output $(abspath $@)

# mondo-ingest's %.db rule. semsql writes next to its input, so build in TMP.
$(RELEASE)/$(SOURCE).db: $(RELEASE)/$(SOURCE).owl $(COMPAT)/prefixes.csv
	mkdir -p $(TMP)/semsql
	cp $< $(TMP)/semsql/$(SOURCE).owl
	rm -f $(TMP)/semsql/$(SOURCE).db
	$(ODK) sh -c 'cd $(abspath $(TMP))/semsql && RUST_BACKTRACE=full semsql make $(SOURCE).db -P $(COMPAT)/prefixes.csv'
	test -f $(TMP)/semsql/$(SOURCE).db
	mv $(TMP)/semsql/$(SOURCE).db $@

# ── Validation ────────────────────────────────────────────────────────────────
# linkml-validate has no importmap option, so it fetches the SSSOM schema from the
# pinned URL in the schema's prefixes (network required).
validate: $(RELEASE)/$(SOURCE).yaml $(RELEASE)/$(SOURCE).sssom.tsv
	uv run linkml-validate -s $(SCHEMA) -C SourceRelease $(RELEASE)/$(SOURCE).yaml
	uv run sssom validate $(RELEASE)/$(SOURCE).sssom.tsv

clean:
	rm -rf $(TMP)/semsql $(RELEASE) $(MODELS)
