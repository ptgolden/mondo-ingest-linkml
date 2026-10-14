# component/: Mondo's editorial policy for ORDO

The release (`ordo.yaml`, `ordo.source.sssom.tsv`, `ordo.linkml.owl`) records what ORDO
says. This directory turns that into what Mondo needs: the bundle mondo-ingest downloads
for ORDO, so mondo-ingest no longer builds anything for ORDO itself (the pattern
mondo-ingest#906 set up for ICD10WHO). `make component` builds it.

| File | mondo-ingest target it replaces |
|---|---|
| `ordo.owl` | `components/ordo.owl` |
| `ordo.db` | `components/ordo.db` (`%.db` rule, semsql) |
| `mirror-ordo.owl` | `tmp/mirror-ordo.owl` |
| `mirror_signature-ordo.tsv`, `component_signature-ordo.tsv` | `reports/*_signature-ordo.tsv` |
| `ordo.sssom.tsv` | `mappings/ordo.sssom.tsv` |
| `ordo-metrics.json` | `metadata/ordo-metrics.json` |

`ordo.owl` is built from `ordo.linkml.owl` with ROBOT, following mondo-ingest's
`$(COMPONENTSDIR)/ordo.owl` recipe step for step. Everything copied is from
monarch-initiative/mondo-ingest@0dc67c4.

## Recipe, step by step

| mondo-ingest step | Here |
|---|---|
| `rename` with `config/property-map.sssom.tsv` | Same file, verbatim (`property-map.sssom.tsv`). It already maps `skos:altLabel` (the release's unscoped synonyms) to `hasExactSynonym`. |
| `fix_partof.ru` | Dropped: `Orphanet_C021` does not occur in ORDO 4.7 or 4.9. |
| `fix_deprecated.ru` | Verbatim. |
| `fix_complex_reification_ordo.ru` | Dropped: targets a nested-annotation layout neither 4.7 nor 4.9 uses. |
| `fix_xref_prefixes.ru` | Dropped: the release already has normalised, NBSP-free CURIEs. `mondo-ingest-mapping-iris.ru` does the remaining prefix work. |
| `fix-labels-with-brackets.ru`, `exact_syn_from_label.ru` | Verbatim. |
| `ordo-construct-subclass-from-part-of.ru` | Verbatim. |
| `ordo-construct-subsets.ru` | Adapted: lowercases category labels (fix 4). |
| `ordo-construct-d2g.ru` | Adapted: reads HGNC ids from IRI xrefs; maps loss of function correctly (fix 5). |
| `ordo-replace-annotation-based-mappings.ru` | Dropped: the release's mappings already carry SKOS predicates. |
| `remove --term oboInOwl:hasDbXref` | Same. Drops ND-qualified and gene xrefs, as before. |
| `remove -T ordo_relevant_signature.txt …` | Same, using `ordo-relevant-signature.sparql` verbatim, preceded by a step that removes the out-of-signature classes' annotations (fix 1). |
| `remove -T config/properties.txt …` | Same list (`properties.txt`) plus `IAO:0100001`, `oboInOwl:consider`, `sssom:mapping_justification` and `RO:0004002`. |
| `annotate` | Same ontology and version IRIs. |
| | New: `mondo-ingest-mapping-iris.ru` rewrites mapping IRIs to mondo-ingest's prefix bases; `drop-obsoletion-reasons.ru` and `drop-definition-citations.ru` remove release content mondo-ingest never carried. |

## Verified against mondo-ingest

Built from ORDO 4.7 and compared with the `ordo.owl` and `ordo.sssom.tsv` in mondo-ingest
release v2026-01-24, which were built from 4.7. Both sides were queried with ROBOT.

These match: classes (15,370), parents (36,729), gene relations (6,886), subset
memberships (18,484), deprecated terms (1,468), and labels, synonyms and definitions on
classes. Mapping rows match too, apart from the fixes below.

The differences are the fixes below, plus mondo-ingest's labels, generated synonyms and
definitions on *properties* (e.g. `part_of`), which aren't carried over.

(The 4.7 comparison build needs two scratch workarounds for 4.7 data errors that the
release pipeline rejects: six classes with case-duplicate labels, and 145 empty gene
xrefs.)

## Fixes relative to mondo-ingest's output

1. **No dangling gene annotations.** `robot remove --trim false` removes an axiom only if
   *all* its objects are selected, so a removed class's label and synonym axioms (which
   also contain `rdfs:label` etc.) survive. mondo-ingest's component carries 4,579 labels
   and 18,586 synonyms for ORDO gene classes it no longer contains. Here, a preceding
   `remove --axioms annotation --trim true` drops them; the signature's ancestors
   (Orphanet:C001) are exempt, because they stay in the component.
2. **Mapping objects are IRIs.** mondo-ingest's are string literals with ORDO's raw
   prefixes (`skos:exactMatch "MeSH:D007713"`), which disagree with its own SSSOM file.
3. **Information kept:**
   - ORDO's replacement pointers: `IAO:0100001` (Moved to), 323 in 4.7, and
     `oboInOwl:consider` (Referred to), 907;
   - each mapping's justification (`semapv:ManualMappingCuration`, where mondo-ingest
     says `UnspecifiedMatching`);
   - ORDO's ICD code-relation type, as an `rdfs:comment` on the mapping.
4. **Subset names survive ORDO 4.9.** `ordo-construct-subsets.ru` builds subset IRIs from
   category labels. 4.9 capitalised those labels, which would have renamed Mondo's
   subsets (`mondo#ordo_disorder` → `mondo#ordo_Disorder`).
5. **Loss of function is loss of function.** mondo-ingest maps Orphanet:410295
   ("disease-causing germline mutation(s) (loss of function) in") to `RO:0004001`, the
   *gain*-of-function relation. That affects 1,222 relations in 4.9; they now use
   `RO:0004002`.
6. **No lost ICD-11 mappings.** Six ORDO ICD-11 xrefs contain non-breaking spaces.
   mondo-ingest keeps them broken in the OWL, and its `sssom parse` silently drops them
   from `ordo.sssom.tsv`. The release strips the NBSPs, so all six are kept.
7. **`ordo.sssom.tsv` passes `sssom validate`.** mondo-ingest's own file fails because
   `creator_id` is a full ORCID IRI; it is contracted to `orcid:` here.

## Known compatibility notes (not fixed)

- **ICD-11 prefix.** ORDO's ICD-11 codes are MMS codes, but mondo-ingest files them under
  `icd11.foundation` (Foundation entity IRIs). Kept for compatibility.
- **The `.db` contracts IRIs with mondo-ingest's `config/prefixes.csv`,** which disagrees
  with its SSSOM metadata:
  - ICD-10 objects come out as `ICD10WHO2010:`, not `ICD10:`;
  - `https://identifiers.org/meddra/` has no prefix there, so MedDRA objects stay full
    IRIs.

  Previously the `.db` held the raw literals (`ICD-10:Q98.8`).
- **Ontology header.** The header is built from the release metadata, so ORDO's
  `dc:creator` names are not carried over.
- **Deprecated category classes.** ORDO's own category classes under "Inactive clinical
  entity" (C041 and the C042–C053 categories under it) are marked deprecated, as
  `fix_deprecated.ru` always did.
