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
| `ordo.yaml` | The release: `metadata` and `terms` (each term carrying its SSSOM `mappings`), per `schema/mondo_source.yaml` |
| `ordo.metadata.yaml` | Just the `metadata` block (source version, schema version, generated_at, ...) |
| `ordo.sssom.tsv` | The terms' mappings, flattened. Never edited directly. |

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
   (`predicate_id`), a mapping justification, and definition `citations`.
4. **Mappings are SSSOM, inline on their term.** The schema imports the `sssom-schema`
   package, and `Term.mappings` is a `TermMapping`: every slot of SSSOM's `mapping` class
   except `subject_id` and `subject_label`. The subject is the term the mapping sits under.
   It reuses SSSOM's slots rather than subclassing `mapping` because that class requires
   `subject_id` through a rule, and a subclass inherits the rule. A curator reading a term
   sees its mappings next to its obsoletion status. The SSSOM file is a flattening that adds
   the subject back, and `sssom validate` checks it as complete SSSOM.

   The SSSOM schema has no PURL for its YAML, so the import goes through a `sssom_schema:`
   prefix pinned to the v1.0.0 GitHub URL. The build redirects that prefix to the installed
   package (same version, pinned in `pyproject.toml`) with a LinkML importmap.
   `linkml-validate` has no importmap option and fetches the URL.

## Findings

### About ORDO and the current pipeline

- **The old orphadata.org URL is frozen at 4.7.** `http://www.orphadata.org/data/ORDO/ordo_orphanet.owl`
  still serves 4.7 (June 2025). The current release is 4.9 (June 2026), at
  `https://www.orphadata.com/data/ontologies/ordo/last_version/ordo_orphanet.owl`, which serves
  the same file as the versioned `ORDO_en_4.9.owl`. mondo-ingest's main branch already uses
  the orphadata.com URL (an earlier version of this note said otherwise, based on an outdated
  local clone). Its latest release, v2026-01-24, was built from 4.7.
- **4.9 changed shape compared with 4.7.** 4.9 adds `owl:deprecated` (4.7 marked obsoletion
  only through its typology classes) and a new `Orphanet_C059` website-link property.
  `fix_complex_reification_ordo.ru` in mondo-ingest targets a nested-annotation layout that
  4.7 already didn't use. Source format drift breaks SPARQL silently.
- **ORDO's mapping qualifier packs two dimensions into one string:** precision
  (E/NTBT/BTNT/ND) and, for ICD, a code-relation type (Specific code / Attributed code /
  Index term / Inclusion term). The precision becomes `predicate_id`. SSSOM has no slot for
  the code relation, so it goes into the mapping's `comment`. mondo-ingest currently keeps
  neither: its `ordo.sssom.tsv` marks every row `semapv:UnspecifiedMatching` and has no
  comment.
- **Data quality issues the pipeline exposed:**
  - Ten ICD-11 xrefs contain non-breaking spaces.
  - 12 classes have both `"X"` and `"X"@en` labels.
  - ORDO's `ClinVar:` and `Genatlas:` xrefs are gene symbols, and its `Reactome:` xrefs are
    UniProt accessions; none are valid IDs in those namespaces.
  - ORDO's ICD-11 xrefs are MMS codes, not Foundation IDs, and there's no agreed Mondo
    prefix for them.
- **mondo-ingest-side check (#900-style).** Mondo's `mondo_exactmatch_orphanet.sssom.tsv` (local
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
    sidecar, generated in the same step, is an option if mondo-ingest's load time ever matters.
- **The schema validators miss CURIE syntax.** `uriorcurie` becomes an unconstrained
  string in JSON Schema, so the NBSP xrefs passed both `linkml-validate` and JSON Schema.
  Only `sssom validate` caught them, and it reported 7 of the 10. The assembler now checks
  CURIE syntax itself.
- **Timestamps.** ORDO publishes `dcterms:modified` without a timezone, which isn't a valid
  RFC 3339 date-time, so `source_date` is kept as a verbatim string.

## Open questions

- **Where does Mondo editorial policy live?** Examples are part_of-as-is_a, ORDO synonyms
  as EXACT, and generated synonyms. Requirement 5 says no source processing in mondo-ingest, but
  these aren't facts about ORDO. If they move to the source repo, the release stops being a
  faithful record of the source.
- **Gene classes.** They are included as terms, with gene-disease relations on the gene, as
  ORDO asserts them. Should mondo-ingest get them in that form?
- **Which classes are in scope?** The release contains every ORDO class: clinical entities,
  inactive entities, genes and typology classes. Today mondo-ingest's
  `ordo-relevant-signature.sparql` decides which are diseases.
- **The non-OWL path.** It isn't exercised here. OMIM would be the next test.
- **The LinkML OWL rendering** that #925 requires is not produced here.
- **`mapping_set_id`** is a placeholder; the PURL scheme isn't decided yet.
