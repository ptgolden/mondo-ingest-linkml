# ORDO ingest for Mondo (experiment).
#
#   make            ordo.yaml (what Mondo takes in from ORDO) and what is rendered from
#                   it: ordo.sssom.tsv, ordo.owl, component signature, metrics
#   make bundle     everything mondo-ingest downloads for ORDO; adds the mirror,
#                   its signature and the semsql db, which need Docker
#   make validate   validate ordo.yaml against the schema and ordo.sssom.tsv as SSSOM
#   make refresh    re-download ORDO, then build
#
# ordo.yaml is built in-process: ORDO is loaded into Oxigraph and queried with the
# SPARQL in sparql/. ROBOT renders ordo.owl from it, and builds the mirror.

# Stable URL for the current English ORDO (the same one mondo-ingest uses). The
# exact version is recorded from the file's own owl:versionIRI.
ORDO_URL := https://www.orphadata.com/data/ontologies/ordo/last_version/ordo_orphanet.owl
COMPONENT_IRI := http://purl.obolibrary.org/obo/mondo/sources/ordo.owl

SCHEMA := schema/mondo_source.yaml
SCHEMA_VERSION := $(shell sed -n 's/^version: *//p' $(SCHEMA))
SPARQL := sparql
UPDATES = $(sort $(wildcard $(SPARQL)/*.ru))
QUERIES = $(wildcard $(SPARQL)/*.rq)
PYTHON_SRC := $(wildcard src/mondo_ingest_ordo/*.py)
COMPAT := mondo-ingest

TMP := tmp
RELEASE := release
TODAY := $(shell date +%Y-%m-%d)

GENERATED_BY = $(shell git remote get-url origin 2>/dev/null || echo $(CURDIR))@$(shell git rev-parse --short HEAD)$(shell git diff --quiet HEAD -- || echo -dirty)

# Named as mondo-ingest's targets expect (cf. ICD10WHO_DOWNLOADS in mondo-ingest.Makefile).
CORE := $(RELEASE)/ordo.yaml $(RELEASE)/ordo.metadata.yaml $(RELEASE)/ordo.sssom.tsv \
	$(RELEASE)/ordo.owl $(RELEASE)/component_signature-ordo.tsv $(RELEASE)/ordo-metrics.json
BUNDLE := $(CORE) $(RELEASE)/ordo.db $(RELEASE)/mirror-ordo.owl $(RELEASE)/mirror_signature-ordo.tsv

.PHONY: all bundle validate refresh clean
all: $(CORE)
bundle: $(BUNDLE)

$(TMP)/ordo.owl:
	mkdir -p $(TMP)
	curl -sSfL -o $@.part $(ORDO_URL)
	mv $@.part $@
	echo $(ORDO_URL) > $(TMP)/source-url.txt

refresh:
	rm -f $(TMP)/ordo.owl $(TMP)/source-url.txt
	$(MAKE) all

# ── ordo.yaml ─────────────────────────────────────────────────────────────────
# Resolve the schema's sssom_schema: import to the installed sssom-schema package
# (pinned in pyproject.toml to the same version as the URL in the schema).
$(TMP)/importmap.json: pyproject.toml uv.lock
	mkdir -p $(TMP)
	uv run python -c 'import json, pathlib, sssom_schema; \
		print(json.dumps({"sssom_schema:": str(pathlib.Path(sssom_schema.__file__).parent / "schema") + "/"}))' > $@

# Pydantic models generated from the schema; a build artifact, not committed.
$(TMP)/datamodel.py: $(SCHEMA) $(TMP)/importmap.json
	uv run gen-pydantic --importmap $(TMP)/importmap.json $(SCHEMA) > $@.part
	mv $@.part $@

$(RELEASE)/ordo.yaml $(RELEASE)/ordo.metadata.yaml &: $(TMP)/ordo.owl $(UPDATES) $(QUERIES) $(TMP)/datamodel.py config/prefixes.yaml $(PYTHON_SRC)
	mkdir -p $(RELEASE)
	uv run python -m mondo_ingest_ordo.assemble \
		--ontology $(TMP)/ordo.owl \
		--sparql $(SPARQL) \
		--models $(TMP)/datamodel.py \
		--prefixes config/prefixes.yaml \
		--set source_id=ordo \
		--set source_download_url=$$(cat $(TMP)/source-url.txt) \
		--set schema_version=$(SCHEMA_VERSION) \
		--set generated_at=$$(date -u +%Y-%m-%dT%H:%M:%SZ) \
		--set generated_by=$(GENERATED_BY) \
		--output $(RELEASE)/ordo.yaml \
		--metadata-output $(RELEASE)/ordo.metadata.yaml

# ── Renderings of ordo.yaml ────────────────────────────────────────────────────
$(RELEASE)/ordo.sssom.tsv: $(RELEASE)/ordo.yaml config/prefixes.yaml $(COMPAT)/ordo.metadata.sssom.yml $(PYTHON_SRC)
	uv run python -m mondo_ingest_ordo.sssom $< \
		--prefixes config/prefixes.yaml \
		--metadata $(COMPAT)/ordo.metadata.sssom.yml \
		--output $@

# ordo.owl: Python flattens ordo.yaml to ROBOT templates and ROBOT builds the OWL.
# Declarations go first so the other templates can resolve what they mention.
$(TMP)/templates/.done: $(RELEASE)/ordo.yaml $(TMP)/importmap.json $(SCHEMA) config/prefixes.yaml $(PYTHON_SRC)
	uv run python -m mondo_ingest_ordo.robot_templates $< \
		--schema $(SCHEMA) --importmap $(TMP)/importmap.json \
		--prefixes config/prefixes.yaml --out-dir $(TMP)/templates
	touch $@

$(RELEASE)/ordo.owl: $(TMP)/templates/.done
	robot template --add-prefixes $(TMP)/templates/prefixes.json \
		--template $(TMP)/templates/declarations.tsv \
		--output $(TMP)/templates/declarations.owl
	robot template --input $(TMP)/templates/declarations.owl --merge-before \
		--add-prefixes $(TMP)/templates/prefixes.json \
		$$(sed 's/^/--template /' $(TMP)/templates/templates.txt) \
		annotate --add-prefixes $(TMP)/templates/prefixes.json \
		--ontology-iri $(COMPONENT_IRI) \
		--version-iri http://purl.obolibrary.org/obo/mondo/sources/$(TODAY)/ordo.owl \
		$$(cat $(TMP)/templates/annotate-args.txt) \
		--output $@

$(RELEASE)/component_signature-ordo.tsv: $(RELEASE)/ordo.owl $(COMPAT)/classes.sparql
	robot query -i $< --query $(COMPAT)/classes.sparql $@
	(head -n 1 $@ && tail -n +2 $@ | sort) > $@-temp
	mv $@-temp $@

$(RELEASE)/ordo-metrics.json: $(RELEASE)/ordo.owl
	robot measure --prefix 'OMIM: http://omim.org/entry/' \
		--prefix 'CHR: http://purl.obolibrary.org/obo/CHR_' \
		--prefix 'UMLS: http://linkedlifedata.com/resource/umls/id/' \
		--prefix 'HGNC: https://www.genenames.org/data/gene-symbol-report/\#!/hgnc_id/' \
		--prefix 'biolink: https://w3id.org/biolink/vocab/' \
		-i $< --format json --metrics extended --output $@

# ── Files that need the ODK image ──────────────────────────────────────────────
# Paths are mounted at the same absolute location so TMP/RELEASE overrides work.
ODK_IMAGE := obolibrary/odkfull:v1.6
ODK = docker run --rm -u $$(id -u):$$(id -g) -e ROBOT_PLUGINS_DIRECTORY=/tools/robot-plugins \
	$(foreach d,$(sort $(CURDIR) $(abspath $(TMP)) $(abspath $(RELEASE))),-v $(d):$(d)) \
	-w $(CURDIR) $(ODK_IMAGE)

# mondo-ingest's mirror recipe, on the downloaded ORDO.
$(RELEASE)/mirror-ordo.owl: $(TMP)/ordo.owl
	$(ODK) robot merge -i $(abspath $<) odk:normalize --add-source true --output $(abspath $@)

$(RELEASE)/mirror_signature-ordo.tsv: $(RELEASE)/mirror-ordo.owl $(COMPAT)/classes.sparql
	robot query -i $< --query $(COMPAT)/classes.sparql $@
	(head -n 1 $@ && tail -n +2 $@ | sort) > $@-temp
	mv $@-temp $@

# mondo-ingest's %.db rule. semsql writes next to its input, so build in TMP.
$(RELEASE)/ordo.db: $(RELEASE)/ordo.owl $(COMPAT)/prefixes.csv
	mkdir -p $(TMP)/semsql
	cp $< $(TMP)/semsql/ordo.owl
	rm -f $(TMP)/semsql/ordo.db
	$(ODK) sh -c 'cd $(abspath $(TMP))/semsql && RUST_BACKTRACE=full semsql make ordo.db -P $(CURDIR)/$(COMPAT)/prefixes.csv'
	test -f $(TMP)/semsql/ordo.db
	mv $(TMP)/semsql/ordo.db $@

# ── Validation ────────────────────────────────────────────────────────────────
# linkml-validate has no importmap option, so it fetches the SSSOM schema from the
# pinned URL in the schema's prefixes (network required).
validate: $(RELEASE)/ordo.yaml $(RELEASE)/ordo.sssom.tsv
	uv run linkml-validate -s $(SCHEMA) -C SourceRelease $(RELEASE)/ordo.yaml
	uv run sssom validate $(RELEASE)/ordo.sssom.tsv

clean:
	rm -rf $(TMP)/query $(TMP)/templates $(TMP)/semsql $(RELEASE)
