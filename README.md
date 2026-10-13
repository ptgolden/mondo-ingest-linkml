# mondo-ingest-ordo (experiment)

An initial experiment for [mondo-ingest#925](https://github.com/monarch-initiative/mondo-ingest/issues/925)
("make the alignment system LinkML-first"), using Orphanet's ORDO as the test case.

The question: what does a source repo look like if it publishes LinkML data plus a
derived SSSOM file, while keeping well-defined semantics (OWL parsed by ROBOT,
transformations in SPARQL) and as little bespoke Python as possible?

This is not production code. Things here that would live in mondo-ingest in the target
architecture (the schema, the prefix map, the generic assembler) are kept here only so the
experiment is self-contained.

## Running it

Needs `uv`, `robot` (tested with 1.9.7), `curl`, and GNU Make 4.3+.

```sh
make            # download ORDO if needed, extract, assemble, project SSSOM
make validate   # linkml-validate the release; sssom validate the SSSOM file
make refresh    # re-download the newest ORDO, then build
```

Outputs, in `release/`:

| File | What it is |
|---|---|
| `ordo.yaml` | The release: `metadata`, `terms`, `mappings`, per `schema/mondo_source.yaml` |
| `ordo.metadata.yaml` | Just the `metadata` block (source version, schema version, generated_at, ...) |
| `ordo.sssom.tsv` | Derived from `ordo.yaml`'s mappings. Never edited directly. |

## How it works

```
ORDO OWL --robot query (9 SPARQL SELECTs, one load)--> CSVs
CSVs --assemble (generic, schema-driven)--> ordo.yaml
ordo.yaml --sssom (generic projection)--> ordo.sssom.tsv
```

- **ROBOT does all the RDF work.** Every source-specific decision lives in `sparql/*.rq`:
  which classes count as terms, IRI-to-CURIE conversion, ORDO precision code to SKOS
  predicate, prefix normalisation. Each query's result columns are named after schema slots.
- **Python only reshapes tables.** `assemble.py` uses the schema (via SchemaView) to decide
  what is multivalued, inlined, boolean or a CURIE. It knows nothing about ORDO or RDF,
  so the same code should work for any source whose queries follow the convention.
  `sssom.py` is a projection of the release. Together they are about 230 non-comment lines.
- **Fail hard.** Assembly stops on two values for a single-valued slot, a row for a term
  that doesn't exist, a malformed CURIE, or a prefix missing from `config/prefixes.yaml`.

## Design rules in the schema

1. **Record what the source says.** Translate into standard vocabulary only where the source
   itself defines the meaning. ORDO defines `E`/`NTBT`/`BTNT`, so those become
   `skos:exactMatch`/`broadMatch`/`narrowMatch`. ORDO defines "Moved to" as redirection to a
   replacement, so it becomes `replaced_by`.
2. **Apply no Mondo editorial policy.** mondo-ingest's current ORDO pipeline also rewrites
   `part_of` as `is_a`, treats unscoped synonyms as EXACT, generates synonyms from labels,
   and invents `mondo#ordo_*` subsets. None of that is done here. `part_of` stays a
   relationship, synonyms have no scope, labels are verbatim (including "OBSOLETE: ").
3. **No overloaded fields.** OBO's `xref` and `source` are split into a mapping predicate
   (`predicate_id`), a mapping justification, definition `citations`, and the source's own
   qualifier kept verbatim (`source_mapping_qualifier`).
4. **Mappings use SSSOM slot names,** so the SSSOM file is a projection and not a second
   source of truth.

## Findings

### About ORDO and the current pipeline

- **mondo-ingest is ingesting a stale ORDO.** Its `ORDO=` URL
  (`http://www.orphadata.org/data/ORDO/ordo_orphanet.owl`) still serves **4.7 (June 2025)**.
  The current release is **4.9 (June 2026)**, on orphadata.com.
- **ORDO has no stable "latest" URL.** The filename embeds the version and the
  `last_version/` directory listing returns 403, so the Makefile reads the link off the
  ORDO landing page. That's fragile; worth asking Orphanet for a stable URL.
- **4.9 changed shape compared with 4.7.** 4.9 adds `owl:deprecated` (4.7 marked obsoletion
  only through its typology classes) and a new `Orphanet_C059` website-link property.
  `fix_complex_reification_ordo.ru` in mondo-ingest targets a nested-annotation layout that
  4.7 already didn't use. Source format drift breaks SPARQL silently.
- **ORDO's mapping qualifier packs two dimensions into one string:** precision
  (E/NTBT/BTNT/ND) and, for ICD, a code-relation type (Specific code / Attributed code /
  Index term / Inclusion term). SSSOM has no slot for the second, so it is kept verbatim and
  declared as an SSSOM extension slot.
- **Data quality issues the pipeline exposed:**
  - Ten ICD-11 xrefs contain non-breaking spaces.
  - 12 classes have both `"X"` and `"X"@en` labels.
  - ORDO's `ClinVar:` and `Genatlas:` xrefs are gene symbols, and its `Reactome:` xrefs are
    UniProt accessions; none are valid IDs in those namespaces.
  - ORDO's ICD-11 xrefs are MMS codes, not Foundation IDs, and there's no agreed Mondo
    prefix for them.
- **Hub-side check (#900-style).** Mondo's `mondo_exactmatch_orphanet.sssom.tsv` (local
  clone, 2026-08-04) has 9,785 rows. Against ORDO 4.9:
  - 9,511 point at active terms;
  - 216 at deprecated terms with `consider` targets;
  - 31 at deprecated terms with a `replaced_by` target;
  - 9 at deprecated terms with no pointer;
  - 18 at IDs that are not ORDO classes.

  This took about 12 lines over the release, with no ROBOT run.

### About the approach

- **ROBOT plus SPARQL is fast enough here.** Loading ORDO once and running all nine queries
  takes about 16 s. The full `make all` from a cold download is about 49 s.
- **YAML is the bottleneck, and a correctness hazard.**
  - Parsing the 25 MB `ordo.yaml` takes 10.8 s with PyYAML's C loader, 58.8 s with ruamel
    (YAML 1.2), and 0.23 s for the same content as JSON.
  - Validating the release takes about 51 s with `linkml-validate` and about 70 s with
    `check-jsonschema`. The JSON Schema check itself takes 6.3 s once the data is in memory;
    the rest is YAML parsing.
  - The gene alias `2E4` is a string under YAML 1.1 (PyYAML) but the float `20000.0` under
    YAML 1.2. The assembler now quotes such strings.
  - YAML stays the published format because curators need to read these files. The costs
    above are manageable: parsing with the C loader and validating with JSON Schema in memory
    takes about 17 s, against 51–70 s for the off-the-shelf validators. A machine-only JSON
    sidecar, generated in the same step, is an option if hub load time ever matters.
- **The schema validators miss CURIE syntax.** `uriorcurie` becomes an unconstrained
  string in JSON Schema, so the NBSP xrefs passed both `linkml-validate` and JSON Schema.
  Only `sssom validate` caught them, and it reported 7 of the 10. The assembler now checks
  CURIE syntax itself.
- **Timestamps.** ORDO publishes `dcterms:modified` without a timezone, which isn't a valid
  RFC 3339 date-time, so `source_date` is kept as a verbatim string.

## Open questions

- **Where does Mondo editorial policy live?** Examples are part_of-as-is_a, ORDO synonyms
  as EXACT, and generated synonyms. Requirement 5 says no source processing in the hub, but
  these aren't facts about ORDO. If they move to the source repo, the release stops being a
  faithful record of the source.
- **Gene classes.** They are included as terms, with gene-disease relations on the gene, as
  ORDO asserts them. Should the hub get them in that form?
- **Which classes are in scope?** The release contains every ORDO class: clinical entities,
  inactive entities, genes and typology classes. Today mondo-ingest's
  `ordo-relevant-signature.sparql` decides which are diseases.
- **The non-OWL path.** It isn't exercised here. OMIM would be the next test.
- **The LinkML OWL rendering** that #925 requires is not produced here.
- **`mapping_set_id`** is a placeholder; the PURL scheme isn't decided yet.
