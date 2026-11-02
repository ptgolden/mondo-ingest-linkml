# ICD10WHO

ICD-10 (WHO, 2019 edition), as Mondo takes it in. Built with mondo-source's shared
rules (`make`, `make bundle`, `make validate`, `make refresh`; see the
[top-level README](../../README.md)).

## The source

WHO publishes ICD-10 only through its JSON API. mondo-ingest-icd10who walks the API and
publishes the result as Turtle, `icd10who.raw.ttl`. That is the input here, pinned to
release v2026-10-12. Its `icd10who.owl` is a rendering, the equivalent of this
directory's output, and is not used.

The Turtle is thin: per class, `rdfs:label`, `rdfs:subClassOf` (chapters under
`owl:Thing`), `skos:notation` (the code) and `rdfs:seeAlso` (the API URI, as a string).
12,597 classes: 22 chapters, their blocks (`A00-A09`) and the codes. Every class has
exactly one label and one parent.

## What's ICD10WHO's own

| File | What it does |
|---|---|
| `sparql/01-mark-in-scope.ru` | the scope: every class in the ICD10WHO namespace, as in mondo-ingest's `icd10who-relevant-signature.sparql` |
| `sparql/metadata.rq` | the version, read from the ontology's `rdfs:comment`, which is all the Turtle says about its release |
| `icd10who.metadata.sssom.yml` | SSSOM metadata for the empty mapping set |

Everything else comes from mondo-source's shared queries. Of mondo-ingest's ICD10WHO
recipe, two steps change the content, and both are in the shared `synonyms.rq`:
`exact_syn_from_label.ru` and `fix-labels-with-brackets.ru`. The rest do nothing for
ICD10WHO: its property renames (the Turtle already uses `rdfs:label`), `fix_omimps.ru`
(no xrefs), and an empty `icd10who_exclusions.tsv`.

## Verified

Against **mondo-ingest-icd10who's own `icd10who.yaml`** (same release): the same 12,597
terms, labels and parents, and every one of its synonyms. The only difference is 293
more synonyms here, the bracket-stripped ones (below).

Against **mondo-ingest's last ICD10WHO component** (release v2026-01-24, its
2026-01-09 build): the classes, labels, parents and synonyms are identical, except for
109 terms under `U` (codes for special purposes), where WHO's data changed in between,
e.g. U08 relabelled from "Emergency use of U08" to "Personal history of COVID-19", and
U10–U12 added.

## Fixes and notes relative to mondo-ingest-icd10who

- **Its bracket-stripped synonyms are missing.** mondo-ingest ran
  `fix-labels-with-brackets.ru` on ICD10WHO: 293 labels end in a bracketed part, and
  each got an exact synonym typed `mondo:GENERATED` with it removed and lowercased
  ("Leprosy [Hansen disease]" gives "leprosy"). mondo-ingest-icd10who dropped the step;
  it's back here.
- **Its `mapping_set_id` is a random UUID per build**, as was mondo-ingest's. Here it's
  `http://purl.obolibrary.org/obo/mondo/sources/mappings/icd10who.sssom.tsv`, following
  mondo-ingest's ORDO metadata.
- **`rdfs:seeAlso` and `skos:notation` are not taken in.** mondo-ingest's component kept
  `seeAlso` (it's in mondo-ingest's shared property list) and dropped `notation`. Both are
  the code again: `notation` equals the local ID on every class, and `seeAlso` is the API
  URI built from it. Nothing in mondo-ingest reads either.
- **The Turtle states no version.** `metadata.rq` parses it out of the comment
  "Created from ICD-10 WHO API release: http://id.who.int/icd/release/10/2019". It would
  be better for mondo-ingest-icd10who to state `owl:versionIRI` and `owl:versionInfo`, and
  to say which API walk (date) the file is from: the U-chapter changes above happened
  within "2019".

## Schema

ICD10WHO needs nothing the schema doesn't already have for ORDO. Everything in it is
either taken in through existing slots (label, parents, synonyms) or is the code
restated (`notation`, `seeAlso`).

What the schema might need for ICD10WHO lies upstream. mondo-ingest-icd10who's walk keeps
only each API entity's title and parent. If the API's other fields (inclusion terms,
exclusions, coding notes, class kind) matter to Mondo, they would have to be added to the
Turtle first. Inclusion terms would fit `synonyms` as they are, and exclusions would be a
new kind of relation.
