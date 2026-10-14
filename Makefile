# ORDO source pipeline (experiment).
#
#   make            download (if needed), extract, assemble, project SSSOM, render OWL
#   make component  build the Mondo-facing bundle mondo-ingest downloads
#                   (component with Mondo policy applied, mirror, signatures,
#                   SSSOM, metrics, semsql db); needs Docker for the last two steps
#   make validate   validate the release against the schema, and the SSSOM file
#   make refresh    re-download the latest ORDO release, then build
#
# ROBOT does all RDF work. Python only reshapes ROBOT's query results.

# Stable URL for the current English ORDO (the same one mondo-ingest uses). The
# exact version is recorded from the file's own owl:versionIRI in the release metadata.
ORDO_URL := https://www.orphadata.com/data/ontologies/ordo/last_version/ordo_orphanet.owl
RENDERED_IRI := https://w3id.org/monarch-initiative/mondo-ingest/sources/ordo/ordo.linkml.owl
MAPPING_SET_ID := https://w3id.org/monarch-initiative/mondo-ingest/sources/ordo/ordo.source.sssom.tsv

SCHEMA := schema/mondo_source.yaml
SCHEMA_VERSION := $(shell sed -n 's/^version: *//p' $(SCHEMA))
QUERIES := $(wildcard sparql/*.rq)
PYTHON_SRC := $(wildcard src/mondo_ingest_ordo/*.py)

TMP := tmp
RELEASE := release

GENERATED_BY = $(shell git remote get-url origin 2>/dev/null || echo $(CURDIR))@$(shell git rev-parse --short HEAD)$(shell git diff --quiet HEAD -- || echo -dirty)

.PHONY: all component validate refresh clean
all: $(RELEASE)/ordo.yaml $(RELEASE)/ordo.metadata.yaml $(RELEASE)/ordo.source.sssom.tsv $(RELEASE)/ordo.linkml.owl

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

$(RELEASE)/ordo.source.sssom.tsv: $(RELEASE)/ordo.yaml config/prefixes.yaml $(PYTHON_SRC)
	uv run python -m mondo_ingest_ordo.sssom $< \
		--prefixes config/prefixes.yaml \
		--mapping-set-id $(MAPPING_SET_ID) \
		--output $@

# linkml-validate has no importmap option, so it fetches the SSSOM schema from the
# pinned URL in the schema's prefixes (network required).
# LinkML OWL rendering of the release: Python flattens it to ROBOT templates and
# ROBOT builds the OWL. Declarations go first so the other templates can resolve
# the classes and properties they mention.
$(TMP)/templates/.done: $(RELEASE)/ordo.yaml $(TMP)/importmap.json $(SCHEMA) config/prefixes.yaml $(PYTHON_SRC)
	uv run python -m mondo_ingest_ordo.robot_templates $< \
		--schema $(SCHEMA) --importmap $(TMP)/importmap.json \
		--prefixes config/prefixes.yaml --out-dir $(TMP)/templates
	touch $@

$(RELEASE)/ordo.linkml.owl: $(TMP)/templates/.done
	robot template --add-prefixes $(TMP)/templates/prefixes.json \
		--template $(TMP)/templates/declarations.tsv \
		--output $(TMP)/templates/declarations.owl
	robot template --input $(TMP)/templates/declarations.owl --merge-before \
		--add-prefixes $(TMP)/templates/prefixes.json \
		$$(sed 's/^/--template /' $(TMP)/templates/templates.txt) \
		annotate --add-prefixes $(TMP)/templates/prefixes.json \
		--ontology-iri $(RENDERED_IRI) $$(cat $(TMP)/templates/annotate-args.txt) \
		--output $@

# ── Mondo-facing component ─────────────────────────────────────────────────────
# Mondo's editorial policy for ORDO, applied to the LinkML OWL rendering. Mirrors
# mondo-ingest's $(COMPONENTSDIR)/ordo.owl recipe step for step; see
# component/README.md for what was copied, adapted, dropped and fixed.
COMPONENT_IRI := http://purl.obolibrary.org/obo/mondo/sources/ordo.owl
TODAY := $(shell date +%Y-%m-%d)
POLICY := component/sparql

# The files mondo-ingest downloads for ORDO, named as its targets expect
# (cf. ICD10WHO_DOWNLOADS in mondo-ingest.Makefile).
BUNDLE := $(RELEASE)/ordo.owl $(RELEASE)/ordo.db $(RELEASE)/mirror-ordo.owl \
	$(RELEASE)/mirror_signature-ordo.tsv $(RELEASE)/component_signature-ordo.tsv \
	$(RELEASE)/ordo.sssom.tsv $(RELEASE)/ordo-metrics.json

component: $(BUNDLE)

# Steps that need ODK's ROBOT plugins or semsql run in the ODK image. Paths are
# mounted at the same absolute location so TMP/RELEASE overrides keep working.
ODK_IMAGE := obolibrary/odkfull:v1.6
ODK = docker run --rm -u $$(id -u):$$(id -g) -e ROBOT_PLUGINS_DIRECTORY=/tools/robot-plugins \
	$(foreach d,$(sort $(CURDIR) $(abspath $(TMP)) $(abspath $(RELEASE))),-v $(d):$(d)) \
	-w $(CURDIR) $(ODK_IMAGE)

$(TMP)/ordo_relevant_signature.txt $(TMP)/ordo_annotated_signature.txt &: $(RELEASE)/ordo.linkml.owl $(POLICY)/ordo-construct-subclass-from-part-of.ru $(POLICY)/ordo-relevant-signature.sparql $(POLICY)/ordo-relevant-signature-ancestors.sparql
	robot query -i $< --update $(POLICY)/ordo-construct-subclass-from-part-of.ru \
		query --query $(POLICY)/ordo-relevant-signature.sparql $(TMP)/ordo_relevant_signature.txt \
		      --query $(POLICY)/ordo-relevant-signature-ancestors.sparql $(TMP)/ordo_signature_ancestors.txt
	cat $(TMP)/ordo_relevant_signature.txt $(TMP)/ordo_signature_ancestors.txt > $(TMP)/ordo_annotated_signature.txt

$(RELEASE)/ordo.owl: $(RELEASE)/ordo.linkml.owl $(TMP)/ordo_relevant_signature.txt $(TMP)/ordo_annotated_signature.txt component/property-map.sssom.tsv component/properties.txt $(wildcard $(POLICY)/*.ru)
	robot rename -i $< --mappings component/property-map.sssom.tsv \
			--allow-missing-entities true --allow-duplicates true \
		query \
			--update $(POLICY)/fix_deprecated.ru \
			--update $(POLICY)/fix-labels-with-brackets.ru \
			--update $(POLICY)/exact_syn_from_label.ru \
			--update $(POLICY)/ordo-construct-subclass-from-part-of.ru \
			--update $(POLICY)/ordo-construct-subsets.ru \
			--update $(POLICY)/ordo-construct-d2g.ru \
			--update $(POLICY)/mondo-ingest-mapping-iris.ru \
			--update $(POLICY)/drop-obsoletion-reasons.ru \
			--update $(POLICY)/drop-definition-citations.ru \
		remove --term oboInOwl:hasDbXref --axioms annotation \
		remove -T $(TMP)/ordo_annotated_signature.txt --select complement --select classes --axioms annotation --trim true \
		remove -T $(TMP)/ordo_relevant_signature.txt --select complement --select "classes individuals" --trim false \
		remove -T component/properties.txt --select complement --select properties --trim true \
		annotate --ontology-iri $(COMPONENT_IRI) --version-iri http://purl.obolibrary.org/obo/mondo/sources/$(TODAY)/ordo.owl \
		--output $@

# mondo-ingest's mirror recipe, on the downloaded ORDO.
$(RELEASE)/mirror-ordo.owl: $(TMP)/ordo.owl
	$(ODK) robot merge -i $(abspath $<) odk:normalize --add-source true --output $(abspath $@)

$(RELEASE)/mirror_signature-ordo.tsv: $(RELEASE)/mirror-ordo.owl component/sparql/classes.sparql
	robot query -i $< --query component/sparql/classes.sparql $@
	(head -n 1 $@ && tail -n +2 $@ | sort) > $@-temp
	mv $@-temp $@

$(RELEASE)/component_signature-ordo.tsv: $(RELEASE)/ordo.owl component/sparql/classes.sparql
	robot query -i $< --query component/sparql/classes.sparql $@
	(head -n 1 $@ && tail -n +2 $@ | sort) > $@-temp
	mv $@-temp $@

$(RELEASE)/ordo-metrics.json: $(RELEASE)/ordo.owl
	robot measure --prefix 'OMIM: http://omim.org/entry/' \
		--prefix 'CHR: http://purl.obolibrary.org/obo/CHR_' \
		--prefix 'UMLS: http://linkedlifedata.com/resource/umls/id/' \
		--prefix 'HGNC: https://www.genenames.org/data/gene-symbol-report/\#!/hgnc_id/' \
		--prefix 'biolink: https://w3id.org/biolink/vocab/' \
		-i $< --format json --metrics extended --output $@

# mondo-ingest's %.db rule. semsql writes next to its input, so build in TMP.
$(RELEASE)/ordo.db: $(RELEASE)/ordo.owl component/prefixes.csv
	mkdir -p $(TMP)/semsql
	cp $< $(TMP)/semsql/ordo.owl
	rm -f $(TMP)/semsql/ordo.db
	cd $(TMP)/semsql && $(ODK) sh -c 'cd $(abspath $(TMP))/semsql && RUST_BACKTRACE=full semsql make ordo.db -P $(CURDIR)/component/prefixes.csv'
	test -f $(TMP)/semsql/ordo.db
	mv $(TMP)/semsql/ordo.db $@

$(TMP)/component-mappings.csv: $(RELEASE)/ordo.owl component/sparql/component-mappings.sparql
	robot query -i $< --format csv --query component/sparql/component-mappings.sparql $@

$(RELEASE)/ordo.sssom.tsv: $(TMP)/component-mappings.csv component/ordo.metadata.sssom.yml component/sssom-extra-prefixes.yaml $(PYTHON_SRC)
	uv run python -m mondo_ingest_ordo.component_sssom $< \
		--metadata component/ordo.metadata.sssom.yml \
		--extra-prefixes component/sssom-extra-prefixes.yaml \
		--set mapping_set_version=$$(sed -n "s/^source_version: *'\{0,1\}\([^']*\)'\{0,1\}$$/\1/p" $(RELEASE)/ordo.metadata.yaml) \
		--output $@

validate: all
	uv run linkml-validate -s $(SCHEMA) -C SourceRelease $(RELEASE)/ordo.yaml
	uv run sssom validate $(RELEASE)/ordo.source.sssom.tsv

clean:
	rm -rf $(TMP)/query $(RELEASE)
