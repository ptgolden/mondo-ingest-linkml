# mondo-ingest-ordo (experiment)

An initial experiment for [mondo-ingest#925](https://github.com/monarch-initiative/mondo-ingest/issues/925)
("make the alignment system LinkML-first"), using Orphanet's ORDO as the test case.

The question: what does a source repo look like if its one reviewable artifact is a LinkML
YAML of **what Mondo takes in from the source**, with everything mondo-ingest needs rendered
from that YAML, so mondo-ingest only downloads files (as mondo-ingest#906 does for
ICD10WHO)? And can it keep well-defined semantics (OWL parsed by ROBOT, transformations in
SPARQL) with as little bespoke Python as possible?

An earlier design, which published a faithful YAML of the *whole* source and applied Mondo's
policy afterwards in OWL, is preserved at tag `original-yaml-approach`; its message explains
why it was replaced.

This is not production code. Things here that would live in mondo-ingest in the target
architecture (the schema, the prefix map, the generic Python) are kept here only so the
experiment is self-contained.

## Running it

Needs `uv`, `robot` (tested with 1.9.7), `curl` and GNU Make 4.3+. `make bundle` also needs
Docker, for the `obolibrary/odkfull:v1.6` image (ODK's ROBOT plugins and semsql).

```sh
make            # download ORDO if needed; build ordo.yaml and its renderings
make bundle     # also the files that need the ODK image (mirror, semsql db)
make validate   # linkml-validate ordo.yaml; sssom validate ordo.sssom.tsv
make refresh    # re-download ORDO, then build
```

Outputs, in `release/`:

| File | What it is | Role |
|---|---|---|
| `ordo.yaml` | ORDO's in-scope terms as Mondo reads them, each carrying its SSSOM `mappings`, per `schema/mondo_source.yaml` | **The target**: reviewed by diffing releases |
| `ordo.metadata.yaml` | The `metadata` block: source version, schema version, generated_at, … | **Target**: the freshness contract |
| `ordo.sssom.tsv` | The terms' mappings, flattened, with mondo-ingest's header | Rendering of `ordo.yaml` |
| `ordo.owl` | `ordo.yaml` as OWL, built by ROBOT from templates | Rendering, transitional until mondo-ingest reads YAML |
| `component_signature-ordo.tsv`, `ordo-metrics.json` | As mondo-ingest builds them | Renderings |
| `ordo.db`, `mirror-ordo.owl`, `mirror_signature-ordo.tsv` | From `make bundle`; the mirror is ORDO itself, ODK-normalised | For mondo-ingest's existing checks |

The file names are the ones mondo-ingest's targets expect (cf. `ICD10WHO_DOWNLOADS`).

## How it works

```
ORDO OWL --robot query: 2 updates, then 11 SELECTs (one load)--> SPARQL XML results
SPARQL XML results --assemble.py (generic, schema-driven)--> ordo.yaml
ordo.yaml --sssom.py--> ordo.sssom.tsv
ordo.yaml --robot_templates.py (flatten to TSV)--> robot template --> ordo.owl
```

- **Mondo's reading of ORDO happens at extraction, in SPARQL run by ROBOT.** Before the
  SELECTs, two updates run:
  - `00-part-of-as-parents.ru` is mondo-ingest's own query, verbatim: Mondo reads ORDO's
    `part_of` as hierarchy;
  - `01-mark-in-scope.ru` marks the classes Mondo takes in.

  Each SELECT then extracts one part of the schema from the marked classes, and is named
  after the slot it fills (`synonyms.rq` fills `Term.synonyms`). Queries return IRIs as
  IRIs; turning them into CURIEs is the assembler's job. Each query documents which
  mondo-ingest step it reproduces: `exact_syn_from_label.ru`,
  `fix-labels-with-brackets.ru`, `ordo-construct-d2g.ru`, `ordo-construct-subsets.ru`,
  `fix_deprecated.ru`, the property map and the relevant-signature query.
- **Created data says so.** Synonyms copied from labels are typed
  `mondo:GENERATED_FROM_LABEL`, and bracket-stripped ones `mondo:GENERATED`, so the YAML
  shows what Mondo added rather than ORDO said.
- **Python only reshapes.**
  - `assemble.py` reads ROBOT's SPARQL XML results, which keep IRIs, literals and
    datatypes apart; ROBOT has no SPARQL JSON output. It uses the schema (via SchemaView)
    to decide what is multivalued, a nested object or a CURIE, and `curies` to compress
    IRIs and check CURIEs. Mapping sort order comes from a `sort_by` annotation in the
    schema. It knows nothing about ORDO.
  - `sssom.py` flattens the mappings.
  - `robot_templates.py` flattens `ordo.yaml` into ROBOT template TSVs, taking OWL
    properties from the schema's slot URIs.
  - `yamlio.py` writes YAML that reads back the same under YAML 1.1 and 1.2.

  None of them is ORDO-specific, and all three CLIs use Typer.
- **Fail hard.** Assembly stops on two values for a single-valued slot, a row for a term
  that doesn't exist, a malformed CURIE, or a prefix missing from `config/prefixes.yaml`.

## Verified against mondo-ingest

Built from ORDO 4.7 and compared with the `ordo.owl` and `ordo.sssom.tsv` in mondo-ingest
release v2026-01-24 (also built from 4.7), with both sides queried by ROBOT:

| Facet | Result |
|---|---|
| Classes (15,370), parents (36,729), subsets (18,484), deprecated (1,468) | Identical |
| Synonyms on classes (24,759) | Identical |
| Labels and definitions on classes | Identical |
| Mappings (45,620) | Identical, except as fixed below; SSSOM rows identical, plus 6 |
| Gene relations | Identical, except the loss-of-function fix: 1,212 relabelled, plus 11 pairs where ORDO states both gain and loss of function, which mondo-ingest merges |

mondo-ingest's component also carries things that are deliberately dropped:
- labels and synonyms on 4,579 gene classes it doesn't contain;
- labels, generated synonyms and definitions on *properties* (e.g. `part_of`).

The 4.7 build needs one comparison-only workaround, for six 4.7 classes with case-duplicate
labels, which the pipeline otherwise rejects.

## Fixes and notes relative to mondo-ingest

These are the seven bugs in [MONDO-INGEST-BUGS.md](MONDO-INGEST-BUGS.md), all fixed here:

1. No dangling gene annotations.
2. Mapping objects are IRIs, not string literals.
3. Mapping justifications (`ManualMappingCuration`), ICD code-relation comments and the
   `replaced_by` / `consider` pointers are kept.
4. Loss-of-function relations use `RO:0004002`.
5. Subset IRIs come from lowercased labels, so 4.9 keeps Mondo's subset names.
6. The six NBSP ICD-11 mappings are kept.
7. `ordo.sssom.tsv` passes `sssom validate`.

Kept for compatibility, though probably wrong:
- ICD-11 MMS codes stay under `icd11.foundation`.
- The `.db` turns ICD-10 objects into `ICD10WHO2010:` and leaves MedDRA ones as full IRIs.
  That's because mondo-ingest's `prefixes.csv` and its SSSOM metadata disagree. Previously
  the `.db` held raw literals, so mondo-ingest code reading mappings from it needs checking
  before switching over.

ORDO content mondo-ingest never took in, and which isn't taken in here either:
- free-text obsoletion reasons;
- definition citations (always just "Orphanet");
- ND-qualified and unqualified xrefs;
- gene classes and their xrefs.

## Findings

### About ORDO

- **The old orphadata.org URL is frozen at 4.7.** The current release is 4.9 (June 2026),
  at `https://www.orphadata.com/data/ontologies/ordo/last_version/ordo_orphanet.owl`, which
  mondo-ingest's main branch already uses. Its latest release, v2026-01-24, was built from
  4.7.
- **4.9 changed shape compared with 4.7.** It adds `owl:deprecated` and a new `Orphanet_C059`
  website-link property, and capitalises its category labels.
  `fix_complex_reification_ordo.ru` in mondo-ingest targets a layout 4.7 already didn't use.
  Source format drift breaks SPARQL silently.
- **ORDO's mapping qualifier packs two dimensions into one string:** precision
  (E/NTBT/BTNT/ND) and, for ICD, a code-relation type (Specific code / Attributed code /
  Index term / Inclusion term). The precision becomes `predicate_id` and the code relation
  the mapping's `comment`.
- **Data quality:**
  - Ten ICD-11 xrefs contain non-breaking spaces.
  - 12 classes have both `"X"` and `"X"@en` labels.
  - ORDO's gene xrefs to ClinVar and Genatlas are gene symbols, and its Reactome xrefs are
    UniProt accessions.
  - 4.7 has 145 empty gene xrefs and six case-duplicate labels.
- **#900-style check.** Of Mondo's 9,785 exactMatch→Orphanet mappings (local clone,
  2026-08-04), against ORDO 4.9:
  - 216 point at deprecated terms with `consider` targets;
  - 31 at deprecated terms with a `replaced_by` target;
  - 9 at deprecated terms with no pointer;
  - 18 at IDs that aren't ORDO classes.

### About the approach

- **Timings (ORDO 4.9):**
  - `make all` takes about 1.5 minutes with ORDO already downloaded;
  - `make bundle` adds about 1.5 minutes;
  - `make validate` takes about 1.5 minutes, almost all YAML parsing.
- **YAML is a cost and a correctness hazard, and stays because curators read it.**
  - The faithful 25 MB YAML of the original approach took 10.8 s to parse with PyYAML's C
    loader, 58.8 s with ruamel (YAML 1.2), and 0.23 s as JSON.
  - The gene alias `2E4` is a string under YAML 1.1 (PyYAML) but the float `20000.0` under
    YAML 1.2. The assembler quotes such strings.
- **The schema validators miss CURIE syntax.** `uriorcurie` becomes an unconstrained string
  in JSON Schema. The assembler checks CURIE syntax itself.
- **Mappings are SSSOM, inline on their term.**
  - `Term.mappings` is a `TermMapping`: every slot of the `sssom-schema` package's `mapping`
    class except `subject_id` and `subject_label`.
  - It doesn't subclass `mapping`, because that class requires `subject_id` through a rule
    a subclass would inherit.
  - The SSSOM schema has no PURL for its YAML, so the import is pinned to the v1.0.0 GitHub
    URL, and redirected to the installed package with a LinkML importmap.
    `linkml-validate` has no importmap option and fetches the URL.
- **Timestamps.** ORDO publishes `dcterms:modified` without a timezone, so `source_date` is
  kept as a verbatim string.

## Open questions

- **Typology in `parents`.** `parents` mixes ORDO's typology classes (Disease, Disorder,
  …) with its classification groups. That's mondo-ingest's reading, reproduced as-is.
- **Steps that need all sources at once.** Nico's concern on #906 still stands: some
  mondo-ingest steps need every source together, and those can't move into a single
  source repo.
- **Switching mondo-ingest over.** It would download this bundle the way it does
  ICD10WHO's (`ORDO_RELEASE_BASE` plus `wget` targets).
- **An audit report.** A report of what each Mondo-interpretation step did (e.g. counts of
  generated synonyms, promoted `part_of` edges) could replace a second, faithful YAML.
- **The non-OWL path.** It isn't exercised here. OMIM would be the next test.
- **`mapping_set_id` and PURLs** are placeholders until the PURL scheme is decided.
