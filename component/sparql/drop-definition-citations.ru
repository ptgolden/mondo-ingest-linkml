# Drop the release's definition citations (axiom annotations on IAO:0000115).
# mondo-ingest's ORDO component never carried them, and the properties filter
# would otherwise remove each cited definition entirely: ROBOT drops any axiom
# that uses a non-whitelisted property, including as an axiom annotation.
prefix owl: <http://www.w3.org/2002/07/owl#>
prefix obo: <http://purl.obolibrary.org/obo/>
prefix dcterms: <http://purl.org/dc/terms/>

DELETE { ?ax ?p ?o }
WHERE {
  ?ax a owl:Axiom ;
      owl:annotatedProperty obo:IAO_0000115 ;
      dcterms:source ?citation ;
      ?p ?o .
}
