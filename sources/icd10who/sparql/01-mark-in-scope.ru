# Mark the classes Mondo takes in from ICD-10: all of them, chapters and blocks
# included, as in mondo-ingest's icd10who-relevant-signature.sparql (every IRI in the
# ICD10WHO namespace). mondo-ingest's icd10who_exclusions.tsv is empty.
PREFIX owl: <http://www.w3.org/2002/07/owl#>

INSERT { ?term <https://w3id.org/monarch-initiative/mondo-source/in_scope> true }
WHERE {
  ?term a owl:Class .
  FILTER(STRSTARTS(STR(?term), "https://icd.who.int/browse10/2019/en#/"))
}
