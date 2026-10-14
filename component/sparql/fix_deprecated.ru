# Copied verbatim from monarch-initiative/mondo-ingest@0dc67c4 src/sparql/fix_deprecated.ru
PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>
PREFIX owl: <http://www.w3.org/2002/07/owl#>
PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>

INSERT {
	?sub owl:deprecated "true"^^xsd:boolean .
}

WHERE {
  ?sub rdfs:subClassOf* <http://www.orpha.net/ORDO/Orphanet_C041> .
}