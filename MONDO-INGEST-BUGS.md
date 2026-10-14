# Bugs found in mondo-ingest's ORDO output

Found while reproducing mondo-ingest's ORDO component in this repo. "mondo-ingest's
output" means `components/ordo.owl` and `mappings/ordo.sssom.tsv` from mondo-ingest
release v2026-01-24 (built from ORDO 4.7); the code is mondo-ingest@0dc67c4.

Bugs 1–3 were found first and were the reason to build a fixed component here; bugs 4–7
turned up while doing it. The component in `component/` fixes all seven (see
[component/README.md](component/README.md)).

## 1. Removed gene classes keep their labels and synonyms

`components/ordo.owl` carries 4,579 `rdfs:label` and 18,586 `oboInOwl:hasExactSynonym`
assertions on ORDO gene classes that are not in the component.

**Cause:** `robot remove -T ordo_relevant_signature.txt --select complement --select
"classes individuals" --trim false` (`mondo-ingest.Makefile`, `$(COMPONENTSDIR)/ordo.owl`).
With `--trim false`, ROBOT removes an axiom only if *all* the objects in it are selected.
An annotation assertion also contains its annotation property, which isn't selected, so
the class goes but its annotations stay.

## 2. Mapping objects are string literals with ORDO's raw prefixes

The component's SKOS mappings point at literals such as `skos:exactMatch "MeSH:D007713"`,
not IRIs, with ORDO's own prefixes (`ICD-10:`, `ICD-11:`, `MeSH:`). mondo-ingest's
`ordo.sssom.tsv` uses different prefixes (`ICD10:`, `icd11.foundation:`, `MESH:`), so the
component and its SSSOM file disagree.

**Cause:** `ordo-replace-annotation-based-mappings.ru` copies the `hasDbXref` literal into
the SKOS triple, and `fix_xref_prefixes.ru` has no effect on the output.

## 3. Replacement pointers and mapping justifications are dropped

- ORDO's "Moved to" (`Orphanet:C056`, a replacement) and "Referred to"
  (`Orphanet:C057`, a suggestion) are removed, because neither is in
  `config/properties.txt`. In 4.7 that loses 323 `replaced_by` and 907 `consider`
  pointers, which is exactly what is needed to repair mappings to obsolete ORDO terms
  (#900).
- Every row of `ordo.sssom.tsv` says `semapv:UnspecifiedMatching`, although Orphanet
  curates these mappings by hand.
- ORDO's ICD code-relation type (Specific code / Attributed code / Index term / Inclusion
  term) is also discarded.

## 4. Loss-of-function gene relations are labelled gain-of-function

`ordo-construct-d2g.ru` maps:

```
( Orphanet:410295 RO:0004001 )   # 410295 = "disease-causing germline mutation(s) (loss of function) in"
( Orphanet:410296 RO:0004001 )   # 410296 = "... (gain of function) in"
```

`RO:0004001` is "has material basis in **gain** of function germline mutation in". The
loss-of-function relation is `RO:0004002`, which isn't in `config/properties.txt` either,
so fixing only the query would still lose it.

**Scale:** in ORDO 4.9, 1,222 of the 1,436 functional gene relations are loss-of-function,
and all of them would be stated as gain-of-function.

## 5. ORDO 4.9 would rename Mondo's `ordo_*` subsets

`ordo-construct-subsets.ru` builds subset IRIs from ORDO category labels:

```sparql
BIND( URI(CONCAT("http://purl.obolibrary.org/obo/mondo#ordo_", REPLACE(?categoryLabel, " ", "_"))) AS ?subset)
```

ORDO 4.7's category labels are lowercase ("disorder"). 4.9's are capitalised ("Disorder"),
so once mondo-ingest ingests 4.9 it will emit `mondo#ordo_Disorder` and so on, instead of
the existing `mondo#ordo_disorder`, `mondo#ordo_group_of_disorders` and
`mondo#ordo_subtype_of_a_disorder`.

**Fix:** `LCASE(STR(?categoryLabel))`.

## 6. Six ICD-11 mappings are silently dropped from `ordo.sssom.tsv`

Six ORDO ICD-11 xrefs contain non-breaking spaces (e.g. `ICD-11: 4A6Y`). In the
component they stay broken (the NBSP stripping in `fix_xref_prefixes.ru` has no effect;
see bug 2). `sssom parse` then treats them as malformed CURIEs and drops them without a
warning, so `ordo.sssom.tsv` has 45,614 rows where the component has 45,620 mappings.

## 7. `ordo.sssom.tsv` fails `sssom validate`

```
jsonschema.exceptions.ValidationError: Slot 'creator_id' has an incorrect value: ['https://orcid.org/0000-0002-2906-7319']
```

`metadata/ordo.metadata.sssom.yml` gives `creator_id` as a full ORCID IRI; SSSOM expects a
CURIE (`orcid:0000-0002-2906-7319`, with `orcid` in the `curie_map`). The other
per-source metadata files probably have the same problem; not checked.

## Related inconsistencies (not bugs in the output as such)

- **ICD-11 MMS codes under the Foundation prefix.** ORDO's ICD-11 codes (e.g. `LD50.3Y`)
  are MMS codes, but `ordo.sssom.tsv` files them under `icd11.foundation`
  (`http://id.who.int/icd/entity/`).
- **Two prefix files disagree.** `config/prefixes.csv` (used by semsql for the `.db`
  files) and `metadata/ordo.metadata.sssom.yml` (used for the SSSOM file) differ:
  - the ICD-10 base `http://apps.who.int/classifications/icd10/browse/2010/en#/` is
    `ICD10WHO2010` in one and `ICD10` in the other;
  - MedDRA is `MEDDRA` at `http://identifiers.org/meddra/` in one, and `MedDRA` at
    `https://identifiers.org/meddra/` in the other.
- **Dead code for current ORDO:**
  - `fix_partof.ru` rewrites `Orphanet_C021`, which doesn't occur in 4.7 or 4.9;
  - `fix_complex_reification_ordo.ru` targets a nested-annotation layout neither uses.
- **mondo-ingest main downloads ICD10WHO from a personal fork.** `ICD10WHO_RELEASE_BASE`
  points at `github.com/Reasat/icd10who`, not the monarch-initiative repo. PR #906 said this
  should move before merge.
