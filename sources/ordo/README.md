# ORDO

Orphanet's Rare Disease Ontology, as Mondo takes it in. Built with mondo-source's
shared rules (`make`, `make bundle`, `make validate`, `make refresh`; see the
[top-level README](../../README.md)).

## What's ORDO's own

| File | What it does |
|---|---|
| `sparql/00-part-of-as-parents.ru` | mondo-ingest's own query, verbatim: Mondo reads ORDO's `part_of` as hierarchy |
| `sparql/01-mark-in-scope.ru` | the scope: descendants of Disorder, Group of disorders, Subtype of a disorder and Inactive clinical entity, minus gene classes, plus the named ancestors of those roots |
| `sparql/02-as-obo.ru` | ORDO's conventions rewritten as OBO ones, for the shared queries: `alternative_term` as exact synonym, `efo:definition`, Inactive clinical entity as deprecated, Moved to as `replaced_by`, Referred to as `consider` |
| `sparql/mappings.rq` | ORDO's qualified xrefs as SSSOM mappings, the precision code as predicate |
| `sparql/relationships.rq` | gene relations, turned around onto the disease |
| `sparql/subsets.rq` | `mondo#ordo_<category>` subsets |
| `ordo.metadata.sssom.yml` | mondo-ingest's own SSSOM metadata for ORDO |

Terms, synonyms, parents, `consider` and the release metadata come from mondo-source's
shared queries. Each query documents which mondo-ingest step it reproduces.

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

## Findings about ORDO


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

## Open questions

- **Typology in `parents`.** `parents` mixes ORDO's typology classes (Disease, Disorder,
  …) with its classification groups. That's mondo-ingest's reading, reproduced as-is.
- **Switching mondo-ingest over.** It would download this bundle the way it does
  ICD10WHO's (`ORDO_RELEASE_BASE` plus `wget` targets).
