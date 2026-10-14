# Rewrite mapping object IRIs from the release's prefix bases (config/prefixes.yaml)
# to the ones mondo-ingest uses for ORDO (src/ontology/metadata/ordo.metadata.sssom.yml),
# so the component matches mondo-ingest's ordo.sssom.tsv. Not in mondo-ingest's
# pipeline: there the mapping objects were string literals ("ICD-10:Q98.8").
#
# NOTE: mondo-ingest files ORDO's ICD-11 codes under icd11.foundation, but they are
# MMS codes, not Foundation IDs. Kept for compatibility.
prefix skos: <http://www.w3.org/2004/02/skos/core#>
prefix owl: <http://www.w3.org/2002/07/owl#>

DELETE {
  ?s ?p ?o .
  ?ax owl:annotatedTarget ?o .
}
INSERT {
  ?s ?p ?new .
  ?ax owl:annotatedTarget ?new .
}
WHERE {
  VALUES ?p { skos:exactMatch skos:broadMatch skos:narrowMatch }
  VALUES (?from ?to) {
    ("https://icd.who.int/browse10/2019/en#/"       "http://apps.who.int/classifications/icd10/browse/2010/en#/")
    ("https://icd.who.int/browse/2024-01/mms/en#"   "http://id.who.int/icd/entity/")
    ("http://id.nlm.nih.gov/mesh/"                  "http://identifiers.org/mesh/")
    ("http://identifiers.org/meddra/"               "https://identifiers.org/meddra/")
  }
  ?s ?p ?o .
  FILTER(STRSTARTS(STR(?o), ?from))
  BIND(IRI(CONCAT(?to, STRAFTER(STR(?o), ?from))) AS ?new)
  OPTIONAL {
    ?ax a owl:Axiom ;
        owl:annotatedSource ?s ;
        owl:annotatedProperty ?p ;
        owl:annotatedTarget ?o .
  }
}
